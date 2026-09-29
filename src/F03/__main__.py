import argparse
import json

import pandas as pd

from src.ai_summary.cli import add_backend_options, selector_from_args
from .summary import build_summary


def main():
    parser = argparse.ArgumentParser(description="F03 고장 위험 기반 한 줄 대응 요약")
    parser.add_argument("--predictions", default="data/processed/predictions.csv")
    parser.add_argument("--maintenance-plan", help="선택: 기존 maintenance_plan.csv")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--horizon-days", type=int, required=True)
    parser.add_argument("--model-version", required=True)
    add_backend_options(parser)
    args = parser.parse_args()
    result = build_summary(
        pd.read_csv(args.predictions), args.as_of, horizon_days=args.horizon_days,
        model_version=args.model_version,
        maintenance_plan=pd.read_csv(args.maintenance_plan) if args.maintenance_plan else None,
        selector=selector_from_args(args),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
