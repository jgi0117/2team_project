"""F03/F05/F06 화면이 기능 결과를 올바른 의미로 표시하는지 확인."""

import unittest
from unittest.mock import patch

from src.ui.pages import main
from src.ui.pages.detail import page as detail


class MainPanelTests(unittest.TestCase):
    def test_current_summary_keeps_only_the_actionable_cost_card(self):
        overview = main.dashboard_overview("2015-12-21")
        cards = main.make_summary_cards(overview)
        titles = [card.children[0].children for card in cards.children]
        self.assertEqual(len(titles), 5)
        self.assertIn("14일 지연 대비 절감 효과", titles)
        self.assertNotIn("미조치 시 예상 손실", titles)
        warning_hover = cards.children[0].children[2]
        self.assertEqual(len(warning_hover.children) - 1,
                         len(overview["warning_machine_ids"]))
        self.assertTrue(all(link.href.startswith("/detail?machine=")
                            for link in warning_hover.children[1:]))
        replacement_hover = cards.children[1].children[2]
        self.assertEqual(len(replacement_hover.children) - 1,
                         len(overview["replacement_due_rows"]))
        order_hover = cards.children[3].children[2]
        self.assertEqual(len(order_hover.children) - 1, len(overview["order_due_rows"]))
        self.assertIn("마감", order_hover.children[1].children)
        self.assertTrue(all(link.href.startswith("/detail?machine=")
                            for link in order_hover.children[1:]))

    def test_surge_chart_supports_hover_and_detail_click(self):
        figure = main.surge_figure(main.dashboard_overview("2015-12-21"))
        self.assertEqual(len(figure.data[0].customdata), 3)
        self.assertNotIn("클릭하여 상세 보기", figure.data[0].hovertemplate)
        self.assertTrue(all(isinstance(row[0], int) for row in figure.data[0].customdata))

    def test_calendar_marks_the_data_cutoff_as_today(self):
        calendar = main.make_calendar(main.dashboard_overview("2015-12-21"))
        today = calendar.children[1].children[20]
        self.assertIn("mn-calendar-today", today.className)
        self.assertEqual(today.to_plotly_json()["props"]["aria-current"], "date")
        self.assertIn("오늘(기준일)", [child.children for child in today.children])

    def test_calendar_shows_monthly_checks_and_actions(self):
        overview = main.dashboard_overview("2015-10-05")
        calendar = main.make_calendar(overview)
        fifth = calendar.children[1].children[4]
        seventh = calendar.children[1].children[6]
        self.assertIn("위험 설비 확인", str(fifth.to_plotly_json()))
        self.assertIn("발주 확인", str(fifth.to_plotly_json()))
        self.assertIn("입고 확인", str(seventh.to_plotly_json()))
        thirteenth = calendar.children[1].children[12]
        self.assertIn("정비 예정", str(thirteenth.to_plotly_json()))
        self.assertIn("10건", calendar.children[2].children)

    def test_f03_panel_uses_summary_and_links_selected_machine(self):
        summary = {"text": "설비 13의 comp2를 우선 확인하세요; 대응 여유 2일; 가용재고 0개.",
                   "selected": {"machineID": 13, "component": "comp2"},
                   "prediction_as_of": "2015-12-21T00:00:00", "horizon_days": 7}
        with patch.object(main, "f03_summary", return_value=summary):
            rendered = main.create_main_layout()
        panel = next(child for child in rendered.children if getattr(child, "id", None) == "mn-f03")
        self.assertEqual(panel.id, "mn-f03")
        self.assertEqual(panel.children[1].children,
                         "설비 13의 comp2를 우선 확인하세요. 근거: 대응 여유 2일 · 가용재고 0개.")
        self.assertEqual(panel.children[2].children[-1].href, "/detail?machine=13")
        self.assertNotIn("향후 7일", str(panel.children[2].to_plotly_json()))
        self.assertIn("2015-10-05", rendered.children[0].children[1].children)
        self.assertEqual(main.layout.children[0].children, None)

    def test_f03_error_is_explicit(self):
        with patch.object(main, "f03_summary", side_effect=OSError("missing")):
            panel = main.make_f03_panel()
        self.assertIn("불러오지 못했습니다", panel.children[1].children)
        self.assertFalse(panel.children[2].children)


class DetailPanelTests(unittest.TestCase):
    def test_component_hotspot_has_no_empty_risk_hover(self):
        components = detail.hotspot("comp1")
        self.assertEqual(len(components), 2)
        self.assertNotIn("hs-pop-comp1", str([item.to_plotly_json() for item in components]))

    def test_history_is_paginated_ten_rows_at_a_time(self):
        first, page, total_pages, total = detail._history_table(1, [], page=0)
        self.assertGreater(total, 10)
        self.assertEqual(page, 0)
        self.assertGreater(total_pages, 1)
        self.assertEqual(len(first.children[1].children), 10)
        second, page, _, _ = detail._history_table(1, [], page=1)
        self.assertEqual(page, 1)
        self.assertNotEqual(str(first.to_plotly_json()), str(second.to_plotly_json()))
        self.assertNotIn("학습 반영", str(first.to_plotly_json()))

    def test_f05_summary_shows_current_condition_instead_of_maximum_component(self):
        diagnosis = {"status": "ok", "highest_component": "comp2",
                     "highest_score": .5234, "calibrated": False,
                     "horizon_days": 28, "text": "현재 정상 범위입니다",
                     "condition_status": "normal", "risk_percentile": .45,
                     "anomaly_detected": False}
        with patch.object(detail, "f05_diagnosis", return_value=diagnosis) as build:
            rendered = detail.show_machine(1)
        build.assert_called_once_with(1, detail.AS_OF)
        self.assertEqual(rendered[-3].children, "현재 정상")
        self.assertEqual(rendered[-3].className, "diagnosis-normal")
        self.assertIn("고장예측·현재 센서 종합", rendered[-2])
        self.assertIn("정상 범위", rendered[-1])
        self.assertTrue(all("%" not in score for score in rendered[2:6]))

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
