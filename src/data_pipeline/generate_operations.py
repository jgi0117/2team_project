"""Generate a reproducible, causal inventory replay. No failure labels are read.

The observed maintenance events are demand arrivals, not counterfactual sensor
truth. Simulated completion times must never replace Azure maintenance features.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import csv
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]
DAY = timedelta(days=1)
HOUR = timedelta(hours=1)
FIELDS = {
    'part_master.csv': 'component,part_name,lead_time_days,preparation_days,target_stock,shelf_life_days,shelf_life_policy,storage_constraint,value_source',
    'costs.csv': 'component,cost_type,amount,currency,unit,value_source',
    'purchase_orders.csv': 'order_id,component,ordered_at,expected_receipt_at,actual_receipt_at,quantity,status,value_source',
    'inventory_lots.csv': 'lot_id,component,received_at,quantity_on_hand,quantity_reserved,use_by_at,quality_status,value_source,order_id,quantity_received,ready_at,as_of',
    'maintenance_records.csv': 'record_id,machineID,component,planned_at,completed_at,maintenance_type,used_lot_id,quantity_used,result,value_source,source_event_at,quantity_requested',
    'inventory_movements.csv': 'movement_id,occurred_at,lot_id,component,movement_type,quantity_delta,quality_status,record_id,value_source',
}


def dt(value):
    return datetime.fromisoformat(value)


def stamp(value):
    return value.isoformat(sep=' ', timespec='seconds') if value else ''


def generate(output_dir=ROOT/'data/operations', *, end=None, raw_path=None):
    config = json.loads((ROOT/'data/operations/scenario_config.json').read_text(encoding='utf-8'))
    start, stop = dt(config['simulation_start']), dt(end or config['simulation_end'])
    if not start <= stop <= dt(config['simulation_end']):
        raise ValueError('End must fall inside the configured simulation period')
    rng = random.Random(config['seed'])
    source = 'assumption:' + config['scenario_id']
    raw_path = Path(raw_path or ROOT/'data/raw/azure_pdm/PdM_maint.csv')
    with raw_path.open(encoding='utf-8-sig', newline='') as stream:
        raw = sorted(csv.DictReader(stream), key=lambda r: (r['datetime'], int(r['machineID']), r['comp']))
    calibration = [r for r in raw if dt(config['calibration_start']) <= dt(r['datetime']) < start]
    counts = Counter(r['comp'] for r in calibration)
    calibration_days = (start-dt(config['calibration_start'])).total_seconds()/86400
    rates = {c: counts[c]/calibration_days for c in config['components']}
    demand = defaultdict(list)
    for row in raw:
        if start <= dt(row['datetime']) <= stop:
            demand[dt(row['datetime'])].append(row)
    recent = {c: deque(dt(r['datetime']) for r in calibration if r['comp'] == c) for c in rates}
    master, costs, orders, lots, records, moves = [], [], [], [], [], []
    waiting = {c: deque() for c in rates}
    had_wait = set()
    targets = {}
    for c, spec in config['components'].items():
        targets[c] = math.ceil(rates[c]*(config['review_days']+spec['safety_days']))
        master.append(dict(component=c, part_name=c+' (가상 운영조건)',
            lead_time_days=spec['lead_time_days'], preparation_days=spec['preparation_days'],
            target_stock=targets[c], shelf_life_days=spec['shelf_life_days'],
            shelf_life_policy='days_after_receipt', storage_constraint=spec['storage_constraint'], value_source=source))
        price = spec['purchase_krw']
        entries = [
            ('purchase', price, 'per_unit'),
            ('order_admin', 20000, 'per_order'),
            ('preventive_labor', spec['preventive_labor_krw'], 'per_event'),
            ('emergency_labor', spec['emergency_labor_krw'], 'per_event'),
            ('holding', round(price*0.20/365, 2), 'per_unit_day'),
            ('disposal_processing', round(price*0.01), 'per_unit'),
            ('downtime', spec['downtime_krw_per_day'], 'per_day'),
            ('expedite_surcharge', round(price*0.25), 'per_unit'),
        ]
        costs.extend(dict(component=c, cost_type=k, amount=v, currency='KRW', unit=u, value_source=source) for k,v,u in entries)

    def movement(lot, when, kind, quantity=0, record=''):
        moves.append(dict(movement_id=f'MV-{len(moves)+1:06}', occurred_at=stamp(when),
            lot_id=lot['lot_id'], component=lot['component'], movement_type=kind,
            quantity_delta=quantity, quality_status=lot['quality_status'], record_id=record, value_source=source))

    def receive(c, quantity, received, now, order_id='', opening=False):
        spec=config['components'][c]
        quarantine = not opening and rng.random() < config['quarantine_probability']
        lot=dict(lot_id=f'LOT-{len(lots)+1:05}', component=c, received_at=stamp(received),
            quantity_on_hand=quantity, quantity_reserved=0,
            use_by_at=stamp(received+DAY*spec['shelf_life_days']),
            quality_status='quarantined' if quarantine else 'available',
            value_source=source, order_id=order_id, quantity_received=quantity,
            ready_at=stamp(received+DAY*spec['preparation_days']), as_of=stamp(stop),
            _release_at=received+DAY*config['quality_release_days'] if quarantine else None)
        lots.append(lot)
        movement(lot,now,'opening' if opening else 'receipt',quantity)

    def order(c, quantity, placed, expected):
        # Delivery delay is exogenous; never conditioned on future demand/failure.
        draw=rng.random()
        delay=0 if draw<0.70 else rng.randint(1,5) if draw<0.90 else rng.randint(7,14)
        orders.append(dict(order_id=f'PO-{len(orders)+1:05}', component=c,
            ordered_at=stamp(placed), expected_receipt_at=stamp(expected), actual_receipt_at='',
            quantity=quantity, status='ordered', value_source=source,
            _due_at=expected+DAY*delay))

    for c,spec in config['components'].items():
        # Opening state is an explicit scenario assumption available at start.
        old=max(1,math.ceil(targets[c]*0.35))
        receive(c,old,start-DAY*(spec['shelf_life_days']-3),start,opening=True)
        receive(c,targets[c]-old,start-DAY*(spec['preparation_days']+2),start,opening=True)
        for offset in range(3,spec['lead_time_days'],7):
            expected=start+DAY*offset
            order(c,math.ceil(rates[c]*7),expected-DAY*spec['lead_time_days'],expected)

    now=start
    while now<=stop:
        for po in orders:
            if not po['actual_receipt_at'] and po['_due_at']<=now:
                po['actual_receipt_at']=stamp(now)
                po['status']='received'
                receive(po['component'],po['quantity'],now,now,po['order_id'])
        for lot in lots:
            deadline=dt(lot['use_by_at'])
            if now>deadline and lot['quality_status']!='expired':
                lot['quality_status']='expired'
                movement(lot,now,'expiry')
            if lot['quality_status']=='quarantined' and lot['_release_at']<=now:
                lot['quality_status']='available'
                movement(lot,now,'quality_release')
            if now>=deadline+DAY*config['expired_disposal_days'] and lot['quantity_on_hand']:
                quantity=lot['quantity_on_hand']
                lot['quantity_on_hand']=0
                movement(lot,now,'disposal',-quantity)
        for event in demand[now]:
            c=event['comp']
            rec=dict(record_id=f'MR-{len(records)+1:05}', machineID=event['machineID'],component=c,
                planned_at=stamp(now), completed_at='',maintenance_type='observed_replacement_demand',
                used_lot_id='',quantity_used=0,result='waiting_for_stock',
                value_source=source+';demand=PdM_maint.csv',source_event_at=stamp(now),quantity_requested=1)
            records.append(rec)
            waiting[c].append(rec)
            recent[c].append(now)
        for c in rates:
            valid=sorted((l for l in lots if l['component']==c and l['quantity_on_hand']>0
                and l['quality_status']=='available' and dt(l['ready_at'])<=now<=dt(l['use_by_at'])),key=lambda l:(l['use_by_at'],l['lot_id']))
            for lot in valid:
                while lot['quantity_on_hand'] and waiting[c]:
                    rec=waiting[c].popleft()
                    lot['quantity_on_hand']-=1
                    rec.update(completed_at=stamp(now),used_lot_id=lot['lot_id'],quantity_used=1,result='completed')
                    movement(lot,now,'issue',-1,rec['record_id'])
            had_wait.update(r['record_id'] for r in waiting[c])
        if (now-start).total_seconds() % (86400*config['review_days'])==0:
            for c,spec in config['components'].items():
                window_start=now-DAY*config['demand_window_days']
                while recent[c] and recent[c][0]<window_start:
                    recent[c].popleft()
                rate=len(recent[c])/config['demand_window_days']
                on_hand=sum(l['quantity_on_hand'] for l in lots if l['component']==c
                    and l['quality_status']=='available' and now<=dt(l['use_by_at']))
                on_order=sum(p['quantity'] for p in orders if p['component']==c and not p['actual_receipt_at'])
                position=on_hand+on_order-len(waiting[c])
                desired=math.ceil(rate*(spec['lead_time_days']+spec['preparation_days']+config['review_days']+spec['safety_days']))
                quantity=max(0,desired-position)
                if quantity:
                    order(c,quantity,now,now+DAY*spec['lead_time_days'])
        now+=HOUR
    for po in orders:
        if not po['actual_receipt_at'] and dt(po['expected_receipt_at'])<stop:
            po['status']='overdue'
    tables={'part_master.csv':master,'costs.csv':costs,'purchase_orders.csv':orders,
        'inventory_lots.csv':lots,'maintenance_records.csv':records,'inventory_movements.csv':moves}
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=True)
    for filename,rows in tables.items():
        with (output_dir/filename).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=FIELDS[filename].split(','),extrasaction='ignore',lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
    summary=dict(scenario_id=config['scenario_id'],seed=config['seed'],
        calibration_start=config['calibration_start'],simulation_start=stamp(start),as_of=stamp(stop),
        calibration_counts=dict(counts),calibration_days=calibration_days,
        calibration_daily_demand=rates,rows={k:len(v) for k,v in tables.items()},
        demand_source_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        output_sha256={k:hashlib.sha256((output_dir/k).read_bytes()).hexdigest() for k in tables},
        component_summary={})
    for c in rates:
        rs=[r for r in records if r['component']==c]
        delivered=[p for p in orders if p['component']==c and p['actual_receipt_at']]
        summary['component_summary'][c]=dict(target_stock=targets[c],demand=len(rs),
            completed=sum(bool(r['completed_at']) for r in rs),
            ever_waited=sum(r['record_id'] in had_wait for r in rs),
            pending=sum(not r['completed_at'] for r in rs),
            late_deliveries=sum(p['actual_receipt_at']>p['expected_receipt_at'] for p in delivered),
            deliveries=len(delivered),
            disposed_units=-sum(m['quantity_delta'] for m in moves if m['component']==c and m['movement_type']=='disposal'))
    (output_dir/'generation_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'data/operations')
    parser.add_argument('--end',help='Optional earlier replay cutoff, YYYY-MM-DD HH:MM:SS')
    args=parser.parse_args()
    print(json.dumps(generate(args.output_dir,end=args.end),ensure_ascii=False,indent=2))
