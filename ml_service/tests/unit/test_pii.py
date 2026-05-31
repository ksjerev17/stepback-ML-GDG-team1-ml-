"""PII 마스킹 12 케이스 — CLAUDE.md §11.1."""
from __future__ import annotations

import pytest

from app.infra.pii_masker import mask_pii


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected_token",
    [
        ("문제 발생 시 https://example.com 로 신고", "[URL]"),
        ("연락은 abc.def+1@school.ac.kr 로", "[이메일]"),
        ("연락처 010-1234-5678 입니다", "[전화]"),
        ("핸드폰 01012345678 임", "[전화]"),
        ("회사 전화 02-555-1234 받음", "[전화]"),
        ("학번 20231234 입니다", "[학번]"),
    ],
)
def test_basic_pii_masking(raw: str, expected_token: str) -> None:
    out = mask_pii(raw)
    assert expected_token in out, f"입력: {raw!r} → {out!r}"


@pytest.mark.unit
def test_honorific_plus_name() -> None:
    out = mask_pii("교수님 김민수 너무 무서워")
    assert "[이름1]" in out
    assert "교수님" in out
    assert "김민수" not in out


@pytest.mark.unit
def test_common_word_not_masked() -> None:
    # '교수님 수업'에서 '수업'은 일반어 — 마스킹 X
    out = mask_pii("교수님 수업 어려워")
    assert "[이름" not in out
    assert "수업" in out


@pytest.mark.unit
def test_korean_surname_plus_one_char() -> None:
    out = mask_pii("이수가 도와줬어")
    assert "[이름1]" in out
    assert "이수" not in out


@pytest.mark.unit
def test_url_and_email_together() -> None:
    out = mask_pii("https://x.com 에서 a@b.co 로 메일")
    assert "[URL]" in out and "[이메일]" in out


@pytest.mark.unit
def test_multiple_names_increment() -> None:
    out = mask_pii("선배 박지영 그리고 후배 김민수")
    assert "[이름1]" in out and "[이름2]" in out


@pytest.mark.unit
def test_empty_input() -> None:
    assert mask_pii("") == ""


@pytest.mark.unit
def test_no_pii_text_unchanged() -> None:
    raw = "오늘 발표 망할 것 같아"
    assert mask_pii(raw) == raw
