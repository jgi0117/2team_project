"""설비 종합진단의 비교 기간과 점수 해석을 확인한다."""

import unittest

import pandas as pd

from src.F05 import build_diagnosis


def predictions():
    return pd.DataFrame([
        dict(machineID=1, component=part, as_of="2015-10-01", horizon_days=28,
             failure_probability=score, model_version="fp_v1", calibrated=False)
        for part, score in (("comp1", .2), ("comp2", .7), ("comp3", .4), ("comp4", .1))
    ])


class F05Tests(unittest.TestCase):
    def diagnose(self, data=None, **kwargs):
        return build_diagnosis(predictions() if data is None else data, 1, "2015-10-01",
                               horizon_days=28, model_version="fp_v1", **kwargs)

    def test_same_horizon_and_uncalibrated_score(self):
        data = pd.concat([predictions(),
                          predictions().assign(horizon_days=7, failure_probability=1.),
                          predictions().assign(as_of="2015-10-02", failure_probability=1.)])
        anomaly = {"if": {"is_anomaly": True}, "observed_at": "2015-10-01T00:00:00",
                   "sensors": []}
        result = self.diagnose(data, anomaly=anomaly)
        self.assertEqual(result["highest_component"], "comp2")
        self.assertIn("센서 IF 경고", result["text"])
        self.assertIn("미보정", result["text"])
        self.assertNotIn("%", result["text"])
        self.assertEqual(result["sensor_observed_at"], anomaly["observed_at"])

    def test_latest_missing_is_not_replaced_with_older_score(self):
        data = pd.concat([predictions().assign(as_of="2015-09-30"),
                          predictions().assign(failure_probability=float("nan"))])
        result = self.diagnose(data)
        self.assertEqual(result["status"], "no_data")

    def test_mixed_calibration_cannot_be_ranked(self):
        data = predictions()
        data.loc[0, "calibrated"] = True
        with self.assertRaises(ValueError):
            self.diagnose(data)


if __name__ == "__main__":
    unittest.main()
