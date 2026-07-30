import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import Vehicle, ServiceRecord, MileageSnapshot  # noqa: E402
from predictor import (  # noqa: E402
    predict_service,
    get_condition_multiplier,
    estimate_daily_mileage,
    compute_stats,
)


class TestConditionMultiplier(unittest.TestCase):
    def test_harsh(self):
        self.assertEqual(get_condition_multiplier("Harsh"), 0.8)

    def test_light(self):
        self.assertEqual(get_condition_multiplier("Light"), 1.15)

    def test_normal_default_for_unknown(self):
        self.assertEqual(get_condition_multiplier("Unknown"), 1.0)


class TestPredictService(unittest.TestCase):
    def _vehicle(self, mileage, condition, last_mileage, last_date):
        v = Vehicle(name="Test", current_mileage=mileage, driving_condition=condition)
        v.service_log.append(ServiceRecord(service="Oil Change", mileage=last_mileage, date=last_date))
        return v

    def test_no_record_returns_no_record_status(self):
        v = Vehicle(name="Test", current_mileage=1000)
        result = predict_service(v, "Oil Change", 5000, 6)
        self.assertEqual(result.status, "no_record")

    def test_overdue_by_km(self):
        v = self._vehicle(mileage=10000, condition="Normal", last_mileage=1000, last_date="2026-01-01")
        result = predict_service(v, "Oil Change", 5000, 6)
        self.assertEqual(result.status, "overdue")

    def test_ok_when_well_within_interval(self):
        recent = datetime.now().strftime("%Y-%m-%d")
        v = self._vehicle(mileage=1000, condition="Normal", last_mileage=900, last_date=recent)
        result = predict_service(v, "Oil Change", 5000, 6)
        self.assertEqual(result.status, "ok")

    def test_harsh_condition_tightens_km_interval(self):
        recent = datetime.now().strftime("%Y-%m-%d")
        # 4000 km since last service; harsh interval = 5000 * 0.8 = 4000 -> overdue
        v = self._vehicle(mileage=4500, condition="Harsh", last_mileage=500, last_date=recent)
        result = predict_service(v, "Oil Change", 5000, 6)
        self.assertEqual(result.status, "overdue")

    def test_light_condition_stretches_km_interval(self):
        recent = datetime.now().strftime("%Y-%m-%d")
        # 4600 km since last service; light interval = 5000 * 1.15 = 5750 -> not overdue
        v = self._vehicle(mileage=5100, condition="Light", last_mileage=500, last_date=recent)
        result = predict_service(v, "Oil Change", 5000, 6)
        self.assertNotEqual(result.status, "overdue")

    def test_due_soon_near_km_threshold(self):
        recent = datetime.now().strftime("%Y-%m-%d")
        # 4300 km since last service out of 5000 -> within 15% -> due_soon
        v = self._vehicle(mileage=4800, condition="Normal", last_mileage=500, last_date=recent)
        result = predict_service(v, "Oil Change", 5000, 6)
        self.assertEqual(result.status, "due_soon")


class TestEstimateDailyMileage(unittest.TestCase):
    def test_none_with_fewer_than_two_points(self):
        v = Vehicle(name="Test")
        v.mileage_log.append(MileageSnapshot(mileage=1000, date="2026-01-01"))
        self.assertIsNone(estimate_daily_mileage(v))

    def test_computes_rate_between_two_points(self):
        v = Vehicle(name="Test")
        v.mileage_log.append(MileageSnapshot(mileage=1000, date="2026-01-01"))
        v.mileage_log.append(MileageSnapshot(mileage=1100, date="2026-01-11"))
        self.assertAlmostEqual(estimate_daily_mileage(v), 10.0)


class TestComputeStats(unittest.TestCase):
    def test_total_spent_and_counts(self):
        v = Vehicle(name="Test")
        v.service_log.append(ServiceRecord(service="Oil Change", mileage=1000, date="2026-01-01", cost=50))
        v.service_log.append(ServiceRecord(service="Oil Change", mileage=6000, date="2026-06-01", cost=55))
        v.service_log.append(ServiceRecord(service="Tire Rotation", mileage=1000, date="2026-01-01", cost=20))
        stats = compute_stats(v)
        self.assertEqual(stats["total_services"], 3)
        self.assertEqual(stats["total_spent"], 125)
        self.assertEqual(stats["most_common_service"], "Oil Change")


if __name__ == "__main__":
    unittest.main()
