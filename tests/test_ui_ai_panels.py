"""F03/F05/F06 화면이 기능 결과를 올바른 의미로 표시하는지 확인."""

import unittest
from unittest.mock import patch

from src.ui.pages import main
from src.ui.pages.detail import page as detail


class MainPanelTests(unittest.TestCase):
    def test_f03_panel_uses_summary_and_links_selected_machine(self):
        summary = {"text": "설비 13의 comp2 점검 우선순위를 검토하세요 (미보정 고장 위험 점수 0.521).",
                   "selected": {"machineID": 13, "component": "comp2"},
                   "prediction_as_of": "2015-12-21T00:00:00", "horizon_days": 7}
        with patch.object(main, "f03_summary", return_value=summary):
            rendered = main.create_main_layout()
        panel = rendered.children[0]
        self.assertEqual(panel.id, "mn-f03")
        self.assertEqual(panel.children[1].children, summary["text"])
        self.assertEqual(panel.children[2].children[-1].href, "/detail?machine=13")
        self.assertIn("2015-12-21", panel.children[2].children[0].children)
        self.assertEqual(main.layout.children[0].children, None)

    def test_f03_error_is_explicit(self):
        with patch.object(main, "f03_summary", side_effect=OSError("missing")):
            panel = main.make_f03_panel()
        self.assertIn("불러오지 못했습니다", panel.children[1].children)
        self.assertFalse(panel.children[2].children)


class DetailPanelTests(unittest.TestCase):
    def test_f05_summary_uses_same_horizon_score_without_percent(self):
        diagnosis = {"status": "ok", "highest_component": "comp2",
                     "highest_score": .5234, "calibrated": False,
                     "horizon_days": 28, "text": "Qwen 종합진단 근거"}
        with patch.object(detail, "f05_diagnosis", return_value=diagnosis) as build:
            rendered = detail.show_machine(1)
        build.assert_called_once_with(1, detail.AS_OF)
        # 요약 숫자는 채택 부품 중 위험이 가장 먼저 오르는 시점(D-day), 확률 표기 없음
        self.assertTrue(rendered[-3].startswith("D-") or rendered[-3] == "안정")
        self.assertNotIn("comp2", rendered[-2])
        self.assertEqual(rendered[-1], diagnosis["text"])
        self.assertTrue(all("%" not in str(score) for score in rendered[2:6]))

    def test_f06_sensor_change_and_if_score_are_not_probabilities(self):
        sensor_rows = [
            {"sensor": name, "value": 20. if name == "volt" else 10.,
             "three_sigma": {"lower": 8., "upper": 12., "is_anomaly": name == "volt"},
             "iqr": {"lower": 9., "upper": 11., "is_anomaly": name == "volt"}}
            for name in detail.SENSOR_NAMES
        ]
        result = {"sensors": sensor_rows,
                  "if": {"anomaly_score": .7, "threshold": .5, "is_anomaly": True},
                  "observed_at": "2015-12-21T00:00:00", "observation_age_hours": 0,
                  "timeline": [
                      {"as_of": "2015-12-20T23:00:00",
                       "sensors": {row["sensor"]: row for row in sensor_rows},
                       "if": {"anomaly_score": .4, "threshold": .5, "is_anomaly": False}},
                      {"as_of": "2015-12-21T00:00:00",
                       "sensors": {row["sensor"]: row for row in sensor_rows},
                       "if": {"anomaly_score": .7, "threshold": .5, "is_anomaly": True}},
                  ]}
        with patch.object(detail, "f06_analysis", return_value=result) as analysis:
            figure, card, table, summary, observed = detail.show_f06(1, "volt")
        analysis.assert_called_once_with(1, detail.AS_OF)
        self.assertEqual(figure.data[0].mode, "lines+markers")
        self.assertEqual(figure.data[0].y, (20., 20.))
        self.assertIn("IQR UDL", [trace.name for trace in figure.data])
        self.assertIn("IQR LDL", [trace.name for trace in figure.data])
        self.assertIn("3σ UCL", [trace.name for trace in figure.data])
        self.assertIn("3σ LCL", [trace.name for trace in figure.data])
        self.assertEqual(figure.data[7].name, "IF 점수")
        self.assertEqual(figure.data[7].y, (.4, .7))
        self.assertEqual(figure.data[-1].name, "IF 이상")
        self.assertEqual(figure.data[-1].x, ("2015-12-21T00:00:00",))
        self.assertIn("IF 1건", summary.children)
        self.assertIn("0.700", str(card.to_plotly_json()))
        self.assertIn("확률 아님", str(card.to_plotly_json()))
        self.assertEqual(len(table.children[1].children), 4)
        self.assertIn("2015-12-21", observed)

    def test_f06_zero_alerts_are_explicit(self):
        normal = {"sensors": {"vibration": {"iqr": {"is_anomaly": False},
                                              "three_sigma": {"is_anomaly": False}}},
                  "if": {"is_anomaly": False}}
        result = {"window_hours": 72, "timeline": [normal, normal]}
        summary = detail.f06_alert_summary(result, "vibration")
        self.assertIn("IQR 0건", summary.children)
        self.assertIn("3σ 0건", summary.children)
        self.assertIn("IF 0건", summary.children)
        self.assertIn("이상 없음", summary.children)


if __name__ == "__main__":
    unittest.main()
