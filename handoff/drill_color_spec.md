# 드릴 색상표 (FE 저장용)

> 방향: **드릴마다 고유색 100개가 아니라**, 기존 캘린더 팔레트 계열의 **카테고리 기반 6색**을 드릴에 부여한다.
> ML은 색을 string으로 매번 넘기지 않아도 되고, **FE가 이 표를 저장해두고 `drill.id`(또는 `category`)만 보고 렌더**하면 된다.
> (캘린더 한 칸의 "그날 감정/지배차원 색"은 별도 로직이며 이 표와 무관 — `calendar_color_spec.md` 참고.)

## 1. 팔레트 (6색 + 보조)

| 카테고리 | 한글 | token | hex | 의미 |
|---|---|---|---|---|
| cognitive_restructuring | 주황 | `orange` | `#F59E0B` | 생각 다시 보기 |
| behavioral_activation | 초록 | `green` | `#10B981` | 작은 행동 |
| habit_design | 청록 | `teal` | `#14B8A6` | 습관·루틴 |
| grounding | 하늘 | `sky` | `#38BDF8` | 지금·진정 |
| self_compassion | 분홍 | `pink` | `#F472B6` | 자기 자비 |
| sleep_circadian | 남보라 | `indigo` | `#6366F1` | 수면·리듬 |

> tone="positive"(잔잔한 날)일 때는 같은 색의 **연한 버전**(예: 10~20% opacity 배경)으로 표시하면 톤이 산다. 위기 카드는 이 팔레트와 무관하게 별도 경고색(예: 빨강 `#EF4444`) 권장.

## 2. 드릴 → 색 매핑 (요약)
드릴 100개 각각의 `id → {category, token, hex}` 전체 매핑은 **`drill_color_table.json`** 파일에 있다(FE가 그대로 import해서 사용). 규칙은 단순히 **"드릴의 category → 위 표의 색"**이라, FE는 둘 중 편한 방식을 쓰면 된다:

```ts
// 방법 A: 카테고리만 보고 (가장 단순, 권장)
const COLOR = {
  cognitive_restructuring: "#F59E0B", behavioral_activation: "#10B981",
  habit_design: "#14B8A6", grounding: "#38BDF8",
  self_compassion: "#F472B6", sleep_circadian: "#6366F1",
};
const hex = COLOR[drill.category];

// 방법 B: drill.id로 바로 (drill_color_table.json 사용)
import table from "./drill_color_table.json";
const { hex, token } = table.drill_color_by_id[drill.id];
```

## 3. ML 응답과의 관계
- ML은 추천 응답에 `drill.id`(정수)와 `drill.category`를 항상 보낸다. **이 둘만 있으면 위 표로 색이 결정**된다.
- 기존엔 ML이 `drill_calendar_color` 같은 문자열을 넘겼는데, 네 제안대로 **FE가 표를 저장**하면 ML은 색 문자열을 안 보내도 된다(보내도 무시 가능). → ML-FE 결합도↓.
- 새 드릴(96~118)도 모두 6개 카테고리 중 하나라 표에 자동 포함됨. 카탈로그가 커져도 FE 표는 **카테고리 6개만 유지**하면 끝.

## 4. 접근성
- 위 hex는 흰 배경에서 충분한 대비를 갖도록 골랐다(텍스트는 카드 안에서 진한 회색 `#1F2937` 권장).
- 색각 이상 대비: 색만으로 구분하지 말고 **카테고리 아이콘/라벨을 함께** 표기 권장(주황=생각, 초록=행동 등).
