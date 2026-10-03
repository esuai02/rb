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
        if not (tokens[i].kind == NAME and tokens[i].text == "local" and tokens[i + 1].kind == NAME):
            continue
        equals = _assign_index(tokens, i)
        if equals is None:
            continue
        j, depth, rhs = equals + 1, 0, []
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


def _assign_index(tokens: list[Token], i: int) -> int | None:
    """`local 이름 [: 형] =` 의 `=` 자리 — 같은 줄에서만 찾는다. 대입이 없으면 None."""
    j, depth = i + 2, 0
    while j < len(tokens) and tokens[j].line == tokens[i].line:
        tok = tokens[j]
        if tok.kind == SYMBOL and tok.text in ("(", "{", "["):
            depth += 1
        elif tok.kind == SYMBOL and tok.text in (")", "}", "]"):
            depth -= 1
        elif depth == 0 and tok.kind == SYMBOL and tok.text == "=":
            return j
        elif depth == 0 and j == i + 2 and not (tok.kind == SYMBOL and tok.text == ":"):
            return None
        j += 1
    return None


def resolve_names(tokens: list[Token]) -> dict[str, object]:
    """이름 → 값. 값은 글자(str) · 수(float) · 가리키는 경로(tuple) · UNRESOLVED."""
    assigned: dict[str, list[list[Token]]] = {}
    for name, rhs in _statements(tokens):
        assigned.setdefault(name, []).append(rhs)
    for name, rhs in _split_assignments(tokens):
        assigned.setdefault(name, []).append(rhs)
    known: dict[str, object] = {name: UNRESOLVED for name, rhs in assigned.items() if len(rhs) > 1}
    for name in _reassigned(tokens) - set(_declared_empty(tokens)):
        known[name] = UNRESOLVED   # 나중에 다시 묶이는 이름은 값을 하나로 볼 수 없다
        assigned.pop(name, None)
    for _round in range(4):   # 몇 단계를 거쳐도 끝까지 따라간다
        before = dict(known)
        for name, rhs_list in assigned.items():
            if known.get(name) is UNRESOLVED and len(rhs_list) > 1:
                continue
            known[name] = _value(rhs_list[0], known)
        if known == before:
            break
    return known


def _declared_empty(tokens: list[Token]) -> set[str]:
    """`local x` 처럼 값 없이 선언한 이름 — 뒤에서 한 번만 대입하면 그 값으로 본다."""
    out = set()
    for i in range(len(tokens) - 1):
        if not (tokens[i].kind == NAME and tokens[i].text == "local" and tokens[i + 1].kind == NAME):
            continue
        after = tokens[i + 2] if i + 2 < len(tokens) else None
        if after is None or after.line > tokens[i + 1].line or (after.kind == NAME and after.text in KEYWORDS):
            out.add(tokens[i + 1].text)
    return out


def _split_assignments(tokens: list[Token]) -> list[tuple[str, list[Token]]]:
    """값 없이 선언한 이름에 뒤에서 한 번 대입하는 꼴 — `local x` … `x = Y.z` (리뷰 R-Q3 29차).

    두 번 이상 대입하면 여기에 넣지 않으므로 UNRESOLVED 로 남는다.
    """
    empty, counts, out = _declared_empty(tokens), {}, []
    for i in range(1, len(tokens) - 1):
        if not (tokens[i].kind == NAME and tokens[i].text in empty
                and tokens[i + 1].kind == SYMBOL and tokens[i + 1].text == "="):
            continue
        prev = tokens[i - 1]
        if prev.kind == NAME and prev.text == "local":
            continue
        counts[tokens[i].text] = counts.get(tokens[i].text, 0) + 1
        out.append((tokens[i].text, _rhs_from(tokens, i + 2)))
    return [(name, rhs) for name, rhs in out if counts[name] == 1]


def _rhs_from(tokens: list[Token], start: int) -> list[Token]:
    """start 부터 그 문장의 오른쪽 식 토큰."""
    depth, j, rhs = 0, start, []
    while j < len(tokens):
        tok = tokens[j]
        if tok.kind == SYMBOL and tok.text in ("(", "{", "["):
            depth += 1
        elif tok.kind == SYMBOL and tok.text in (")", "}", "]"):
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and j > start and (tok.line > tokens[j - 1].line or (tok.kind == NAME and tok.text in KEYWORDS)):
            break
        rhs.append(tok)
        j += 1
    return rhs


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
        value = known.get(rhs[0].text)
        return value if isinstance(value, (str, float, tuple)) else (rhs[0].text,)   # 값을 모르면 '그 이름을 가리킨다'로 둔다
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


KEYWORDS = {"and", "break", "continue", "do", "else", "elseif", "end", "false", "for", "function", "if", "in",
            "nil", "not", "or", "repeat", "return", "then", "true", "until", "while"}


def _reassigned(tokens: list[Token]) -> set[str]:
    """`local` 없이 다시 묶이는 이름 — 값이 바뀔 수 있으므로 상수로 보지 않는다.

    문장이 시작하는 자리는 앞 토큰이 기호(`.`·`,` 제외)이거나 예약어(end·then·do …)일 때다.
    """
    out = set()
    for i in range(1, len(tokens) - 1):
        if not (tokens[i].kind == NAME and tokens[i + 1].kind == SYMBOL and tokens[i + 1].text == "="):
            continue
        prev = tokens[i - 1]
        starts = (prev.line < tokens[i].line or (prev.kind == SYMBOL and prev.text not in (".", ",", "="))
                  or (prev.kind == NAME and prev.text in KEYWORDS)) and prev.text not in ("local", ".", ",")
        if starts:
            out.add(tokens[i].text)
    return out
