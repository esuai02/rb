"""서버 권위 검사 (INV-4 · K3 §5). 보상·저장은 서버만 정하고, 완료·수령은 한 번만, 원격 입력은 형식을 검사하고 쿨다운을 거친다."""
from __future__ import annotations

from harness import luau
from harness.luau import NAME, STRING


def _at(f, tok) -> str:
    return f"{f.rel}:{tok.line}"


def client_reward(tree, rules, config) -> list[str]:
    """클라이언트가 실행하거나 require 할 수 있는 코드는 보상·저장 권한 이름을 쓰지 않는다. 보상 모듈은 서버 전용 위치에 있다."""
    names, module = set(config["authority_names"]), config["reward_module"]
    out = []
    for f in tree.luau:
        if f.rel.rsplit("/", 1)[-1].split(".")[0] == module and f.client_visible:
            out.append(f"{f.rel}:1 보상 모듈 {module} 이 클라이언트가 볼 수 있는 곳({f.container})에 있다")
        if not f.client_visible:
            continue
        out += [f"{_at(f, t)} 클라이언트 코드가 보상·저장 권한 {t.text} 를 쓴다" for t in f.tokens if t.text in names and t.kind in (NAME, STRING)]
    return out


def _grant_calls(f, module: str) -> list[int]:
    return luau.find_calls(f.tokens, (module, "grant"))


def duplicate_reward(tree, rules, config) -> list[str]:
    """보상 모듈의 grant 는 맨 앞에서 claimOnce 로 한 번만 지급을 보장하고, 같은 보상 id 를 주는 호출 자리는 하나뿐이다."""
    module, out, sites = config["reward_module"], [], {}
    owners = [f for f in tree.luau if f.rel.rsplit("/", 1)[-1].split(".")[0] == module]
    if not owners:
        out.append(f"보상 모듈 {module} 이 없다")
    for f in owners:
        grants = [(p, body, i) for p, body, i in luau.function_bodies(f.tokens) if _names_grant(f.tokens, i)]
        if not grants:
            out.append(f"{f.rel}:1 {module}.grant 함수가 없다")
        for params, body, i in grants:
            texts = [t.text for t in body]
            then = texts.index("then") if "then" in texts else -1
            if texts[:3] != ["if", "not", "claimOnce"] or then < 0 or texts[then + 1:then + 2] != ["return"]:
                out.append(f"{_at(f, f.tokens[i])} grant 가 맨 앞에서 'if not claimOnce(...) then return' 으로 중복 지급을 막지 않는다")
    for f in tree.luau:
        for i in _grant_calls(f, module):
            args = luau.call_args(f.tokens, i)
            reward = args[1][0] if len(args) > 1 and len(args[1]) == 1 and args[1][0].kind == STRING else None
            if reward is None:
                out.append(f"{_at(f, f.tokens[i])} 보상 id 는 글자 그대로 써야 한다(어떤 보상을 주는지 정적으로 알 수 있게)")
                continue
            sites.setdefault(reward.text, []).append(_at(f, f.tokens[i]))
    out += [f"{where[1]} 보상 {rid} 를 주는 호출이 {len(where)}곳이다 ({', '.join(where)}) — 한 곳에서만" for rid, where in sites.items() if len(where) > 1]
    return out


def _names_grant(tokens, i: int) -> bool:
    """function M.grant( / function M:grant( / function grant( 처럼 grant 를 정의하는 function 인가."""
    j = i + 1
    names = []
    while j < len(tokens) and tokens[j].text != "(":
        if tokens[j].kind == NAME:
            names.append(tokens[j].text)
        j += 1
    return bool(names) and names[-1] == "grant"


def _handlers(f) -> list[tuple[list[str], list, int]]:
    """X.OnServerEvent:Connect(function(...) ... end) 또는 Connect(이름) 의 처리 함수."""
    toks, out = f.tokens, []
    bodies = luau.function_bodies(toks)
    for i, t in enumerate(toks):
        if not (t.kind == NAME and t.text == "OnServerEvent" and i + 3 < len(toks) and toks[i + 1].text == ":" and toks[i + 2].text == "Connect"):
            continue
        arg = toks[i + 4] if i + 4 < len(toks) else None
        if arg is not None and arg.kind == NAME and arg.text == "function":
            out += [b for b in bodies if b[2] == i + 4]
        elif arg is not None and arg.kind == NAME:
            named = [b for b in bodies if b[2] + 1 < len(toks) and toks[b[2] + 1].text == arg.text]
            out += named or [([], [], i)]
    return out


def remote_validation(tree, rules, config) -> list[str]:
    """원격 이벤트 처리 함수는 player 다음의 인자마다 typeof 로 형식을 검사한다."""
    out = []
    for f in tree.luau:
        for params, body, i in _handlers(f):
            if not params:
                out.append(f"{_at(f, f.tokens[i])} OnServerEvent 처리 함수를 찾지 못했다")
                continue
            checked = {body[k + 2].text for k in range(len(body) - 2) if body[k].text == "typeof" and body[k + 1].text == "("}
            out += [f"{_at(f, f.tokens[i])} 원격 입력 {p} 의 형식을 typeof 로 검사하지 않는다" for p in params[1:] if p not in checked]
            if f.client_visible:
                out.append(f"{_at(f, f.tokens[i])} 원격 이벤트 처리가 클라이언트가 볼 수 있는 코드에 있다")
    return out


def remote_cooldown(tree, rules, config) -> list[str]:
    """원격 이벤트 처리 함수는 쿨다운(cv.server_cooldown) 모듈을 거친다 — 값의 실측은 Q4."""
    path = tuple(config["cooldown_call"])
    out = []
    for f in tree.luau:
        for params, body, i in _handlers(f):
            if params and not luau.find_calls(body, path):
                out.append(f"{_at(f, f.tokens[i])} 원격 이벤트 처리가 {'.'.join(path)} 를 거치지 않는다 (연타·자동 반복 방지)")
    return out

