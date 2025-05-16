from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple

from .config import create_kolo_directory
from .serialize import dump_msgpack, load_msgpack

logger = logging.getLogger("kolo")


class SchemaNotFoundError(Exception):
    pass


class TraceNotFoundError(Exception):
    pass


@contextmanager
def db_connection(db_path, timeout=60):
    """
    Wrap sqlite's connection for use as a context manager

    Commits all changes if no exception is raised.
    Always closes the connection after the context manager exits.
    """
    connection = sqlite3.connect(str(db_path), isolation_level=None, timeout=timeout)
    try:
        connection.execute("pragma journal_mode=wal")
    finally:
        connection.close()

    connection = sqlite3.connect(str(db_path), isolation_level=None, timeout=timeout)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def get_db_path() -> Path:
    return create_kolo_directory() / "db.sqlite3"


def get_db_last_modified() -> datetime | None:
    try:
        modified = get_db_path().stat().st_mtime_ns
    except FileNotFoundError:
        return None
    else:
        return datetime.fromtimestamp(modified / 1e9, tz=timezone.utc)


def create_traces_table(connection) -> None:
    create_table_query = """
    CREATE TABLE IF NOT EXISTS traces (
        id text PRIMARY KEY NOT NULL,
        created_at TEXT DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW')) NOT NULL,
        data text NULL,
        msgpack blob NULL,
        is_pinned INTEGER DEFAULT 0
    );
    """
    create_timestamp_index_query = """
        CREATE INDEX IF NOT EXISTS
        idx_traces_created_at
        ON traces (created_at);
        """

    connection.execute(create_table_query)
    connection.execute(create_timestamp_index_query)


def setup_db() -> Path:
    db_path = get_db_path()

    with db_connection(db_path) as connection:
        create_traces_table(connection)

    return db_path


def save_trace_in_sqlite(
    db_path: Path,
    trace_id: str,
    msgpack: bytes,
    *,
    ignore_errors: bool = True,
    created_at: datetime | None = None,
    timeout=60,
) -> None:
    ignore = " OR IGNORE" if ignore_errors else ""
    _columns = ["id", "msgpack"]
    values: list[object] = [trace_id, msgpack]
    if created_at is not None:
        _columns.append("created_at")
        values.append(created_at)
    columns = ", ".join(_columns)
    params = ",".join(["?" for _ in _columns])

    insert_sql = f"INSERT{ignore} INTO traces({columns}) VALUES({params})"

    # We can't reuse a connection
    # because we're in a new thread
    with db_connection(db_path, timeout) as connection:
        try:
            connection.execute(insert_sql, values)
        except (sqlite3.DataError, sqlite3.InterfaceError):
            # DataError on python 3.11+
            # InterfaceError on python 3.10-
            logger.exception("The generated trace was too big to store in sqlite.")


def load_trace_from_db(db_path: Path, trace_id: str) -> Tuple[bytes, str]:
    fetch_sql = "SELECT msgpack, created_at FROM traces WHERE id = ?"

    with db_connection(db_path) as connection:
        cursor = connection.execute(fetch_sql, (trace_id,))
        row = cursor.fetchone()
    if row is None:
        raise TraceNotFoundError(trace_id)
    return row


def load_trace_with_size_from_db(
    db_path: Path, trace_id: str
) -> Tuple[str, str, int, bytes]:
    fetch_sql = """
        SELECT id, created_at, LENGTH(msgpack), msgpack
        FROM traces WHERE id = ?
    """

    with db_connection(db_path) as connection:
        cursor = connection.execute(fetch_sql, (trace_id,))
        row = cursor.fetchone()
    if row is None:
        raise TraceNotFoundError(trace_id)
    return row


def list_traces_from_db(db_path: Path, count=500, reverse=False):
    list_sql = """
    SELECT id, created_at, LENGTH(msgpack)
    FROM traces ORDER BY id DESC LIMIT ?
    """

    with db_connection(db_path) as connection:
        cursor = connection.execute(list_sql, [count])
        rows = cursor.fetchall()
    if reverse:
        return reversed(rows)
    return rows


def list_traces_with_data_from_db(db_path: Path, count=500, reverse=False):
    """Like list_traces_from_db but includes the msgpack data for each trace."""
    list_sql = """
    SELECT id, created_at, LENGTH(msgpack), msgpack
    FROM traces ORDER BY id DESC LIMIT ?
    """

    with db_connection(db_path) as connection:
        cursor = connection.execute(list_sql, [count])
        rows = []
        while True:
            row = cursor.fetchone()
            if row is None:
                break
            if reverse:
                rows.append(row)
            else:
                yield row

    if reverse:
        for row in reversed(rows):
            yield row


def get_pinned_traces(db_path: Path) -> Iterator[Tuple[str, str, int, bytes]]:
    """Get all pinned traces from the database."""
    with db_connection(db_path) as connection:
        cursor = connection.execute(
            """
            SELECT id, created_at, LENGTH(msgpack), msgpack
            FROM traces
            WHERE is_pinned = 1
            ORDER BY id DESC
            """
        )
        while True:
            row = cursor.fetchone()
            if row is None:
                break
            yield row


def delete_traces_by_id(db_path: Path, trace_ids: Tuple[str, ...]):
    params = ", ".join("?" * len(trace_ids))
    delete_sql = f"DELETE FROM traces WHERE id in ({params})"

    with db_connection(db_path) as connection:
        cursor = connection.execute(delete_sql, trace_ids)
        return cursor.rowcount


def delete_traces_before(db_path: Path, before: datetime):
    delete_sql = "DELETE FROM traces WHERE (created_at < ?)"

    with db_connection(db_path) as connection:
        connection.execute(delete_sql, (before,))
        cursor = connection.execute("SELECT changes()")
        deleted_count = cursor.fetchone()[0]
    return deleted_count


def vacuum_db(db_path):
    with db_connection(db_path) as connection:
        connection.execute("VACUUM")


def create_schema_table(connection) -> None:
    create_table_query = """
    CREATE TABLE IF NOT EXISTS schemas (
        id integer PRIMARY KEY,
        created_at TEXT DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW')) NOT NULL,
        git_commit TEXT NULL,
        data text NOT NULL
    );
    """

    connection.execute(create_table_query)


class SchemaEncoder(json.JSONEncoder):
    def default(self, obj):
        from django.utils.functional import Promise

        if isinstance(obj, Promise):
            return str(obj)
        if isinstance(obj, datetime):
            return {"__type": "datetime", "value": obj.isoformat()}
        if isinstance(obj, date):
            return {"__type": "date", "value": obj.isoformat()}
        if isinstance(obj, time):
            return {"__type": "time", "value": obj.isoformat()}
        return super().default(obj)  # pragma: no cover


def decode_value(obj):
    if "__type" not in obj:
        return obj
    _type = obj["__type"]
    value = obj["value"]
    if _type == "datetime":
        return datetime.fromisoformat(value)
    if _type == "date":
        return date.fromisoformat(value)
    if _type == "time":
        return time.fromisoformat(value)
    raise ValueError(f"Could not decode: {obj}")  # pragma: no cover


def save_schema(connection, schema, commit_sha) -> None:
    delete_sql = "DELETE FROM schemas WHERE git_commit = ?"
    insert_sql = 'INSERT INTO schemas("data", "git_commit") VALUES(?, ?)'

    json_schema = json.dumps(schema, cls=SchemaEncoder)
    connection.execute(delete_sql, (commit_sha,))
    connection.execute(insert_sql, (json_schema, commit_sha))


def load_schema(db_path: Path) -> Tuple[Dict[str, Any], str]:
    load_sql = """SELECT data, git_commit FROM schemas
        ORDER BY created_at DESC LIMIT 1"""

    with db_connection(db_path) as connection:
        cursor = connection.execute(load_sql)
        data, commit = cursor.fetchone()

    data = json.loads(data, object_hook=decode_value)
    return data, commit


def load_schema_for_commit_sha(
    db_path: Path, commit_sha: str
) -> Tuple[Dict[str, Any], str]:
    load_sql = """SELECT data FROM schemas WHERE git_commit = ?
        ORDER BY created_at DESC LIMIT 1"""

    with db_connection(db_path) as connection:
        try:
            cursor = connection.execute(load_sql, [commit_sha])
        except sqlite3.OperationalError:
            row = None
        else:
            row = cursor.fetchone()

    if not row:
        raise SchemaNotFoundError(commit_sha)

    return json.loads(row[0], object_hook=decode_value)


def convert_json_to_msgpack(db_path: Path):  # pragma: no cover
    json_traces = "SELECT id, data FROM traces WHERE data IS NOT NULL"
    update_trace = "UPDATE traces SET data = NULL, msgpack = ? WHERE id = ?"

    with db_connection(db_path) as connection:
        cursor = connection.execute(json_traces)
        rows = cursor.fetchall()

        for trace_id, json_data in rows:
            msgpack_data = dump_msgpack(json.loads(json_data))
            cursor.execute(update_trace, (msgpack_data, trace_id))

    return len(rows)


def pin_trace(db_path: Path, trace_id: str) -> bool:
    """Pin a trace. Returns True if the trace was found and pinned."""
    update_sql = """
    UPDATE traces 
    SET is_pinned = 1
    WHERE id = ?
    """

    with db_connection(db_path) as connection:
        try:
            connection.execute(
                "ALTER TABLE traces ADD COLUMN is_pinned INTEGER DEFAULT 0"
            )
        except sqlite3.OperationalError:
            # Column already exists
            pass

        cursor = connection.execute(update_sql, (trace_id,))
        return cursor.rowcount > 0


def unpin_trace(db_path: Path, trace_id: str) -> bool:
    """Unpin a trace. Returns True if the trace was found and unpinned."""
    update_sql = """
    UPDATE traces 
    SET is_pinned = 0
    WHERE id = ?
    """

    with db_connection(db_path) as connection:
        cursor = connection.execute(update_sql, (trace_id,))
        return cursor.rowcount > 0
