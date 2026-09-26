"""python -m src.F09 --as-of 2015-12-21 --horizon 28"""

import argparse
from pathlib import Path

from .heatmap import ROOT, build_heatmap, load_predictions, machine_ids


def main():
    parser = argparse.ArgumentParser(description="F09 설비별 고장 예측 히트맵")
    parser.add_argument("--as-of")
    parser.add_argument("--horizon", type=int, default=28)
    parser.add_argument("--version")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/F09/heatmap.html")
    args = parser.parse_args()
    data = load_predictions()
    figure, metadata = build_heatmap(data, args.as_of or data.as_of.max(), args.horizon,
                                     args.version or sorted(data.model_version.unique())[-1], machines=machine_ids())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    note = "설비별 부품 위험 점수의 최댓값입니다. 설비 전체의 고장 확률은 아닙니다."
    document = '<!doctype html><html lang="ko"><meta charset="utf-8"><title>F09 히트맵</title><body><p>' + note + '</p>'
    document += figure.to_html(full_html=False, include_plotlyjs=True) + '</body></html>'
    args.output.write_text(document, encoding="utf-8")
    print(f"Saved: {args.output} ({metadata['cells']} cells)")


if __name__ == "__main__":
    main()
