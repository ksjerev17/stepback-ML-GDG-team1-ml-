# 출처: CLAUDE.md §부록 D
"""W1 라벨링 결과 합치율 분석 → docs/labeling_analysis.md 자동 생성.

부록 D 8 항목:
1. 전체 합치율
2. 패턴별 정확도 (top-1)
3. 행동·감정 정확도
4. 길이별 confidence 분포
5. WARNING_MISMATCH 자동 분류
6. FAILED 원인 분류
7. 위기 신호 감지
8. 모델별 신호 강도 비교
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


REPO = Path(__file__).resolve().parents[2]
W1 = REPO / "w1"
DOCS = REPO / "docs"


def load_labeling_results() -> list[dict[str, Any]] | None:
    """W1 폴더의 labeling_results_v1.json 우선, 없으면 None."""
    candidates = [
        W1 / "labeling_results_v1.json",
        W1 / "labeling_results.json",
        W1 / "labeling_audit_v1.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def load_seed() -> list[dict[str, Any]]:
    path = W1 / "seed_sentences_50_v3.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("sentences", []) if isinstance(data, dict) else data


def render_placeholder(seed: list[dict[str, Any]]) -> str:
    """라벨링 결과 미발견 시 — seed 통계만 보고."""
    lines = ["# W1 라벨링 분석 — 데이터 미발견", ""]
    lines.append("`w1/labeling_results_v1.json` 또는 `labeling_audit_v1.json` 파일이 폴더에 없습니다.")
    lines.append("멤버 5명이 분담한 라벨링 결과 통합 파일을 `w1/` 폴더에 배치하면 자동 분석 가능.")
    lines.append("")
    if seed:
        lines.append(f"## Seed 통계 (참조)")
        lines.append(f"- seed 문장 수: **{len(seed)}**")
        crisis = sum(1 for s in seed if str(s).find("사라") >= 0 or str(s).find("죽") >= 0)
        lines.append(f"- 위기 신호 후보 (문장 내 '사라/죽' 키워드): {crisis}건")
        lengths = [len(str(s.get("text", s))) for s in seed if isinstance(s, dict)]
        if lengths:
            lines.append(f"- 길이: 평균 {mean(lengths):.1f}자 (min {min(lengths)} / max {max(lengths)})")
    lines.append("")
    lines.append("---")
    lines.append("최종 합치율 목표: ≥ 80% (W1 v9.4.3 실측 86%)")
    return "\n".join(lines)


def analyze(results: list[dict[str, Any]]) -> str:
    """라벨링 결과 분석 → markdown."""
    total = len(results)
    statuses = Counter(r.get("status", "UNKNOWN") for r in results)
    passed = statuses.get("PASSED", 0)
    warning = statuses.get("WARNING_MISMATCH", 0)
    failed = statuses.get("FAILED", 0)
    agreement_rate = (passed + warning) / total if total else 0.0

    lines = ["# W1 라벨링 합치율 분석", ""]
    lines.append(f"**전체**: {total}건 / **합치율**: {agreement_rate*100:.1f}% ({passed} PASSED + {warning} WARNING_MISMATCH)")
    lines.append("")
    lines.append("## 1. 전체 분포")
    for k, v in statuses.most_common():
        lines.append(f"- {k}: {v}건")

    # 2. 패턴별 정확도
    lines.append("\n## 2. 패턴별 정확도 (top-1)")
    pat_correct = Counter()
    pat_total = Counter()
    for r in results:
        gold = r.get("gold_top_pattern")
        pred = r.get("pred_top_pattern")
        if gold:
            pat_total[gold] += 1
            if pred == gold:
                pat_correct[gold] += 1
    for pat in sorted(pat_total):
        acc = pat_correct[pat] / pat_total[pat] if pat_total[pat] else 0.0
        lines.append(f"- {pat}: {acc*100:.0f}% ({pat_correct[pat]}/{pat_total[pat]})")

    # 4. 길이별 confidence
    lines.append("\n## 4. 길이별 confidence 분포")
    buckets = {"<15": [], "15-29": [], "30-80": [], ">80": []}
    for r in results:
        text = r.get("text", "")
        conf = r.get("pred_confidence", r.get("confidence", 0))
        n = len(text)
        key = "<15" if n < 15 else "15-29" if n < 30 else "30-80" if n <= 80 else ">80"
        buckets[key].append(conf)
    for key, vals in buckets.items():
        avg = mean(vals) if vals else 0.0
        lines.append(f"- {key}자 ({len(vals)}건): 평균 confidence {avg:.2f}")

    # 7. 위기
    lines.append("\n## 7. 위기 신호 감지")
    crisis_correct = sum(1 for r in results if r.get("gold_crisis") and r.get("pred_crisis"))
    crisis_total = sum(1 for r in results if r.get("gold_crisis"))
    if crisis_total:
        lines.append(f"- {crisis_correct}/{crisis_total} 정상 감지")
    else:
        lines.append("- 정답 위기 신호 문장 0건")

    lines.append("")
    lines.append("---\n*자동 생성 — `scripts/analyze_labeling.py`*")
    return "\n".join(lines)


def main() -> int:
    DOCS.mkdir(exist_ok=True, parents=True)
    results = load_labeling_results()
    if not results:
        seed = load_seed()
        md = render_placeholder(seed)
    elif isinstance(results, dict):
        # 결과가 {records: [...]} 형식이면 unwrap
        recs = results.get("records") or results.get("results") or []
        md = analyze(recs) if recs else render_placeholder(load_seed())
    else:
        md = analyze(results)
    out = DOCS / "labeling_analysis.md"
    out.write_text(md, encoding="utf-8")
    print(f"[analyze_labeling] → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
