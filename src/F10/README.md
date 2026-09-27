# F10 설비별 이상 위험

`outputs/model3/predictions.csv`에 저장된 Isolation Forest 이상 점수를 설비 한 대당 한 칸으로 표시합니다. 설비의 공정·라인 연결 정보가 없으므로 설비 단위로 제공합니다.

- Dash에서는 F09 예측 기준일을 조회 마감 시점으로 사용합니다. 날짜만 있는 기준일은 00:00입니다.
- 그 시점 이전의 가장 최근 공통 관측 시각을 선택하고, 100대 설비를 F09와 같은 위치에 배치합니다.
- 해당 관측 시각에 없는 설비 결과는 회색으로 표시합니다. 이전 관측을 정상값으로 채우지 않습니다.
- IF 이상 점수는 센서 패턴의 이례적인 정도입니다. 고장 확률이나 F09 점수와 같은 의미가 아닙니다.
- 저장된 임계값과 `is_anomaly`의 일치 여부를 검증합니다. 현재 경고 기준은 `anomaly_score > 0.5`입니다.
- 호버에는 원래 IF 점수·경고 여부·관측 시각을 표시합니다. 화면에는 설비 번호와 색상만 표시합니다.

```python
from src.F10 import load_predictions, build_heatmap

figure, metadata = build_heatmap(load_predictions(), "2015-12-21")
```
