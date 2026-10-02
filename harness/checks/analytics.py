"""분석 호출 검사 (INV-10 · F10 · F11). 분석은 서버 전용 모듈 하나를 거치고, 이벤트·필드·값은 허용 목록의 글자 그대로이며,
온보딩 퍼널 단계와 사용자 정의 이벤트를 각각 맞는 전송 함수로 보낸다."""
from __future__ import annotations

from harness import luau, resolve
from harness.luau import NAME, STRING

FUNNEL, CUSTOM = "funnel", "custom"


def _allowed(rules) -> dict[str, tuple[str, list[str]]]:
    """이벤트 이름 → (전송 종류, 허용 필드)."""
    events = rules.events
    out = {e["name"]: (FUNNEL, e.get("fields", [])) for e in events.get("onboarding_funnel", [])}
    out.update({e["name"]: (CUSTOM, e.get("fields", [])) for e in events.get("custom_events", [])})
    return out


def _aliases(f, module: str) -> set[str]:
    return luau.require_aliases(f.tokens, module) | resolve.names_for(f.resolved, (module,))


def _table_fields(arg: list) -> tuple[dict, list[str]]:
    """{ field = "value", ... } 표를 읽는다. 반환: (필드 → 값 토큰 목록, 문제)."""
    if not arg or arg[0].text != "{" or arg[-1].text != "}":
        return {}, ["필드는 { 이름 = \"값\" } 표 글자 그대로여야 한다"]
    fields, problems, parts, cur, depth = {}, [], [], [], 0
    for t in arg[1:-1]:
        if t.text in ("{", "(", "["):
            depth += 1
        elif t.text in ("}", ")", "]"):
            depth -= 1
        if t.text in (",", ";") and depth == 0:
            parts.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        parts.append(cur)
    for part in parts:
        if len(part) >= 3 and part[0].kind == NAME and part[1].text == "=":
            fields[part[0].text] = part[2:]
        else:
            problems.append("필드는 이름 = 값 꼴이어야 한다")
    return fields, problems


def calls(tree, rules, config) -> list[str]:
    """AnalyticsService 는 서버 전용 분석 모듈 안에서만, 모듈 호출은 서버에서 허용 이벤트·필드·열거형 값 글자 그대로만."""
    module, allowed, enums = config["analytics_module"], _allowed(rules), rules.events.get("fields", {})
    senders = {FUNNEL: config["funnel_call"], CUSTOM: config["custom_call"]}
    out = []
    for f in tree.luau:
        if f.name == module:
            if f.client_visible:
                out.append(f"{f.rel}:1 분석 모듈이 클라이언트가 볼 수 있는 곳({f.container})에 있다 — 분석은 서버에서만 보낸다(F10)")
            out += [f"{f.rel}:1 분석 모듈이 플랫폼 전송 함수 {api} 를 쓰지 않는다 (퍼널·사용자 정의를 모두 보내야 한다, F11)"
                    for api in config["platform_apis"] if not any(t.kind == NAME and t.text == api for t in f.tokens)]
            out += _check_module(f, config)
            continue
        out += [f"{f.rel}:{t.line} 분석 모듈을 거치지 않고 AnalyticsService 를 쓴다" for t in f.tokens
                if t.text in ("AnalyticsService", *config["platform_apis"]) and t.kind in (NAME, STRING)]
        names = _aliases(f, module)
        out += [f"{f.rel}:{f.tokens[i].line} 분석 모듈 {name} 의 멤버를 값을 알 수 없는 방식으로 고른다 — 어떤 이벤트를 보내는지 검사할 수 없다"
                for i, name in resolve.dynamic_member_calls(f, names)]
        out += [f"{f.rel}:{f.tokens[i].line} 플랫폼 전송 함수를 다른 이름({alias})에 담아 부른다 — 분석 모듈을 거쳐야 한다"
                for api in config["platform_apis"] for alias in resolve.names_for(f.resolved, ("AnalyticsService", api)) if alias != "AnalyticsService"
                for i in luau.find_calls(f.tokens, (alias,))]
        for kind, sender in senders.items():
            for name in names:
                out += _check_call(f, name, sender, kind, allowed, enums, module, (name, sender))
            for direct in _method_aliases(f, names, sender):
                out += _check_call(f, direct, sender, kind, allowed, enums, module, (direct,))
        out += [f"{f.rel}:{f.tokens[i].line} 분석 모듈의 모르는 함수 {f.tokens[i + 2].text} 를 부른다 — {sender_names(config)} 만 쓴다"
                for name in names for i in range(len(f.tokens) - 3)
                if f.tokens[i].kind == NAME and f.tokens[i].text == name and f.tokens[i + 1].text == "."
                and f.tokens[i + 2].kind == NAME and f.tokens[i + 2].text not in senders.values() and f.tokens[i + 3].text == "("]
    return out


def sender_names(config) -> str:
    return f"{config['analytics_module']}.{config['custom_call']} · {config['analytics_module']}.{config['funnel_call']}"


def _method_aliases(f, module_names: set[str], sender: str) -> set[str]:
    """전송 함수를 담은 이름 — 몇 단계를 거쳐 담아도 따라간다."""
    return {alias for name in module_names for alias in resolve.names_for(f.resolved, (name, sender)) if alias != name}


def _plain_name(f, arg: list, params: set[str]) -> bool:
    """이벤트 이름 자리에 쓸 수 있는 값인가 — 글자 그대로, 받은 매개변수, 또는 풀리는 글자뿐."""
    if len(arg) == 1 and arg[0].kind == STRING:
        return True
    if len(arg) == 1 and arg[0].kind == NAME:
        return arg[0].text in params or isinstance(f.resolved.get(arg[0].text), str)
    return False


def _resolvable(f, arg: list) -> bool:
    """인자의 값을 정적으로 알 수 있는가 — 글자·수·표 리터럴·풀리는 이름."""
    if not arg:
        return False
    if arg[0].kind in (STRING, luau.NUMBER) or arg[0].text == "{":
        return True
    if len(arg) == 1 and arg[0].kind == NAME:
        return isinstance(f.resolved.get(arg[0].text), (str, float))
    value, _ = resolve.expression_value(arg, 0, f.resolved)
    return isinstance(value, (str, float))


def _function_params(f, index: int) -> set[str]:
    """index 가 들어 있는 함수의 매개변수 이름."""
    for params, body, start in luau.function_bodies(f.tokens):
        if body and start <= index <= f.tokens.index(body[-1], start):
            return set(params)
    return set()


def _player_names(f, config) -> set[str]:
    """플레이어를 가리키는 이름 — 설정의 이름과 거기에 담긴 다른 이름(`local p = player`)."""
    base = set(config["player_variable_names"])
    return base | {name for name, value in f.resolved.items() if isinstance(value, tuple) and len(value) == 1 and value[0] in base}


def _check_module(f, config) -> list[str]:
    """분석 모듈 자신도 믿지 않는다 — 이벤트 이름은 받은 값이어야 하고, 플레이어 개인정보 속성을 쓰지 않는다 (INV-10)."""
    out = []
    for api in config["platform_apis"]:
        for i in [k for k in range(len(f.tokens) - 1) if f.tokens[k].kind == NAME and f.tokens[k].text == api
                  and f.tokens[k + 1].text == "(" and (k == 0 or f.tokens[k - 1].text in (":", "."))]:
            args = luau.call_args(f.tokens, i)
            literals = [a[0].text for a in args if len(a) == 1 and a[0].kind == STRING]
            literals += [f.resolved[a[0].text] for a in args if len(a) == 1 and a[0].kind == NAME and isinstance(f.resolved.get(a[0].text), str)]
            params, slot = _function_params(f, i), config["platform_event_arg"].get(api)
            name_arg = args[slot] if slot is not None and slot < len(args) else None
            if name_arg is not None and not _plain_name(f, name_arg, params):
                shown = " ".join(x.text for x in name_arg)[:24]
                out.append(f"{f.rel}:{f.tokens[i].line} 분석 모듈이 {api} 의 이벤트 이름 자리에 '{shown}' 을 넣는다 — 글자 그대로이거나 받은 값이어야 한다")
            if literals:
                out.append(f"{f.rel}:{f.tokens[i].line} 분석 모듈이 {api} 에 정해진 값 {literals} 를 넣는다 — 이벤트 이름·필드는 받은 값이어야 한다")
    out += [f"{f.rel}:{t.line} 분석 모듈이 플레이어 개인정보 속성 {t.text} 를 쓴다 (INV-10)" for k, t in enumerate(f.tokens)
            if t.kind == NAME and t.text in config["player_identity_names"] and k >= 2 and f.tokens[k - 1].text == "."
            and f.tokens[k - 2].kind == NAME and f.tokens[k - 2].text in _player_names(f, config)]
    return out


def _check_call(f, name: str, sender: str, kind: str, allowed: dict, enums: dict, module: str, path: tuple[str, ...]) -> list[str]:
    out = []
    for i in luau.find_calls(f.tokens, path):
        where = f"{f.rel}:{f.tokens[i].line}"
        if f.client_visible:
            out.append(f"{where} 클라이언트 코드가 분석을 보낸다 — 서버에서만(F10)")
        args = luau.call_args(f.tokens, i)
        if len(args) != 3 or len(args[1]) != 1 or args[1][0].kind != STRING:
            out.append(f"{where} {module}.{sender}(player, \"이벤트\", {{필드}}) 꼴이어야 한다")
            continue
        event = args[1][0].text
        if event not in allowed:
            out.append(f"{where} 이벤트 {event} 가 허용 목록(specs/analytics/events.yaml)에 없다")
            continue
        event_kind, fields_allowed = allowed[event]
        if event_kind != kind:
            out.append(f"{where} {event} 는 {'온보딩 퍼널 단계' if event_kind == FUNNEL else '사용자 정의 이벤트'}인데 다른 전송 함수({sender})로 보낸다 (F11)")
            continue
        fields, problems = _table_fields(args[2])
        out += [f"{where} {p}" for p in problems]
        for field, value in fields.items():
            if field not in fields_allowed:
                out.append(f"{where} 이벤트 {event} 에 필드 {field} 는 허용되지 않는다")
            elif len(value) != 1 or value[0].kind != STRING or value[0].text not in enums.get(field, []):
                shown = " ".join(t.text for t in value)[:30]
                out.append(f"{where} 필드 {field} 의 값 '{shown}' 이 열거형 글자 그대로가 아니다 (개인정보·자유 값 금지, INV-10)")
    return out
