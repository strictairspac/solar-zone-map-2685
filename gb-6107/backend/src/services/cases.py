from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import insert, select

from src.constants.purge_state import PurgeState
from src.domain import scenario
from src.models.cases import cases
from src.services import retention
from .audit import record


def get(db, case_id):
    entry = db.execute(select(cases).where(cases.c.id == case_id)).mappings().first()
    if entry is None:
        raise HTTPException(404, "资料不存在")
    entry = dict(entry)
    entry["progress"] = retention.summarise(db, [entry])[case_id]
    return entry


def list_entries(db):
    rows = [dict(row) for row in db.execute(select(cases).order_by(cases.c.id.desc()).limit(100)).mappings()]
    progress = retention.summarise(db, rows)
    return [{**row, "progress": progress[row["id"]]} for row in rows]


def create(db, data, actor):
    validator = getattr(scenario, "validate", None)
    if validator is not None:
        try:
            validator(data.payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    change = db.execute(insert(cases).values(
        **data.model_dump(), code=f"CASE-{uuid4().hex[:12].upper()}", created_by=actor,
        purge_state=PurgeState.ACTIVE,
    ))
    case_id = change.inserted_primary_key[0]
    record(db, "create_case", actor, "case", case_id)
    return get(db, case_id)
