"""Read only operational facts known by the requested decision time."""
from collections import defaultdict
import csv
from datetime import datetime
import json
from pathlib import Path

DEFAULT_DIR=Path(__file__).resolve().parents[2]/'data/operations'


def snapshot(as_of, directory=DEFAULT_DIR):
    directory=Path(directory)
    cutoff=datetime.fromisoformat(as_of) if isinstance(as_of,str) else as_of
    report=json.loads((directory/'generation_report.json').read_text(encoding='utf-8'))
    if not datetime.fromisoformat(report['simulation_start'])<=cutoff<=datetime.fromisoformat(report['as_of']):
        raise ValueError('Requested time is outside generated operations coverage')
    def read(name):
        with (directory/name).open(encoding='utf-8-sig',newline='') as stream:
            return list(csv.DictReader(stream))
    def known(value):return bool(value) and datetime.fromisoformat(value)<=cutoff
    movement_by_lot=defaultdict(list)
    for row in read('inventory_movements.csv'):
        if known(row['occurred_at']):movement_by_lot[row['lot_id']].append(row)
    lots=[]
    for row in read('inventory_lots.csv'):
        history=movement_by_lot[row['lot_id']]
        if not known(row['received_at']) or not history:continue
        row['quantity_on_hand']=sum(int(m['quantity_delta']) for m in history)
        row['quantity_reserved']=0  # This baseline policy consumes immediately, no advance reservation.
        row['quality_status']=history[-1]['quality_status']
        row['as_of']=cutoff.isoformat(sep=' ',timespec='seconds')
        row['quantity_available']=row['quantity_on_hand'] if (row['quality_status']=='available'
            and known(row['ready_at']) and cutoff<=datetime.fromisoformat(row['use_by_at'])) else 0
        lots.append(row)
    orders=[]
    for row in read('purchase_orders.csv'):
        if not known(row['ordered_at']):continue
        if known(row['actual_receipt_at']):row['status']='received'
        else:
            row['actual_receipt_at']=''
            row['status']='overdue' if datetime.fromisoformat(row['expected_receipt_at'])<cutoff else 'ordered'
        orders.append(row)
    records=[]
    for row in read('maintenance_records.csv'):
        if not known(row['source_event_at']):continue
        if not known(row['completed_at']):
            row.update(completed_at='',used_lot_id='',quantity_used='0',result='waiting_for_stock')
        records.append(row)
    return {'as_of':cutoff.isoformat(sep=' ',timespec='seconds'),
        'part_master':read('part_master.csv'),'costs':read('costs.csv'),
        'inventory_lots':lots,'purchase_orders':orders,'maintenance_records':records}
