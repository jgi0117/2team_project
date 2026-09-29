import argparse
import json

import pandas as pd

from .analysis import analyze_equipment


def main():
    parser = argparse.ArgumentParser(description="F06 센서 이상 신호와 근거 분석")
    parser.add_argument("--telemetry", default="data/raw/azure_pdm/PdM_telemetry.csv")
    parser.add_argument("--if-predictions", help="선택: outputs/model3/predictions.csv")
    parser.add_argument("--machine-id", required=True, type=int)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--window-hours", type=int, default=72)
    args = parser.parse_args()
    result = analyze_equipment(
        pd.read_csv(args.telemetry), args.machine_id, args.as_of,
        if_predictions=pd.read_csv(args.if_predictions) if args.if_predictions else None,
        window_hours=args.window_hours,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
