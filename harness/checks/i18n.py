"""번역·문구 검사 (INV-3 · K4 U7 · K3 E5 · intent §4 번역 금지 구간).

화면 문구는 LocalizationTable(CSV)을 거치고, 코드가 쓰는 키는 표에 있으며, 문구는 칸에 들어가는 길이·읽기 쉬운 문장이고,
수식·좌표는 번역해도 그대로 남는다.
"""
from __future__ import annotations

import re

from harness import luau
from harness.luau import NAME, STRING

HANGUL = re.compile(r"[가-힣]")
WORDS = re.compile(r"[A-Za-z]{2,}(?:\s+[A-Za-z]{2,})+")
SENTENCE_END = re.compile(r"(?<=[.!?。])\s+")
DEV_MESSAGE_CALLS = {"error", "warn", "print", "assert"}   # 개발자용 메시지 — 화면 문구가 아니다


def _text_columns(row: dict) -> dict[str, str]:
    return {col: text for col, text in row.items() if text}


def _key_calls(f, config) -> list[tuple[int, list]]:
    out = []
    for path in config["text_key_calls"]:
        out += [(i, luau.call_args(f.tokens, i)) for i in luau.find_calls(f.tokens, tuple(path))]
    if f.rel.rsplit("/", 1)[-1].split(".")[0] == config["text_module"]:
        return out   # 문구 모듈 자신은 받은 키를 그대로 넘긴다 — 그 모듈을 부르는 쪽(Text.get("키"))을 검사한다
    for i, t in enumerate(f.tokens):   # translator:FormatByKey("key") — 받는 쪽 이름이 무엇이든
        if t.kind == NAME and t.text in config["text_key_methods"] and i and f.tokens[i - 1].text == ":":
            out.append((i, luau.call_args(f.tokens, i)))
    return out


def missing_key(tree, rules, config) -> list[str]:
    """코드가 쓰는 문구 키는 글자 그대로이고 LocalizationTable 에 있다 (끊긴 번역 키)."""
    out = []
    if not tree.csv_files:
        out.append("LocalizationTable(CSV)이 없다")
    for f in tree.luau:
        for i, args in _key_calls(f, config):
            key = args[0] if args else []
            if len(key) != 1 or key[0].kind != STRING:
                out.append(f"{f.rel}:{f.tokens[i].line} 문구 키는 글자 그대로 써야 한다(표에 있는지 검사할 수 있게)")
            elif key[0].text not in tree.strings:
                out.append(f"{f.rel}:{key[0].line} 문구 키 {key[0].text} 가 LocalizationTable 에 없다")
    return out


def _budget(key: str, config) -> int:
    best = max((p for p in config["length_budget"] if p != "*" and key.startswith(p)), key=len, default="*")
    return config["length_budget"][best]


def length_budget(tree, rules, config) -> list[str]:
    """문구가 키 종류별 글자 수 상한(버튼·목표·이름·대사)을 넘지 않는다 — 넘치는 긴 번역문 (U7 의 정적 부분)."""
    return [f"{tree.csv_files[0] if tree.csv_files else 'csv'} {key}[{col}] {len(text)}자 — 상한 {_budget(key, config)}자를 넘는다"
            for key, row in sorted(tree.strings.items()) for col, text in _text_columns(row).items() if len(text) > _budget(key, config)]


def do_not_translate(tree, rules, config) -> list[str]:
    """원문(Source)의 수식·좌표 조각이 모든 번역 칸에 그대로 있다 (intent §4 번역 금지 구간)."""
    patterns = [re.compile(r["pattern"]) for r in rules.world_spec.get("do_not_translate", [])]
    out = []
    for key, row in sorted(tree.strings.items()):
        source = row.get("Source", "")
        pieces = [m.group() for p in patterns for m in p.finditer(source)]
        for col, text in _text_columns(row).items():
            if col == "Source":
                continue
            out += [f"{key}[{col}] 번역 금지 조각 '{piece}' 이 그대로 남지 않았다" for piece in pieces if piece not in text]
    return out


def hardcoded_text(tree, rules, config) -> list[str]:
    """엔진 코드에 화면 문구(한글 또는 띄어 쓴 영어 낱말들)를 쓰지 않는다 — LocalizationTable 을 거친다 (INV-3)."""
    out = []
    for f in tree.luau:
        dev = set()
        for name in DEV_MESSAGE_CALLS:
            for i in luau.find_calls(f.tokens, (name,)):
                dev |= {id(t) for arg in luau.call_args(f.tokens, i) for t in arg}
        out += [f"{f.rel}:{t.line} 코드에 화면 문구 '{t.text[:20]}' 가 있다 — 문구 키로 바꿔야 한다" for t in f.tokens
                if t.kind == STRING and id(t) not in dev and (HANGUL.search(t.text) or WORDS.search(t.text))]
    return out


def readability(tree, rules, config) -> list[str]:
    """문장 하나는 상한 글자 수 안, 문구 하나는 상한 문장 수 안 — 수학이 아니라 문장 때문에 막히지 않게 (K3 E5)."""
    limit = config["readability"]
    out = []
    for key, row in sorted(tree.strings.items()):
        for col, text in _text_columns(row).items():
            sentences = [s for s in SENTENCE_END.split(text.strip()) if s]
            if len(sentences) > limit["max_sentences"]:
                out.append(f"{key}[{col}] 문장이 {len(sentences)}개다 — {limit['max_sentences']}개 이하")
            out += [f"{key}[{col}] 문장이 {len(s)}자다 — {limit['max_sentence_chars']}자 이하" for s in sentences if len(s) > limit["max_sentence_chars"]]
    return out
