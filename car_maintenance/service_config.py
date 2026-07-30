"""Configurable service intervals, loaded from service_intervals.json.

This is what makes the interval table 'advanced': instead of a hardcoded
dict baked into the script, users can add their own custom service types
(with their own km/month intervals) and they persist across runs.
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "service_intervals.json")

DEFAULT_INTERVALS = {
    "Oil Change": {"km": 5000, "months": 6},
    "Tire Rotation": {"km": 10000, "months": 6},
    "Air Filter": {"km": 15000, "months": 12},
    "Brake Inspection": {"km": 20000, "months": 12},
    "Coolant Check": {"km": 40000, "months": 24},
}


def load_intervals() -> dict:
    if not os.path.exists(CONFIG_FILE):
        save_intervals(DEFAULT_INTERVALS)
        return dict(DEFAULT_INTERVALS)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_intervals(intervals: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(intervals, f, indent=2)


def add_or_update_service(name: str, km: float, months: int) -> dict:
    intervals = load_intervals()
    intervals[name] = {"km": km, "months": months}
    save_intervals(intervals)
    return intervals
