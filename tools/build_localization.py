#!/usr/bin/env python3
"""용어집(잠긴 Q2 명세)에서 LocalizationTable CSV 를 만든다 (DEC-8 · F9 · F13).

  python3 tools/build_localization.py            # src/shared/Localization.csv 를 다시 만든다
  python3 tools/build_localization.py --check    # 파일이 생성 결과와 같은지만 본다 (다르면 종료 코드 1)

CSV 를 손으로 고치지 않는다 — 문구의 정본은 specs/localization/terms/<market>.yaml 이고
이 생성기가 Roblox 가 읽는 꼴로 옮긴다. 번역 열은 시장 교육팩(Q8)에서 붙는다.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
GLOSSARY = REPO / "specs/localization/terms/ko-KR.yaml"
OUT = REPO / "world/src/shared/Localization.csv"
COLUMNS = ("Key", "Source", "Context", "Example")

# 키 앞머리 → 번역하는 사람이 보는 쓰임새. 금지어(INV-11)를 쓰지 않는 말로 적는다.
CONTEXT = {
    "world.": "월드 이름",
    "npc.": "동행 캐릭터 이름",
    "term.": "수학 용어 이름",
    "label.": "이름표 대사",
    "goal.": "HUD 목표",
    "sit.": "상황 설명",
    "prompt.": "조작 안내",
    "action.": "행동 선택지",
    "choice.": "말하기 선택지",
    "expr.": "수식 표기",
    "resp.": "월드 반응",
    "hint.": "힌트",
    "coop.": "함께하기 안내",
    "role.": "역할 이름",
    "ping.": "신호 버튼",
    "reward.": "보상 이름",
    "unlock.": "열린 길 이름",
    "zone.": "구역 안내",
    "retry.": "다시 하기 안내",
    "pacing.": "쉬어가기 선택지",
}


def context_for(key: str) -> str:
    """가장 긴(가장 구체적인) 앞머리의 쓰임새를 쓴다."""
    best = max((p for p in CONTEXT if key.startswith(p)), key=len, default=None)
    return CONTEXT[best] if best else "문구"


def rows(glossary: Path = GLOSSARY) -> list[list[str]]:
    strings = yaml.safe_load(glossary.read_text(encoding="utf-8"))["strings"]
    return [[key, text, context_for(key), ""] for key, text in sorted(strings.items())]


def render(glossary: Path = GLOSSARY) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows(glossary))
    return buffer.getvalue()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 tools/build_localization.py")
    parser.add_argument("--check", action="store_true", help="다시 만든 결과와 같은지만 본다")
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current == text:
            print(f"OK {OUT.relative_to(REPO)} — 용어집에서 생성한 결과와 같다 ({len(rows())}개 문구)")
            return 0
        print(f"FAIL {OUT.relative_to(REPO)} 가 용어집에서 생성한 결과와 다르다 — 손으로 고치지 말고 생성기를 다시 돌린다")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"{OUT.relative_to(REPO)} — 문구 {len(rows())}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
