from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import get_settings

# A dbt/seeds/categories.csv-vel egyezik, ezt teszt ellenőrzi.
CATEGORIES = frozenset({"élelmiszer", "háztartás", "lakbér", "közlekedés", "szórakozás", "egészség"})

SHARED_PAYER = "shared"
MOCK_AUTHOR = "mock"
# A worker készpénznél és számlánál is ennyit enged a kerekítés miatt.
CORRECTION_SUM_LIMIT = 2


class ManualEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: Literal["expense", "income", "transfer"]
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="HUF", pattern=r"^[A-Z]{3}$")
    occurred_on: date
    entered_by: str
    purchased_by: str | None = None
    payer: str
    tags: list[str] = []
    note: str | None = None

    @model_validator(mode="after")
    def check_people(self) -> Self:
        members = get_settings().members
        if self.entered_by not in members | {MOCK_AUTHOR}:
            raise ValueError("ismeretlen entered_by")
        if self.purchased_by is None:
            self.purchased_by = self.entered_by
        if self.purchased_by not in members:
            raise ValueError("ismeretlen purchased_by")
        if self.payer not in members | {SHARED_PAYER}:
            raise ValueError("ismeretlen payer")
        return self

    @model_validator(mode="after")
    def check_tags(self) -> Self:
        if self.kind == "expense":
            if len(self.tags) != 1 or self.tags[0] not in CATEGORIES:
                raise ValueError("a kiadásnak pontosan egy alap kategóriája van")
        elif self.tags:
            raise ValueError("csak kiadásnak lehet kategóriája")
        return self


class UploadForm(BaseModel):
    uploaded_by: str
    purchased_by: str | None = None
    purchase_date: date | None = None
    payer: str = SHARED_PAYER
    tags: list[str]

    @field_validator("purchase_date", mode="before")
    @classmethod
    def empty_date_is_missing(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def check_people(self) -> Self:
        members = get_settings().members
        if self.uploaded_by not in members:
            raise ValueError("ismeretlen uploaded_by")
        if not self.purchased_by:
            self.purchased_by = self.uploaded_by
        if self.purchased_by not in members:
            raise ValueError("ismeretlen purchased_by")
        if self.payer not in members | {SHARED_PAYER}:
            raise ValueError("ismeretlen payer")
        return self

    @model_validator(mode="after")
    def check_date(self) -> Self:
        # A szerver UTC-ben fut, a böngésző helyi napja egy nappal előrébb járhat.
        if self.purchase_date and self.purchase_date > date.today() + timedelta(days=1):
            raise ValueError("a blokk dátuma nem lehet jövőbeli")
        return self

    @model_validator(mode="after")
    def check_tags(self) -> Self:
        if not CATEGORIES.intersection(self.tags):
            raise ValueError("legalább egy alap kategória kell")
        return self


class ServiceReport(BaseModel):
    name: str
    state: str
    health: str = ""


class JobReport(BaseModel):
    name: Literal["dbt", "backup"]
    active: str
    result: str
    last_run: datetime | None = None
    next_run: datetime | None = None


class HostReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    services: list[ServiceReport]
    jobs: list[JobReport]
    row_counts: dict[str, int]
    garage_objects: int | None = None
    garage_size: str | None = None
    disk_free_bytes: int
    disk_total_bytes: int
    memory_available_bytes: int
    memory_total_bytes: int
    load: float


class WorkerReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: Literal["idle", "download", "storage", "read_text", "parse", "close"]
    step_started_at: datetime
    ollama_reachable: bool
    model_name: str
    model_version: str | None = None
    model_downloaded: bool
    model_loaded: bool
    model_memory_bytes: int


class CloseResult(BaseModel):
    result: Literal["ok", "review", "unparsed", "unreadable", "duplicate", "reopened"]
    seconds: float | None = None
    items: int | None = None


class ReviewPackage(BaseModel):
    """Amit a worker visszatölt: a webapp a bronzot és a Garage-ot nem éri el."""

    parse_id: UUID
    parser_version: str
    result: Literal["ok", "review", "unparsed", "unreadable"]
    document_type: str | None = None
    parsed: dict
    checks: dict
    ocr_text: str
    uploaded_at: datetime
    content_types: list[str] = Field(min_length=1, max_length=20)
    sha256s: list[str] = Field(min_length=1, max_length=20)


class CorrectedItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    value: float
    kind: Literal["item", "deposit", "discount", "voucher"] = "item"
    quantity: float | None = None
    unit: str | None = Field(default=None, max_length=20)
    unit_price: float | None = None


class Correction(BaseModel):
    store_name: str | None = Field(default=None, max_length=200)
    purchased_on: date
    total: float = Field(gt=0)
    items: list[CorrectedItem] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def check_sum(self) -> Self:
        if abs(sum(item.value for item in self.items) - self.total) > CORRECTION_SUM_LIMIT:
            raise ValueError("a tételek összege nem egyezik a végösszeggel")
        return self


class ReviewReopen(BaseModel):
    decided_by: str

    @model_validator(mode="after")
    def check_person(self) -> Self:
        if self.decided_by not in get_settings().members:
            raise ValueError("ismeretlen decided_by")
        return self


class WorkerReopen(ReviewReopen):
    """A workernél a döntés már a bronzban van, ezért a saját azonosítójával érkezik."""

    id: UUID


class ReviewDecision(BaseModel):
    parse_id: UUID
    action: Literal["approved", "corrected", "rejected"]
    decided_by: str
    corrected: Correction | None = None

    @model_validator(mode="after")
    def check_decision(self) -> Self:
        if self.decided_by not in get_settings().members:
            raise ValueError("ismeretlen decided_by")
        if (self.action == "corrected") != (self.corrected is not None):
            raise ValueError("javított adat csak javításnál van, és ott kötelező")
        return self
