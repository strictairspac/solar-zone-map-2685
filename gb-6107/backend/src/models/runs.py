from sqlalchemy import JSON, BigInteger, Column, ForeignKey, Integer, String, Table
from .base import metadata


runs = Table(
    "runs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("case_id", ForeignKey("cases.id"), nullable=False, index=True),
    Column("status", String(16), nullable=False, index=True),
    Column("parameter", Integer, nullable=False),
    Column("actor", String(48), nullable=False),
    Column("created_at", BigInteger, nullable=False),
    Column("finished_at", BigInteger, nullable=True),
    Column("result", JSON(none_as_null=True), nullable=True),
    Column("failure", String(320), nullable=True),
    Column("digest", String(64), nullable=True),
    # The test boards the batch was accepted to inspect. Null means "same as
    # the case payload"; kept separate so an in-flight run still has a source
    # after the case's raw readings are purged.
    Column("source", JSON(none_as_null=True), nullable=True),
    # Set when the case's retention expires. Queued runs that have not started
    # are refused; accepted ones finish against this snapshot.
    Column("accepted_at", BigInteger, nullable=False),
    Column("purged_at", BigInteger, nullable=True),
)
