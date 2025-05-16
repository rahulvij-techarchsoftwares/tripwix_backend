from __future__ import annotations

import asyncio
import gzip
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from runpy import run_module, run_path
from typing import Any, Dict, List, Optional, Sequence, Union

import click
import httpx
import msgpack

from . import django_schema
from .cli_mcp_shared import (
    get_compact_traces,
    get_execution_tree,
    get_formatted_traces,
    get_node_data,
)
from .config import load_config
from .db import (
    TraceNotFoundError,
    convert_json_to_msgpack,
    create_schema_table,
    db_connection,
    delete_traces_before,
    delete_traces_by_id,
    list_traces_from_db,
    load_trace_from_db,
    pin_trace,
    save_schema,
    save_trace_in_sqlite,
    setup_db,
    unpin_trace,
    vacuum_db,
)
from .generate_tests import generate_from_trace_ids, generate_test_intermediate_format
from .profiler import enable
from .serialize import load_msgpack, monkeypatch_queryset_repr
from .upload import upload_to_dashboard
from .utils import (
    extract_main_frames_from_data,
    get_terminal_formatter,
    highlight_python,
    highlight_sql,
    maybe_format,
)
from .web.server import KoloRequestHandler

DATETIME_FORMATS = click.DateTime(
    (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S.%f",
    )
)


DJANGO_SETTINGS_ERROR = """Django settings not found.
Use `--settings` or set the `DJANGO_SETTINGS_MODULE` environment variable."""

TRACE_NOT_FOUND_ERROR = "Could not find trace_id: `{trace_id}`"


@click.group()
def cli():
    # Ensure the current working directory is on the path.
    # Important when running the `kolo` script installed by setuptools.
    # Not really necessary when using `python -m kolo`, but doesn't hurt.
    # Note, we use 1, not 0: https://stackoverflow.com/q/10095037
    # This probably doesn't matter for our use case, but it doesn't hurt.
    sys.path.insert(1, ".")


def python_noop_profiler(frame, event, arg):  # pragma: no cover
    pass


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("path")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@click.option(
    "--one-trace-per-test",
    default=False,
    is_flag=True,
    help="Generate a trace for each test traced by Kolo.",
)
@click.option("--noop", default=False, is_flag=True, hidden=True)
@click.option(
    "--use-monitoring",
    default=False,
    is_flag=True,
    help="Enable Kolo implementation using sys.monitoring",
)
def run(path, args, one_trace_per_test, noop, use_monitoring):
    """
    Profile Python code using Kolo.

    PATH is the path to the python file or module being profiled.
    """
    if path == "python":
        path, *args = args
        if path == "-m":
            path, *args = args
            module = True
        else:
            module = False
    elif path.endswith(".py"):
        module = False
    else:
        module = True

    existing_profiler = sys.getprofile()
    if existing_profiler:
        raise click.ClickException(
            f"Cannot run Kolo: {existing_profiler} is already active."
        )

    # Monkeypatch sys.argv, so the profiled code doesn't get confused
    # Without this, the profiled code would see extra args it doesn't
    # know how to handle.
    sys.argv = [path, *args]

    if noop:  # pragma: no cover
        config = load_config()
        if config.get("use_rust", True):
            from ._kolo import register_noop_profiler

            register_noop_profiler()
        else:
            sys.setprofile(python_noop_profiler)

        try:
            if module:
                run_module(path, run_name="__main__", alter_sys=True)
            else:
                run_path(path, run_name="__main__")
        finally:
            sys.setprofile(None)
        return

    if use_monitoring:
        config = {"use_monitoring": True}
    else:
        config = {}
    monkeypatch_queryset_repr()
    with enable(config, source="kolo run", _one_trace_per_test=one_trace_per_test):
        if module:
            run_module(path, run_name="__main__", alter_sys=True)
        else:
            run_path(path, run_name="__main__")


@cli.command()
@click.option(
    "--port",
    default=5656,
    help="Custom port for the server to run on. Defaults to 5656.",
)
@click.option(
    "--ip",
    default="127.0.0.1",
    help="Custom ip for the server to run on. Defaults to 127.0.0.1",
)
def server(port, ip):
    """
    Start a server to view traces.
    """
    server = ThreadingHTTPServer((ip, port), KoloRequestHandler)
    click.echo(f"View Kolo traces at http://{ip}:{port}/_kolo/")
    server.serve_forever()


@cli.group()
def trace():
    """
    Subcommands for working with Kolo traces.
    """


@trace.command()
@click.argument("path")
@click.option(
    "--created-at",
    help="Mark this trace as created at this time.",
    type=DATETIME_FORMATS,
)
def load(path, created_at):
    """
    Load a trace from a file into the Kolo database.
    """
    db_path = setup_db()

    try:
        with open(path, "rb") as dump:
            raw_data = dump.read()
    except FileNotFoundError:
        raise click.ClickException(f'File "{path}" not found')

    try:
        data = msgpack.unpackb(raw_data, strict_map_key=False)
    except Exception:
        raise click.ClickException("Trace file is not valid msgpack")

    try:
        trace_id = data["trace_id"]
    except KeyError:
        raise click.ClickException("Trace file is missing the `trace_id`")

    try:
        save_trace_in_sqlite(
            db_path,
            trace_id,
            msgpack=raw_data,
            ignore_errors=False,
            created_at=created_at,
        )
    except sqlite3.IntegrityError:
        raise click.ClickException(f"Trace ID `{trace_id}` already exists")

    click.echo(f"Loaded trace {trace_id}")


@trace.command()
@click.argument("trace_id")
@click.option("--file", help="The name of the file to save the trace to.")
@click.option(
    "--as-python",
    default=False,
    is_flag=True,
    help="Show the trace as readable Python types.",
)
@click.option(
    "--syntax-highlight",
    help="Highlight Python syntax. Ignored unless `--as-python` is set.",
    default="off",
    flag_value="dark",
    is_flag=False,
    type=click.Choice(["off", "light", "dark"], case_sensitive=False),
)
def dump(trace_id, file, as_python, syntax_highlight):
    """
    Dump a trace from the Kolo database to stdout or a specified file.
    """
    db_path = setup_db()

    try:
        msgpack_data, _ = load_trace_from_db(db_path, trace_id)
    except TraceNotFoundError:
        raise click.ClickException(TRACE_NOT_FOUND_ERROR.format(trace_id=trace_id))

    if as_python:
        data = load_msgpack(msgpack_data)
        data = repr(data)
        data = maybe_format(data)
        if syntax_highlight != "off":
            formatter = get_terminal_formatter(syntax_highlight)
            data = highlight_python(data, formatter)
        if file:
            with open(file, "w") as f:
                f.write(data)
        else:
            click.echo(data)
    elif file:
        with open(file, "wb") as f:
            f.write(msgpack_data)

    else:
        click.echo(msgpack_data, nl=False)


@trace.command()
@click.option("--count", help="The number of rows to show.", default=500)
@click.option(
    "--reverse",
    help="Reverse the order of the rows: newest at the bottom.",
    default=False,
    is_flag=True,
)
def list(count, reverse):
    """
    Concisely list available traces, ordered by most recent first.

    This is useful for getting an overview of what traces are available and
    finding specific traces you might want to analyze further.

    After listing the trace, you can use `kolo trace compact <trace_id> to get more
    details about the trace.

    If you're an LLM, use `kolo trace list` often to orient yourself.
    """
    db_path = setup_db()
    found_any = False

    for formatted_trace in get_formatted_traces(db_path, count=count, reverse=reverse):
        found_any = True
        click.echo(formatted_trace)

    if not found_any:
        click.echo("No traces found")


@trace.command()
@click.argument("trace_id")
@click.option(
    "--syntax-highlight",
    help="Highlight SQL query syntax.",
    default="off",
    flag_value="dark",
    is_flag=False,
    type=click.Choice(["off", "light", "dark"], case_sensitive=False),
)
def list_queries(trace_id, syntax_highlight):
    """List all SQL queries in a trace."""
    db_path = setup_db()

    try:
        msgpack_data, _ = load_trace_from_db(db_path, trace_id)
    except TraceNotFoundError:
        raise click.ClickException(TRACE_NOT_FOUND_ERROR.format(trace_id=trace_id))

    formatter = get_terminal_formatter(syntax_highlight)

    data = load_msgpack(msgpack_data)
    frames = extract_main_frames_from_data(data)
    for frame in frames:
        if frame["type"] == "end_sql_query":
            query = highlight_sql(
                frame["query"], dialect=frame["database"], formatter=formatter
            )
            click.echo(query)


@trace.command()
@click.argument("trace_id")
@click.argument("node_index", type=int)
def node(trace_id: str, node_index: int):
    """Get detailed information about a specific node in a trace.
    This is useful when you need to deeply understand what happened at a specific
    point in the execution, like examining function arguments, local variables,
    or the exact line of code being executed.
    """
    db_path = setup_db()

    async def _get_node():
        try:
            trace_data, _ = load_trace_from_db(db_path, trace_id)
            node_data = await get_node_data(trace_id, node_index, trace_data)
            click.echo(json.dumps(node_data, indent=2))
        except TraceNotFoundError:
            raise click.ClickException(TRACE_NOT_FOUND_ERROR.format(trace_id=trace_id))
        except httpx.HTTPError as e:
            if hasattr(e, "response") and e.response.status_code == 404:
                raise click.ClickException(
                    f"Node {node_index} not found in trace {trace_id}"
                )
            raise click.ClickException(f"Error fetching node data: {e}")

    asyncio.run(_get_node())


@trace.command()
@click.argument("trace_ids", required=False, nargs=-1)
@click.option("--old", is_flag=True, default=False, help="Delete old traces.")
@click.option(
    "--before",
    help="Delete traces older than this datetime. Must be used with `--old`.",
    type=DATETIME_FORMATS,
)
@click.option(
    "--vacuum",
    help="Recover disk space from the Kolo database.",
    default=False,
    is_flag=True,
)
def delete(trace_ids, old, before, vacuum):
    """
    Delete one or more traces stored by Kolo.
    """

    if before is not None and old is False:
        raise click.ClickException("--before requires --old")

    if old is False and not trace_ids and vacuum is False:
        raise click.ClickException("Must specify either TRACE_IDS, --old, or --vacuum")

    if trace_ids and old:
        raise click.ClickException("Cannot specify TRACE_IDS and --old together")

    db_path = setup_db()

    if trace_ids:
        delete_traces_by_id(db_path, trace_ids)
    elif old:
        if before is None:
            before = datetime.now() - timedelta(days=30)

        deleted_count = delete_traces_before(db_path, before)
        click.echo(f"Deleted {deleted_count} old traces created before {before}.")

    if vacuum:
        vacuum_db(db_path)


@trace.command()
@click.argument("trace_id")
def pin(trace_id):
    """Pin a trace.
    This includes the trace in the output of using `kolo trace compact --pinned`,
    which can be helpful to give an LLM an overview of the key transactions in your project.
    """
    db_path = setup_db()
    try:
        if pin_trace(db_path, trace_id):
            click.echo(f"Pinned trace {trace_id}")
        else:
            raise click.ClickException(TRACE_NOT_FOUND_ERROR.format(trace_id=trace_id))
    except TraceNotFoundError:
        raise click.ClickException(TRACE_NOT_FOUND_ERROR.format(trace_id=trace_id))


@trace.command()
@click.argument("trace_id")
def unpin(trace_id):
    """Unpin a previously pinned trace."""
    db_path = setup_db()
    try:
        if unpin_trace(db_path, trace_id):
            click.echo(f"Unpinned trace {trace_id}")
        else:
            raise click.ClickException(TRACE_NOT_FOUND_ERROR.format(trace_id=trace_id))
    except TraceNotFoundError:
        raise click.ClickException(TRACE_NOT_FOUND_ERROR.format(trace_id=trace_id))


@trace.command()
@click.argument("trace_id", required=False)
@click.option(
    "--pinned", is_flag=True, help="Show compact representation of all pinned traces"
)
@click.option(
    "--returns",
    is_flag=True,
    help="Include return values in compact representation (warning: can be verbose)",
)
@click.option(
    "--recent",
    type=int,
    is_flag=False,
    flag_value=5,
    help="Show compact representation of the N most recent traces (default: 5)",
)
def compact(trace_id: str | None, pinned: bool, returns: bool, recent: int | None):
    """Get a compact representation of a specific trace.

    Get a concise yet detailed overview of everything that happened in the trace.
    You will see a tree representation of all function calls (and optionally return values),
    as well as other relevant information and points of interest in the trace like logs or sql queries.
    """
    if not any([pinned, trace_id is not None, recent is not None]):
        raise click.UsageError("Please provide a trace_id, --pinned, or --recent")

    db_path = setup_db()

    async def _get_compact():
        try:
            results = await get_compact_traces(
                db_path, trace_id, pinned=pinned, returns=returns, recent=recent or 0
            )
            for tid, compact_repr in results:
                if pinned or recent is not None:
                    click.echo(f"\n=== Trace {tid} ===")
                click.echo(compact_repr)
        except TraceNotFoundError as e:
            raise click.ClickException(TRACE_NOT_FOUND_ERROR.format(trace_id=e.args[0]))

    asyncio.run(_get_compact())


@trace.command()
@click.argument("trace_id")
def tree(trace_id: str):
    """Get the full JSON execution tree for a trace. Very verbose.
    Most likely you want to use `kolo trace compact` instead.
    """
    db_path = setup_db()

    async def _get_tree():
        try:
            trace_data, _ = load_trace_from_db(db_path, trace_id)
            tree_data = await get_execution_tree(trace_id, trace_data)
            click.echo(json.dumps(tree_data, indent=2))
        except TraceNotFoundError:
            raise click.ClickException(TRACE_NOT_FOUND_ERROR.format(trace_id=trace_id))
        except httpx.HTTPError as e:
            raise click.ClickException(f"Error fetching execution tree: {e}")

    asyncio.run(_get_tree())


def manage_py_settings():
    import ast

    try:
        with open("manage.py") as f:
            data = f.read()
    except OSError:  # pragma: no cover
        return None
    source = ast.parse(data, "manage.py")
    for node in ast.walk(source):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "setdefault"
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "DJANGO_SETTINGS_MODULE"
            and isinstance(node.args[1], ast.Constant)
        ):
            return node.args[1].value  # pragma: no cover
    return None


def load_django(settings):
    import django

    if settings:
        os.environ["DJANGO_SETTINGS_MODULE"] = settings
    elif os.environ.get("DJANGO_SETTINGS_MODULE"):
        pass
    else:
        settings = manage_py_settings()
        if settings:
            os.environ["DJANGO_SETTINGS_MODULE"] = settings  # pragma: no cover
        else:
            raise click.ClickException(DJANGO_SETTINGS_ERROR)

    django.setup()


@cli.command()
@click.argument("trace_ids", nargs=-1)
@click.option(
    "--test-name", default="test_my_view", help="The name of the generated test."
)
@click.option(
    "--test-class",
    default="MyTestCase",
    help="The name of the generated TestCase class.",
)
@click.option(
    "--file",
    type=click.File("w"),
    help="Write the generated test to this file.",
)
@click.option(
    "--settings", default="", help="The dotted path to a Django settings module."
)
@click.option(
    "--use-saved-schemas",
    default=False,
    is_flag=True,
    help="Load Django schemas saved with `kolo store-django-model-schema` instead of using the current schema. This may be useful when generating a test from an old trace.",
)
@click.option(
    "--intermediate-format",
    default=False,
    is_flag=True,
    help="Show an intermediate format of the data Kolo has extracted from the trace for use in the test.",
)
@click.option(
    "--and-run",
    default=False,
    is_flag=True,
    help="[Experimental, Use not recommended] Immediately run the newly generated test.",
)
@click.option(
    "--unittest", "pytest", flag_value=False, help="Generate a unittest style test."
)
@click.option(
    "--pytest",
    "pytest",
    flag_value=True,
    default=True,
    help="Generate a pytest style test (default).",
)
def generate_test(
    trace_ids,
    test_name,
    test_class,
    file,
    settings,
    use_saved_schemas,
    intermediate_format,
    and_run,
    pytest,
):
    """Generate a test from a Kolo trace."""
    import logging

    logging.disable()

    try:
        load_django(settings)

        if intermediate_format:
            for data in generate_test_intermediate_format(
                *trace_ids,
                test_class=test_class,
                test_name=test_name,
                use_saved_schemas=use_saved_schemas,
            ):
                click.echo(data)
            return
        try:
            test_code = generate_from_trace_ids(
                *trace_ids,
                test_class=test_class,
                test_name=test_name,
                use_saved_schemas=use_saved_schemas,
                pytest=pytest,
            )
        except TraceNotFoundError as e:
            raise click.ClickException(TRACE_NOT_FOUND_ERROR.format(trace_id=e.args[0]))

        if and_run:
            import unittest

            from django.test.runner import DiscoverRunner

            our_globals: Dict[Any, Any] = {}
            exec(test_code, our_globals)

            # Create TestSuite manually and add test cases
            test_suite = unittest.TestSuite()
            test_suite.addTest(
                unittest.defaultTestLoader.loadTestsFromTestCase(
                    our_globals[test_class]
                )
            )

            class CustomRunner(DiscoverRunner):
                def build_suite(
                    self, test_labels: Optional[Sequence[str]] = None, **kwargs
                ) -> unittest.TestSuite:
                    return test_suite

                def suite_result(self, suite, result, **kwargs):
                    return suite, result

            runner = CustomRunner()

            # Test output will be output in the terminal as usual
            suite, result = runner.run_tests([])  # type: ignore # we're now returning a tuple (see CustomRunner.suite_result above)
        elif file:
            file.write(test_code)
        else:
            click.echo(test_code)
    finally:
        logging.disable(logging.NOTSET)


@cli.command()
@click.option(
    "--settings", default="", help="The dotted path to a Django settings module."
)
def store_django_model_schema(settings):
    """Store Django model info for test generation."""
    from .git import COMMIT_SHA

    load_django(settings)

    schema = django_schema.get_schema()

    db_path = setup_db()
    with db_connection(db_path) as connection:
        create_schema_table(connection)
        save_schema(connection, schema, COMMIT_SHA)


@cli.command()
def dbshell():  # pragma: no cover
    """
    Open a sqlite3 shell to the Kolo database.
    """
    db_path = setup_db()
    subprocess.run(["sqlite3", db_path], check=True)


@trace.command()
@click.argument("trace_id")
def upload(trace_id):
    """
    Upload a trace to the Kolo dashboard
    """
    db_path = setup_db()

    try:
        msgpack_data, _ = load_trace_from_db(db_path, trace_id)
    except TraceNotFoundError:
        raise click.ClickException(TRACE_NOT_FOUND_ERROR.format(trace_id=trace_id))

    response = upload_to_dashboard(msgpack_data)

    if response.status_code == 201:
        click.echo(f"{trace_id} uploaded successfully!")
    else:
        errors = response.json()
        raise click.ClickException(errors)


@trace.command()
@click.argument("trace_id")
def download(trace_id):
    """
    Download a trace from the Kolo dashboard
    """
    db_path = setup_db()

    # TODO(later): The ability to download will ultimately likely be guarded by authenticating
    # against a given project/organisation etc so that you cannot download someone else's trace
    # just by guessing a ULID, so we'll probably need to pass those along eventually too...
    base_url = os.environ.get("KOLO_BASE_URL", "https://my.kolo.app")
    url = f"{base_url}/api/traces/{trace_id}/download"
    response = httpx.get(url)

    if response.status_code == 404:
        raise click.ClickException(f"`{trace_id}` was not found by the server.")
    elif response.status_code != 200:
        raise click.ClickException(f"Unexpected status code: {response.status_code}.")

    raw_data = response.content

    try:
        msgpack.unpackb(raw_data, strict_map_key=False)
    except Exception:
        raise click.ClickException("Downloaded trace was not valid msgpack.")

    try:
        save_trace_in_sqlite(
            db_path,
            trace_id,
            msgpack=raw_data,
            ignore_errors=False,
        )
    except sqlite3.IntegrityError:
        raise click.ClickException(f"`{trace_id}` already exists.")

    click.echo(f"`{trace_id}` downloaded successfully!")


@trace.command()
def json_to_msgpack():  # pragma: no cover
    """
    Convert all legacy json traces to msgpack
    """
    db_path = setup_db()
    count = convert_json_to_msgpack(db_path)
    click.echo(f"{count} traces converted!")


@cli.group()
def ci():
    """
    Subcommands for CI-related operations.
    """
    pass


def compress_trace(trace_data: bytes) -> bytes:
    compressed_data = BytesIO()
    with gzip.GzipFile(fileobj=compressed_data, mode="wb") as gz:
        gz.write(trace_data)
    return compressed_data.getvalue()


def create_trace_group() -> str:
    auth_token = os.environ["KOLO_TOKEN"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    base_url = os.environ.get("KOLO_BASE_URL", "https://my.kolo.app")
    response = httpx.post(
        f"{base_url}/api/trace-groups", headers=headers, json={"name": "ci"}
    )
    if response.status_code != 201:
        error_message = f"Failed to create trace group. Status code: {response.status_code}\n{response.text}"

        click.echo(click.style(error_message, fg="red"), err=True)
        raise click.Abort()

    trace_group = response.json()

    return trace_group["id"]


async def upload_trace(
    client: Union[httpx.Client, httpx.AsyncClient],
    trace_id: str,
    upload_url: str,
    db_path: Path,
    max_retries: int = 3,
    initial_backoff: float = 1.0,
) -> Optional[str]:
    loaded_trace = load_trace_from_db(db_path, trace_id)

    msgpack = loaded_trace[0]
    compressed_data = compress_trace(msgpack)

    for attempt in range(max_retries):
        try:
            if isinstance(client, httpx.AsyncClient):
                response = await client.put(
                    upload_url,
                    content=compressed_data,
                    headers={"Content-Type": "application/gzip"},
                    timeout=30.0,
                )
            else:
                response = client.put(
                    upload_url,
                    content=compressed_data,
                    headers={"Content-Type": "application/gzip"},
                    timeout=30.0,
                )

            if response.status_code != 200:
                error_message = (
                    f"Failed to upload {trace_id}.msgpack.gz. Status code: {response.status_code}\n"
                    f"{response.text}"
                )
                click.echo(click.style(error_message, fg="red"), err=True)
                return error_message

            return None  # Success case

        except (httpx.TimeoutException, httpx.RequestError) as e:
            if attempt < max_retries - 1:
                backoff = initial_backoff * (2**attempt)
                error_message = f"Error uploading {trace_id}.msgpack.gz (attempt {attempt + 1}/{max_retries}): {str(e)}. Retrying in {backoff:.2f} seconds..."
                click.echo(click.style(error_message, fg="yellow"), err=True)
                if isinstance(client, httpx.AsyncClient):
                    await asyncio.sleep(backoff)
                else:
                    time.sleep(backoff)
            else:
                error_message = f"Failed to upload {trace_id}.msgpack.gz after {max_retries} attempts: {str(e)}"
                click.echo(click.style(error_message, fg="red"), err=True)
                return error_message

    return f"Failed to upload {trace_id}.msgpack.gz after {max_retries} attempts"


def sync_ci_upload(traces: List[Dict[str, Any]], db_path: Path):
    with httpx.Client() as client:
        with click.progressbar(traces, label="Uploading traces", show_pos=True) as bar:
            for trace in bar:
                result = asyncio.run(
                    upload_trace(
                        client=client,
                        trace_id=trace["id"],
                        upload_url=trace["upload_url"],
                        db_path=db_path,
                    )
                )
                if result:
                    click.echo(f"\n{result}", err=True)


async def async_ci_upload(traces: List[Dict[str, Any]], db_path: Path):
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=20)) as client:
        tasks = [
            upload_trace(
                client=client,
                trace_id=trace["id"],
                upload_url=trace["upload_url"],
                db_path=db_path,
            )
            for trace in traces
        ]

        bar: click._termui_impl.ProgressBar[Any]
        with click.progressbar(
            length=len(tasks), label="Uploading traces", show_pos=True
        ) as bar:
            results = []
            for task in asyncio.as_completed(tasks):
                result = await task
                bar.update(1)
                if result:
                    results.append(result)
                    click.echo(f"\n{result}", err=True)


@ci.command("upload")
@click.option("--sync", is_flag=True, help="Use synchronous upload instead of async")
def ci_upload(sync: bool):
    """
    Upload all traces in the local Kolo db to Kolo Cloud
    """
    db_path = setup_db()
    auth_token = os.environ["KOLO_TOKEN"]

    traces_in_local_db = list_traces_from_db(db_path, count=10000)

    trace_group_id = create_trace_group()

    traces_registered = []
    page_size = 500

    for i in range(0, len(traces_in_local_db), page_size):
        page = traces_in_local_db[i : i + page_size]

        base_url = os.environ.get("KOLO_BASE_URL", "https://my.kolo.app")
        response = httpx.post(
            f"{base_url}/api/traces/bulk",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "trace_group_id": trace_group_id,
                "traces": [{"id": trace[0], "recorded_at": trace[1]} for trace in page],
            },
        )

        if response.status_code != 201:
            error_message = f"Failed to bulk create traces. Status code: {response.status_code}\n{response.text}"
            click.echo(click.style(error_message, fg="red"), err=True)
            raise click.Abort()

        traces_registered.extend(response.json()["traces"])

        click.echo(
            f"Registered {min(i + page_size, len(traces_in_local_db))} of {len(traces_in_local_db)} traces"
        )

    if sync:
        sync_ci_upload(traces=traces_registered, db_path=db_path)
    else:
        asyncio.run(async_ci_upload(traces=traces_registered, db_path=db_path))


@cli.command()
def mcp():
    """
    Start the Kolo MCP server.
    """
    import asyncio

    from .mcp_server import mcp

    asyncio.run(mcp.run_stdio())


if __name__ == "__main__":
    cli()  # pragma: no cover
