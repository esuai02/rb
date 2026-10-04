"""이름이 가리키는 값 풀기 (작업 Graph Q3 — 검수 Harness).

검사를 비켜 가는 방법은 거의 하나다: 값을 변수에 한 번 더 담는 것(`local a = "Text"; Instance.new(a .. "Box")`).
그래서 이 묶음은 `local` 로 한 번만 묶인 이름을 끝까지 따라가고, **끝까지 풀리지 않으면 검사가 거부한다**.
조립한 값을 알 수 없으면 통과가 아니라 실패다 — 검사기가 읽을 수 있는 코드만 쓰게 한다.
"""
from __future__ import annotations

from harness.luau import INTERP, NAME, NUMBER, STRING, SYMBOL, Token, balanced

UNRESOLVED = object()   # 여러 번 묶였거나 알 수 없는 값


def _statements(tokens: list[Token]):
    """`local 이름 = …` 하나하나를 (이름, 오른쪽 토큰) 으로. 여러 이름이면 오른쪽을 쉼표로 나눠 차례로 짝짓는다.

    짝이 없는 이름(`local a, b = f()` 의 b)은 빈 오른쪽 — 값을 알 수 없다.
    """
    for i in range(len(tokens) - 2):
        if not _is_local(tokens, i):
            continue
        names, equals = _declaration(tokens, i)
        if equals is None:
            continue
        pieces = _split(_rhs_from(tokens, equals + 1), ",")
        for k, name in enumerate(names):
            yield name, pieces[k] if k < len(pieces) else []


def _is_local(tokens: list[Token], i: int) -> bool:
    """i 가 `local 이름` 선언의 시작인가 (`local function` 은 아니다)."""
    return (tokens[i].kind == NAME and tokens[i].text == "local" and i + 1 < len(tokens)
            and tokens[i + 1].kind == NAME and tokens[i + 1].text != "function")


def _declaration(tokens: list[Token], i: int) -> tuple[list[str], int | None]:
    """`local a [: 형], b … = …` — (이름들, `=` 자리 또는 None). 형 표기는 건너뛰고, 줄이 바뀌어도 선언이 이어지면 따라간다.

    `local g` 다음 줄의 `= M.f` 도 같은 선언이다 (리뷰 R-Q3 33차).
    """
    names, j, depth, want_name = [tokens[i + 1].text], i + 2, 0, False
    while j < len(tokens):
        tok = tokens[j]
        if want_name:
            if tok.kind != NAME:
                return names, None
            names.append(tok.text)
            want_name = False
        elif tok.kind == SYMBOL and tok.text in ("(", "{", "[", "<"):
            depth += 1
        elif tok.kind == SYMBOL and tok.text in (")", "}", "]", ">"):
            depth -= 1
        elif depth == 0 and tok.kind == SYMBOL and tok.text == "=":
            return names, j
        elif depth == 0 and tok.kind == SYMBOL and tok.text == ",":
            want_name = True
        elif depth == 0 and (_starts_statement(tok) or (tok.line > tokens[j - 1].line and not _continues(tokens[j - 1], tok))):
            return names, None
        j += 1
    return names, None


STATEMENT_START = {"local", "function", "end", "return", "if", "for", "while", "repeat", "until", "do", "break",
                   "continue", "else", "elseif", "then"}
OPERATORS = {"..", "+", "-", "*", "/", "//", "%", "^", "==", "~=", "<", ">", "<=", ">="}


def _starts_statement(tok: Token) -> bool:
    return (tok.kind == NAME and tok.text in STATEMENT_START) or (tok.kind == SYMBOL and tok.text == ";")


def _continues(prev: Token, nxt: Token) -> bool:
    """줄이 바뀌어도 식이 이어지는가 — 앞 줄이 `=`·연산자·점·쉼표로 끝나거나, 다음 줄이 연산자·점·`=`·글자로 시작하면.

    한 줄에 다 쓰지 않은 식을 끊어 읽으면 `local g =⏎ M.f` 의 값이 비어 별칭을 놓친다 (리뷰 R-Q3 33차).
    """
    if prev.kind == SYMBOL and prev.text in OPERATORS | {"=", ".", ":", ",", "::", "#"}:
        return True
    if prev.kind == NAME and prev.text in ("and", "or", "not"):
        return True
    if nxt.kind == SYMBOL and nxt.text in OPERATORS | {"=", ".", ":", "::"}:
        return True
    return nxt.kind in (STRING, NUMBER, INTERP) or (nxt.kind == NAME and nxt.text in ("and", "or"))


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
    """`local x` · `local a, b` 처럼 값 없이 선언한 이름 — 뒤에서 한 번만 대입하면 그 값으로 본다."""
    out = set()
    for i in range(len(tokens) - 1):
        if _is_local(tokens, i):
            names, equals = _declaration(tokens, i)
            if equals is None:
                out |= set(names)
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
    """start 부터 그 문장의 오른쪽 식 토큰. 줄이 바뀌어도 식이 이어지는 꼴(_continues)이면 따라간다.

    문장을 시작하는 말(local·if·return …)이나 `;` 에서 멈춘다. and·or·not 은 식의 일부로 둔다 —
    `a or M.f` 를 `a` 로 줄여 읽으면 값이 틀린다. 그런 식은 _value 가 풀지 못해 UNRESOLVED 가 된다.
    """
    depth, j, rhs = 0, start, []
    while j < len(tokens):
        tok = tokens[j]
        if tok.kind == SYMBOL and tok.text in ("(", "{", "["):
            depth += 1
        elif tok.kind == SYMBOL and tok.text in (")", "}", "]"):
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and (_starts_statement(tok) or (j > start and tok.line > tokens[j - 1].line
                                                        and not _continues(tokens[j - 1], tok))):
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


def require_bound(tokens: list[Token], module: str) -> set[str]:
    """`local X = require(….Module)` 로 그 모듈을 받은 이름."""
    out = set()
    for i in range(len(tokens) - 4):
        if (tokens[i].kind == NAME and tokens[i].text == "local" and tokens[i + 1].kind == NAME and tokens[i + 2].text == "="
                and tokens[i + 3].kind == NAME and tokens[i + 3].text == "require" and tokens[i + 4].text == "("):
            names = [x.text for x in balanced(tokens, i + 4) if x.kind == NAME]
            if names and names[-1] == module:
                out.add(tokens[i + 1].text)
    return out


def shape_violations(f, module: str, members: set[str]) -> list[tuple[int, str]]:
    """신뢰 모듈은 `모듈.함수(…)` 꼴로만 쓴다 (사람 결정 Q3-SHAPE-RULES).

    모듈을 받는 꼴은 `local 이름 = require(….모듈)` 하나뿐이고, 받은 이름은 언제나 `이름.멤버` 로만 쓴다.
    신뢰 함수(members)는 그 자리에서 바로 부른다 — 다른 이름·표에 담기, 값으로 넘기기, 콜론 호출은 거부한다.
    별칭을 풀어 따라가던 방식은 담는 꼴(줄바꿈·표·여러 이름·다시 대입)이 늘 때마다 구멍이 났다 —
    이제 이름이 무엇을 가리키는지 풀지 않고 토큰 모양만 본다 (리뷰 R-Q3 33차).
    돌려주는 것: (토큰 번호, 무엇을 했는가).
    """
    toks, bound, out = f.tokens, require_bound(f.tokens, module) | {module}, []
    for i, tok in enumerate(toks):
        if tok.kind == NAME and tok.text == "require" and i + 1 < len(toks) and toks[i + 1].text == "(":
            names = [x.text for x in balanced(toks, i + 1) if x.kind == NAME]
            if names and names[-1] == module and not _standard_require(toks, i):
                out.append((i, f"모듈 {module} 을 `local 이름 = require(…)` 가 아닌 꼴로 받는다"))
            continue
        before = toks[i - 1] if i else None
        if tok.kind != NAME or tok.text not in bound or (before is not None and (
                (before.kind == SYMBOL and before.text in (".", ":")) or (before.kind == NAME and before.text in ("local", "function")))):
            continue   # 다른 것의 멤버(script.Parent.RewardService) · 선언 자리
        holder = held_by(toks, i)
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        if nxt is not None and nxt.kind == SYMBOL and nxt.text in ("[", "="):
            continue   # `M[…]` 는 dynamic_member_calls 가 본다 · `M = …`(표 키·이름 다시 묶기)는 호출 검사를 속이지 못한다
        if nxt is None or nxt.kind != SYMBOL or nxt.text not in (".", ":"):
            out.append((i, f"모듈 {module} 을 다른 이름({holder})에 다시 담는다" if holder
                        else f"모듈 {module} 을 `{module}.멤버` 가 아닌 꼴로 쓴다(표에 담기·값으로 넘기기)"))
            continue
        member = toks[i + 2] if i + 2 < len(toks) else None
        if member is None or member.kind != NAME or member.text not in members:
            continue
        call = toks[i + 3] if i + 3 < len(toks) else None
        if nxt.text == ":":
            out.append((i, f"{module}:{member.text} 처럼 콜론으로 부른다 — 인자 자리가 하나씩 밀린다"))
        elif call is None or not (call.text in ("(", "{") or call.kind == STRING):
            out.append((i, f"{module}.{member.text} 를 다른 이름({holder})에 담는다" if holder
                        else f"{module} 의 함수를 부르지 않고 값으로 넘긴다"))
    return out


def _standard_require(toks: list[Token], i: int) -> bool:
    """i 의 require 가 `local 이름 = require(…)` 의 오른쪽 전부인가 — 바로 멤버를 부르는 꼴은 이미 접혀 있다(fold_require_calls)."""
    return (i >= 3 and toks[i - 1].kind == SYMBOL and toks[i - 1].text == "=" and toks[i - 2].kind == NAME
            and toks[i - 3].kind == NAME and toks[i - 3].text == "local")


def held_by(toks: list[Token], i: int) -> str | None:
    """i 에서 시작하는 값이 `대상 = …` 의 오른쪽 전부의 맨 앞이면 그 대상 — 멤버면 `t.g` 처럼 (`local g =⏎ M.f` 도).

    대상이 여럿(`local a, b = …`)이면 어느 이름에 담기는지 따지지 않고 None — 거부는 같고 이름만 적지 않는다.
    """
    if not (i >= 2 and toks[i - 1].kind == SYMBOL and toks[i - 1].text == "=" and toks[i - 2].kind == NAME):
        return None
    k = i - 2
    while k >= 2 and toks[k - 1].kind == SYMBOL and toks[k - 1].text == "." and toks[k - 2].kind == NAME:
        k -= 2
    if k and toks[k - 1].kind == SYMBOL and toks[k - 1].text == ",":
        return None
    return "".join(t.text for t in toks[k:i - 1])


def local_tables(tokens: list[Token]) -> set[str]:
    """`local X = {…}` (형 표기 포함)로 만든 평범한 표 — 다시 묶이지 않는 것만. 대괄호로 읽고 써도 자료일 뿐이다."""
    out = set()
    for i in range(len(tokens) - 2):
        if not _is_local(tokens, i):
            continue
        names, equals = _declaration(tokens, i)
        if equals is not None and len(names) == 1 and equals + 1 < len(tokens) and tokens[equals + 1].text == "{":
            out.add(names[0])
    return out - _reassigned(tokens)


def unreadable_reads(f) -> list[tuple[int, str]]:
    """값을 알 수 없는 키로 대괄호 읽기 — (여는 대괄호 토큰 번호, 바로 앞 토큰 글자).

    서비스·인스턴스·모듈의 멤버를 값을 모르는 키로 꺼내면 무엇을 부르는지(외부 호출인지) 알 수 없다.
    어떤 이름에 담아 왔는지 따라가는 대신, 이 파일에서 만든 평범한 표(local_tables)가 아니면 모두 거부한다 (리뷰 R-Q3 33차).
    쓰기(`x[k] = …`)는 무엇을 부르지 않으므로 보지 않는다. 글자·수 키와 값이 풀리는 이름 키는 읽을 수 있다.
    """
    toks, tables, out = f.tokens, local_tables(f.tokens), []
    for i, tok in enumerate(toks):
        if not (tok.kind == SYMBOL and tok.text == "[" and i and (toks[i - 1].kind == NAME or toks[i - 1].text in (")", "]"))):
            continue
        inside = balanced(toks, i)
        key, after = inside[1:-1], i + len(inside)
        if len(key) == 1 and (key[0].kind in (STRING, NUMBER) or isinstance(f.resolved.get(key[0].text), (str, float))):
            continue
        if after < len(toks) and toks[after].kind == SYMBOL and toks[after].text == "=":
            continue
        receiver = toks[i - 1]
        if receiver.kind == NAME and receiver.text in tables and not (i >= 2 and toks[i - 2].text in (".", ":")):
            continue
        out.append((i, receiver.text if receiver.kind == NAME else "(식의 결과)"))
    return out


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


COMPOUND = {"+=", "-=", "*=", "/=", "//=", "%=", "^=", "..="}


def _reassigned(tokens: list[Token]) -> set[str]:
    """`local` 없이 다시 묶이는 이름 — 값이 바뀔 수 있으므로 상수로 보지 않는다.

    `x = …` 뿐 아니라 여러 대상(`a, x = …` · `t.k, x = …`)과 복합 대입(`x ..= …`)도 다시 묶는 것이다 (리뷰 R-Q3 33차).
    문장이 시작하는 자리는 맨 왼쪽 대상의 앞 토큰이 기호(`.`·`,`·`=` 제외)이거나 예약어(end·then·do …)이거나 줄이 바뀐 자리다.
    """
    out = set()
    for e in range(1, len(tokens)):
        tok = tokens[e]
        if not (tok.kind == SYMBOL and (tok.text == "=" or tok.text in COMPOUND)):
            continue
        names, left, member_listed = _assignment_targets(tokens, e)
        if not names:
            continue
        before = tokens[left - 1] if left else None
        if before is not None and before.kind == NAME and before.text == "local":
            continue   # 선언이다
        starts = before is None or ((before.line < tokens[left].line
                                     or (before.kind == SYMBOL and before.text not in (".", ",", "="))
                                     or (before.kind == NAME and before.text in KEYWORDS))
                                    and before.text not in (".", ","))
        if starts or member_listed or tok.text in COMPOUND:
            out |= set(names)
    return out


def _assignment_targets(tokens: list[Token], e: int) -> tuple[list[str], int, bool]:
    """`=` 앞의 이름 대상들 — (이름들, 맨 왼쪽 이름의 토큰 번호, 쉼표 뒤에 멤버 대상이 있었는가).

    멤버 대상(t.x)은 이름을 다시 묶지 않으므로 넣지 않는다. 다만 `t.x, y =` 처럼 멤버가 목록에 끼어 있으면
    표 생성자가 아니라 대입문이 틀림없다.
    """
    names, k, left = [], e - 1, e - 1
    while k >= 0 and tokens[k].kind == NAME and tokens[k].text not in KEYWORDS:
        prev = tokens[k - 1] if k else None
        if prev is not None and prev.kind == SYMBOL and prev.text in (".", ":"):
            return names, left, bool(names)
        names.append(tokens[k].text)
        left = k
        if not (prev is not None and prev.kind == SYMBOL and prev.text == ","):
            break
        k -= 2
    return names, left, False
