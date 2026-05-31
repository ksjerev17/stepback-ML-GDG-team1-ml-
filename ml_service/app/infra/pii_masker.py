# 출처: CLAUDE.md §11.1
"""PII 마스킹 — LLM 호출 전 모든 텍스트가 이곳을 통과."""
from __future__ import annotations

import re
from typing import Final


COMMON_WORDS: Final[set[str]] = {
    "전화", "이메일", "학번", "주소", "이름", "사람", "친구", "교수", "선생",
    "오늘", "내일", "어제", "지금", "여기", "거기", "저기", "이거", "저거",
    "그거", "이것", "저것", "그것", "오빠", "언니", "누나", "동생", "엄마",
    "아빠", "선배", "후배", "수업", "시험", "과제", "공부", "학교", "회사",
    "우울해", "우울", "울고", "울어", "울었", "조용", "조심", "차분",
    "성공", "성장", "성숙", "한참", "한가", "신경", "신기", "권태", "안심",
    "전부", "전국", "전공",
    "발표", "면접", "취업", "졸업", "동기", "선후배",
    "강의", "기말", "중간", "리포트",
}

KOREAN_SURNAMES: Final[tuple[str, ...]] = (
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
    "한", "오", "서", "신", "권", "황", "안", "송", "전", "홍",
    "고", "문", "양", "손", "배", "백", "허", "유", "남", "심",
    "노", "하", "곽", "성", "차", "주", "우", "구", "민", "류",
    "나", "진", "지", "엄", "채", "원", "천", "방", "공", "현",
    "함", "여", "염", "변", "추", "도", "소", "석", "선", "설",
)

HONORIFIC_PATTERN: Final[str] = (
    r"(교수님|선생님|선배님|선배|후배|박사님|조교님|강사님|회장님|반장님)"
)

URL_RE = re.compile(r"https?://\S+|www\.\S+")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"\b(?:0\d{1,2}|1\d{3})[-.\s]\d{3,4}[-.\s]\d{4}\b|\b01\d{8,9}\b"
)
STUDENT_ID_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")
HONORIFIC_NAME_RE = re.compile(HONORIFIC_PATTERN + r"\s+([가-힣]{2,4})")


def _build_surname_pattern() -> re.Pattern[str]:
    surname_alt = "|".join(KOREAN_SURNAMES)
    return re.compile(rf"(?<![가-힣])({surname_alt})([가-힣]{{1,2}})(?![가-힣])")


SURNAME_NAME_RE = _build_surname_pattern()


def mask_pii(text: str) -> str:
    """7종 PII 마스킹. 일반어 화이트리스트로 오탐 방지."""
    if not text:
        return text

    result = text

    # 1. URL
    result = URL_RE.sub("[URL]", result)

    # 2. 이메일
    result = EMAIL_RE.sub("[이메일]", result)

    # 3. 전화
    result = PHONE_RE.sub("[전화]", result)

    # 4. 학번 (8자리 숫자)
    result = STUDENT_ID_RE.sub("[학번]", result)

    # 5. 호칭+이름
    name_counter = {"n": 0}

    def _next_name() -> str:
        name_counter["n"] += 1
        return f"[이름{name_counter['n']}]"

    def _honorific_replace(match: re.Match[str]) -> str:
        honor = match.group(1)
        name = match.group(2)
        if name in COMMON_WORDS:
            return match.group(0)
        return f"{honor} {_next_name()}"

    result = HONORIFIC_NAME_RE.sub(_honorific_replace, result)

    # 6. 일반 한국 성씨 + 1~2자 (화이트리스트 외)
    def _surname_replace(match: re.Match[str]) -> str:
        full = match.group(0)
        if full in COMMON_WORDS:
            return full
        # 두 글자 검사: 성+한 글자가 일반어인지
        if len(full) >= 2 and full[:2] in COMMON_WORDS:
            return full
        return _next_name()

    result = SURNAME_NAME_RE.sub(_surname_replace, result)

    return result
