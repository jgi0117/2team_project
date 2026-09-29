"""수치 의미, 시점 누수, 결측과 모델 응답 검증 회귀 테스트."""

import json
import unittest

import numpy as np
import pandas as pd

from src.F03 import build_summary
from src.F06 import analyze_equipment
from src.ai_summary import summarize
from src.ai_summary.qwen import _parse_selection


def predictions():
    return pd.DataFrame([
        dict(machineID=1, component="comp1", as_of="2015-10-01", horizon_days=7,
             failure_probability=.9, model_version="fp_v1", calibrated=False),
        dict(machineID=2, component="comp2", as_of="2015-10-01", horizon_days=7,
             failure_probability=.6, model_version="fp_v1", calibrated=False),
    ])


def telemetry():
    times = pd.date_range("2015-10-01", periods=73, freq="h")
    return pd.DataFrame({"machineID": 1, "datetime": times,
                         **{sensor: [10.] * 72 + [20.] for sensor in
                            ["volt", "rotate", "pressure", "vibration"]}})


def saved_if():
    return pd.DataFrame([dict(machineID=1, as_of="2015-10-04", anomaly_score=.7,
                              threshold=.5, is_anomaly=1)])


class FakeSelector:
    model_id = "test"

    def __init__(self, result):
        self.result = result

    def select(self, task, evidence, limit):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class F03Tests(unittest.TestCase):
    def run_summary(self, data=None, **kwargs):
        return build_summary(predictions() if data is None else data, "2015-10-02",
                             horizon_days=7, model_version="fp_v1", **kwargs)

    def test_uncalibrated_score_is_not_percentage(self):
        result = self.run_summary()
        self.assertIn("미보정", result["text"])
        self.assertNotIn("%", result["text"])
        self.assertEqual(result["selected"]["machineID"], 1)
        self.assertIn("정보 미제공", result["text"])

    def test_calibrated_and_missing_flag(self):
        data = predictions()
        data["calibrated"] = "true"
        self.assertIn("90.0%", self.run_summary(data)["text"])
        self.assertNotIn("%", self.run_summary(data.drop(columns="calibrated"))["text"])

    def test_future_predictions_and_plans_excluded(self):
        future = predictions().assign(as_of="2015-11-01", failure_probability=1.)
        plan = pd.DataFrame([dict(machineID=2, component="comp2", as_of="2015-11-01",
                                  response_margin_days=-5)])
        result = self.run_summary(pd.concat([predictions(), future]), maintenance_plan=plan)
        self.assertEqual(result["selected"]["machineID"], 1)
        self.assertIsNone(result["selected"]["plan_as_of"])

    def test_negative_margin_precedes_score(self):
        plan = pd.DataFrame([dict(machineID=2, component="comp2", as_of="2015-10-01",
                                  response_margin_days=-2, available_stock=0,
                                  order_by_at="2015-09-30")])
        result = self.run_summary(maintenance_plan=plan)
        self.assertEqual(result["selected"]["machineID"], 2)
        self.assertEqual(result["selected"]["priority_reason"], "negative_margin")
        self.assertIn("-2일", result["text"])

    def test_latest_unknown_is_not_replaced_with_old_value(self):
        data = pd.concat([predictions(), predictions().assign(as_of="2015-10-02", failure_probability=np.nan)])
        result = self.run_summary(data)
        self.assertEqual(result["status"], "no_data")
        self.assertEqual(result["missing_scores"], 2)

    def test_horizon_and_model_selection(self):
        other = predictions().assign(horizon_days=30, failure_probability=1.)
        model = predictions().assign(model_version="other", failure_probability=1.)
        result = self.run_summary(pd.concat([predictions(), other, model]))
        self.assertEqual(result["selected"]["failure_probability"], .9)

    def test_reject_duplicate_and_invalid_scores(self):
        for data in [pd.concat([predictions(), predictions()]), predictions().assign(failure_probability=1.1)]:
            with self.assertRaises(ValueError):
                self.run_summary(data)

    def test_reject_mixed_calibration(self):
        data = predictions()
        data.loc[0, "calibrated"] = True
        with self.assertRaises(ValueError):
            self.run_summary(data)

    def test_invalid_and_timezone_aware_keys_rejected(self):
        for date in ["NaT", "2015-10-01T00:00:00+09:00"]:
            with self.assertRaises(ValueError):
                self.run_summary(predictions().assign(as_of=date))


class F06Tests(unittest.TestCase):
    def analyze(self, data=None, **kwargs):
        return analyze_equipment(telemetry() if data is None else data, 1, "2015-10-04", **kwargs)

    def test_constant_baseline_current_excluded(self):
        result = self.analyze(if_predictions=saved_if())
        self.assertEqual(result["status"], "ok")
        for sensor in result["sensors"]:
            self.assertEqual(sensor["mean"], 10.)
            self.assertEqual(sensor["std"], 0.)
            self.assertTrue(sensor["three_sigma"]["is_anomaly"])
            self.assertTrue(sensor["iqr"]["is_anomaly"])
        self.assertNotIn("text", result)
        self.assertNotIn("backend", result)
        json.dumps(result, allow_nan=False)

    def test_future_and_other_machine_excluded(self):
        source = telemetry()
        extra = source.iloc[[-1]].assign(datetime=pd.Timestamp("2015-10-05"), volt=1e8)
        other = source.assign(machineID=2, volt=1e8)
        baseline = self.analyze()
        result = self.analyze(pd.concat([source, extra, other]))
        self.assertEqual(result, baseline)

    def test_missing_hour_does_not_mean_normal(self):
        result = self.analyze(telemetry().drop(index=10))
        self.assertEqual(result["status"], "partial")
        self.assertTrue(all(s["three_sigma"] is None for s in result["sensors"]))
        self.assertEqual(result["sensors"][0]["status"], "insufficient_history")

    def test_missing_sensor_and_zero_variance(self):
        data = telemetry()
        data.loc[72, "volt"] = np.nan
        data.loc[72, "rotate"] = 10.
        result = self.analyze(data)
        self.assertEqual(result["sensors"][0]["status"], "missing_current")
        self.assertFalse(result["sensors"][1]["three_sigma"]["is_anomaly"])
        json.dumps(result, allow_nan=False)

    def test_if_must_match_exact_observation(self):
        result = self.analyze(if_predictions=saved_if().assign(as_of="2015-10-03"))
        self.assertIsNone(result["if"])
        self.assertIsNone(result["timeline"][-1]["if"])

    def test_if_flags_and_sensor_values_validated(self):
        for scores in [saved_if().assign(is_anomaly=0), saved_if().assign(volt=99.)]:
            with self.assertRaises(ValueError):
                self.analyze(if_predictions=scores)

    def test_nonconstant_numerical_bounds(self):
        data = telemetry()
        data["volt"] = np.arange(73, dtype=float)
        sensor = self.analyze(data)["sensors"][0]
        history = np.arange(72, dtype=float)
        self.assertAlmostEqual(sensor["three_sigma"]["upper"], history.mean() + 3 * history.std())
        self.assertAlmostEqual(sensor["iqr"]["upper"], 53.25 + 1.5 * 35.5)

    def test_no_data_and_staleness(self):
        result = self.analyze(telemetry().assign(machineID=2))
        self.assertEqual(result["status"], "no_data")
        result = analyze_equipment(telemetry(), 1, "2015-10-05")
        self.assertEqual(result["observation_age_hours"], 24)

    def test_missing_baseline_value_and_threshold_equality(self):
        data = telemetry()
        data.loc[10, "volt"] = np.nan
        result = self.analyze(data, if_predictions=saved_if().assign(anomaly_score=.5, is_anomaly=0))
        self.assertIsNone(result["sensors"][0]["three_sigma"])
        self.assertFalse(result["if"]["is_anomaly"])

    def test_hourly_timeline_uses_only_previous_window_and_if_per_hour(self):
        hours = pd.date_range("2015-10-01", periods=7, freq="h")
        data = pd.DataFrame({"machineID": 1, "datetime": hours,
                             **{sensor: [10., 10., 10., 30., 10., 10., 10.]
                                for sensor in ("volt", "rotate", "pressure", "vibration")}})
        scores = pd.DataFrame({"machineID": [1, 1], "as_of": [hours[3], hours[4]],
                               "anomaly_score": [.8, .2], "threshold": [.5, .5],
                               "is_anomaly": [True, False]})
        result = analyze_equipment(data, 1, hours[4], window_hours=2,
                                   if_predictions=scores)
        timeline = result["timeline"]
        self.assertEqual([point["as_of"] for point in timeline],
                         [hour.isoformat() for hour in hours[2:5]])
        self.assertTrue(timeline[1]["sensors"]["volt"]["iqr"]["is_anomaly"])
        self.assertTrue(timeline[1]["sensors"]["volt"]["three_sigma"]["is_anomaly"])
        self.assertFalse(timeline[2]["sensors"]["volt"]["three_sigma"]["is_anomaly"])
        self.assertTrue(timeline[1]["if"]["is_anomaly"])
        self.assertFalse(timeline[2]["if"]["is_anomaly"])
        self.assertIsNone(timeline[0]["if"])
        self.assertEqual(result["observed_at"], hours[4].isoformat())


class SummaryTests(unittest.TestCase):
    def test_qwen_json_code_block(self):
        self.assertEqual(
            _parse_selection('```json\n{"evidence_ids": ["planning_missing"]}\n```'),
            {"evidence_ids": ["planning_missing"]},
        )
        with self.assertRaises(ValueError):
            _parse_selection('Explanation\n```json\n{"evidence_ids": []}\n```')

    def test_selection_cannot_change_facts(self):
        result = summarize("필수 판단", {"e1": "값 0.7", "e2": "값 0.2"},
                           task="test", selector=FakeSelector(["e2"]))
        self.assertEqual(result["text"], "필수 판단; 값 0.2.")
        self.assertEqual(result["backend"], "qwen")

    def test_invalid_output_and_runtime_failure_fall_back(self):
        for output in [["invented"], ["e1", "e1"], [], "e1", [42], RuntimeError("failure")]:
            result = summarize("필수 판단", {"e1": "값 0.7"}, task="test", selector=FakeSelector(output))
            self.assertEqual(result["backend"], "template")
            self.assertIsNotNone(result["fallback_reason"])
            self.assertEqual(result["text"], "필수 판단; 값 0.7.")


if __name__ == "__main__":
    unittest.main()
