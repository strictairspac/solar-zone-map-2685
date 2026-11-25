from sqlalchemy import JSON, BigInteger, Column, ForeignKey, String, Table
from .base import metadata


reviews = Table(
    "reviews", metadata,
    Column("run_id", ForeignKey("runs.id"), primary_key=True),
    Column("actor", String(48), nullable=False),
    Column("note", String(500), nullable=False),
    Column("created_at", BigInteger, nullable=False),
    # Frozen copy of the run result at signing time. Survives purging of the
    # batch so the receipt keeps its board items and page-skip basis.
    Column("evidence", JSON(none_as_null=True), nullable=True),
)
