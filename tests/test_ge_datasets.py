import unittest

import pandas as pd

from src.ge_db.connection import ROOT
from src.ge_db.datasets import read_csv
from src.ui.settings import DEFAULTS, merged


class DatasetTests(unittest.TestCase):
    def test_database_frames_preserve_ge_contract(self):
        for relative in ["data/processed/predictions.csv", "data/operations/inventory_lots.csv",
                         "data/operations/supplier_terms.csv", "data/processed/risk_curve.csv",
                         "outputs/model3/predictions.csv"]:
            with self.subTest(source=relative):
                path = ROOT / relative
                actual = read_csv(path)
                self.assertIsNotNone(actual, "Expected an imported MySQL dataset, not CSV fallback")
                pd.testing.assert_frame_equal(actual, pd.read_csv(path), check_exact=True)

    def test_if_column_selection_and_dates(self):
        path = ROOT / "outputs/model3/predictions.csv"
        options = {"usecols": ["machineID", "as_of", "anomaly_score"], "parse_dates": ["as_of"]}
        pd.testing.assert_frame_equal(read_csv(path, **options), pd.read_csv(path, **options), check_exact=True)

    def test_old_or_invalid_browser_settings_use_defaults(self):
        self.assertEqual(merged({"stats_horizon": "bad", "main_if_threshold": 999}), DEFAULTS)
        self.assertEqual(merged([]), DEFAULTS)


if __name__ == "__main__":
    unittest.main()
