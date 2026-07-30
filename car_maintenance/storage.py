"""Persistence layer: load/save the garage, with backups and legacy migration.

Handles two jobs an 'advanced' version needs that the original didn't:
1. Migrating the old single-car car_data.json schema into a multi-vehicle garage.
2. Cleaning up dirty data on the way in (duplicate log entries, typo'd service
   names like "Oil Chnage") instead of silently trusting whatever's on disk.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from difflib import get_close_matches
from typing import Optional

from models import Vehicle, ServiceRecord, MileageSnapshot

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "car_data.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
MAX_BACKUPS = 5

KNOWN_SERVICES = [
    "Oil Change", "Tire Rotation", "Air Filter",
    "Brake Inspection", "Coolant Check",
]


class Garage:
    def __init__(self, vehicles: dict, active: Optional[str] = None):
        self.vehicles: dict = vehicles  # name -> Vehicle
        self.active = active or (next(iter(vehicles), None))

    def active_vehicle(self) -> Optional[Vehicle]:
        if self.active is None:
            return None
        return self.vehicles.get(self.active)

    def as_dict(self) -> dict:
        return {
            "active_vehicle": self.active,
            "vehicles": {name: v.as_dict() for name, v in self.vehicles.items()},
        }


def _fix_typo(service_name: str) -> str:
    """Correct near-miss spellings against the known service list, e.g. 'Oil Chnage'."""
    if service_name in KNOWN_SERVICES:
        return service_name
    match = get_close_matches(service_name, KNOWN_SERVICES, n=1, cutoff=0.75)
    return match[0] if match else service_name


def _dedupe_service_log(records: list) -> list:
    seen = set()
    deduped = []
    for r in records:
        key = (r.service, r.mileage, r.date)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


def _migrate_legacy(raw: dict) -> Garage:
    """Convert the old single-vehicle schema into the new multi-vehicle Garage."""
    name = raw.get("car_name") or "My Car"
    log = []
    for entry in raw.get("service_log", []):
        entry = dict(entry)
        entry["service"] = _fix_typo(entry.get("service", ""))
        log.append(ServiceRecord.from_dict(entry))
    log = _dedupe_service_log(log)

    vehicle = Vehicle(
        name=name,
        current_mileage=float(raw.get("current_mileage", 0.0)),
        driving_condition=raw.get("driving_condition", "Normal"),
        service_log=log,
    )
    # Seed a mileage snapshot so date-projection has at least one data point.
    vehicle.mileage_log.append(
        MileageSnapshot(
            mileage=vehicle.current_mileage,
            date=datetime.now().strftime("%Y-%m-%d"),
        )
    )
    return Garage(vehicles={name: vehicle}, active=name)


def load_garage() -> Garage:
    if not os.path.exists(DATA_FILE):
        return Garage(vehicles={})

    with open(DATA_FILE, "r") as f:
        raw = json.load(f)

    if "vehicles" in raw:  # already in the new schema
        vehicles = {n: Vehicle.from_dict(v) for n, v in raw["vehicles"].items()}
        return Garage(vehicles=vehicles, active=raw.get("active_vehicle"))

    # legacy single-car schema (car_name / current_mileage / service_log at top level)
    return _migrate_legacy(raw)


def _rotate_backups():
    if not os.path.exists(DATA_FILE):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    shutil.copy2(DATA_FILE, os.path.join(BACKUP_DIR, f"car_data_{stamp}.json"))

    backups = sorted(os.listdir(BACKUP_DIR))
    while len(backups) > MAX_BACKUPS:
        os.remove(os.path.join(BACKUP_DIR, backups.pop(0)))


def save_garage(garage: Garage):
    _rotate_backups()
    tmp_path = DATA_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(garage.as_dict(), f, indent=2)
    os.replace(tmp_path, DATA_FILE)
