# Kolo Test Generation

Kolo supports generating integration tests from traces. The main entry point to this is the `kolo generate-test` command in the Kolo cli (`kolo.__main__.generate_test`).

This works in a few stages:

* load a trace from the Kolo database
* load the enabled trace processors with `load_processors`
* build a `context` dictionary which stores useful data for use during test generation
* run the trace processors in order, mutating the `context` with more refined data
* build a test plan from the `context`
* render the test plan
* format the generated test with black (if black is installed)

## Trace Processors

Trace processors are used to build up the `context` dictionary that is used to build the test plan.

Kolo defines several default processors:

### `kolo.generate_tests.processors.process_django_version`

This is a simple processor that adds the version number of Django to the context. If Django is not installed, `""` is used instead.

```python
{"django_version": django_version}
```

### `kolo.generate_tests.processors.process_django_schema`

This generates a representation of the database schema managed by Django for use in later processors. The core implementation is in `kolo.django_schema.get_schema`. If the trace was generated on the active git commit, this is called. Otherwise we try to load a saved schema from Kolo's database. If the commit sha doesn't match and we don't have one saved, we use the current commit and emit a warning on stdout.

```python
{"schema_data": schema_data}
```

### `kolo.generate_tests.processors.process_django_request`

This searches through the trace frames to find Django request/response frames. These are collected into `sections`, one request/response pair for each section.

For each section we include the starting `django_request` frame and the ending `django_response` frame. We also search through the intermediate frames for any `django_template_start` frames and include the `template` name for each.

The `django_request` frame is further processed to extract `timestamp` and to generate a call to the Django test client in unittest syntax and in pytest syntax.

All this data is wrapped up into the context:

```python
{
    "sections": [
        {
            "request": django_request,
            "request_timestamp": timestamp,
            "response": django_response,
            "template_names": ["template_1", "template_2", ...],
            "test_client_call": unittest_client_call,
            "test_client_call_pytest": pytest_client_call,
            "frames": intermediate_frames,
        },
        ...
    ]
}
```

If there are no Django request frames, we just create one section with all the frames:

```python
{"sections": {"frames": frames}}
```

### `kolo.generate_tests.processors.process_outbound_requests`

For each section added by `process_django_request` we search for any `outbound_http_request` and `outbound_http_response` frames. These are added to an `outbound_request_frames` list:

```python
{
    "sections": [
        {
            "outbound_request_frames": [
                {
                    "request": outbound_http_request,
                    "response": outbound_http_response,
                },
                ...
            ],
        },
    ]
}
```

### `kolo.generate_tests.processors.process_sql_queries`

For each section, this processor extracts all `end_sql_query` frames and processes them into a collection of Django model create calls and a collection of asserts. In the test plan, the create calls for each section are put before that section's call to the Django test client. The asserts are put after the test client call.

A subtlety here is that we filter out duplicate create calls between sections, so data is only created the first time it is needed.

We also maintain a collection of imports required for the create calls and asserts.

```python
{
    "imports": ["from myapp.models import MyModel", ...],
    "sections": [
        {
            "sql_fixtures": django_model_creates,
            "asserts": asserts,
        },
    ],
}
```

### `kolo.generate_tests.processors.process_factories`

The model create calls we generate in `process_sql_queries` are not very pretty, so we support converting these into factory-boy calls. We load a list of possible factories from the Kolo config file - `test_generation.factories`. For each model create in a `sql_fixtures` list we try to find a matching factory. If we can, we generate a replacement factory create call.

After this step the `context` looks the same as in `process_sql_queries` except `sql_fixtures` and `imports` have been updated with the appropriate factory data.

### `kolo.generate_tests.processors.process_time_travel`

Kolo generated tests support two time management libraries: `time_machine` and `freezegun`. We use `time_machine` by default, but if `freezegun` is installed and `time_machine` is not, we use it instead.

```python
{
    "time_travel_import": "import time_machine",
    "time_travel_call": "time_machine.travel",
    "time_travel_tick": "",
}
```

`time_travel_tick` is used when `freezegun` is chosen to enable the frozen clock to tick forward during tests. `time_machine` defaults to this behaviour.

## Query processing

The conversion of recorded SQL queries in a trace into a sequence of Django model create calls and a collection of asserts is by far the most complicated part of test generation.

The core of this is implemented in the `kolo.generate_tests.queries.SQLParser` class. The entry point is the `parse_sql_queries` method, which takes a list of `sql_queries` (`end_sql_queries` frames) and the `schema_data` from `process_django_schema`.

For each query frame, we parse the query using `sqlglot`.

### `SELECT` queries

`SELECT` queries are candidates to become Django create calls in our test.

The simplest case we have is a query selecting one row of data from one database table. In this case we create a `DjangoCreate` object and append it to a list of `inserts`. We also determine the correct import path and add that to a set of `imports`.

Moving beyond the simplest case, we may have multiple tables involved. We create one `DjangoCreate` instance for each table. The query may also select multiple rows. Each row generates one `DjangoCreate` per table.

The other major case here is that we may be seeing a select for a row of a table that we've seen mutated by an `INSERT`, `UPDATE` or `DELETE` query. In this case, we know the row is created by the code we want to test and therefore skip over it instead of generating a `DjangoCreate`.

The `SQLParser.parse_columns` method is used in this process to group columns by table and to pair columns with their corresponding row value. These pairs are turned into `DjangoField` instances which are then passed to `DjangoCreate`.

After all `DjangoCreate` instances have been collected into `inserts` they are deduplicated and sorted. We then post-process each instance to remove unwanted fields:

* The primary key field since we store that in the `primary_key` attribute instead.
* Nullable fields with value `None`.
* Auto-now fields.
* Fields where their value matches the default value.

We also add fields for generic foreign keys (built from their component fields) and update foreign keys to refer to other generated model instances instead of raw primary key values.

### `INSERT` queries

`INSERT` queries are candiates to become asserts in our test. For each query we build up a collection of asserts by calling `SQLParser.build_assert_inserts`.

For each query, we obtain the columns, values and returning value via sqlglot. We zip each row of values with their columns and convert them into a list of `DjangoField` instances with `SQLParser.build_insert_assert_fields`. If there was a `returning` value, we try to build a primary key and mark the table as "seen" so we stop generating `DjangoCreate` calls for this table. We then build an `AssertInsert` instance from the fields and primary key.

If there was no `returning` value or we couldn't build a primary key, we skip this query.

### `UPDATE` queries

`UPDATE` queries are also candidates to become asserts in our test. For each query we build a list of `DjangoField` instances by calling `SQLParser.build_update_assert_fields`.

We then build a list of `lookups` from the `WHERE` clause if one exists. For simple lookups (`IN` and `==`) we find the variable name for a matching `DjangoCreate` and build an `AssertUpdate` for each of these lookups. If any of the lookups corresponds to a primary key we also mark the table as "seen" to stop generating more `DjangoCreate` calls for this table.

If the lookup is too complicated or if there was no `WHERE` clause in the first case, we skip generating any asserts.

### `DELETE` queries

`DELETE` queries are the final candidates to become assets. For each query, we build a list of lists of `DjangoField` instances from the `WHERE` clause by calling `SQLParser.build_delete_lookup_fields`. Each list of fields is turned into an `AssertDelete` instance.

If there was no `WHERE` clause we skip generating any asserts.

### Merging asserts

After all insert, update and delete assertions have been generated, we try to merge them together so we only keep the latest database state we actually care about.

For example, if the code we're testing inserted a row and later updated one of the columns, we would want to keep most of the creation asserts, but replace the updated column value. If we inserted a row and then deleted it, we only want to assert that the row does not exist. This logic is handled in `merge_asserts` and several helper functions.

### Updating fields

After merging asserts, we do a final post-processing step on the asserts to omit uninteresting fields, add generic foreign keys and update foreign key values to refer to appropriate variable names.

For insert asserts we omit:

* Primary keys
* `DateTimeField`s
* `DurationField`s
* `JSONField`s
* Fields with a value matching the default

For update asserts we omit:

* Primary keys
* `DateTimeField`s
* `JSONField`s
* Fields with a value matching the default

We don't omit any fields from delete asserts.
