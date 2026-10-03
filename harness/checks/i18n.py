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
SENTENCE_END = re.compile(r"(?<=[.!?。！？])(?!\d)\s*")   # 전각 부호·공백 없는 경계도 센다. 소수점(0.5)은 자르지 않는다
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
    out, toks = [], f.tokens
    if f.name == config["text_module"]:
        # 문구 모듈은 받은 키를 그대로 넘기는 것이 일이다. 다만 모듈 안에서 글자 그대로 적은 키는 표에 있어야 한다.
        return [(i, luau.call_args(toks, i)) for i, t in enumerate(toks)
                if t.kind == NAME and t.text in config["text_key_methods"] and i and toks[i - 1].text == ":"
                and (args := luau.call_args(toks, i)) and len(args[0]) == 1 and args[0][0].kind == STRING]
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
        out += [f"{f.rel}:{f.tokens[i].line} 문구 모듈 {name} 을 표·멤버에 담는다 — 이름 하나에 담아야 어떤 키를 쓰는지 검사할 수 있다"
                for i, name in luau.indirect_requires(f.tokens) if name == config["text_module"]]
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


def _ui_texts(f, start: int, end: int) -> list:
    """오른쪽 식 안의 글자 — 괄호 안이든 상수에 담았든 화면에 닿는 것은 같다 (리뷰 R-Q3 21차)."""
    constants = _string_constants(f)
    out = [t for t in f.tokens[start:end] if t.kind == STRING]
    for t in f.tokens[start:end]:
        if t.kind != NAME:
            continue
        if t.text in constants:
            out.append(constants[t.text])
        elif isinstance(f.resolved.get(t.text), str):
            out.append(luau.Token(STRING, f.resolved[t.text], t.line))
    return out


def _table_names(f) -> set[str]:
    """`local X = {` 로 만든 평범한 표 — 속성이 아니라 자료이므로 대괄호 대입을 막지 않는다.

    형 표기가 붙은 `local X: {[string]: number} = {}` 도 같이 본다.
    """
    toks, out = f.tokens, set()
    for i in range(len(toks) - 3):
        if not (toks[i].kind == NAME and toks[i].text == "local" and toks[i + 1].kind == NAME):
            continue
        equals = resolve._assign_index(toks, i)
        if equals is not None and equals + 1 < len(toks) and toks[equals + 1].text == "{":
            out.add(toks[i + 1].text)
    return out


def _chain_root(toks, j: int) -> int | None:
    """j 의 여는 대괄호 바로 앞 이름 경로(A.b.c)가 시작하는 토큰 번호."""
    k = j - 1
    if k < 0 or toks[k].kind != NAME:
        return None
    while k >= 2 and toks[k - 1].kind == SYMBOL and toks[k - 1].text == "." and toks[k - 2].kind == NAME:
        k -= 2
    return k


def _bracket_assignments(f) -> list[tuple[int, int, object]]:
    """obj[키] = … 대입 — (경로 시작 토큰 번호, 오른쪽 시작 토큰 번호, 풀린 키 값). 평범한 표에 담는 것은 뺀다."""
    toks, tables, out = f.tokens, _table_names(f), []
    for j, tok in enumerate(toks):
        if not (tok.kind == SYMBOL and tok.text == "["):
            continue
        start = _chain_root(toks, j)
        if start is None or (start == j - 1 and toks[start].text in tables):
            continue
        close = j + len(luau.balanced(toks, j)) - 1
        if close + 1 >= len(toks) or toks[close + 1].text != "=":
            continue
        key, _has_text = resolve.expression_value(toks, j + 1, f.resolved)
        out.append((start, close + 2, key))
    return out


def unresolved_ui_property(f, config) -> list[str]:
    """속성 이름을 값을 알 수 없는 방식으로 고르면 거부한다 — 화면 문구 속성인지 검사할 수 없다."""
    return [f"{f.rel}:{f.tokens[i].line} {f.tokens[i].text} 의 속성 이름을 값을 알 수 없는 방식으로 고른다 "
            f"— 화면 문구 속성인지 검사할 수 없으므로 쓰지 않는다" for i, rhs, key in _bracket_assignments(f)
            if not isinstance(key, str) and not (rhs < len(f.tokens) and f.tokens[rhs].kind == NAME and f.tokens[rhs].text == "function")]


def _ui_assignments(f, config) -> list:
    """UI 글자 속성 대입의 (속성, 오른쪽 시작 토큰 번호)."""
    toks, out = f.tokens, []
    for i in range(len(toks) - 3):
        if toks[i].text == "." and toks[i + 1].kind == NAME and toks[i + 1].text in config["ui_text_properties"] and toks[i + 2].text == "=":
            out.append((toks[i + 1].text, i + 3))
    return out   # 글자로 풀리는 대괄호 키는 luau.normalize_index 가 이미 점 접근으로 바꿔 두므로 위 고리가 함께 본다


def _expression_end(tokens, start: int) -> int:
    """start 에서 시작하는 식의 끝(뒤쪽 경계, 미포함). 괄호 안은 줄이 바뀌어도 이어진다."""
    depth, j = 0, start
    while j < len(tokens):
        tok = tokens[j]
        if tok.kind == SYMBOL and tok.text in ("(", "{", "["):
            depth += 1
        elif tok.kind == SYMBOL and tok.text in (")", "}", "]"):
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and j > start and (tok.line > tokens[j - 1].line
                                           or (tok.kind == NAME and tok.text in ("local", "function", "end", "return"))):
            break
        j += 1
    return j


def _is_only_key_call(f, start: int, end: int, key_calls: set[int]) -> bool:
    """오른쪽 식 전체가 허용된 문구 키 호출 하나인가 — 뒤에 덧붙인 조립이 있으면 아니다."""
    if start not in key_calls:
        return False   # 키 호출이 식의 맨 앞이 아니면 앞뒤로 덧붙인 것이 있다
    opened = next((k for k in range(start, end) if f.tokens[k].kind == SYMBOL and f.tokens[k].text == "("), None)
    if opened is None:
        return False
    close = opened + len(luau.balanced(f.tokens, opened)) - 1
    return close == end - 1


def unresolved_ui_text(f, config) -> list[str]:
    """UI 에 들어가는 값은 문구 키 호출 하나이거나 풀 수 있는 값이어야 한다 — 알 수 없는 조립은 거부한다."""
    out, key_calls = [], {i for i, _args in _key_calls(f, config)}
    for prop, start in _ui_assignments(f, config):
        end = _expression_end(f.tokens, start)
        if _is_only_key_call(f, start, end, key_calls):
            continue
        calls = [k for k in range(start, end)
                 if k + 1 < len(f.tokens) and f.tokens[k + 1].text == "("
                 and (f.tokens[k].kind == NAME or (f.tokens[k].kind == SYMBOL and f.tokens[k].text == "]"))]
        texts = _ui_texts(f, start, end)
        if calls:
            # 호출이 섞였다면 그 안의 글자는 문구 키일 수 있으므로 화면 문구로 부르지 않는다
            out.append(f"{f.rel}:{f.tokens[start].line} UI 글자 속성 .{prop} 에 허용된 문구 키 호출이 아닌 함수의 결과를 넣는다 — 문구 키를 거쳐야 한다")
        elif texts:
            out += [f"{f.rel}:{t.line} UI 글자 속성 .{prop} 에 문구 '{t.text[:20]}' 를 바로 넣었다 — 문구 키로 바꿔야 한다" for t in texts]
        else:
            out.append(f"{f.rel}:{f.tokens[start].line} UI 글자 속성 .{prop} 에 값을 알 수 없는 글자를 넣는다 — 문구 키를 거치거나 풀리는 값이어야 한다")
    return out


def hardcoded_text(tree, rules, config) -> list[str]:
    """엔진 코드·데이터 파일에 화면 문구를 쓰지 않는다 — LocalizationTable 을 거친다 (INV-3)."""
    out = []
    for f in tree.luau:
        dev = _dev_strings(f)
        out += [f"{f.rel}:{t.line} 코드에 화면 문구 '{t.text[:20]}' 가 있다 — 문구 키로 바꿔야 한다" for t in f.tokens
                if t.kind == STRING and id(t) not in dev and LETTER.search(t.text) and not IDENTIFIER.fullmatch(t.text)]
    for f in tree.luau:
        out += unresolved_ui_text(f, config) + unresolved_ui_property(f, config)
    out += [f"{d.rel} 데이터 파일에 화면 문구 '{text[:20]}' 가 있다 — 문구 키로 바꿔야 한다" for d in tree.data for text in d.strings
            if LETTER.search(text) and not IDENTIFIER.fullmatch(text)]
    out += [f"{d.rel} 데이터 파일의 UI 글자 속성 {name} 에 '{value[:20]}' 가 있다 — LocalizationTable 의 키여야 한다"
            for d in tree.data for name, value in d.properties
            if name in config["ui_text_properties"] and value not in tree.strings]
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
