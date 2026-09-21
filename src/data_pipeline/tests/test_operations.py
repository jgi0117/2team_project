"""Inventory accounting and point-in-time leakage checks for synthetic data."""
import csv
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from src.data_pipeline.generate_operations import FIELDS, ROOT, generate
from src.maintenance_planning.operations_snapshot import snapshot


class OperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.folder=Path(cls.temp.name)/'full'
        cls.report=generate(cls.folder)
        cls.tables={}
        for filename in FIELDS:
            with (cls.folder/filename).open(encoding='utf-8',newline='') as stream:
                cls.tables[filename]=list(csv.DictReader(stream))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_reproducibility_and_committed_output(self):
        for filename in [*FIELDS,'generation_report.json']:
            expected=(self.folder/filename).read_text(encoding='utf-8')
            actual=(ROOT/'data/operations'/filename).read_text(encoding='utf-8')
            self.assertEqual(expected,actual,filename)

    def test_accounting_and_referential_integrity(self):
        lots={r['lot_id']:r for r in self.tables['inventory_lots.csv']}
        orders={r['order_id']:r for r in self.tables['purchase_orders.csv']}
        records={r['record_id']:r for r in self.tables['maintenance_records.csv']}
        with (ROOT/'data/raw/azure_pdm/PdM_machines.csv').open(encoding='utf-8-sig',newline='') as stream:
            machines={r['machineID'] for r in csv.DictReader(stream)}
        master={r['component']:r for r in self.tables['part_master.csv']}
        balances={k:0 for k in lots}
        statuses={}
        seen=set()
        issues={}
        for m in self.tables['inventory_movements.csv']:
            self.assertNotIn(m['movement_id'],seen)
            seen.add(m['movement_id'])
            lot=lots[m['lot_id']]
            self.assertEqual(lot['component'],m['component'])
            balances[m['lot_id']]+=int(m['quantity_delta'])
            self.assertGreaterEqual(balances[m['lot_id']],0)
            statuses[m['lot_id']]=m['quality_status']
            if m['movement_type']=='issue':
                self.assertNotIn(m['record_id'],issues)
                issues[m['record_id']]=m
                rec=records[m['record_id']]
                self.assertEqual(rec['used_lot_id'],m['lot_id'])
                self.assertEqual(rec['completed_at'],m['occurred_at'])
                self.assertEqual(m['quality_status'],'available')
                self.assertLessEqual(lot['ready_at'],m['occurred_at'])
                self.assertLessEqual(m['occurred_at'],lot['use_by_at'])
        for key,lot in lots.items():
            self.assertEqual(balances[key],int(lot['quantity_on_hand']))
            self.assertEqual(statuses[key],lot['quality_status'])
            self.assertLessEqual(int(lot['quantity_reserved']),balances[key])
            self.assertEqual(datetime.fromisoformat(lot['use_by_at'])-datetime.fromisoformat(lot['received_at']),
                timedelta(days=int(master[lot['component']]['shelf_life_days'])))
            if lot['order_id']:
                po=orders[lot['order_id']]
                self.assertEqual(po['component'],lot['component'])
                self.assertEqual(po['actual_receipt_at'],lot['received_at'])
                self.assertEqual(po['quantity'],lot['quantity_received'])
        for rec in records.values():
            self.assertIn(rec['machineID'],machines)
            self.assertEqual(bool(rec['completed_at']),rec['record_id'] in issues)
            if rec['completed_at']:
                self.assertLessEqual(rec['source_event_at'],rec['completed_at'])
            else:
                self.assertEqual(rec['quantity_used'],'0')
                self.assertEqual(rec['used_lot_id'],'')
        for po in orders.values():
            self.assertLess(po['ordered_at'],po['expected_receipt_at'])
            if po['actual_receipt_at']:
                self.assertLessEqual(po['expected_receipt_at'],po['actual_receipt_at'])

    def test_historical_views_equal_independent_prefix_replay(self):
        for index,cutoff in enumerate(['2015-04-01 06:00:00','2015-06-01 06:00:00','2015-10-01 06:00:00']):
            folder=Path(self.temp.name)/f'prefix-{index}'
            generate(folder,end=cutoff)
            self.assertEqual(snapshot(cutoff,self.folder),snapshot(cutoff,folder))

    def test_future_demand_is_not_needed_for_prefix(self):
        cutoff='2015-06-01 06:00:00'
        original=ROOT/'data/raw/azure_pdm/PdM_maint.csv'
        with original.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream)
            columns=reader.fieldnames
            past=[r for r in reader if r['datetime']<=cutoff]
        trimmed=Path(self.temp.name)/'past_only.csv'
        with trimmed.open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=columns)
            writer.writeheader();writer.writerows(past)
        folder=Path(self.temp.name)/'past_only'
        generate(folder,end=cutoff,raw_path=trimmed)
        self.assertEqual(snapshot(cutoff,self.folder),snapshot(cutoff,folder))

    def test_future_values_masked_and_invalid_dates_rejected(self):
        cutoff='2015-06-01 06:00:00'
        view=snapshot(cutoff,self.folder)
        for row in view['purchase_orders']:
            self.assertLessEqual(row['ordered_at'],cutoff)
            self.assertTrue(not row['actual_receipt_at'] or row['actual_receipt_at']<=cutoff)
        for row in view['maintenance_records']:
            self.assertLessEqual(row['source_event_at'],cutoff)
            self.assertTrue(not row['completed_at'] or row['completed_at']<=cutoff)
        with self.assertRaises(ValueError):snapshot('2015-03-31 06:00:00',self.folder)
        with self.assertRaises(ValueError):snapshot('2016-01-02 06:00:00',self.folder)


if __name__=='__main__':unittest.main()
