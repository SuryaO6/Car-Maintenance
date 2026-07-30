"""Data models for the car maintenance predictor."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class ServiceRecord:
    service: str
    mileage: float
    date: str  # ISO format YYYY-MM-DD
    cost: Optional[float] = None
    notes: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "ServiceRecord":
        return ServiceRecord(
            service=d["service"],
            mileage=float(d["mileage"]),
            date=d["date"],
            cost=d.get("cost"),
            notes=d.get("notes", ""),
        )

    @property
    def date_obj(self) -> datetime:
        return datetime.strptime(self.date, "%Y-%m-%d")


@dataclass
class MileageSnapshot:
    mileage: float
    date: str

    @staticmethod
    def from_dict(d: dict) -> "MileageSnapshot":
        return MileageSnapshot(mileage=float(d["mileage"]), date=d["date"])

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Vehicle:
    name: str
    current_mileage: float = 0.0
    driving_condition: str = "Normal"
    service_log: list = field(default_factory=list)   # list[ServiceRecord]
    mileage_log: list = field(default_factory=list)    # list[MileageSnapshot]

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "current_mileage": self.current_mileage,
            "driving_condition": self.driving_condition,
            "service_log": [s.as_dict() for s in self.service_log],
            "mileage_log": [m.as_dict() for m in self.mileage_log],
        }

    @staticmethod
    def from_dict(d: dict) -> "Vehicle":
        return Vehicle(
            name=d["name"],
            current_mileage=float(d.get("current_mileage", 0.0)),
            driving_condition=d.get("driving_condition", "Normal"),
            service_log=[ServiceRecord.from_dict(s) for s in d.get("service_log", [])],
            mileage_log=[MileageSnapshot.from_dict(m) for m in d.get("mileage_log", [])],
        )
