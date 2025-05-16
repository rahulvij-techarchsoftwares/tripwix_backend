from datetime import datetime
from typing import Any

import sqlglot
from more_itertools import flatten


def sql_overview(query, *, database, query_data=None):
    parsed = sqlglot.parse_one(query, read=database)
    data: Any = {}
    if isinstance(parsed, sqlglot.expressions.Select):
        if query_data is None:
            return {"type": "other"}

        data["type"] = "select"
        data["columns"] = []

        try:
            rows = list(flatten(query_data))
        except TypeError:
            return {"type": "other"}

        for row in rows:
            columns = []
            for column, value in zip(parsed.expressions, row):
                if isinstance(column, sqlglot.expressions.Column):
                    column_data = {
                        "name": column.name,
                        "table": column.table,
                        "derived": False,
                        "value": value,
                    }
                else:
                    children = column.find_all(sqlglot.expressions.Column)
                    tables = {column.table for column in children}
                    column_data = {
                        "name": column.alias_or_name,
                        "tables": tables,
                        "derived": True,
                        "value": value,
                    }
                columns.append(column_data)
            data["columns"].append(columns)

    elif isinstance(parsed, sqlglot.expressions.Insert):
        data["type"] = "insert"
        data["table"] = parsed.this.this.name
        data["columns"] = []
        for values in parsed.expression.expressions:
            columns = [
                {
                    "name": column.name,
                    "value": parse_value(value),
                    "table": data["table"],
                }
                for column, value in zip(parsed.this.expressions, values)
            ]
            data["columns"].append(columns)
        data["returning"] = []
        if parsed.args["returning"]:
            for row in query_data:
                returning = []
                for column, value in zip(parsed.args["returning"].expressions, row):
                    returning.append(
                        {
                            "name": column.name,
                            "value": value,
                        }
                    )
                data["returning"].append(returning)

    elif isinstance(parsed, sqlglot.expressions.Update):
        data["type"] = "update"
        data["table"] = parsed.this.this.name
        data["where"] = parse_where(parsed)
        data["columns"] = [
            {
                "name": expression.this.name,
                "value": parse_value(expression.expression),
                "table": data["table"],
            }
            for expression in parsed.expressions
        ]

    elif isinstance(parsed, sqlglot.expressions.Delete):
        data["type"] = "delete"
        tables = parsed.args["tables"]
        if tables:
            data["tables"] = {table.name for table in tables}
        else:
            data["tables"] = {parsed.this.name}

        data["where"] = parse_where(parsed)

    else:
        data["type"] = "other"

    return data


def parse_where(parsed):
    where = parsed.args["where"]
    if where is None:
        return {}

    where = where.this
    if isinstance(where, sqlglot.expressions.EQ):
        return {
            "name": where.this.name,
            "value": where.expression.name,
        }
    elif isinstance(where, sqlglot.expressions.In):
        return {
            "name": where.this.name,
            "value": [v.name for v in where.expressions],
        }
    raise ValueError(f"Unexpected WHERE expression: {where}")  # pragma: no cover


def parse_value(expression):
    if isinstance(expression, sqlglot.expressions.Literal):
        return expression.name
    if isinstance(expression, sqlglot.expressions.Boolean):
        return expression.this
    if isinstance(expression, sqlglot.expressions.Cast):
        value = parse_value(expression.this)
        if expression.to.this == sqlglot.expressions.DataType.Type.TIMESTAMPTZ:
            return datetime.fromisoformat(value)
    if isinstance(expression, sqlglot.expressions.Null):
        return None
    return str(expression)
