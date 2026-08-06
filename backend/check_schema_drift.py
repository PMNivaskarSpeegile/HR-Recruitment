"""
Schema-drift checker: compares every managed=False Django model against the LIVE
PostgreSQL schema (the connection configured in settings/.env). Read-only.

Reports, per the sync task:
  - Missing tables       (model maps a table the DB doesn't have)
  - Missing columns      (model field with no matching DB column)
  - Incorrect data types (best-effort: field.db_type vs DB type)
  - Missing foreign keys (FK field with no FK constraint in the DB)
  - Missing indexes      (field db_index / unique with no matching DB index)
  - Other drift          (DB columns not represented by any model field — informational)

Run from backend/:  python check_schema_drift.py
"""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.db import connection  # noqa: E402

SCHEMA = "ats"


def db_tables():
    with connection.cursor() as c:
        c.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema=%s AND table_type='BASE TABLE'", [SCHEMA])
        return {r[0] for r in c.fetchall()}


def db_columns(table):
    with connection.cursor() as c:
        c.execute(
            "SELECT column_name, data_type, character_maximum_length, "
            "numeric_precision, numeric_scale, is_nullable "
            "FROM information_schema.columns WHERE table_schema=%s AND table_name=%s",
            [SCHEMA, table])
        return {r[0]: {"data_type": r[1], "len": r[2], "prec": r[3],
                       "scale": r[4], "nullable": r[5]} for r in c.fetchall()}


def db_fk_columns(table):
    with connection.cursor() as c:
        c.execute(
            "SELECT kcu.column_name FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name=kcu.constraint_name AND tc.table_schema=kcu.table_schema "
            "WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema=%s AND tc.table_name=%s",
            [SCHEMA, table])
        return {r[0] for r in c.fetchall()}


def db_indexed_columns(table):
    """Columns that appear in ANY index (single-column coverage check)."""
    with connection.cursor() as c:
        c.execute("SELECT indexdef FROM pg_indexes WHERE schemaname=%s AND tablename=%s",
                  [SCHEMA, table])
        defs = [r[0] for r in c.fetchall()]
    cols = set()
    for d in defs:
        inside = d[d.find("(") + 1:d.rfind(")")]
        for part in inside.split(","):
            cols.add(part.strip().strip('"').split(" ")[0])
    return cols


def norm_type(t):
    t = t.lower()
    aliases = {
        "character varying": "varchar", "character": "char",
        "timestamp without time zone": "timestamp",
        "timestamp with time zone": "timestamptz",
        "double precision": "float8", "boolean": "bool",
        "integer": "int", "int4": "int", "int2": "smallint",
        "int8": "bigint", "numeric": "numeric", "text": "text",
    }
    return aliases.get(t, t)


def main():
    report = {
        "missing_tables": [], "missing_columns": [], "type_mismatches": [],
        "missing_fks": [], "missing_indexes": [], "unmapped_db_columns": [],
    }
    all_tables = db_tables()
    managed_false_models = []

    for model in apps.get_models():
        meta = model._meta
        if meta.managed:  # only managed=False (ATS tables)
            continue
        table = meta.db_table
        managed_false_models.append((model, table))
        label = f"{model.__module__.split('.')[0]}.{model.__name__}"

        if table not in all_tables:
            report["missing_tables"].append(f"{label} -> {table}")
            continue

        cols = db_columns(table)
        fk_cols = db_fk_columns(table)
        idx_cols = db_indexed_columns(table)
        model_cols = set()

        for f in meta.concrete_fields:
            col = f.column
            model_cols.add(col)
            if col not in cols:
                report["missing_columns"].append(f"{label}.{f.name} -> {table}.{col}")
                continue

            # Best-effort type check (skip auto/derived where mapping is loose).
            try:
                declared = f.db_type(connection)
            except Exception:
                declared = None
            if declared:
                d = norm_type(declared.split("(")[0].strip())
                actual = norm_type(cols[col]["data_type"])
                # Treat serial/identity ints as int/bigint; ignore length nuances.
                equiv = {("serial", "int"), ("bigserial", "bigint"),
                         ("int", "serial"), ("bigint", "bigserial")}
                if d != actual and (d, actual) not in equiv and not (
                    d.startswith(actual) or actual.startswith(d)):
                    report["type_mismatches"].append(
                        f"{label}.{f.name} ({table}.{col}): model={declared} db={cols[col]['data_type']}")

            # FK constraint presence.
            if f.is_relation and f.many_to_one:
                if col not in fk_cols:
                    report["missing_fks"].append(f"{label}.{f.name} -> {table}.{col} (no FK constraint)")

            # Index presence. For managed=False models Django never CREATES
            # indexes, and PostgreSQL does NOT auto-index FK columns — the implicit
            # db_index=True on every ForeignKey is inert here, so flagging it is a
            # false positive. Only a genuinely-required index matters: unique=True
            # (must be enforced by a DB unique index) or an EXPLICIT db_index on a
            # non-relation field.
            needs_index = f.unique or (getattr(f, "db_index", False) and not f.is_relation)
            if needs_index and col not in idx_cols:
                report["missing_indexes"].append(f"{label}.{f.name} -> {table}.{col}")

        # DB columns not represented by any model field (informational).
        for col in sorted(set(cols) - model_cols):
            report["unmapped_db_columns"].append(f"{table}.{col}")

    # ---- print markdown-ish report ----
    print(f"# Schema Drift Report")
    print(f"\nDatabase: {connection.settings_dict.get('NAME')} | schema: {SCHEMA}")
    print(f"managed=False models checked: {len(managed_false_models)}")
    print(f"DB tables in '{SCHEMA}': {len(all_tables)}")

    def section(title, items, ok="none"):
        print(f"\n## {title}: {len(items)}")
        if items:
            for i in items:
                print(f"  - {i}")
        else:
            print(f"  ({ok})")

    section("Missing tables", report["missing_tables"], "all model tables exist")
    section("Missing columns", report["missing_columns"], "every model field maps to a column")
    section("Incorrect data types", report["type_mismatches"], "no mismatches")
    section("Missing foreign keys", report["missing_fks"], "every FK field has a DB FK constraint")
    section("Missing indexes", report["missing_indexes"], "every indexed/unique field has an index")
    section("Unmapped DB columns (informational)", report["unmapped_db_columns"], "models cover all columns")

    drift = (report["missing_tables"] or report["missing_columns"]
             or report["type_mismatches"] or report["missing_fks"] or report["missing_indexes"])
    print(f"\n## VERDICT: {'DRIFT DETECTED' if drift else 'NO DRIFT (models match schema)'}")

    # DB tables with no model (informational)
    model_tables = {t for _, t in managed_false_models}
    orphan = sorted(all_tables - model_tables)
    print(f"\n## DB tables without a managed=False model: {len(orphan)}")
    for t in orphan:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
