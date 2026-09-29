import unittest

import pandas as pd

from src.maintenance_planning import (
    build_maintenance_plan,
    cost_analysis,
    dashboard_overview,
    response_history,
    snapshot,
    supplier_detail,
)
from src.F01 import build_detection
from src.F02 import build_plan, build_procurement
from src.F04 import build_tracking
from src.F07 import analyze_order
from src.F08 import get_history, get_supplier


class PlanningFeatureTests(unittest.TestCase):
    def test_all_feature_packages_expose_public_services(self):
        self.assertEqual(build_detection("2015-12-21")["feature"], "F01")
        self.assertEqual(len(build_plan("2015-12-21")), 400)
        self.assertEqual(build_procurement("2015-12-21")["feature"], "F02")
        self.assertEqual(build_tracking("2015-12-21")["feature"], "F04")
        self.assertEqual(analyze_order(1, "comp1", "2015-12-21")["feature"], "F07")
        self.assertEqual(get_supplier("comp1", "2015-12-21")["feature"], "F08")
        self.assertTrue((get_history(1, "2015-12-21").machineID == 1).all())

    def test_snapshot_hides_future_actual_results(self):
        state = snapshot("2015-04-01 06:00:00")
        self.assertTrue(all(pd.Timestamp(row["planned_at"]) <= pd.Timestamp(state["as_of"])
                            for row in state["maintenance_records"]))
        future_receipts = [row for row in state["purchase_orders"]
                           if row["actual_receipt_at"] is None]
        self.assertTrue(future_receipts)
        self.assertTrue(all(row["status_as_of"] == "open" for row in future_receipts))

    def test_f02_plan_has_all_machine_components_and_deadlines(self):
        plan = build_maintenance_plan("2015-12-21")
        self.assertEqual(len(plan), 400)
        self.assertEqual(plan[["machineID", "component"]].drop_duplicates().shape[0], 400)
        self.assertTrue((plan.order_by_at <= plan.target_maintenance_at).all())
        self.assertTrue((plan.available_stock >= 0).all())

    def test_f01_f04_overview_uses_saved_results(self):
        result = dashboard_overview("2015-12-21")
        self.assertEqual(len(result["surges"]), 3)
        self.assertEqual(len(result["part_risk"]), 4)
        self.assertGreater(len(result["history"]), 0)
        self.assertEqual(result["kpis"]["prediction_rows"], 3600)
        self.assertEqual(result["kpis"]["warning_machines"], 7)
        self.assertEqual(result["warning_machine_ids"], [13, 18, 19, 24, 37, 52, 85])
        self.assertEqual(result["history"].period.iloc[0], "2015-01")
        self.assertEqual(len(result["surges"]), 3)
        self.assertEqual(result["previous_as_of"], pd.Timestamp("2015-12-20"))
        self.assertEqual([row["machineID"] for row in result["surges"]], [17, 58, 13])
        self.assertTrue(all("component" not in row for row in result["surges"]))
        self.assertTrue(all(row["horizon_days"] == 7 for row in result["surges"]))
        self.assertIn("replacement_due", result["kpis"])
        self.assertGreaterEqual(result["kpis"]["unacted_loss"], result["kpis"]["action_savings"])
        self.assertEqual(result["kpis"]["cost_scope"], 0)
        self.assertEqual(result["order_schedule"].date.dt.day.tolist(), [21, 23, 29])

    def test_f02_inventory_risk_uses_high_risk_candidates_not_all_machines(self):
        result = dashboard_overview("2015-10-05")
        self.assertEqual(result["part_risk"].risk_machines.tolist(), [5, 5, 5, 5])
        comp1 = result["part_risk"].set_index("component").loc["comp1"]
        self.assertEqual(int(comp1.demand_shortage), 1)
        self.assertEqual(int(comp1.urgent), 1)
        self.assertEqual(len(result["priority_equipment"]), 10)
        self.assertEqual(result["kpis"]["order_due"], 1)
        self.assertEqual(result["action_schedule"].date.dt.day.tolist(), [5, 7, 13, 21, 29])

    def test_f07_cost_curve_and_scenarios_are_consistent(self):
        result = cost_analysis(1, "comp2", "2015-12-21")
        self.assertEqual(sorted(result["scenarios"]), [0, 7, 14])
        self.assertEqual(result["optimum"]["total_cost"],
                         min(row["total_cost"] for row in result["curve"]))
        self.assertGreater(result["quantity"], 0)

    def test_f08_supplier_history_and_training_flag(self):
        supplier = supplier_detail("comp1", "2015-12-21")
        self.assertNotIn("training_inclusion", supplier)
        self.assertIn("supplier", supplier["contact_email"])
        history = response_history(1, "2015-12-21")
        self.assertTrue((history.machineID == 1).all())
        self.assertNotIn("training_included", history)


if __name__ == "__main__":
    unittest.main()
