"""번역·문구 검사 (INV-3 · K4 U7 · K3 E5 · intent §4 번역 금지 구간).

화면 문구는 LocalizationTable(CSV)을 거치고, 코드가 쓰는 키는 표에 있으며, 문구는 칸에 들어가는 폭·읽기 쉬운 문장이고,
수식·좌표는 번역해도 그대로 남는다.
"""
from __future__ import annotations

import re
import unicodedata

from harness import luau, resolve
from harness.luau import NAME, STRING, SYMBOL

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")      # 키·열거형 토큰 — 화면 문구가 아니다
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)               # 어떤 문자 체계든 '글자'
SENTENCE_END = re.compile(r"(?<=[.!?。])\s+")
DEV_MESSAGE_CALLS = {"error", "warn", "print", "assert"}   # 개발자용 메시지 — 화면 문구가 아니다


def width(text: str) -> int:
    """화면 폭 — 한글·전각은 2, 그 밖은 1로 센다(글자 수는 언어마다 뜻이 달라 폭으로 잰다)."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def _text_columns(row: dict) -> dict[str, str]:
    return {col: text for col, text in row.items() if text}


def _aliases(f, module: str) -> set[str]:
    return luau.require_aliases(f.tokens, module) | resolve.names_for(f.resolved, (module,))


def _key_calls(f, config) -> list[tuple[int, list]]:
    """문구 키를 쓰는 호출 — <문구 모듈>.get("키") 와 translator:FormatByKey("키")."""
    if f.name == config["text_module"]:
        return []   # 문구 모듈 자신은 받은 키를 그대로 넘긴다 — 그 모듈을 부르는 쪽을 검사한다
    out, toks = [], f.tokens
    modules = _aliases(f, config["text_module"])
    direct = {alias for name in modules for alias in resolve.names_for(f.resolved, (name, "get")) if alias != name}
    for path in [(name, "get") for name in modules] + [(name,) for name in direct]:
        out += [(i, luau.call_args(toks, i)) for i in luau.find_calls(toks, path)]
    for i, t in enumerate(f.tokens):
        if t.kind == NAME and t.text in config["text_key_methods"] and i and f.tokens[i - 1].text == ":":
            out.append((i, luau.call_args(f.tokens, i)))
    return out


def missing_key(tree, rules, config) -> list[str]:
    """코드가 쓰는 문구 키는 글자 그대로이고 LocalizationTable 에 있다 (끊긴 번역 키)."""
    out = []
    if not tree.csv_files:
        out.append("LocalizationTable(CSV)이 없다")
    for f in tree.luau:
        out += [f"{f.rel}:{f.tokens[i].line} 문구 모듈 {name} 의 멤버를 값을 알 수 없는 방식으로 고른다 — 어떤 키를 쓰는지 검사할 수 없다"
                for i, name in resolve.dynamic_member_calls(f, _aliases(f, config["text_module"]))]
        for i, args in _key_calls(f, config):
            key = args[0] if args else []
            if len(key) != 1 or key[0].kind != STRING:
                out.append(f"{f.rel}:{f.tokens[i].line} 문구 키는 글자 그대로 써야 한다(표에 있는지 검사할 수 있게)")
            elif key[0].text not in tree.strings:
                out.append(f"{f.rel}:{key[0].line} 문구 키 {key[0].text} 가 LocalizationTable 에 없다")
    return out


def _budget(key: str, config) -> int:
    best = max((p for p in config["width_budget"] if p != "*" and key.startswith(p)), key=len, default="*")
    return config["width_budget"][best]


def length_budget(tree, rules, config) -> list[str]:
    """문구가 키 종류별 화면 폭 상한을 넘지 않는다 — 넘치는 긴 번역문 (U7 의 정적 부분). 실제 화면 폭 실측은 Q4."""
    return [f"{key}[{col}] 폭 {width(text)} — 상한 {_budget(key, config)} 을 넘는다"
            for key, row in sorted(tree.strings.items()) for col, text in _text_columns(row).items() if width(text) > _budget(key, config)]


def math_fragments(text: str, rules) -> list[str]:
    """번역해도 그대로 남아야 하는 조각(수식·좌표)."""
    return sorted(m.group() for r in rules.world_spec.get("do_not_translate", []) for m in re.finditer(r["pattern"], text))


def do_not_translate(tree, rules, config) -> list[str]:
    """원문의 수식·좌표 조각이 모든 번역 칸에 똑같이(빠짐도 더함도 없이) 있다 (intent §4 번역 금지 구간)."""
    out = []
    for key, row in sorted(tree.strings.items()):
        source = math_fragments(row.get("Source", ""), rules)
        for col, text in _text_columns(row).items():
            if col == "Source":
                continue
            found = math_fragments(text, rules)
            if found != source:
                out.append(f"{key}[{col}] 번역 금지 조각이 원문과 다르다 (원문 {source} · 번역 {found})")
    return out


def _dev_strings(f) -> set[int]:
    return {id(t) for name in DEV_MESSAGE_CALLS for i in luau.find_calls(f.tokens, (name,)) for arg in luau.call_args(f.tokens, i) for t in arg}


def _string_constants(f) -> dict:
    """`local name = "글자"` 로 묶인 이름 → 그 문자열 토큰."""
    toks = f.tokens
    return {toks[i + 1].text: toks[i + 3] for i in range(len(toks) - 3)
            if toks[i].kind == NAME and toks[i].text == "local" and toks[i + 1].kind == NAME and toks[i + 2].text == "=" and toks[i + 3].kind == STRING}


def _ui_text_literals(f, config) -> list:
    """UI 글자 속성에 들어가는 문자열 — 바로 쓴 것도, 문자열 상수에 담아 쓴 것도 문구 키를 거쳐야 한다."""
    toks, out, constants = f.tokens, [], _string_constants(f)
    for i in range(len(toks) - 2):
        dotted = toks[i].text == "." and toks[i + 1].kind == NAME and toks[i + 1].text in config["ui_text_properties"] and toks[i + 2].text == "="
        bracket = (toks[i].text == "[" and toks[i + 1].kind == STRING and toks[i + 1].text in config["ui_text_properties"]
                   and i + 3 < len(toks) and toks[i + 2].text == "]" and toks[i + 3].text == "=")
        if not (dotted or bracket):
            continue
        prop = toks[i + 1].text
        depth, j = 0, i + 3 + (1 if bracket else 0)
        while j < len(toks) and not (toks[j].kind == NAME and toks[j].text in ("local", "function", "end", "return")):
            if toks[j].kind == luau.SYMBOL and toks[j].text in ("(", "{", "["):
                depth += 1
            elif toks[j].kind == luau.SYMBOL and toks[j].text in (")", "}", "]"):
                if depth == 0:
                    break
                depth -= 1
            elif toks[j].kind == STRING and depth == 0:
                out.append((prop, toks[j]))
            elif toks[j].kind == NAME and depth == 0 and toks[j].text in constants:
                out.append((prop, constants[toks[j].text]))
            elif toks[j].kind == NAME and depth == 0 and isinstance(f.resolved.get(toks[j].text), str):
                out.append((prop, luau.Token(STRING, f.resolved[toks[j].text], toks[j].line)))
            elif toks[j].line > toks[i].line and depth == 0:
                break
            j += 1
    return out


def _ui_assignments(f, config) -> list:
    """UI 글자 속성 대입의 (속성, 오른쪽 시작 토큰 번호)."""
    toks, out = f.tokens, []
    for i in range(len(toks) - 3):
        if toks[i].text == "." and toks[i + 1].kind == NAME and toks[i + 1].text in config["ui_text_properties"] and toks[i + 2].text == "=":
            out.append((toks[i + 1].text, i + 3))
    return out


def unresolved_ui_text(f, config) -> list[str]:
    """UI 에 들어가는 값은 문구 키 호출이거나 풀 수 있는 값이어야 한다 — 알 수 없는 조립은 검사할 수 없으므로 거부한다."""
    out, key_calls = [], {i for i, _args in _key_calls(f, config)}
    for prop, start in _ui_assignments(f, config):
        rhs = f.tokens[start:start + 12]
        if any(k in key_calls for k in range(start, start + 12)):
            continue
        calls = [k for k in range(start, min(start + 12, len(f.tokens)))
                 if f.tokens[k].kind == NAME and k + 1 < len(f.tokens) and f.tokens[k + 1].text == "("]
        if calls:
            out.append(f"{f.rel}:{f.tokens[start].line} UI 글자 속성 .{prop} 에 허용된 문구 키 호출이 아닌 함수의 결과를 넣는다 — 문구 키를 거쳐야 한다")
        elif not any(t.kind == STRING for t in rhs) and not any(isinstance(f.resolved.get(t.text), str) for t in rhs if t.kind == NAME):
            out.append(f"{f.rel}:{f.tokens[start].line} UI 글자 속성 .{prop} 에 값을 알 수 없는 글자를 넣는다 — 문구 키를 거치거나 풀리는 값이어야 한다")
    return out


def hardcoded_text(tree, rules, config) -> list[str]:
    """엔진 코드·데이터 파일에 화면 문구를 쓰지 않는다 — LocalizationTable 을 거친다 (INV-3)."""
    out = []
    for f in tree.luau:
        dev = _dev_strings(f)
        out += [f"{f.rel}:{t.line} UI 글자 속성 .{prop} 에 문구 '{t.text[:20]}' 를 바로 넣었다 — 문구 키로 바꿔야 한다"
                for prop, t in _ui_text_literals(f, config)]
        out += [f"{f.rel}:{t.line} 코드에 화면 문구 '{t.text[:20]}' 가 있다 — 문구 키로 바꿔야 한다" for t in f.tokens
                if t.kind == STRING and id(t) not in dev and LETTER.search(t.text) and not IDENTIFIER.fullmatch(t.text)]
    for f in tree.luau:
        out += unresolved_ui_text(f, config)
    out += [f"{d.rel} 데이터 파일에 화면 문구 '{text[:20]}' 가 있다 — 문구 키로 바꿔야 한다" for d in tree.data for text in d.strings
            if LETTER.search(text) and not IDENTIFIER.fullmatch(text)]
    return out


def readability(tree, rules, config) -> list[str]:
    """문장 하나는 상한 폭 안, 문구 하나는 상한 문장 수 안 — 수학이 아니라 문장 때문에 막히지 않게 (K3 E5).

    학년에 맞는 어휘인지는 사람(현지 교사 승인, Q8)이 본다.
    """
    limit, out = config["readability"], []
    for key, row in sorted(tree.strings.items()):
        for col, text in _text_columns(row).items():
            sentences = [s for s in SENTENCE_END.split(text.strip()) if s]
            if len(sentences) > limit["max_sentences"]:
                out.append(f"{key}[{col}] 문장이 {len(sentences)}개다 — {limit['max_sentences']}개 이하")
            out += [f"{key}[{col}] 문장 폭이 {width(s)} 다 — {limit['max_sentence_width']} 이하" for s in sentences
                    if width(s) > limit["max_sentence_width"]]
    return out
