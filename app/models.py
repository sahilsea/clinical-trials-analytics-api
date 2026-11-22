"""SQLAlchemy ORM models."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Trial(Base):
    __tablename__ = "trials"

    id: Mapped[int] = mapped_column(primary_key=True)
    nct_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    acronym: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), index=True)
    has_results: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Multi-valued fields are stored pipe-delimited and exposed as lists by the API.
    conditions: Mapped[str | None] = mapped_column(Text)
    interventions: Mapped[str | None] = mapped_column(Text)
    outcome_measures: Mapped[str | None] = mapped_column(Text)
    sponsors: Mapped[str | None] = mapped_column(Text)
    funded_by: Mapped[str | None] = mapped_column(String(200))
    study_designs: Mapped[str | None] = mapped_column(Text)

    gender: Mapped[str | None] = mapped_column(String(20), index=True)
    age_description: Mapped[str | None] = mapped_column(String(200))
    min_age_years: Mapped[float | None] = mapped_column(Float)
    max_age_years: Mapped[float | None] = mapped_column(Float)
    includes_children: Mapped[bool] = mapped_column(Boolean, default=False)
    includes_adults: Mapped[bool] = mapped_column(Boolean, default=False)
    includes_older_adults: Mapped[bool] = mapped_column(Boolean, default=False)

    phases: Mapped[str | None] = mapped_column(String(50), index=True)
    enrollment: Mapped[int | None] = mapped_column(Integer)
    study_type: Mapped[str | None] = mapped_column(String(100), index=True)

    start_date: Mapped[date | None] = mapped_column(Date, index=True)
    primary_completion_date: Mapped[date | None] = mapped_column(Date)
    completion_date: Mapped[date | None] = mapped_column(Date)
    first_posted: Mapped[date | None] = mapped_column(Date)
    last_update_posted: Mapped[date | None] = mapped_column(Date)
    url: Mapped[str | None] = mapped_column(String(300))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    locations: Mapped[list["TrialLocation"]] = relationship(
        back_populates="trial", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Trial {self.nct_number} {self.status!r}>"


class TrialLocation(Base):
    __tablename__ = "trial_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    trial_id: Mapped[int] = mapped_column(ForeignKey("trials.id", ondelete="CASCADE"), index=True)
    facility: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(255))
    state: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(100), index=True)

    trial: Mapped[Trial] = relationship(back_populates="locations")


class EtlRun(Base):
    """Audit record for every ETL pipeline execution."""

    __tablename__ = "etl_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20))  # running | success | failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_valid: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
