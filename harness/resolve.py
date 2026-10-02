"""이름이 가리키는 값 풀기 (작업 Graph Q3 — 검수 Harness).

검사를 비켜 가는 방법은 거의 하나다: 값을 변수에 한 번 더 담는 것(`local a = "Text"; Instance.new(a .. "Box")`).
그래서 이 묶음은 `local` 로 한 번만 묶인 이름을 끝까지 따라가고, **끝까지 풀리지 않으면 검사가 거부한다**.
조립한 값을 알 수 없으면 통과가 아니라 실패다 — 검사기가 읽을 수 있는 코드만 쓰게 한다.
"""
from __future__ import annotations

from harness.luau import NAME, NUMBER, STRING, SYMBOL, Token

UNRESOLVED = object()   # 여러 번 묶였거나 알 수 없는 값


def _statements(tokens: list[Token]):
    """`local 이름 = …` 하나하나를 (이름, 오른쪽 토큰) 으로. 오른쪽은 줄이 바뀌거나 다음 문장이 시작할 때까지."""
    for i in range(len(tokens) - 3):
        if not (tokens[i].kind == NAME and tokens[i].text == "local" and tokens[i + 1].kind == NAME and tokens[i + 2].text == "="):
            continue
        j, depth, rhs = i + 3, 0, []
        while j < len(tokens):
            tok = tokens[j]
            if tok.kind == SYMBOL and tok.text in ("(", "{", "["):
                depth += 1
            elif tok.kind == SYMBOL and tok.text in (")", "}", "]"):
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and (tok.line > tokens[i].line or (tok.kind == NAME and tok.text in ("local", "function", "end", "return", "if", "for", "while"))):
                break
            rhs.append(tok)
            j += 1
        yield tokens[i + 1].text, rhs


def resolve_names(tokens: list[Token]) -> dict[str, object]:
    """이름 → 값. 값은 글자(str) · 수(float) · 가리키는 경로(tuple) · UNRESOLVED."""
    assigned: dict[str, list[list[Token]]] = {}
    for name, rhs in _statements(tokens):
        assigned.setdefault(name, []).append(rhs)
    known: dict[str, object] = {name: UNRESOLVED for name, rhs in assigned.items() if len(rhs) > 1}
    for _round in range(4):   # 몇 단계를 거쳐도 끝까지 따라간다
        before = dict(known)
        for name, rhs_list in assigned.items():
            if known.get(name) is UNRESOLVED and len(rhs_list) > 1:
                continue
            known[name] = _value(rhs_list[0], known)
        if known == before:
            break
    return known


def _value(rhs: list[Token], known: dict[str, object]) -> object:
    """오른쪽 식의 값 — 글자 이어 붙이기·수·이름 경로까지."""
    if not rhs:
        return UNRESOLVED
    parts = _split(rhs, "..")
    if len(parts) > 1:
        pieces = [_value(part, known) for part in parts]
        return "".join(p for p in pieces) if all(isinstance(p, str) for p in pieces) else UNRESOLVED
    rhs = [t for t in rhs if not (t.kind == SYMBOL and t.text in ("::",))]
    if len(rhs) == 1 and rhs[0].kind == STRING:
        return rhs[0].text
    if len(rhs) == 1 and rhs[0].kind == NUMBER:
        return float(rhs[0].text)
    if len(rhs) == 2 and rhs[0].text == "-" and rhs[1].kind == NUMBER:
        return -float(rhs[1].text)
    if len(rhs) == 1 and rhs[0].kind == NAME:
        return known.get(rhs[0].text, (rhs[0].text,))
    if rhs[0].kind == NAME and rhs[0].text == "require":
        names = [t.text for t in rhs if t.kind == NAME]
        return (names[-1],) if len(names) > 1 else UNRESOLVED
    path = _path(rhs)
    if path:
        head = known.get(path[0])
        return tuple(head) + path[1:] if isinstance(head, tuple) else path
    return UNRESOLVED


def _split(tokens: list[Token], symbol: str) -> list[list[Token]]:
    parts, cur, depth = [], [], 0
    for tok in tokens:
        if tok.kind == SYMBOL and tok.text in ("(", "{", "["):
            depth += 1
        elif tok.kind == SYMBOL and tok.text in (")", "}", "]"):
            depth -= 1
        if depth == 0 and tok.kind == SYMBOL and tok.text == symbol:
            parts.append(cur)
            cur = []
        else:
            cur.append(tok)
    parts.append(cur)
    return parts


def _path(tokens: list[Token]) -> tuple[str, ...] | None:
    """A.b.c 처럼 점으로 이은 이름이면 경로로."""
    out = []
    for k, tok in enumerate(tokens):
        if k % 2 == 0 and tok.kind == NAME:
            out.append(tok.text)
        elif k % 2 == 1 and tok.kind == SYMBOL and tok.text == ".":
            continue
        else:
            return None
    return tuple(out) if len(out) > 1 else None


def expression_value(tokens: list[Token], start: int, known: dict[str, object]) -> tuple[object, bool]:
    """start 부터 식 하나의 값과 '글자가 섞였는가'. 풀리지 않으면 (UNRESOLVED, 글자 섞임)."""
    depth, end = 0, start
    while end < len(tokens):
        tok = tokens[end]
        if tok.kind == SYMBOL and tok.text in ("(", "{", "["):
            depth += 1
        elif tok.kind == SYMBOL and tok.text in (")", "}", "]"):
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and tok.kind == SYMBOL and tok.text in (",", ";"):
            break
        end += 1
    expr = tokens[start:end]
    has_text = any(t.kind == STRING for t in expr) or any(
        isinstance(known.get(t.text), str) for t in expr if t.kind == NAME)
    return _value(expr, known), has_text


def names_for(known: dict[str, object], path: tuple[str, ...]) -> set[str]:
    """그 경로를 가리키는 이름 모두 — `local R = RewardService` 도, `local g = R.grant` 도."""
    return {path[0]} | {name for name, value in known.items() if isinstance(value, tuple) and tuple(value) == tuple(path)}


def dynamic_member_calls(f, module_names: set[str]) -> list[tuple[int, str]]:
    """모듈에 대괄호로 멤버를 골라 부르는데 값을 알 수 없는 자리 — (토큰 번호, 모듈 이름).

    값이 풀리면 harness.luau.normalize_index 가 이미 점 접근으로 바꿔 두었으므로, 여기 남은 것은 알 수 없는 것뿐이다.
    """
    toks, out = f.tokens, []
    for i, tok in enumerate(toks):
        if tok.kind == NAME and tok.text in module_names and i + 1 < len(toks) and toks[i + 1].text == "[":
            out.append((i, tok.text))
    return out
