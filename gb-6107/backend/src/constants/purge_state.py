from enum import StrEnum


class PurgeState(StrEnum):
    ACTIVE = "active"
    PURGING = "purging"
    PURGED = "purged"
