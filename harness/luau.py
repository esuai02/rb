"""Luau 소스를 토큰으로 나눈다 (작업 Graph Q3 — 검수 Harness).

검사가 주석이나 문자열 속 글자에 속지 않게, 주석은 버리고 문자열은 문자열 토큰으로 따로 둔다.
문법 분석기는 아니다 — 검사에 필요한 만큼만 나눈다: 이름·문자열·수·기호.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NAME, STRING, NUMBER, SYMBOL = "name", "string", "number", "symbol"
_LONG_OPEN = re.compile(r"\[(=*)\[")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER = re.compile(r"0[xX][0-9a-fA-F_]+|0[bB][01_]+|(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:[eE][+-]?\d+)?")
_SYMBOLS = ("...", "..=", "==", "~=", "<=", ">=", "::", "->", "+=", "-=", "*=", "/=", "//=", "%=", "^=", "..", "//")


@dataclass(frozen=True)
class Token:
    kind: str
    text: str   # 문자열 토큰은 따옴표를 뗀 내용
    line: int


class LuauSyntaxError(ValueError):
    pass


def _long_bracket(src: str, i: int) -> tuple[str, int] | None:
    """i 위치의 [[...]] / [==[...]==] 를 읽어 (내용, 끝 다음 위치)."""
    m = _LONG_OPEN.match(src, i)
    if not m:
        return None
    close = "]" + m.group(1) + "]"
    end = src.find(close, m.end())
    if end < 0:
        raise LuauSyntaxError(f"닫히지 않은 긴 괄호 ({src.count(chr(10), 0, i) + 1}행)")
    return src[m.end():end], end + len(close)


def tokenize(src: str) -> list[Token]:
    tokens, i, line, n = [], 0, 1, len(src)
    while i < n:
        ch = src[i]
        if ch == "\n":
            line += 1
            i += 1
        elif ch.isspace():
            i += 1
        elif src.startswith("--", i):
            long = _long_bracket(src, i + 2)
            if long:
                line += src.count("\n", i, long[1])
                i = long[1]
            else:
                end = src.find("\n", i)
                i = n if end < 0 else end
        elif ch in "\"'`":
            j, buf = i + 1, []
            while j < n and src[j] != ch:
                if src[j] == "\\" and j + 1 < n:
                    buf.append(src[j:j + 2])
                    j += 2
                    continue
                if src[j] == "\n" and ch != "`":
                    raise LuauSyntaxError(f"줄이 바뀌는데 문자열이 닫히지 않음 ({line}행)")
                buf.append(src[j])
                j += 1
            if j >= n:
                raise LuauSyntaxError(f"닫히지 않은 문자열 ({line}행)")
            tokens.append(Token(STRING, "".join(buf), line))
            line += src.count("\n", i, j)
            i = j + 1
        elif ch == "[" and _LONG_OPEN.match(src, i):
            text, end = _long_bracket(src, i)
            tokens.append(Token(STRING, text, line))
            line += src.count("\n", i, end)
            i = end
        elif m := _NAME.match(src, i):
            tokens.append(Token(NAME, m.group(), line))
            i = m.end()
        elif (m := _NUMBER.match(src, i)) and m.group() not in ("", "."):
            tokens.append(Token(NUMBER, m.group(), line))
            i = m.end()
        else:
            sym = next((s for s in _SYMBOLS if src.startswith(s, i)), ch)
            tokens.append(Token(SYMBOL, sym, line))
            i += len(sym)
    return tokens


def find_calls(tokens: list[Token], path: tuple[str, ...]) -> list[int]:
    """이름 경로(예: ("RewardService", "grant"))로 시작하는 호출 위치(첫 토큰 번호). 구분자는 . 또는 :"""
    hits = []
    for i in range(len(tokens)):
        j, ok = i, True
        for k, part in enumerate(path):
            if k:
                if j >= len(tokens) or tokens[j].text not in (".", ":"):
                    ok = False
                    break
                j += 1
            if j >= len(tokens) or tokens[j].kind != NAME or tokens[j].text != part:
                ok = False
                break
            j += 1
        if ok and j < len(tokens) and (tokens[j].text in ("(", "{") or tokens[j].kind == STRING):
            before = tokens[i - 1] if i else None
            if before is None or (before.text not in (".", ":") and not (before.kind == NAME and before.text == "function")):
                hits.append(i)   # 정의(function X.f( ) 와 더 긴 이름의 일부(a.X.f)는 호출이 아니다
    return hits


def call_args(tokens: list[Token], start: int) -> list[list[Token]]:
    """start(호출 이름 첫 토큰)에서 시작하는 호출의 인자 토큰 묶음. 괄호 없는 호출 f"x" · f{...} 는 인자 하나."""
    i = start
    while i < len(tokens) and tokens[i].text not in ("(", "{") and tokens[i].kind != STRING:
        i += 1
    if i >= len(tokens):
        return []
    if tokens[i].kind == STRING:
        return [[tokens[i]]]
    if tokens[i].text == "{":
        return [balanced(tokens, i)]
    args, cur, depth = [], [], 0
    for tok in tokens[i + 1:]:
        if tok.text in ("(", "{", "[") and tok.kind == SYMBOL:
            depth += 1
        elif tok.text in (")", "}", "]") and tok.kind == SYMBOL:
            if depth == 0:
                if cur:
                    args.append(cur)
                return args
            depth -= 1
        if tok.text == "," and tok.kind == SYMBOL and depth == 0:
            args.append(cur)
            cur = []
        else:
            cur.append(tok)
    raise LuauSyntaxError(f"닫히지 않은 호출 ({tokens[start].line}행)")


def balanced(tokens: list[Token], open_index: int) -> list[Token]:
    """open_index 의 여는 괄호부터 짝이 맞는 닫는 괄호까지(양 끝 포함)."""
    pairs = {"(": ")", "{": "}", "[": "]"}
    opener = tokens[open_index].text
    depth = 0
    for j in range(open_index, len(tokens)):
        tok = tokens[j]
        if tok.kind == SYMBOL and tok.text == opener:
            depth += 1
        elif tok.kind == SYMBOL and tok.text == pairs[opener]:
            depth -= 1
            if depth == 0:
                return tokens[open_index:j + 1]
    raise LuauSyntaxError(f"닫히지 않은 괄호 ({tokens[open_index].line}행)")


# 식(expression) 자리의 if — `local x = if a then b else c` — 는 end 가 없다. 바로 앞 토큰으로 가른다
_EXPR_BEFORE = {"=", "(", ",", "{", "[", "..", "==", "~=", "<", ">", "<=", ">=", "+", "-", "*", "/", "//", "%", "^", "#", "+=", "-=",
                "*=", "/=", "//=", "%=", "^=", "..="}
_EXPR_WORDS = {"return", "and", "or", "not", "then", "else", "in"}


def _block_delta(tokens: list[Token], k: int) -> int:
    """k 번 토큰이 블록을 열면 +1, 닫으면 -1. 블록을 여는 말: function · do(while/for 포함) · repeat · 문장 자리의 if."""
    t = tokens[k]
    if t.kind != NAME:
        return 0
    if t.text in ("function", "do", "repeat"):
        return 1
    if t.text in ("end", "until"):
        return -1
    if t.text == "if":
        prev = tokens[k - 1] if k else None
        expression = prev is not None and (prev.kind == SYMBOL and prev.text in _EXPR_BEFORE or prev.kind == NAME and prev.text in _EXPR_WORDS
                                           and not _then_starts_statement(tokens, k))
        return 0 if expression else 1
    return 0


def _then_starts_statement(tokens: list[Token], k: int) -> bool:
    """`if a then if b then ... end end` 처럼 then·else 바로 뒤의 if 는 문장이다(if 식의 then 뒤가 아니면)."""
    prev = tokens[k - 1]
    if prev.text not in ("then", "else"):
        return False
    depth = 0
    for j in range(k - 2, -1, -1):  # 이 then/else 를 가진 if 가 문장 자리인지 거슬러 본다
        if tokens[j].kind == NAME and tokens[j].text == "if":
            if depth == 0:
                return _block_delta(tokens, j) == 1
            depth -= 1
        elif tokens[j].kind == NAME and tokens[j].text == "end":
            depth += 1
    return True


def function_bodies(tokens: list[Token]) -> list[tuple[list[str], list[Token], int]]:
    """function(...) ... end 묶음마다 (매개변수 이름, 본문 토큰, 시작 토큰 번호). 중첩 블록을 센다."""
    out = []
    for i, tok in enumerate(tokens):
        if tok.kind != NAME or tok.text != "function":
            continue
        j = i + 1
        while j < len(tokens) and tokens[j].text != "(":
            j += 1
        if j >= len(tokens):
            raise LuauSyntaxError(f"function 에 매개변수 괄호가 없음 ({tok.line}행)")
        params_tokens = balanced(tokens, j)
        params = _param_names(params_tokens)
        depth, k = 1, j + len(params_tokens)
        while k < len(tokens) and depth:
            depth += _block_delta(tokens, k)
            k += 1
        if depth:
            raise LuauSyntaxError(f"function 이 end 로 닫히지 않음 ({tok.line}행)")
        out.append((params, tokens[j + len(params_tokens):k - 1], i))
    return out


def _param_names(params_tokens: list[Token]) -> list[str]:
    """(a: number, b: {x: T}, ...) 에서 매개변수 이름만 — 괄호 바로 안에서 ( 나 , 바로 뒤에 오는 이름. 타입 표기는 건너뛴다."""
    names, depth = [], 0
    for k, t in enumerate(params_tokens):
        if t.kind == SYMBOL and t.text in ("(", "{", "["):
            depth += 1
        elif t.kind == SYMBOL and t.text in (")", "}", "]"):
            depth -= 1
        elif t.kind == NAME and depth == 1 and params_tokens[k - 1].text in ("(", ","):
            names.append(t.text)
    return names
