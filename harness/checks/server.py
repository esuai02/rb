"""서버 권위 검사 (INV-4 · K3 §5). 보상·저장은 보상 모듈만 정하고, 완료·수령은 한 번만,
원격 입력은 막는 형태로 형식을 검사하고 쿨다운을 거치며, 보상은 서버 판정 뒤에만 준다."""
from __future__ import annotations

from harness import luau
from harness.luau import NAME, STRING, SYMBOL

BLOCKING = ("return", "error")   # 조건이 맞지 않을 때 멈추는 말


def _at(f, tok) -> str:
    return f"{f.rel}:{tok.line}"


def _module_names(f, module: str) -> set[str]:
    return luau.require_aliases(f.tokens, module)


def _grant_aliases(f, module_names: set[str]) -> set[tuple[str, ...]]:
    """grant 를 부르는 이름 경로 — M.grant 들과 `local g = M.grant` 의 g."""
    paths = {(name, "grant") for name in module_names}
    toks = f.tokens
    for i in range(len(toks) - 4):
        if toks[i].kind == NAME and toks[i + 1].text == "=" and toks[i + 2].kind == NAME and toks[i + 2].text in module_names \
                and toks[i + 3].text == "." and toks[i + 4].text == "grant":
            paths.add((toks[i].text,))
    return paths


def grant_calls(f, module: str) -> list[int]:
    """이 파일에서 보상을 주는 호출 위치(별칭 포함)."""
    return sorted(i for path in _grant_aliases(f, _module_names(f, module)) for i in luau.find_calls(f.tokens, path))


def reward_reaching(tree, module: str) -> set[str]:
    """보상에 닿는 함수 이름 — 본문에서 grant 를 부르는 함수(M.openGate 의 openGate)."""
    names = set()
    for f in tree.luau:
        calls, spans = set(grant_calls(f, module)), _function_spans(f.tokens)
        for start, end in spans:
            if any(start <= i < end for i in calls):
                named = _declared_name(f.tokens, start)
                if named:
                    names.add(named)
                elif start >= 2 and f.tokens[start - 1].text == "=" and f.tokens[start - 2].kind == NAME:
                    names.add(f.tokens[start - 2].text)   # local award = function() … grant … end
    return names


def _declared_name(tokens, start: int) -> str | None:
    """function M.openGate( … 에서 선언된 이름(openGate). 이름 없는 function 이면 None."""
    j, names = start + 1, []
    while j < len(tokens) and tokens[j].text != "(":
        if tokens[j].kind == NAME:
            names.append(tokens[j].text)
        j += 1
    return names[-1] if names else None


def _function_spans(tokens) -> list[tuple[int, int]]:
    """function 토큰 번호 → 그 함수가 끝나는 end 다음 번호."""
    spans, bodies = [], luau.function_bodies(tokens)
    for _params, body, start in bodies:
        j = start
        while j < len(tokens) and tokens[j].text != "(":
            j += 1
        depth, k = 1, j + len(luau.balanced(tokens, j))
        while k < len(tokens) and depth:
            depth += luau._block_delta(tokens, k)
            k += 1
        spans.append((start, k))
    return spans


def reward_authority(tree, rules, config) -> list[str]:
    """보상·저장 권한(leaderstats·DataStore·보상 속성)은 보상 모듈 파일 안에서만 쓴다 — 클라이언트도, 다른 서버 코드도 쓰지 않는다 (INV-4)."""
    names, module, out = set(config["authority_names"]), config["reward_module"], []
    for f in tree.luau:
        if f.name == module and f.client_visible:
            out.append(f"{f.rel}:1 보상 모듈 {module} 이 클라이언트가 볼 수 있는 곳({f.container})에 있다")
        if f.name == module:
            continue
        where = "클라이언트 코드" if f.client_visible else "보상 모듈 밖 서버 코드"
        out += [f"{_at(f, t)} {where}가 보상·저장 권한 {t.text} 를 쓴다 — 보상은 {module} 만 정한다" for t in f.tokens
                if t.text in names and t.kind in (NAME, STRING)]
    return out


def duplicate_reward(tree, rules, config) -> list[str]:
    """보상 모듈의 grant 는 맨 앞에서 claimOnce 로 한 번만 지급을 보장하고, 같은 보상 id 를 주는 호출 자리는 하나뿐이다."""
    module, out, sites = config["reward_module"], [], {}
    owners = [f for f in tree.luau if f.name == module]
    if not owners:
        out.append(f"보상 모듈 {module} 이 없다")
    for f in owners:
        grants = [(p, body, i) for p, body, i in luau.function_bodies(f.tokens) if _names_grant(f.tokens, i)]
        if not grants:
            out.append(f"{f.rel}:1 {module}.grant 함수가 없다")
        for _params, body, i in grants:
            texts = [t.text for t in body]
            then = texts.index("then") if "then" in texts else -1
            if texts[:3] != ["if", "not", "claimOnce"] or then < 0 or texts[then + 1:then + 2] != ["return"]:
                out.append(f"{_at(f, f.tokens[i])} grant 가 맨 앞에서 'if not claimOnce(...) then return' 으로 중복 지급을 막지 않는다")
    for f in tree.luau:
        for i in grant_calls(f, module):
            args = luau.call_args(f.tokens, i)
            literal = [a[0] if len(a) == 1 and a[0].kind == STRING else None for a in args]
            if len(args) < 3 or literal[1] is None or literal[2] is None:
                out.append(f"{_at(f, f.tokens[i])} 보상 id 와 미션 id 는 글자 그대로 써야 한다(누구에게 무엇을 주는지 정적으로 알 수 있게)")
                continue
            sites.setdefault((literal[1].text, literal[2].text), []).append(_at(f, f.tokens[i]))
    out += [f"{where[1]} 보상 {rid}({mid})를 주는 호출이 {len(where)}곳이다 ({', '.join(where)}) — 한 곳에서만"
            for (rid, mid), where in sites.items() if len(where) > 1]
    return out


def _names_grant(tokens, i: int) -> bool:
    """function M.grant( / function M:grant( / function grant( 처럼 grant 를 정의하는 function 인가."""
    return _declared_name(tokens, i) == "grant"


def _handlers(f) -> list[tuple[list[str], list, int, str]]:
    """원격 입력 처리 함수 — (매개변수, 본문, 알림 위치 토큰 번호, 문제). 못 찾으면 문제를 적어 보수적으로 실패시킨다.

    보는 꼴: X.OnServerEvent:Connect(function…) · :Connect(이름) · X.OnServerInvoke = function… · = 이름
    """
    toks, bodies, out = f.tokens, luau.function_bodies(f.tokens), []
    for i, t in enumerate(toks):
        if t.kind != NAME or t.text not in ("OnServerEvent", "OnServerInvoke"):
            continue
        after = toks[i + 1:i + 4]
        shape = [x.text for x in after]
        target = None
        if t.text == "OnServerEvent" and shape[:2] == [":", "Connect"]:
            target = i + 3
        elif t.text == "OnServerInvoke" and shape[:1] == ["="]:
            target = i + 2
        if target is None or target >= len(toks):
            out.append(([], [], i, f"{t.text} 를 Connect(함수)·= 함수 가 아닌 방식({' '.join(shape[:2])})으로 이었다 — 처리 함수를 검사할 수 없다"))
            continue
        arg = toks[target + 1] if toks[target].text == "(" else toks[target]
        if arg.kind == NAME and arg.text == "function":
            found = [b for b in bodies if b[2] == (target + 1 if toks[target].text == "(" else target)]
        elif arg.kind == NAME:
            found = [b for b in bodies if b[2] + 1 < len(toks) and toks[b[2] + 1].text == arg.text]
        else:
            found = []
        if not found:
            out.append(([], [], i, "처리 함수를 찾지 못했다"))
        else:
            out += [(params, body, i, "") for params, body, _ in found]
    return out


def _typeof_pairs(toks) -> list[tuple[str, str, str]]:
    """typeof(x) ~= "T" · typeof(x.f) == "T" 꼴에서 (검사한 이름, 요구한 종류, 비교 기호)."""
    pairs = []
    for k in range(len(toks) - 3):
        if not (toks[k].kind == NAME and toks[k].text == "typeof" and toks[k + 1].text == "(" and toks[k + 2].kind == NAME):
            continue
        name, j = toks[k + 2].text, k + 3
        while j + 1 < len(toks) and toks[j].text == "." and toks[j + 1].kind == NAME:
            name += "." + toks[j + 1].text
            j += 2
        if toks[j].text != ")" or j + 2 >= len(toks) or toks[j + 1].text not in ("~=", "==") or toks[j + 2].kind != STRING:
            continue
        pairs.append((name, toks[j + 2].text, toks[j + 1].text))
    return pairs


def _fields_used(body, name: str) -> set[str]:
    return {f"{name}.{body[k + 2].text}" for k in range(len(body) - 2)
            if body[k].kind == NAME and body[k].text == name and body[k + 1].text == "." and body[k + 2].kind == NAME}


def _if_spans(body, top_level_only: bool = True) -> list[tuple[int, int]]:
    """if 문의 (시작, 조건 끝=then). 기본은 처리 함수 맨 바깥의 if 만 — 어떤 경로로 와도 거치는 가드만 센다."""
    spans, depth, i = [], 0, 0
    while i < len(body):
        tok = body[i]
        if tok.kind == NAME and tok.text == "if":
            j = i + 1
            while j < len(body) and not (body[j].kind == NAME and body[j].text == "then"):
                j += 1
            if depth == 0 or not top_level_only:
                spans.append((i, j))
            depth += 1
            i = j + 1
            continue
        if tok.kind == NAME and tok.text in ("do", "function", "repeat"):
            depth += 1
        elif tok.kind == NAME and tok.text in ("end", "until"):
            depth = max(0, depth - 1)
        i += 1
    return spans


def _top_level_asserts(body) -> list[int]:
    """처리 함수 맨 바깥의 assert( 위치."""
    out, depth = [], 0
    for i, tok in enumerate(body):
        if tok.kind == NAME and tok.text in ("if", "do", "function", "repeat"):
            depth += 1
        elif tok.kind == NAME and tok.text in ("end", "until"):
            depth = max(0, depth - 1)
        elif depth == 0 and tok.kind == NAME and tok.text == "assert" and i + 1 < len(body) and body[i + 1].text == "(":
            out.append(i)
    return out


def _guards(body) -> dict[str, str]:
    """막는 형태의 typeof 가드로 보호되는 이름 → 요구한 종류. 처리 함수 맨 바깥의 가드만 센다(어떤 경로로 와도 거친다).

    `if typeof(p) ~= "T" [or …] then return/error` 와 `assert(typeof(p) == "T" [and …])` 만 인정한다.
    """
    guarded = {}
    for start, stop in _if_spans(body):
        cond, after = body[start + 1:stop], body[stop + 1:stop + 2]
        blocks = bool(after) and after[0].kind == NAME and after[0].text in BLOCKING
        pairs = _typeof_pairs(cond)
        if blocks and pairs and not any(x.kind == NAME and x.text == "and" for x in cond) and all(op == "~=" for _n, _k, op in pairs):
            guarded.update({name: kind for name, kind, _op in pairs})
    for i in _top_level_asserts(body):
        args = luau.balanced(body, i + 1)
        if not any(x.kind == NAME and x.text == "or" for x in args):
            guarded.update({name: kind for name, kind, op in _typeof_pairs(args) if op == "=="})
    return guarded


def _guard_positions(body) -> dict[str, int]:
    """막는 형태의 typeof 가드가 시작하는 자리 — 이름 → if 토큰 번호."""
    out = {}
    for start, stop in _if_spans(body):
        cond = body[start + 1:stop]
        after = body[stop + 1:stop + 2]
        blocks = bool(after) and after[0].kind == NAME and after[0].text in BLOCKING
        pairs = _typeof_pairs(cond)
        if blocks and pairs and not any(x.kind == NAME and x.text == "and" for x in cond) and all(op == "~=" for _n, _k, op in pairs):
            for name, _kind, _op in pairs:
                out.setdefault(name, start)
    for i in _top_level_asserts(body):
        args = luau.balanced(body, i + 1)
        if not any(x.kind == NAME and x.text == "or" for x in args):
            for name, _kind, op in _typeof_pairs(args):
                if op == "==":
                    out.setdefault(name, i)
    return out


LOW, HIGH = ("<", "<="), (">", ">=")


def _split_or(cond: list) -> list[list]:
    """조건을 맨 바깥 or 로 나눈다."""
    parts, cur, depth = [], [], 0
    for tok in cond:
        if tok.kind == SYMBOL and tok.text in ("(", "{", "["):
            depth += 1
        elif tok.kind == SYMBOL and tok.text in (")", "}", "]"):
            depth -= 1
        if depth == 0 and tok.kind == NAME and tok.text == "or":
            parts.append(cur)
            cur = []
        else:
            cur.append(tok)
    parts.append(cur)
    return parts


def _comparisons(part: list) -> list[tuple[str, str]]:
    """한 조각이 비교 하나뿐이면 (이름, 막는 방향) 목록.

    막는 가드이므로 `x < A` 는 A 보다 작은 값을 거른다 = x 의 하한, `x > A` 는 상한이다. 이름이 오른쪽이면 방향이 뒤집힌다.
    """
    ops = [k for k, tok in enumerate(part) if tok.kind == SYMBOL and tok.text in LOW + HIGH]
    if len(ops) != 1 or any(tok.kind == NAME and tok.text in ("and", "not") for tok in part):
        return []
    k = ops[0]
    before, after, op = part[:k], part[k + 1:], part[ops[0]].text
    out = []
    if len(before) == 1 and before[0].kind == NAME:
        out.append((before[0].text, "low" if op in LOW else "high"))
    if after and after[-1].kind == NAME and len([x for x in after if x.kind == NAME]) == 1:
        out.append((after[-1].text, "high" if op in LOW else "low"))
    return out


def _range_positions(body) -> dict[str, int]:
    """막는 형태의 범위 가드 — `if x < A or x > B then return end` 처럼 하한·상한을 or 로 걸러야 센다.

    `x < A and x > B` 처럼 둘 다여야 멈추는 조건은 성립할 수 없으므로 세지 않는다.
    """
    found: dict[str, dict[str, int]] = {}
    for start, stop in _if_spans(body):
        cond, after = body[start + 1:stop], body[stop + 1:stop + 2]
        if not (after and after[0].kind == NAME and after[0].text in BLOCKING):
            continue
        for part in _split_or(cond):
            for name, side in _comparisons(part):
                found.setdefault(name, {}).setdefault(side, start)
    return {name: max(sides.values()) for name, sides in found.items() if len(sides) == 2}


def _first_work(body, cooldown: tuple[str, ...]) -> int:
    """처리를 시작하는 첫 호출 — 가드 조건 밖에 있는, 검증·쿨다운이 아닌 호출."""
    guard_ranges = _if_spans(body)
    skip = {"typeof", "assert", "warn", "print", "error", cooldown[0]}   # 검증·쿨다운·로그는 '처리' 가 아니다
    for i, tok in enumerate(body):
        if tok.kind != NAME or i + 1 >= len(body) or body[i + 1].text not in ("(", ".", ":"):
            continue
        if tok.text in skip or any(start <= i <= stop for start, stop in guard_ranges):
            continue
        if body[i + 1].text in (".", ":"):
            if not (i + 2 < len(body) and body[i + 2].kind == NAME and i + 3 < len(body) and body[i + 3].text == "("):
                continue
        return i
    return len(body)


def remote_validation(tree, rules, config) -> list[str]:
    """원격 처리 함수는 player 다음 인자마다 형식(typeof)과 수의 범위를 막는 형태로, 처리를 시작하기 전에 거른다 (INV-4).

    상태 검증은 보상에 닿는 경로에서 server.reward_after_verdict 가 맡는다.
    """
    out, cooldown = [], tuple(config["cooldown_call"])
    for f in tree.luau:
        for params, body, i, problem in _handlers(f):
            where = _at(f, f.tokens[i])
            if problem:
                out.append(f"{where} {problem}")
                continue
            if f.client_visible:
                out.append(f"{where} 원격 이벤트 처리가 클라이언트가 볼 수 있는 코드에 있다")
            if "..." in params:
                out.append(f"{where} 가변 인자(...)는 형식을 검사할 수 없다 — 받는 값을 이름으로 적어야 한다")
            guarded, positions = _guards(body), _guard_positions(body)
            ranges, work = _range_positions(body), _first_work(body, cooldown)
            for p in params[1:]:
                if p == "...":
                    continue
                if p not in guarded:
                    out.append(f"{where} 원격 입력 {p} 를 막는 형태의 typeof 검사로 거르지 않는다")
                    continue
                if positions.get(p, len(body)) > work:
                    out.append(f"{where} 원격 입력 {p} 의 형식 검사가 처리를 시작한 뒤에 있다 — 쓰기 전에 걸러야 한다")
                if guarded[p] == "number" and ranges.get(p, len(body)) > work:
                    out.append(f"{where} 원격 입력 {p} 의 범위를 처리 전에 검사하지 않는다 (INV-4 타입·범위)")
                if guarded[p] == "table":
                    for field in sorted(_fields_used(body, p)):
                        if field not in guarded:
                            out.append(f"{where} 표로 받은 {field} 의 형식을 검사하지 않는다")
                        elif guarded[field] == "number" and ranges.get(field, len(body)) > work:
                            out.append(f"{where} 표로 받은 {field} 의 범위를 처리 전에 검사하지 않는다")
    return out


def remote_cooldown(tree, rules, config) -> list[str]:
    """원격 처리 함수는 처리를 시작하기 전에 쿨다운(cv.server_cooldown)의 결과로 멈춘다 — 값의 실측은 Q4."""
    path, out = tuple(config["cooldown_call"]), []
    for f in tree.luau:
        for _params, body, i, problem in _handlers(f):
            if problem:
                continue
            where, work = _at(f, f.tokens[i]), _first_work(body, path)
            blocking = [start for start, stop in _if_spans(body)
                        if luau.find_calls(body[start:stop], path) and body[stop + 1:stop + 2]
                        and body[stop + 1].kind == NAME and body[stop + 1].text in BLOCKING
                        and any(x.kind == NAME and x.text == "not" for x in body[start:stop])]
            if not luau.find_calls(body, path):
                out.append(f"{where} 원격 이벤트 처리가 {'.'.join(path)} 를 거치지 않는다 (연타·자동 반복 방지)")
            elif not blocking:
                out.append(f"{where} 쿨다운 결과로 멈추지 않는다 — if not {'.'.join(path)}(…) then return end 꼴이어야 한다")
            elif min(blocking) > work:
                out.append(f"{where} 쿨다운 검사가 처리를 시작한 뒤에 있다")
    return out


def reward_after_verdict(tree, rules, config) -> list[str]:
    """원격 처리에서 보상에 닿는 호출은 서버 판정의 결과 안에서만 — 클라이언트가 '다 했다'고 알린다고 보상하지 않는다 (INV-4)."""
    module, verdicts, out = config["reward_module"], [tuple(v) for v in config["verdict_calls"]], []
    reaching = reward_reaching(tree, module)
    for f in tree.luau:
        for _params, body, i, problem in _handlers(f):
            if problem:
                continue
            calls = set(luau.find_calls(body, (module, "grant"))) | {k for k in range(len(body))
                       if body[k].kind == NAME and body[k].text in reaching and k + 1 < len(body) and body[k + 1].text == "("}
            calls |= {k for k in range(len(body) - 2) if body[k + 2].kind == NAME and body[k + 2].text in reaching and body[k + 1].text == "."}
            for k in sorted(calls):
                if not _inside_verdict(body, k, verdicts):
                    out.append(f"{_at(f, f.tokens[i])} 원격 처리가 서버 판정({' · '.join('.'.join(v) for v in verdicts)}) 없이 보상에 닿는다 "
                               f"— 클라이언트가 완료를 정하면 안 된다")
    return out


def _inside_verdict(body, index: int, verdicts) -> bool:
    """index 의 호출이 `if <판정 호출> ... then … end` 안에 있는가."""
    for start in range(index):
        if not (body[start].kind == NAME and body[start].text == "if"):
            continue
        j = start + 1
        while j < len(body) and not (body[j].kind == NAME and body[j].text == "then"):
            j += 1
        cond = body[start:j]
        if not any(luau.find_calls(cond, v) for v in verdicts) or any(x.kind == NAME and x.text == "not" for x in cond):
            continue   # 판정이 거짓일 때 들어가는 가지는 보상 자리가 아니다
        depth, k = 1, j + 1
        while k < len(body) and depth:
            if body[k].kind == NAME and body[k].text in ("if", "do", "function", "repeat"):
                depth += 1
            elif body[k].kind == NAME and body[k].text in ("end", "until"):
                depth -= 1
            elif depth == 1 and body[k].kind == NAME and body[k].text in ("else", "elseif"):
                break   # 판정이 참일 때 들어가는 가지(then)만 보상 자리다
            if depth and k == index:
                return True
            k += 1
    return False


__all__ = ["reward_authority", "duplicate_reward", "remote_validation", "remote_cooldown", "reward_after_verdict",
           "grant_calls", "reward_reaching", "SYMBOL"]
