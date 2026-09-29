import unittest

import pandas as pd

from src.maintenance_planning.history import (
    build_inventory_daily_history,
    build_procurement_history,
)


class OperationHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.procurement = build_procurement_history()
        cls.inventory = build_inventory_daily_history()

    def test_procurement_history_explains_every_order(self):
        orders = pd.read_csv("data/operations/purchase_orders.csv")
        self.assertEqual(len(self.procurement), len(orders))
        self.assertTrue(self.procurement.order_id.is_unique)
        self.assertTrue((self.procurement.planned_order_cost > 0).all())
        self.assertTrue(self.procurement.delivery_status.isin(["open", "on_time", "delayed"]).all())
        known_stock = self.procurement.available_stock_at_order.dropna()
        self.assertTrue((known_stock >= 0).all())
        self.assertEqual(int(self.procurement.available_stock_at_order.isna().sum()), 11)

    def test_inventory_history_has_daily_component_balances(self):
        self.assertEqual(self.inventory.component.nunique(), 4)
        self.assertEqual(self.inventory.groupby("date").size().nunique(), 1)
        self.assertEqual(self.inventory.groupby("date").size().iloc[0], 4)
        self.assertTrue((self.inventory.closing_on_hand >= 0).all())
        self.assertTrue((self.inventory.available_stock >= 0).all())
        self.assertTrue((self.inventory.available_stock <= self.inventory.closing_on_hand).all())

    def test_history_contains_explainable_events_and_shortages(self):
        self.assertTrue(self.inventory.daily_event_summary.str.contains("입고").any())
        self.assertTrue(self.inventory.daily_event_summary.str.contains("출고").any())
        self.assertTrue((self.inventory.stock_gap > 0).any())
        self.assertTrue((self.procurement.receipt_delay_days > 0).any())


if __name__ == "__main__":
    unittest.main()
