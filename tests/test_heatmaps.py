import unittest

import pandas as pd

from src.F09 import build_heatmap, load_predictions
from src.F10.heatmap import build_heatmap as build_anomaly, load_predictions as load_anomaly


class HeatmapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_predictions()
        cls.anomalies = load_anomaly()

    def test_f09_has_one_maximum_score_per_machine(self):
        figure, meta = build_heatmap(self.data, "2015-12-21", 28, "fp_v1")
        self.assertEqual((meta["cells"], meta["component_cells"]), (100, 400))
        labels = list(figure.data[2].text)
        self.assertEqual(labels, [f"{i:03d}" for i in range(1, 101)])
        scores = [v for row in figure.data[1].z for v in row]
        expected = self.data.query("as_of == '2015-12-21' and horizon_days == 28 and model_version == 'fp_v1'").groupby("machineID").failure_probability.max()
        self.assertEqual(scores, expected.tolist())
        self.assertEqual((figure.layout.coloraxis.cmin, figure.layout.coloraxis.cmax), (0, 1))

    def test_missing_component_does_not_understate_machine_risk(self):
        data = self.data.loc[~(self.data.machineID.eq(1) & self.data.component.eq("comp1"))]
        figure, meta = build_heatmap(data, "2015-12-21", 28, "fp_v1")
        self.assertIsNone(figure.data[1].z[0][0])
        self.assertEqual(meta["cells"], 99)
        self.assertEqual(figure.data[2].text[0], "001")

    def test_f10_uses_saved_if_score_at_shared_cutoff(self):
        figure, meta = build_anomaly(self.anomalies, "2015-12-21", machines=list(range(1, 101)))
        self.assertEqual(meta["cells"], 100)
        self.assertEqual(meta["observed_at"], pd.Timestamp("2015-12-21"))
        expected = self.anomalies.loc[self.anomalies.as_of.eq(meta["observed_at"])].sort_values("machineID")
        self.assertEqual([v for row in figure.data[1].z for v in row], expected.anomaly_score.tolist())
        # A missing machine at the cutoff must not silently reuse an earlier value.
        data = self.anomalies.loc[~(self.anomalies.machineID.eq(1) & self.anomalies.as_of.eq(meta["observed_at"]))]
        figure, meta = build_anomaly(data, "2015-12-21", machines=list(range(1, 101)))
        self.assertIsNone(figure.data[1].z[0][0])
        self.assertEqual(meta["cells"], 99)

    def test_page_contains_both_maps_without_controls(self):
        from src.UI.app import app

        response = app.server.test_client().get("/_dash-layout")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("f09-heatmap", body)
        self.assertIn("f10-heatmap", body)
        self.assertNotIn("Dropdown", body)
        self.assertNotIn("Slider", body)
        self.assertEqual(app.callback_map, {})


if __name__ == "__main__":
    unittest.main()
