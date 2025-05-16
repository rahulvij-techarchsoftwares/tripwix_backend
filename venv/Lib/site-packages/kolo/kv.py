from typing import Optional, Tuple

from .db import db_connection, get_db_path


def create_kolo_kv_table(connection) -> None:
    create_table_query = """
    CREATE TABLE IF NOT EXISTS kolo_kv (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT,
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    );
    """

    connection.execute(create_table_query)


def set(key, value) -> None:
    db_path = get_db_path()
    with db_connection(db_path) as connection:
        create_kolo_kv_table(connection)

        cursor = connection.execute("SELECT id FROM kolo_kv WHERE key = ?;", (key,))

        if cursor.fetchone():
            connection.execute(
                "UPDATE kolo_kv SET value = ?, updated_at = (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')) WHERE key = ?;",
                (value, key),
            )
        else:
            connection.execute(
                "INSERT INTO kolo_kv (key, value) VALUES (?, ?);", (key, value)
            )


def get(key) -> Tuple[int, str, str, str, str]:
    db_path = get_db_path()
    with db_connection(db_path) as connection:
        create_kolo_kv_table(connection)

        cursor = connection.execute(
            "SELECT id, key, value, updated_at, created_at FROM kolo_kv WHERE key = ?;",
            (key,),
        )
        result = cursor.fetchone()
        if not result:
            raise KeyError(f"Key {key} not found in kolo_kv")

        return result


def get_value(key) -> Optional[str]:
    id, key, value, updated_at, created_at = get(key)

    return value
