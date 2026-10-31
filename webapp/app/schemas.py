from datetime import date, timedelta
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import get_settings

# A dbt/seeds/categories.csv-vel egyezik, ezt teszt ellenőrzi.
CATEGORIES = frozenset({"élelmiszer", "háztartás", "lakbér", "közlekedés", "szórakozás", "egészség"})

SHARED_PAYER = "shared"
MOCK_AUTHOR = "mock"


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
    purchase_date: date
    payer: str = SHARED_PAYER
    tags: list[str]

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
        if self.purchase_date > date.today() + timedelta(days=1):
            raise ValueError("a blokk dátuma nem lehet jövőbeli")
        return self

    @model_validator(mode="after")
    def check_tags(self) -> Self:
        if not CATEGORIES.intersection(self.tags):
            raise ValueError("legalább egy alap kategória kell")
        return self
