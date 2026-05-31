"""
apply_postprocess.py
====================
기존 labeling_results_*.json에 후처리(label_postprocess)를 일괄 적용.

쓸 때:
- LLM 호출 끝난 결과에 후처리 규칙 변경되었을 때 재호출 없이 적용
- 또는 후처리 적용 안 된 외부 결과 받았을 때

사용:
    python apply_postprocess.py [results_file]
"""
import json
import sys
from pathlib import Path
from label_postprocess import postprocess


def main(results_path: Path = None):
    if results_path is None:
        results_path = Path(__file__).parent / "labeling_results_v1.json"

    if not results_path.exists():
        print(f"ERROR: {results_path} 없음")
        return

    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", [])
    if not results:
        print("결과 없음")
        return

    changed = 0
    for r in results:
        text = r.get("text", "")
        result = r.get("result", {})
        if "_error" in result or result.get("_crisis"):
            continue
        before_conf = result.get("confidence")
        before_span = result.get("evidence_span")
        new_result = postprocess(result, text)
        if (new_result.get("confidence") != before_conf
                or new_result.get("evidence_span") != before_span):
            changed += 1
            r["result"] = new_result

    output = results_path.with_name(results_path.stem + "_postprocessed.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"입력:  {results_path.name} ({len(results)}개)")
    print(f"수정:  {changed}개")
    print(f"출력:  {output.name}")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    main(path)
