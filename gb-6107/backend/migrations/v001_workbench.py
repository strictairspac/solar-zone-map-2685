from sqlalchemy import inspect, text

from src.models.base import metadata
from src.models import audit, cases, reviews, runs, users  # Register the tables.

# Retention columns added after the first version. They are applied additively
# so that an existing volume keeps its data instead of being recreated.
ADDED_COLUMNS = {
    "cases": {
        "expires_at": "BIGINT",
        "purge_state": "VARCHAR(16) NOT NULL DEFAULT 'active'",
        "purge_started_at": "BIGINT",
        "purged_at": "BIGINT",
    },
    "runs": {
        "source": "JSON",
        "accepted_at": "BIGINT",
        "purged_at": "BIGINT",
    },
    "reviews": {
        "evidence": "JSON",
    },
}


def upgrade(connection):
    metadata.create_all(connection)
    apply_additions(connection)


def apply_additions(connection):
    inspector = inspect(connection)
    tables = inspector.get_table_names()
    for name, columns in ADDED_COLUMNS.items():
        if name not in tables:
            continue
        existing = {column["name"] for column in inspector.get_columns(name)}
        for column, definition in columns.items():
            if column not in existing:
                connection.execute(text(f"ALTER TABLE {name} ADD COLUMN {column} {definition}"))
    # Raw readings are cleared by nulling the payload, so the column must accept
    # null on databases created before retention existed.
    relax_column(connection, tables, "cases", "payload", "JSON")
    # Existing runs predate explicit acceptance; keep them attributable.
    connection.execute(text("UPDATE runs SET accepted_at = created_at WHERE accepted_at IS NULL"))
    relax_column(connection, tables, "runs", "accepted_at", "BIGINT", nullable=False)


def relax_column(connection, tables, name, column, data_type, nullable=True):
    if name not in tables:
        return
    definition = next(
        (entry for entry in inspect(connection).get_columns(name) if entry["name"] == column), None,
    )
    if definition is None or bool(definition.get("nullable", True)) is nullable:
        return
    if connection.dialect.name == "postgresql":
        action = "DROP NOT NULL" if nullable else "SET NOT NULL"
        connection.execute(text(f"ALTER TABLE {name} ALTER COLUMN {column} {action}"))
    elif connection.dialect.name == "mysql":
        suffix = "NULL" if nullable else "NOT NULL"
        connection.execute(text(f"ALTER TABLE {name} MODIFY {column} {data_type} {suffix}"))
    # SQLite (used only by local test harnesses) cannot alter a column in place;
    # fresh databases already pick up the model definitions.
