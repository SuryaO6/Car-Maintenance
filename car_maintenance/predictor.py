"""Rule-based maintenance prediction engine.

Still rule-based (not ML) like the original, but upgraded:
- estimates km/day from mileage history to project a *calendar date*,
  not just "months remaining"
- returns structured PredictionResult objects instead of only printing,
  so the CLI (or any other frontend) can render/color/filter them
- adds a small stats module (spend, frequency) on top of the raw log
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from models import Vehicle, ServiceRecord

CONDITION_MULTIPLIERS = {"Harsh": 0.8, "Normal": 1.0, "Light": 1.15}


@dataclass
class PredictionResult:
    service: str
    status: str  # "overdue", "due_soon", "ok", "no_record"
    km_remaining: Optional[float]
    months_remaining: Optional[int]
    projected_date: Optional[str]
    message: str


def get_condition_multiplier(condition: str) -> float:
    return CONDITION_MULTIPLIERS.get(condition, 1.0)


def get_last_service(vehicle: Vehicle, service_type: str) -> Optional[ServiceRecord]:
    matches = [e for e in vehicle.service_log if e.service == service_type]
    if not matches:
        return None
    return max(matches, key=lambda e: e.mileage)


def estimate_daily_mileage(vehicle: Vehicle) -> Optional[float]:
    """Estimate km/day from the recorded mileage history, for date projections."""
    points = sorted(vehicle.mileage_log, key=lambda m: m.date)
    if len(points) < 2:
        return None
    first, last = points[0], points[-1]
    days = (datetime.strptime(last.date, "%Y-%m-%d") - datetime.strptime(first.date, "%Y-%m-%d")).days
    if days <= 0 or last.mileage <= first.mileage:
        return None
    return (last.mileage - first.mileage) / days


def predict_service(vehicle: Vehicle, service: str, km_interval: float, month_interval: int) -> PredictionResult:
    multiplier = get_condition_multiplier(vehicle.driving_condition)
    adjusted_km_interval = km_interval * multiplier
    last = get_last_service(vehicle, service)

    if last is None:
        return PredictionResult(
            service=service, status="no_record", km_remaining=None,
            months_remaining=None, projected_date=None,
            message=(f"No record found. Recommended every {adjusted_km_interval:.0f} km "
                     f"or {month_interval} months. Log one once it's done."),
        )

    km_since = vehicle.current_mileage - last.mileage
    km_remaining = adjusted_km_interval - km_since

    last_date = last.date_obj
    today = datetime.now()
    months_since = (today.year - last_date.year) * 12 + (today.month - last_date.month)
    months_remaining = month_interval - months_since

    daily_rate = estimate_daily_mileage(vehicle)
    projected_date = None
    if daily_rate and km_remaining > 0:
        days_left = km_remaining / daily_rate
        projected_date = datetime.fromordinal(today.toordinal() + int(days_left)).strftime("%Y-%m-%d")

    if km_remaining <= 0 or months_remaining <= 0:
        status = "overdue"
        message = (f"OVERDUE. Last done at {last.mileage:.0f} km ({last.date}). "
                   f"Get this checked soon.")
    elif km_remaining <= adjusted_km_interval * 0.15 or months_remaining <= 1:
        status = "due_soon"
        extra = f" Projected around {projected_date}." if projected_date else ""
        message = (f"Due soon, about {max(km_remaining, 0):.0f} km "
                   f"or {max(months_remaining, 0)} month(s) left.{extra}")
    else:
        status = "ok"
        extra = f" Projected around {projected_date}." if projected_date else ""
        message = (f"All good. Around {km_remaining:.0f} km "
                   f"or {months_remaining} month(s) remaining.{extra}")

    return PredictionResult(
        service=service, status=status, km_remaining=km_remaining,
        months_remaining=months_remaining, projected_date=projected_date, message=message,
    )


def predict_all(vehicle: Vehicle, intervals: dict) -> list:
    return [
        predict_service(vehicle, service, interval["km"], interval["months"])
        for service, interval in intervals.items()
    ]


def compute_stats(vehicle: Vehicle) -> dict:
    log = vehicle.service_log
    total_spent = sum(e.cost for e in log if e.cost)
    counts: dict = {}
    for e in log:
        counts[e.service] = counts.get(e.service, 0) + 1
    most_common = max(counts.items(), key=lambda kv: kv[1])[0] if counts else None
    return {
        "total_services": len(log),
        "total_spent": total_spent,
        "service_counts": counts,
        "most_common_service": most_common,
    }
