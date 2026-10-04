"""서버 권위 검사 (INV-4 · K3 §5). 보상·저장은 보상 모듈만 정하고, 완료·수령은 한 번만,
원격 입력은 막는 형태로 형식을 검사하고 쿨다운을 거치며, 보상은 서버 판정 뒤에만 준다."""
from __future__ import annotations

from harness import luau, resolve, source
from harness.checks import i18n
from harness.luau import NAME, NUMBER, STRING, SYMBOL

BLOCKING = ("return", "error")   # 조건이 맞지 않을 때 멈추는 말


def _at(f, tok) -> str:
    return f"{f.rel}:{tok.line}"


def _module_names(f, module: str) -> set[str]:
    return luau.require_aliases(f.tokens, module) | resolve.names_for(f.resolved, (module,))


def _grant_aliases(f, module_names: set[str]) -> set[tuple[str, ...]]:
    """grant 를 부르는 이름 경로 — M.grant 들과, 몇 단계를 거쳐 그 함수를 담은 이름들."""
    paths = {(name, "grant") for name in module_names}
    for name in module_names:
        paths |= {(alias,) for alias in resolve.names_for(f.resolved, (name, "grant")) if alias != name}
    return paths


def grant_calls(f, module: str) -> list[int]:
    """이 파일에서 보상을 주는 호출 위치(별칭 포함)."""
    return sorted(i for path in _grant_aliases(f, _module_names(f, module)) for i in luau.find_calls(f.tokens, path))


def reward_reaching(tree, module: str) -> set[str]:
    """보상에 닿는 함수 이름 — 직접 grant 를 부르는 함수와, 그런 함수를 부르는 함수까지 끝까지(전이 폐포)."""
    bodies = []   # (이름, 본문 토큰 번호 구간, 파일)
    names = set()
    for f in tree.luau:
        calls, spans = set(grant_calls(f, module)), _function_spans(f.tokens)
        for start, end in spans:
            named = _declared_name(f.tokens, start)
            if not named and start >= 2 and f.tokens[start - 1].text == "=" and f.tokens[start - 2].kind == NAME:
                named = f.tokens[start - 2].text
            if not named:
                continue
            bodies.append((named, start, end, f))
            if any(start <= i < end for i in calls):
                names.add(named)
    for _round in range(6):
        before = set(names)
        for named, start, end, f in bodies:
            if named in names:
                continue
            body = f.tokens[start:end]
            if any(tok.kind == NAME and tok.text in names and k + 1 < len(body) and body[k + 1].text == "(" for k, tok in enumerate(body)) \
                    or any(tok.kind == NAME and tok.text in names and k and body[k - 1].text == "." for k, tok in enumerate(body)):
                names.add(named)
        if names == before:
            break
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
    path, trusted = config["reward_module_path"], _trusted_reward_file(tree, config)
    if trusted is None:
        out.append(f"보상 모듈은 {path} 의 ModuleScript 하나여야 한다 — 그 파일만 보상·저장 권한을 쓸 수 있다")
    for f in tree.luau:
        if f is trusted:
            continue
        out += [f"{_at(f, f.tokens[i])} 보상 모듈 {module} 을 표·멤버에 담는다 — 이름 하나에 담아야 어디서 보상을 주는지 검사할 수 있다"
                for i, name in luau.indirect_requires(f.tokens) if name == module]
        if f.client_visible:
            out += [f"{_at(f, f.tokens[i])} 클라이언트가 볼 수 있는 코드가 보상 지급 {module}.grant 를 부른다 — 보상은 서버만 정한다"
                    for i in grant_calls(f, module)]
        if f.name == module:
            reason = f"클라이언트가 볼 수 있는 곳({f.container})에 있다" if f.client_visible else f"정해진 자리({path})의 ModuleScript 가 아니다"
            out.append(f"{f.rel}:1 보상 모듈과 같은 이름인데 {reason} — 권한을 믿을 수 없다")
        where = "클라이언트 코드" if f.client_visible else "보상 모듈 밖 서버 코드"
        out += [f"{_at(f, t)} {where}가 보상·저장 권한 {t.text} 를 쓴다 — 보상은 {module} 만 정한다" for t in f.tokens
                if t.text in names and t.kind in (NAME, STRING)]
        out += [f"{_at(f, f.tokens[i])} {where}가 {name} 의 멤버를 값을 알 수 없는 방식으로 고른다 — 보상·저장 권한인지 검사할 수 없다"
                for i, name in resolve.dynamic_member_calls(f, _player_like(f, config))]
    return out


def _trusted_reward_file(tree, config):
    """보상·저장 권한을 쓸 수 있는 단 하나의 파일."""
    return source.trusted_module(tree, config["reward_module_path"], config["reward_module"])


def _player_params(f) -> set[str]:
    """`function f(actor: Player, …)` 처럼 Player 로 적은 매개변수 — 이름을 바꿔도 플레이어다 (리뷰 R-Q3 30차)."""
    toks = f.tokens
    return {toks[i - 2].text for i in range(2, len(toks))
            if toks[i].kind == NAME and toks[i].text == "Player" and toks[i - 1].text == ":" and toks[i - 2].kind == NAME}


def _player_like(f, config) -> set[str]:
    """플레이어·서비스를 가리키는 이름 — 설정의 이름, Player 매개변수, 거기에 담긴 다른 이름."""
    base = set(config["player_variable_names"]) | {"game", "workspace"} | _player_params(f)
    return base | {name for name, value in f.resolved.items() if isinstance(value, tuple) and len(value) == 1 and value[0] in base}


def duplicate_reward(tree, rules, config) -> list[str]:
    """보상 모듈의 grant 는 맨 앞에서 claimOnce 로 한 번만 지급을 보장하고, 같은 보상 id 를 주는 호출 자리는 하나뿐이다."""
    module, out, sites = config["reward_module"], [], {}
    values = {v["id"]: v.get("value") for v in rules.canonical.get("values", []) if isinstance(v, dict)}
    named = {k[: -len(".name")] for k in (rules.glossary.get("strings") or {}) if k.startswith(("reward.", "unlock.")) and k.endswith(".name")}
    rewards = set(values.get("cv.first_rewards") or []) | named
    missions = set((rules.events.get("fields") or {}).get("mission") or [])
    trusted = _trusted_reward_file(tree, config)
    owners = [trusted] if trusted is not None else []
    if trusted is None:
        out.append(f"보상 모듈 {module} 이 없다 (정해진 자리 {config['reward_module_path']} 의 ModuleScript 하나여야 한다)")
    for f in owners:
        out += _claim_once_errors(f)
        grants = [(p, body, i) for p, body, i in luau.function_bodies(f.tokens) if _names_grant(f.tokens, i)]
        if not grants:
            out.append(f"{f.rel}:1 {module}.grant 함수가 없다")
        for _params, body, i in grants:
            texts = [x.text for x in body]
            then = texts.index("then") if "then" in texts else -1
            called = len(body) > 3 and body[3].text == "(" and len(luau.call_args(body, 2)) >= 1
            if texts[:3] != ["if", "not", "claimOnce"] or not called or then < 0 or texts[then + 1:then + 2] != ["return"]:
                out.append(f"{_at(f, f.tokens[i])} grant 가 맨 앞에서 'if not claimOnce(…) then return' 으로 중복 지급을 막지 않는다(실제 호출이어야 한다)")
    for f in tree.luau:
        out += [f"{f.rel}:{f.tokens[i].line} 보상 모듈 {name} 의 멤버를 값을 알 수 없는 방식으로 고른다 — 어떤 함수인지 검사할 수 없다"
                for i, name in resolve.dynamic_member_calls(f, _module_names(f, module))]
        if f.name != module:
            out += [f"{f.rel}:{f.tokens[i].line} {what} — 보상 지급은 `{module}.grant(…)` 로 바로 부른다(사람 결정 Q3-SHAPE-RULES)"
                    for i, what in resolve.shape_violations(f, module, {"grant"})]
        for i in grant_calls(f, module):
            args = luau.call_args(f.tokens, i)
            literal = [a[0] if len(a) == 1 and a[0].kind == STRING else None for a in args]
            if len(args) < 3 or literal[1] is None or literal[2] is None:
                out.append(f"{_at(f, f.tokens[i])} 보상 id 와 미션 id 는 글자 그대로 써야 한다(누구에게 무엇을 주는지 정적으로 알 수 있게)")
                continue
            reward_id, mission_id = literal[1].text, literal[2].text
            if reward_id not in rewards:
                out.append(f"{_at(f, f.tokens[i])} 보상 {reward_id} 가 잠긴 명세의 보상 목록(cv.first_rewards · 용어집의 보상 이름)에 없다")
            if mission_id not in missions:
                out.append(f"{_at(f, f.tokens[i])} 미션 {mission_id} 가 잠긴 명세의 미션 목록에 없다")
            sites.setdefault((reward_id, mission_id), []).append(_at(f, f.tokens[i]))
    out += [f"{where[1]} 보상 {rid}({mid})를 주는 호출이 {len(where)}곳이다 ({', '.join(where)}) — 한 곳에서만"
            for (rid, mid), where in sites.items() if len(where) > 1]
    return out


CLAIM_ONCE_SHAPE = "if 표[키] then return false end · 표[키] = true · return true"


def _claim_once_shape(body, tables: set[str]) -> bool:
    """claimOnce 본문이 정해진 꼴인가 (사람 결정 Q3-SHAPE-RULES).

    앞에는 `local` 선언만 올 수 있고, 그 뒤는 정확히
    `if T[K] then return false end` · `T[K] = true` · `return true` 다. T 는 모듈의 표, K 는 두 곳에서 같은 식.
    여러 조건을 하나씩 보던 방식(읽기·표시·거부·순서·되돌림)은 변형마다 구멍이 났다 — 꼴 하나만 받는다.
    """
    if body and body[0].text == ":":
        body = [x for x in body if x.line != body[0].line]   # 반환 형 표기(`: boolean`)는 본문이 아니다
    texts = [x.text for x in body]
    start = next((k for k, x in enumerate(body) if x.kind == NAME and x.text == "if"), None)
    if start is None:
        return False
    lines = {x.line for x in body[:start]}
    if any(next(x for x in body[:start] if x.line == line).text != "local" for line in lines):
        return False   # if 앞에는 local 선언만
    rest = texts[start:]
    if len(rest) < 4 or rest[1] not in tables or rest[2] != "[":
        return False
    close = start + 2 + len(luau.balanced(body, start + 2)) - 1
    key = texts[start + 3:close]
    after = texts[close + 1:]
    want = ["then", "return", "false", "end", rest[1], "[", *key, "]", "=", "true", "return", "true"]
    return after == want


def _claim_once_errors(f) -> list[str]:
    """claimOnce 가 정해진 꼴로 '한 번만' 을 지키는지 (사람 결정 Q3-SHAPE-RULES)."""
    tables = i18n._table_names(f)
    for _params, body, i in luau.function_bodies(f.tokens):
        if _declared_name(f.tokens, i) != "claimOnce":
            continue
        if _claim_once_shape(body, tables):
            return []
        return [f"{_at(f, f.tokens[i])} claimOnce 가 정해진 꼴이 아니다 — `{CLAIM_ONCE_SHAPE}` 로만 쓴다(그래야 한 번만 주는지 검사할 수 있다)"]
    return [f"{f.rel}:1 보상 모듈에 claimOnce 함수가 없다 — 중복 지급을 막는 자리를 검사할 수 없다"]


def _names_grant(tokens, i: int) -> bool:
    """function M.grant( / function M:grant( / function grant( 처럼 grant 를 정의하는 function 인가."""
    return _declared_name(tokens, i) == "grant"


def _is_surely_not_a_function(f, start: int, config) -> bool:
    """그 자리의 값이 함수가 아님을 확정할 수 있는가 — 글자·수 리터럴, 풀리는 값, 표 리터럴, 허용된 문구 키 호출.

    확정하지 못하면 거부한다. 함수일 수도 있는 값을 멤버에 담으면 어떤 원격에 무엇을 이었는지 알 수 없다.
    """
    tok = f.tokens[start]
    if tok.kind in (STRING, NUMBER) or (tok.kind == SYMBOL and tok.text == "{"):
        return True
    if tok.kind == NAME and isinstance(f.resolved.get(tok.text), (str, float)):
        return True
    return start in {i for i, _args in i18n._key_calls(f, config)}


def _handlers(f, config) -> list[tuple[list[str], list, int, str]]:
    """원격 입력 처리 함수 — (원격 이름, 매개변수, 본문, 알림 위치 토큰 번호, 문제). 못 찾으면 문제를 적어 보수적으로 실패시킨다.

    보는 꼴: X.OnServerEvent:Connect(function…) · :Connect(이름) · X.OnServerInvoke = function… · = 이름
    """
    toks, bodies, out = f.tokens, luau.function_bodies(f.tokens), []
    for i, _rhs, key in i18n._bracket_assignments(f):
        close = i + 1
        while close < len(toks) and not (toks[close].kind == SYMBOL and toks[close].text == "["):
            close += 1
        rhs = close + len(luau.balanced(toks, close)) + 1
        if not isinstance(key, str) and rhs < len(toks) and not _is_surely_not_a_function(f, rhs, config):
            out.append(("?", [], [], i, f"값을 알 수 없는 멤버({toks[i].text}[…])에 처리 함수를 대입했다 — 어떤 원격인지 검사할 수 없다"))
    for i, tok in enumerate(toks):
        if not (tok.kind == NAME and tok.text in ("Connect", "Once", "ConnectParallel") and i and toks[i - 1].text == ":"):
            continue
        before = toks[i - 2] if i >= 2 else None
        if before is not None and before.text == "]":
            out.append(("?", [], [], i, "값을 알 수 없는 멤버에 처리 함수를 이었다 — 어떤 원격인지 검사할 수 없다"))
        elif before is not None and before.kind == NAME and (i < 4 or toks[i - 3].text != "."):
            out.append(("?", [], [], i, f"연결 대상 {before.text} 가 멤버 경로가 아니다 — 어떤 신호에 이은 것인지 검사할 수 없다"))
    for i, t in enumerate(toks):
        if t.kind != NAME or t.text not in ("OnServerEvent", "OnServerInvoke"):
            continue
        remote = toks[i - 2].text if i >= 2 and toks[i - 1].text == "." and toks[i - 2].kind == NAME else "?"
        after = toks[i + 1:i + 4]
        shape = [x.text for x in after]
        target = None
        if t.text == "OnServerEvent" and shape[:2] == [":", "Connect"]:
            target = i + 3
        elif t.text == "OnServerInvoke" and shape[:1] == ["="]:
            target = i + 2
        if target is None or target >= len(toks):
            out.append((remote, [], [], i, f"{t.text} 를 Connect(함수)·= 함수 가 아닌 방식({' '.join(shape[:2])})으로 이었다 — 처리 함수를 검사할 수 없다"))
            continue
        arg = toks[target + 1] if toks[target].text == "(" else toks[target]
        if arg.kind == NAME and arg.text == "function":
            found = [b for b in bodies if b[2] == (target + 1 if toks[target].text == "(" else target)]
        elif arg.kind == NAME:
            found = [b for b in bodies if b[2] + 1 < len(toks) and toks[b[2] + 1].text == arg.text]
        else:
            found = []
        if not found:
            out.append((remote, [], [], i, "처리 함수를 찾지 못했다"))
        else:
            out += [(remote, params, body, i, "") for params, body, _ in found]
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


def _comparisons(part: list) -> list[tuple[str, str, str]]:
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
        out.append((before[0].text, "low" if op in LOW else "high", op))
    if after and after[-1].kind == NAME and len([x for x in after if x.kind == NAME]) == 1:
        out.append((after[-1].text, "high" if op in LOW else "low", op))
    return out


def _range_positions(body, constants: dict | None = None) -> dict[str, tuple[int, float | None, float | None]]:
    """막는 형태의 범위 가드 — `if x < A or x > B then return end` 처럼 하한·상한을 or 로 걸러야 센다.

    `x < A and x > B` 처럼 둘 다여야 멈추는 조건은 성립할 수 없으므로 세지 않는다.
    """
    constants, found = constants or {}, {}
    for start, stop in _if_spans(body):
        cond, after = body[start + 1:stop], body[stop + 1:stop + 2]
        if not (after and after[0].kind == NAME and after[0].text in BLOCKING):
            continue
        for part in _split_or(cond):
            for name, side, op in _comparisons(part):
                found.setdefault(name, {}).setdefault(side, (start, _bound_value(part, constants), op))
    out = {}
    for name, sides in found.items():
        if len(sides) == 2:
            low, high = sides["low"], sides["high"]
            # `x < A` 는 A 미만을 거르므로 허용 하한이 A, `x <= A` 는 A 도 걸러 하한이 A+1 이다(정수 격자)
            out[name] = (max(low[0], high[0]),
                         None if low[1] is None else low[1] + (1 if low[2] in ("<=",) else 0),
                         None if high[1] is None else high[1] - (1 if high[2] in (">=",) else 0))
    return out


def number_constants(tokens) -> dict[str, float]:
    """`local GRID = 2` 처럼 수에 묶인 이름 → 값. 가드의 경계를 계약과 견주려면 이 값이 필요하다."""
    out = {}
    for i in range(len(tokens) - 3):
        if tokens[i].kind == NAME and tokens[i].text == "local" and tokens[i + 1].kind == NAME and tokens[i + 2].text == "=":
            sign, k = 1, i + 3
            if tokens[k].text == "-":
                sign, k = -1, k + 1
            if tokens[k].kind == NUMBER:
                out[tokens[i + 1].text] = sign * float(tokens[k].text)
    return out


def _bound_value(part, constants) -> float | None:
    """비교 조각의 경계 수 — -GRID · 2 · -2 처럼 적은 값."""
    sign, toks = 1, [x for x in part if not (x.kind == SYMBOL and x.text in LOW + HIGH)]
    out = None
    for tok in toks:
        if tok.kind == SYMBOL and tok.text == "-":
            sign = -sign
        elif tok.kind == NUMBER:
            out = sign * float(tok.text)
        elif tok.kind == NAME and tok.text in constants:
            out = sign * constants[tok.text]
    return out


def _first_work(body, cooldown: tuple[str, ...]) -> int:
    """처리를 시작하는 첫 호출 — 가드 조건 밖에 있는, 검증·쿨다운이 아닌 호출."""
    guard_ranges = _if_spans(body)
    skip = {"typeof", "assert", "warn", "print", "error", cooldown[0]}   # 검증·쿨다운·로그는 '처리' 가 아니다
    for i, tok in enumerate(body):
        if any(start <= i <= stop for start, stop in guard_ranges):
            continue
        if tok.kind == NAME and tok.text == "local" and i + 2 < len(body) and body[i + 2].text == "=":
            return i   # 받은 값으로 계산해 담는 것도 처리의 시작이다
        if tok.kind == SYMBOL and tok.text == "=" and i and body[i - 1].kind == NAME and body[i - 1].text not in skip \
                and (i < 2 or body[i - 2].text != "local") and (i + 1 >= len(body) or body[i + 1].text != "="):
            return max(0, i - 1)   # 전역·속성·표에 담는 것도 처리의 시작이다 (local 만 보면 비켜 간다)
        if tok.kind != NAME or i + 1 >= len(body) or body[i + 1].text not in ("(", ".", ":"):
            continue
        if tok.text in skip:
            continue
        if body[i + 1].text in (".", ":"):
            if not (i + 2 < len(body) and body[i + 2].kind == NAME and i + 3 < len(body) and body[i + 3].text == "("):
                continue
            if body[i + 2].text in skip:
                continue
        return i
    return len(body)


def remote_validation(tree, rules, config) -> list[str]:
    """원격 처리 함수는 계약(content/remote_contracts.yaml)대로 형식·범위를 처리 전에 막는 형태로 거른다 (INV-4).

    계약의 범위는 잠긴 Q2 정본 값과 같아야 하고, 코드의 경계 수는 계약과 같아야 한다. 상태 검증은 server.reward_after_verdict 가 맡는다.
    """
    out, cooldown = [], tuple(config["cooldown_call"])
    out += _contract_errors(tree, rules)
    for f in tree.luau:
        constants = {k: v for k, v in f.resolved.items() if isinstance(v, float)}
        for remote, params, body, i, problem in _handlers(f, config):
            where = _at(f, f.tokens[i])
            if problem:
                out.append(f"{where} {problem}")
                continue
            if f.client_visible:
                out.append(f"{where} 원격 이벤트 처리가 클라이언트가 볼 수 있는 코드에 있다")
            if "..." in params:
                out.append(f"{where} 가변 인자(...)는 형식을 검사할 수 없다 — 받는 값을 이름으로 적어야 한다")
            out += [f"{where} {problem}" for problem in _dynamic_reads(f, body)]
            contract = tree.contracts.get(remote)
            if contract is None:
                out.append(f"{where} 원격 {remote} 의 입력 계약이 content/remote_contracts.yaml 에 없다")
                contract = []
            elif not isinstance(contract, list):
                out.append(f"{where} 원격 {remote} 의 입력 계약을 받는 값 목록으로 읽을 수 없다 — 형식·범위를 검사할 수 없다")
                contract = []
            elif len(contract) != len([p for p in params[1:] if p != "..."]):
                out.append(f"{where} 원격 {remote} 가 받는 값의 수가 계약({len(contract)})과 다르다")
            guarded, positions = _guards(body), _guard_positions(body)
            ranges, work = _range_positions(body, constants), _first_work(body, cooldown)
            for n, p in enumerate([p for p in params[1:] if p != "..."]):
                want = contract[n] if n < len(contract) else {}
                if not isinstance(want, dict):
                    out.append(f"{where} 원격 {remote} 의 {n + 1}번째 받는 값 계약이 이름 = 값 표가 아니다 — 형식·범위를 검사할 수 없다")
                    continue
                out += _param_errors(where, p, want, guarded, positions, ranges, work, body, constants)
    return out


def _dynamic_reads(f, body) -> list[str]:
    """처리 함수 안에서 값을 알 수 없는 키로 읽는 자리 — 계약의 어느 필드를 쓰는지 알 수 없으므로 거부한다.

    `local t = {}` 로 만든 제 표에서 꺼내는 것은 받은 입력이 아니므로 뺀다.
    """
    tables, out = i18n._table_names(f), []
    for j, tok in enumerate(body):
        if not (tok.kind == SYMBOL and tok.text == "["):
            continue
        before = body[j - 1] if j else None
        if before is not None and before.kind == NAME and before.text in tables:
            continue
        key, _has_text = resolve.expression_value(body, j + 1, f.resolved)
        if not isinstance(key, (str, float)):
            out.append("받은 입력을 값을 알 수 없는 키로 읽는다 — 계약의 어느 필드인지 검사할 수 없다")
    return out


def _param_errors(where, name, want, guarded, positions, ranges, work, body, constants) -> list[str]:
    out, kind = [], want.get("type")
    if name not in guarded:
        return [f"{where} 원격 입력 {name} 를 막는 형태의 typeof 검사로 거르지 않는다"]
    if kind and guarded[name] != kind:
        out.append(f"{where} 원격 입력 {name} 를 {guarded[name]} 로 검사하지만 계약은 {kind} 다")
    if positions.get(name, len(body)) > work:
        out.append(f"{where} 원격 입력 {name} 의 형식 검사가 처리를 시작한 뒤에 있다 — 쓰기 전에 걸러야 한다")
    elif name in ranges and positions.get(name, len(body)) > ranges[name][0]:
        out.append(f"{where} 원격 입력 {name} 의 형식 검사가 범위 검사보다 뒤에 있다 — 수인지 먼저 확인해야 한다")
    if guarded[name] == "number":
        got = ranges.get(name)
        if got is None or got[0] > work:
            out.append(f"{where} 원격 입력 {name} 의 범위를 처리 전에 검사하지 않는다 (INV-4 타입·범위)")
        elif (got[1], got[2]) != (want.get("min"), want.get("max")):
            out.append(f"{where} 원격 입력 {name} 의 범위 가드({got[1]}~{got[2]})가 계약({want.get('min')}~{want.get('max')})과 다르다")
    if guarded[name] == "table":
        # 표 필드의 범위 가드는 아직 경계 수를 읽지 못한다 — 그래서 넓든 좁든 '처리 전에 검사하지 않는다' 로 거부된다(보수적)
        for field in sorted(_fields_used(body, name)):
            if field not in guarded:
                out.append(f"{where} 표로 받은 {field} 의 형식을 검사하지 않는다")
            elif guarded[field] == "number" and (ranges.get(field) is None or ranges[field][0] > work):
                out.append(f"{where} 표로 받은 {field} 의 범위를 처리 전에 검사하지 않는다")
    return out


def _contract_errors(tree, rules) -> list[str]:
    """계약의 범위가 잠긴 Q2 정본 값과 같은지 — 게임 격자를 벗어난 임의의 경계를 쓰지 못하게."""
    values = {v["id"]: v.get("value") for v in rules.canonical.get("values", []) if isinstance(v, dict)}
    out = []
    for remote, params in sorted(tree.contracts.items()):
        if not isinstance(params, list):
            out.append(f"원격 계약 {remote}: 받는 값 목록이어야 한다")
            continue
        for want in params:
            if not isinstance(want, dict) or not want.get("name") or not want.get("type"):
                out.append(f"원격 계약 {remote}: 받는 값마다 이름과 종류를 적어야 한다")
                continue
            nested = [dict(x, name=f"{want['name']}.{x.get('name')}") for x in (want.get("fields") or []) if isinstance(x, dict)]
            out += _contract_errors_for(remote, nested, values)
            if want["type"] != "number":
                continue
            ref = want.get("canonical")
            bounds = _dotted(values, ref) if ref else None
            if not (isinstance(bounds, list) and len(bounds) == 2):
                out.append(f"원격 계약 {remote}.{want['name']}: 수 입력은 정본 값(canonical)의 범위를 가리켜야 한다")
            elif [want.get("min"), want.get("max")] != list(bounds):
                out.append(f"원격 계약 {remote}.{want['name']}: 범위({want.get('min')}~{want.get('max')})가 정본 값 {ref}({bounds})와 다르다")
    return out


def _contract_errors_for(remote: str, params: list[dict], values: dict) -> list[str]:
    """표로 받는 값의 필드 계약도 정본 값과 대조한다 (리뷰 R-Q3 31차)."""
    out = []
    for want in params:
        if want.get("type") != "number":
            continue
        ref = want.get("canonical")
        bounds = _dotted(values, ref) if ref else None
        if not (isinstance(bounds, list) and len(bounds) == 2):
            out.append(f"원격 계약 {remote}.{want['name']}: 수 입력은 정본 값(canonical)의 범위를 가리켜야 한다")
        elif [want.get("min"), want.get("max")] != list(bounds):
            out.append(f"원격 계약 {remote}.{want['name']}: 범위({want.get('min')}~{want.get('max')})가 정본 값 {ref}({bounds})와 다르다")
    return out


def _dotted(values: dict, path: str):
    parts = str(path).split(".")
    node = values.get(".".join(parts[:2]))
    for part in parts[2:]:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def remote_cooldown(tree, rules, config) -> list[str]:
    """원격 처리 함수는 처리를 시작하기 전에 쿨다운(cv.server_cooldown)의 결과로 멈춘다 — 값의 실측은 Q4."""
    path, out = tuple(config["cooldown_call"]), []
    for f in tree.luau:
        for remote, _params, body, i, problem in _handlers(f, config):
            if problem:
                continue
            where, work = _at(f, f.tokens[i]), _first_work(body, path)
            blocking = [start for start, stop in _if_spans(body)
                        if _is_sole_cooldown_guard(body, start, stop, path)]
            if not luau.find_calls(body, path):
                out.append(f"{where} 원격 이벤트 처리가 {'.'.join(path)} 를 거치지 않는다 (연타·자동 반복 방지)")
            elif not blocking:
                out.append(f"{where} 쿨다운 결과로 멈추지 않는다 — if not {'.'.join(path)}(…) then return end 꼴이어야 한다")
            elif min(blocking) > work:
                out.append(f"{where} 쿨다운 검사가 처리를 시작한 뒤에 있다")
    return out


def _is_sole_cooldown_guard(body, start: int, stop: int, path: tuple[str, ...]) -> bool:
    """조건이 `not <쿨다운 호출>` 하나뿐이고 실패하면 바로 멈추는가 — 다른 조건과 and/or 로 섞이면 모든 경로를 막지 못한다."""
    cond, after = body[start + 1:stop], body[stop + 1:stop + 2]
    if not (after and after[0].kind == NAME and after[0].text in BLOCKING):
        return False
    if not cond or not (cond[0].kind == NAME and cond[0].text == "not") or luau.find_calls(cond, path) != [1]:
        return False
    call = luau.balanced(cond, 1 + len(path) * 2 - 1) if len(cond) > len(path) * 2 else []
    return bool(call) and len(cond) == 1 + len(path) * 2 - 1 + len(call)   # not <호출 하나> 뿐이어야 한다


def self_verdicting(tree, verdicts, module: str, reaching: set[str]) -> set[str]:
    """스스로 판정을 거쳐 보상하는 함수 — 그 함수 안의 보상이 모두 판정의 참 가지 안에 있을 때만. 부르는 쪽은 판정을 또 하지 않아도 된다."""
    names = set()
    for f in tree.luau:
        aliases = _grant_aliases(f, _module_names(f, module))
        for start, end in _function_spans(f.tokens):
            named = _declared_name(f.tokens, start)
            if not named and start >= 2 and f.tokens[start - 1].text == "=" and f.tokens[start - 2].kind == NAME:
                named = f.tokens[start - 2].text
            body = f.tokens[start:end]
            rewards = {k for alias in aliases for k in luau.find_calls(body, alias)}
            rewards |= {k for k, tok in enumerate(body) if tok.kind == NAME and tok.text in reaching and tok.text != named
                        and ((k + 1 < len(body) and body[k + 1].text == "(") or (k and body[k - 1].text == "."))}
            if named and rewards and any(luau.find_calls(body, v) for v in verdicts) \
                    and all(_inside_verdict(body, k, verdicts) for k in rewards):
                names.add(named)
    return names


def reward_after_verdict(tree, rules, config) -> list[str]:
    """원격 처리에서 보상에 닿는 호출은 서버 판정의 결과 안에서만 — 클라이언트가 '다 했다'고 알린다고 보상하지 않는다 (INV-4)."""
    module, verdicts, out = config["reward_module"], [tuple(v) for v in config["verdict_calls"]], []
    reaching_all = reward_reaching(tree, module)
    reaching = reaching_all - self_verdicting(tree, verdicts, module, reaching_all)
    for f in tree.luau:
        for remote, _params, body, i, problem in _handlers(f, config):
            if problem:
                continue
            calls = {k for alias in _grant_aliases(f, _module_names(f, module)) for k in luau.find_calls(body, alias)} | {k for k in range(len(body))
                       if body[k].kind == NAME and body[k].text in reaching and k + 1 < len(body) and body[k + 1].text == "("}
            calls |= {k for k in range(len(body) - 2) if body[k + 2].kind == NAME and body[k + 2].text in reaching and body[k + 1].text == "."}
            for k in sorted(calls):
                if not _inside_verdict(body, k, verdicts):
                    out.append(f"{_at(f, f.tokens[i])} 원격 처리가 서버 판정({' · '.join('.'.join(v) for v in verdicts)}) 없이 보상에 닿는다 "
                               f"— 클라이언트가 완료를 정하면 안 된다")
    return out


def _is_exact_verdict(cond, verdicts) -> bool:
    """조건이 판정 호출 하나뿐인가 — `if M.verdict(…) then` 만 판정 성공으로 본다 (사람 결정 Q3-SHAPE-RULES).

    부정·비교(== nil · == false · ~= true …)·다른 조건과 섞은 꼴은 모두 판정 성공으로 보지 않는다.
    하나씩 막던 변형을 '검사할 수 있는 꼴 하나' 로 바꾼 것이다.
    """
    for v in verdicts:
        if luau.find_calls(cond, v) != [0]:
            continue
        opened = next((k for k in range(len(cond)) if cond[k].kind == SYMBOL and cond[k].text == "("), None)
        if opened is not None and opened + len(luau.balanced(cond, opened)) == len(cond):
            return True
    return False


def _inside_verdict(body, index: int, verdicts) -> bool:
    """index 의 호출이 `if <판정 호출> ... then … end` 안에 있는가."""
    for start in range(index):
        if not (body[start].kind == NAME and body[start].text == "if"):
            continue
        j = start + 1
        while j < len(body) and not (body[j].kind == NAME and body[j].text == "then"):
            j += 1
        if not _is_exact_verdict(body[start + 1:j], verdicts):
            continue   # 조건이 판정 호출 하나가 아니면 보상 자리가 아니다
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
