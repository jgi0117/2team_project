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

    def test_f10_predictions_start_on_shared_october_cutoff(self):
        self.assertEqual(self.anomalies.as_of.min(), pd.Timestamp("2015-10-05"))
        _, meta = build_anomaly(self.anomalies, "2015-10-05",
                                machines=list(range(1, 101)))
        self.assertEqual(meta["observed_at"], pd.Timestamp("2015-10-05"))
        self.assertEqual(meta["cells"], 100)

    def test_integrated_statistics_page_contains_both_maps(self):
        from src.ui.pages.statistics.page import create_statistics_page

        page = create_statistics_page()
        sections = page.children[1].children[1:]
        self.assertEqual([section.id for section in sections],
                         ["stats-f10-content", "stats-f09-content"])
        self.assertIn("f10-heatmap", str(sections[0].to_plotly_json()))
        self.assertIn("f09-heatmap", str(sections[1].to_plotly_json()))
        risk_panel = str(sections[1].to_plotly_json())
        self.assertIn("f09-horizon", risk_panel)
        self.assertIn("향후 7일 설비 위험 분포", risk_panel)
        self.assertIn("즉시 대응용", risk_panel)
        self.assertIn("7일", risk_panel)
        self.assertIn("14일", risk_panel)
        self.assertIn("42일", risk_panel)
        self.assertNotIn("28일", risk_panel)

    def test_statistics_horizon_can_change_to_long_term(self):
        from src.F09.dashboard import update_horizon

        figure, title, meaning = update_horizon(42)
        self.assertTrue(figure.data)
        self.assertEqual(title, "향후 42일 설비 위험 분포")
        self.assertIn("장기 조달계획 참고용", meaning)


if __name__ == "__main__":
    unittest.main()
