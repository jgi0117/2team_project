# F08 · 담당자 및 조치 이력 관리

부품별 협력사 담당 정보와 설비별 정비·조치 이력을 제공합니다. UI에서는 전체
이력을 페이지당 10건씩 조회하고, 추가한 조치 메모는 브라우저 로컬 저장소에
보관합니다.

```python
from src.F08 import get_history, get_supplier

supplier = get_supplier("comp2", "2015-12-21")
history = get_history(1, "2015-12-21")
```
