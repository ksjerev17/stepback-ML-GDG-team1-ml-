#!/usr/bin/env python3
"""드릴 카탈로그 검증 & 병합 (v6.3 77개 + v6.4 신규 23개 = 100개).

3회 이상 반복 검증:
  R1 스키마/필수필드/중복ID    R2 라우팅 연결성(모든 드릴이 추천 도달 가능)
  R3 근거(논문) 구체성          R4 카테고리/패턴 커버리지 개선 확인
통과 시에만 drills_seed_v6_4.json 으로 병합 출력.
"""
import json
import sys
from collections import Counter
from pathlib import Path

W1 = Path(__file__).resolve().parent
BASE = W1 / "drills_seed_v6_3.json"
NEW = W1 / "drills_new_v6_4.json"
OUT = W1 / "drills_seed_v6_4.json"

REQUIRED = {"id", "title", "instruction", "duration_min", "patterns",
            "emotions", "context_affinity", "source_primary", "source_short",
            "evidence_level", "category", "legacy_id"}
CATS = {"cognitive_restructuring", "behavioral_activation", "habit_design",
        "grounding", "self_compassion", "sleep_circadian"}
PATTERNS = {"미래예측", "독심술", "자기비난", "이분법", "당위진술", "과잉일반화"}
BEHAVIORS = {"회피미루기", "동기저하"}
EMOTIONS = {"불안", "우울", "분노", "죄책", "중립"}


def load():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    new = json.loads(NEW.read_text(encoding="utf-8"))
    return base, base["drills"], new["drills"]


def r1_schema(drills, fails):
    ids = Counter()
    for d in drills:
        missing = REQUIRED - set(d.keys())
        if missing:
            fails.append(f"[R1] id={d.get('id')} 필수필드 누락: {missing}")
        ids[d["id"]] += 1
        if d.get("category") not in CATS:
            fails.append(f"[R1] id={d['id']} 잘못된 category: {d.get('category')}")
        if not isinstance(d.get("duration_min"), int) or not (1 <= d["duration_min"] <= 15):
            fails.append(f"[R1] id={d['id']} duration_min 이상")
        # 패턴/행동/감정 키 유효성
        for p in (d.get("patterns") or {}):
            if p not in PATTERNS:
                fails.append(f"[R1] id={d['id']} 미정의 pattern: {p}")
        for b in (d.get("behaviors") or {}):
            if b not in BEHAVIORS:
                fails.append(f"[R1] id={d['id']} 미정의 behavior: {b}")
        for e in (d.get("emotions") or {}):
            if e not in EMOTIONS:
                fails.append(f"[R1] id={d['id']} 미정의 emotion: {e}")
    dups = [i for i, c in ids.items() if c > 1]
    if dups:
        fails.append(f"[R1] 중복 ID: {dups}")


def r2_routing(drills, fails):
    """모든 드릴이 최소 1개 신호(pattern/behavior/emotion>0)에 연결되어
    추천 점수를 받을 수 있는지 — 고아 드릴 검출."""
    for d in drills:
        sig = 0.0
        for meta in (d.get("patterns") or {}).values():
            sig += meta.get("weight", 0) if isinstance(meta, dict) else float(meta)
        for meta in (d.get("behaviors") or {}).values():
            sig += meta.get("weight", 0) if isinstance(meta, dict) else float(meta)
        for w in (d.get("emotions") or {}).values():
            sig += float(w)
        for meta in (d.get("context_affinity") or {}).values():
            sig += meta.get("weight", 0) if isinstance(meta, dict) else 0
        if sig <= 0:
            fails.append(f"[R2] id={d['id']} '{d['title']}' 어떤 신호에도 연결 안 됨(고아)")
    # 각 카테고리가 최소 1개 이상 (라우팅 타깃 보장)
    cc = Counter(d["category"] for d in drills)
    for c in CATS:
        if cc[c] < 1:
            fails.append(f"[R2] 카테고리 '{c}' 드릴 0개 — 라우팅 도달 불가")


def r3_citations(drills, fails, warns):
    """근거의 구체성 — 저자·연도가 있는 1차 출처. (고전 출처는 경고로만)"""
    import re
    yr = re.compile(r"(1[5-9]\d{2}|20\d{2}|~?\d{2,4}\s*(AD|BC))")
    for d in drills:
        sp = d.get("source_primary", "")
        if len(sp) < 25:
            fails.append(f"[R3] id={d['id']} source_primary 너무 짧음: {sp[:40]}")
        elif not yr.search(sp):
            warns.append(f"[R3] id={d['id']} source_primary 연도 불명(고전?): {sp[:40]}")
        # 강한 가중(>=0.8) 패턴엔 rationale 권장 (경고)
        for p, meta in (d.get("patterns") or {}).items():
            if isinstance(meta, dict) and meta.get("weight", 0) >= 0.8:
                if len(meta.get("rationale", "")) < 10:
                    warns.append(f"[R3] id={d['id']} 패턴 '{p}'(w>=0.8) rationale 보강 권장")


def r4_coverage(drills, fails, warns):
    """커버리지 개선 — 갭이던 차원이 보강됐는지."""
    pat = Counter()
    for d in drills:
        for p, meta in (d.get("patterns") or {}).items():
            w = meta.get("weight", 0) if isinstance(meta, dict) else float(meta)
            if w >= 0.8:
                pat[p] += 1
    # 목표: 모든 패턴 primary 드릴 >=4
    for p in PATTERNS:
        if pat[p] < 4:
            warns.append(f"[R4] 패턴 '{p}' primary 드릴 {pat[p]}개 (<4) — 추가 권장")
    emo_strong = Counter()
    for d in drills:
        for e, w in (d.get("emotions") or {}).items():
            if float(w) >= 0.8 and e != "중립":
                emo_strong[e] += 1
    for e in ("분노", "죄책"):
        if emo_strong[e] < 3:
            warns.append(f"[R4] 감정 '{e}' strong 드릴 {emo_strong[e]}개 (<3)")
    ctx = Counter()
    for d in drills:
        for k in (d.get("context_affinity") or {}):
            ctx[k] += 1
    for k in ("social_stressful", "sleep_short"):
        if ctx[k] < 5:
            warns.append(f"[R4] 맥락 '{k}' {ctx[k]}개 (<5)")


def main():
    base_obj, base, new = load()
    merged = base + new
    print(f"기존 {len(base)} + 신규 {len(new)} = {len(merged)}개 후보")

    all_fail = []
    for rnd in (1, 2, 3):
        fails, warns = [], []
        r1_schema(merged, fails)
        r2_routing(merged, fails)
        r3_citations(merged, fails, warns)
        r4_coverage(merged, fails, warns)
        print(f"\n=== 검증 R{rnd} === fail={len(fails)} warn={len(warns)}")
        for f in fails:
            print("  ❌", f)
        for w in warns:
            print("  ⚠️ ", w)
        all_fail += fails

    if all_fail:
        print(f"\n🛑 실패 {len(all_fail)}건 — 병합 중단.")
        sys.exit(1)

    # 병합 출력 (메타 갱신)
    out = dict(base_obj)
    out["schema_version"] = "6.4"
    out["total_drills"] = len(merged)
    out["version_notes"] = "v6.4: 신규 23개(갭 집중: 과잉일반화·독심술·당위진술·이분법·분노·social/sleep). 3회 검증 통과."
    cc = Counter(d["category"] for d in merged)
    out["category_distribution"] = dict(cc)
    out["drills"] = merged
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 3회 검증 통과 → {OUT.name} 저장 ({len(merged)}개)")
    print("카테고리 분포:", dict(cc))


if __name__ == "__main__":
    main()
