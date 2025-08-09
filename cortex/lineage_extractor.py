import argparse
import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from utils.config import get_environment_snowflake_connection


@dataclass
class ColumnLineage:
    column_name: str
    sources: List[Dict[str, Any]]  # Each: {table_catalog, table_schema, table_name, source_column?}
    notes: Optional[str] = None


@dataclass
class ViewLineage:
    database: str
    schema: str
    view_name: str
    ddl: Optional[str]
    table_usage: List[Dict[str, Any]]
    column_lineage: List[ColumnLineage]


def fetch_view_ddl(conn, database: str, schema: str, view_name: str) -> Optional[str]:
    cursor = conn.cursor()
    try:
        fq_name = f"{database}.{schema}.{view_name}"
        cursor.execute("SELECT GET_DDL('VIEW', %s)", (fq_name,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()


def fetch_table_usage(conn, database: str, schema: str, view_name: str) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    try:
        sql = (
            "SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME "
            "FROM INFORMATION_SCHEMA.VIEW_TABLE_USAGE "
            "WHERE TABLE_CATALOG = %s AND TABLE_SCHEMA = %s AND VIEW_NAME = %s "
            "ORDER BY TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME"
        )
        cursor.execute(sql, (database, schema, view_name))
        rows = cursor.fetchall() or []
        return [
            {
                "TABLE_CATALOG": r[0],
                "TABLE_SCHEMA": r[1],
                "TABLE_NAME": r[2],
            }
            for r in rows
        ]
    finally:
        cursor.close()


def fetch_column_usage(conn, database: str, schema: str, view_name: str) -> List[Dict[str, Any]]:
    """Fetch base column usage for the view.
    Note: In Snowflake, INFORMATION_SCHEMA.VIEW_COLUMN_USAGE sometimes omits source column details.
    We'll still group by column for a coarse lineage.
    """
    cursor = conn.cursor()
    try:
        sql = (
            "SELECT COLUMN_NAME, TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME "
            "FROM INFORMATION_SCHEMA.VIEW_COLUMN_USAGE "
            "WHERE TABLE_CATALOG = %s AND TABLE_SCHEMA = %s AND VIEW_NAME = %s "
            "ORDER BY COLUMN_NAME, TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME"
        )
        cursor.execute(sql, (database, schema, view_name))
        rows = cursor.fetchall() or []
        return [
            {
                "COLUMN_NAME": r[0],
                "TABLE_CATALOG": r[1],
                "TABLE_SCHEMA": r[2],
                "TABLE_NAME": r[3],
            }
            for r in rows
        ]
    finally:
        cursor.close()


def describe_view_columns(conn, database: str, schema: str, view_name: str) -> List[str]:
    cursor = conn.cursor()
    try:
        fq_name = f"{database}.{schema}.{view_name}"
        cursor.execute(f"DESCRIBE TABLE {fq_name}")
        rows = cursor.fetchall() or []
        # Snowflake describe returns column name in first position
        return [r[0] for r in rows if r and isinstance(r[0], str)]
    finally:
        cursor.close()


def build_column_lineage(
    all_columns: List[str], column_usage: List[Dict[str, Any]]
) -> List[ColumnLineage]:
    by_col: Dict[str, List[Dict[str, Any]]] = {}
    for entry in column_usage:
        by_col.setdefault(entry["COLUMN_NAME"], []).append(entry)

    lineage: List[ColumnLineage] = []
    for col in all_columns:
        usage_entries = by_col.get(col, [])
        sources = []
        for u in usage_entries:
            sources.append(
                {
                    "table_catalog": u.get("TABLE_CATALOG"),
                    "table_schema": u.get("TABLE_SCHEMA"),
                    "table_name": u.get("TABLE_NAME"),
                }
            )

        notes = None
        if not sources:
            notes = "No explicit base column usage reported; likely derived/CASE/constant."

        lineage.append(ColumnLineage(column_name=col, sources=sources, notes=notes))
    return lineage


def write_lineage_json(
    output_dir: str, database: str, schema: str, view_name: str, lineage: ViewLineage
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{view_name}_lineage.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "database": lineage.database,
                "schema": lineage.schema,
                "view_name": lineage.view_name,
                "ddl": lineage.ddl,
                "table_usage": lineage.table_usage,
                "column_lineage": [asdict(c) for c in lineage.column_lineage],
            },
            f,
            indent=2,
        )
    return path


def upsert_ai_schema_metadata_relationships(
    conn, database: str, schema: str, view_name: str, column_lineage: List[ColumnLineage]
):
    cursor = conn.cursor()
    try:
        for col in column_lineage:
            relationships_json = json.dumps(
                {
                    "variants": [
                        {
                            "source_object": 
                                f"{src.get('table_catalog')}.{src.get('table_schema')}.{src.get('table_name')}",
                        }
                        for src in col.sources
                    ],
                    "notes": col.notes,
                }
            )

            # Try update first
            update_sql = (
                "UPDATE PF.BI.AI_SCHEMA_METADATA "
                "SET RELATIONSHIPS = %s "
                "WHERE TABLE_NAME = %s AND COLUMN_NAME = %s"
            )
            cursor.execute(update_sql, (relationships_json, view_name, col.column_name))
            if cursor.rowcount == 0:
                # Insert minimal row
                insert_sql = (
                    "INSERT INTO PF.BI.AI_SCHEMA_METADATA (ID, TABLE_NAME, COLUMN_NAME, RELATIONSHIPS) "
                    "SELECT COALESCE(MAX(ID),0)+1, %s, %s, %s FROM PF.BI.AI_SCHEMA_METADATA"
                )
                cursor.execute(insert_sql, (view_name, col.column_name, relationships_json))

        conn.commit()
    finally:
        cursor.close()


def main():
    parser = argparse.ArgumentParser(description="Extract lineage for a Snowflake view and write JSON/optional DB updates.")
    parser.add_argument("--database", required=True, help="Database name, e.g., PF")
    parser.add_argument("--schema", required=True, help="Schema name, e.g., BI")
    parser.add_argument("--view", required=True, help="View name, e.g., V_CREATOR_PAYMENTS_UNION")
    parser.add_argument("--out", default="cortex/narratives/lineage", help="Output directory for lineage JSON")
    parser.add_argument("--update-db", action="store_true", help="Update AI_SCHEMA_METADATA.RELATIONSHIPS with lineage JSON")
    parser.add_argument("--skip-info", action="store_true", help="Skip INFORMATION_SCHEMA usage queries (use DDL+DESCRIBE only)")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    conn = get_environment_snowflake_connection()
    try:
        ddl = fetch_view_ddl(conn, args.database, args.schema, args.view)
        if args.skip_info:
            table_usage = []
            column_usage = []
        else:
            table_usage = fetch_table_usage(conn, args.database, args.schema, args.view)
            column_usage = fetch_column_usage(conn, args.database, args.schema, args.view)
        columns = describe_view_columns(conn, args.database, args.schema, args.view)

        column_lineage = build_column_lineage(columns, column_usage)
        lineage = ViewLineage(
            database=args.database,
            schema=args.schema,
            view_name=args.view,
            ddl=ddl,
            table_usage=table_usage,
            column_lineage=column_lineage,
        )

        path = write_lineage_json(args.out, args.database, args.schema, args.view, lineage)
        logging.info(f"Wrote lineage JSON: {path}")

        if args.update_db:
            upsert_ai_schema_metadata_relationships(conn, args.database, args.schema, args.view, column_lineage)
            logging.info("Updated AI_SCHEMA_METADATA.RELATIONSHIPS")

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()


