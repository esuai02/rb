"""분석 호출 검사 (INV-10 · F10). 분석은 서버 전용 모듈 하나를 거치고, 이벤트·필드·값은 허용 목록의 글자 그대로다."""
from __future__ import annotations

from harness import luau
from harness.luau import NAME, STRING


def _allowed(rules) -> dict[str, list[str]]:
    events = rules.events
    return {e["name"]: e.get("fields", []) for e in events.get("onboarding_funnel", []) + events.get("custom_events", [])}


def _table_fields(arg: list) -> tuple[dict, list[str]]:
    """{ field = "value", ... } 표를 읽는다. 반환: (필드 → 값 토큰 목록, 문제)."""
    if not arg or arg[0].text != "{" or arg[-1].text != "}":
        return {}, ["필드는 { 이름 = \"값\" } 표 글자 그대로여야 한다"]
    inner, fields, problems, cur = arg[1:-1], {}, [], []
    parts, depth = [], 0
    for t in inner:
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
    """AnalyticsService 는 서버 전용 분석 모듈 안에서만 쓰고, 그 모듈 호출은 서버 코드에서 허용 이벤트·필드·열거형 값 글자 그대로만 보낸다."""
    module, allowed, enums = config["analytics_module"], _allowed(rules), rules.events.get("fields", {})
    out = []
    for f in tree.luau:
        is_module = f.rel.rsplit("/", 1)[-1].split(".")[0] == module
        if is_module and f.client_visible:
            out.append(f"{f.rel}:1 분석 모듈이 클라이언트가 볼 수 있는 곳({f.container})에 있다 — 분석은 서버에서만 보낸다(F10)")
        if not is_module:
            out += [f"{f.rel}:{t.line} 분석 모듈을 거치지 않고 AnalyticsService 를 쓴다" for t in f.tokens if t.text == "AnalyticsService" and t.kind in (NAME, STRING)]
        for i in luau.find_calls(f.tokens, (module, "log")):
            where = f"{f.rel}:{f.tokens[i].line}"
            if f.client_visible:
                out.append(f"{where} 클라이언트 코드가 분석을 보낸다 — 서버에서만(F10)")
            args = luau.call_args(f.tokens, i)
            if len(args) != 3 or len(args[1]) != 1 or args[1][0].kind != STRING:
                out.append(f"{where} {module}.log(player, \"이벤트\", {{필드}}) 꼴이어야 한다")
                continue
            event = args[1][0].text
            if event not in allowed:
                out.append(f"{where} 이벤트 {event} 가 허용 목록(specs/analytics/events.yaml)에 없다")
                continue
            fields, problems = _table_fields(args[2])
            out += [f"{where} {p}" for p in problems]
            for name, value in fields.items():
                if name not in allowed[event]:
                    out.append(f"{where} 이벤트 {event} 에 필드 {name} 는 허용되지 않는다")
                elif len(value) != 1 or value[0].kind != STRING or value[0].text not in enums.get(name, []):
                    shown = " ".join(t.text for t in value)[:30]
                    out.append(f"{where} 필드 {name} 의 값 '{shown}' 이 열거형 글자 그대로가 아니다 (개인정보·자유 값 금지, INV-10)")
    return out
