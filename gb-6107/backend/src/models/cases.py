from sqlalchemy import JSON, BigInteger, Column, Integer, String, Table

from src.constants.purge_state import PurgeState
from .base import metadata


cases = Table(
    "cases", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(48), unique=True, nullable=False),
    Column("title", String(120), nullable=False),
    Column("description", String(420), nullable=False),
    Column("payload", JSON, nullable=True),
    Column("created_by", String(48), nullable=False),
    Column("expires_at", BigInteger, nullable=True),
    Column("purge_state", String(16), nullable=False, server_default=PurgeState.ACTIVE.value),
    Column("purge_started_at", BigInteger, nullable=True),
    Column("purged_at", BigInteger, nullable=True),
)
