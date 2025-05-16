from itertools import groupby
from operator import attrgetter

from tabulate import tabulate

from .queries import SkipQueryReason


def format_creates(model, creates):
    yield ""
    yield model
    queries = list(creates)
    first = queries[0]
    headers = ["variable name"]
    headers.extend([field.name for field in first.all_fields()])
    rows = []
    for query in queries:
        row = [query.variable_name]
        row.extend([field.value_repr for field in query.all_fields()])
        rows.append(row)
    yield tabulate(rows, headers=headers, disable_numparse=True)


def format_reason(reason):
    if reason is SkipQueryReason.NO_COLUMNS:
        yield "These queries did not select any columns:"
    elif reason is SkipQueryReason.NO_PRIMARY_KEY:
        yield "These queries did not select the primary key for a table:"
    elif reason is SkipQueryReason.NULL_PRIMARY_KEY:
        yield "These queries have a primary key set to NULL:"
    elif reason is SkipQueryReason.SEEN_MUTATION:
        yield "These queries select a row that has been mutated by an earlier query:"
    elif reason is SkipQueryReason.UNSUPPORTED_WHERE:
        yield "These queries use a WHERE clause Kolo doesn't yet handle:"


def format_skips(skips):
    for skip in skips:
        if skip.table:
            yield f"table: {skip.table}"
        yield f"query: {skip.query['query']}"
        yield f"query data: {skip.query['query_data']}"
        yield ""


def format_intermediate(context):
    for index, section in enumerate(context["sections"]):
        yield f"Section {index}"

        for model, creates in groupby(section["sql_fixtures"], key=attrgetter("model")):
            yield from format_creates(model, creates)

        yield "\nSkipped Queries:"

        skipped = sorted(section["skipped_inserts"], key=attrgetter("reason.value"))
        for reason, skips in groupby(skipped, key=attrgetter("reason")):
            yield from format_reason(reason)
            yield from format_skips(skips)
