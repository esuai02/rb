"""안전 검사 — 금지어(INV-11) · URL·런타임 외부 호출·자유 입력(INV-16) · 무작위·유료 보상(INV-12)."""
from __future__ import annotations

import re
import unicodedata

from harness import luau, resolve
from harness.checks import i18n
from harness.luau import NAME, NUMBER, STRING, SYMBOL

# 도메인 끝 목록은 넓히되 목록으로 둔다 — 모든 `낱말.낱말` 을 막으면 문구 키(goal.signal_2)까지 걸린다 (리뷰 R-Q3 26차)
URL = re.compile(r"(?i)\b[a-z][a-z0-9+.\-]*://|\bwww\.|\b[a-z0-9-]+\.(?:com|net|org|gg|io|kr|ly|me|co|xyz|app|dev|link|site|online|info|biz|tv|cc|to|ai|education|edu|gov|academy|school|shop|store|blog|page|cloud|tech|zone|world|games|fun|live|news|wiki|uk|jp|cn|de|fr|eu|us|ca|au|in|br|ru)\b")
RANDOM_PATHS = (("math", "random"), ("Random", "new"))
RANDOM_METHODS = {"NextInteger", "NextNumber", "NextUnitVector"}


def _squash(text: str) -> str:
    """띄어쓰기·대소문자·보이지 않는 서식 문자를 지우고 정규화해 비교한다 — 글자 사이에 폭 0 문자를 끼워 넣는 우회를 막는다."""
    plain = "".join(c for c in unicodedata.normalize("NFKC", text) if unicodedata.category(c) != "Cf")
    return re.sub(r"\s+", "", plain).lower()


def banned_terms(tree, rules, config) -> list[str]:
    """화면 문구·코드 문자열·데이터 파일에 ko-KR 용어집의 금지어가 없다(띄어쓰기·대소문자 무시)."""
    terms = [_squash(x["term"]) for x in rules.glossary.get("banned_terms", []) if isinstance(x, dict) and x.get("term")]
    if not terms:
        return ["금지어 목록을 읽지 못했다 (specs/localization/terms/ko-KR.yaml)"]
    out = []
    for where, text in tree.texts():
        hits = [t for t in terms if t in _squash(text)]
        if hits:
            out.append(f"{where} 금지어 {hits}")
    return out


def _dotted_ids(node, out: set[str]) -> None:
    if isinstance(node, dict):
        for key, child in node.items():
            if isinstance(key, str) and "." in key:
                out.add(key)
            _dotted_ids(child, out)
    elif isinstance(node, list):
        for child in node:
            _dotted_ids(child, out)
    elif isinstance(node, str) and "." in node:
        out.add(node)


def known_ids(tree, rules) -> set[str]:
    """점이 찍힌 식별자 — 번역표의 키와 잠긴 Q2 명세에 적힌 id 전체 (리뷰 R-Q3 27·28차).

    앞머리만 보면 `goal.museum` 같은 도메인까지 키로 봐 버린다. 그래서 적힌 id 는 전체로 맞춰 보고,
    아직 표에 없는 키(`goal.missing`)는 '문구 모듈에 넘기는 글자인가' 라는 쓰임으로 가린다.
    """
    ids = set(tree.strings)
    for spec in (rules.events, rules.glossary, rules.world_spec, rules.canonical):
        _dotted_ids(spec, ids)
    return ids


def _domain(text: str, ids: set[str]) -> str | None:
    """글자 안의 도메인. 잠긴 명세에 그대로 적힌 식별자는 도메인으로 세지 않는다."""
    plain = unicodedata.normalize("NFKC", text)
    if plain.strip() in ids:
        return None
    found = URL.search(plain)
    if found:
        return found.group()
    host = HOST.search(plain)
    return host.group() if host and host.group() not in ids else None


def url(tree, rules, config) -> list[str]:
    """게임 안 외부 링크 없음 (INV-16). 글자를 이어 붙여 만든 값도 풀어서 보고, 풀 수 없으면 거부한다."""
    ids = known_ids(tree, rules)
    skip = {(f"{f.rel}:{f.tokens[k].line}", f.tokens[k].text) for f in tree.luau for k in _id_argument_strings(f, config)}
    out = [f"{where} URL 이나 도메인 '{found}' 이 있다" for where, text in tree.texts()
           for found in [_domain(text, ids)] if found and (where, text) not in skip]
    for f in tree.luau:
        for name, value in sorted(f.resolved.items()):
            if isinstance(value, str) and _domain(value, ids):
                out.append(f"{f.rel} 이름 {name} 가 가리키는 글자에 URL 이 있다 ('{value[:40]}')")
        for i, tok in enumerate(f.tokens):
            if not (tok.kind == SYMBOL and tok.text == ".." and i):
                continue
            start = _start_of(f.tokens, i)
            value, _has_text = resolve.expression_value(f.tokens, start, f.resolved)
            if isinstance(value, str):
                if _domain(value, ids):
                    out.append(f"{f.rel}:{tok.line} 이어 붙인 글자가 URL 이 된다 ('{value[:40]}')")
            elif _url_like_part(f, start, i):
                out.append(f"{f.rel}:{tok.line} URL 조각을 이어 붙이는데 값을 알 수 없다 — 외부 링크인지 검사할 수 없으므로 쓰지 않는다")
    return sorted(set(out))


# 일반 호스트 이름. 점 찍힌 식별자(문구 키·미션 id)와 겹치므로 known_ids 로 걸러 쓴다.
HOST = re.compile(r"(?i)\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,24}\b")

def _id_argument_strings(f, config) -> set[int]:
    """이미 다른 검사가 허용 목록과 대조하는 id 자리의 글자 — 문구 키·보상 id·분석 이벤트 (리뷰 R-Q3 28·29차).

    `reward.explorer_card` 처럼 점이 찍힌 id 를 도메인으로 세지 않는다. 목록 대조는 그 검사들이 한다.
    """
    toks = i18n.text_call_strings(f, config)
    names = {"grant", config["funnel_call"], config["custom_call"]}
    for i, tok in enumerate(f.tokens):
        if not (tok.kind == NAME and tok.text in names and i + 1 < len(f.tokens) and f.tokens[i + 1].text == "("):
            continue
        opened = i + 1
        toks |= {k for k in range(opened, opened + len(luau.balanced(f.tokens, opened))) if f.tokens[k].kind == STRING}
    return toks


URL_PART = re.compile(r"(?i)https?|ftp|://|www\.|\.(?:com|net|org|gg|io|kr|ly|me|co|xyz|app|dev|link|site|online|info|biz|tv|cc|to|ai|education|edu|gov|academy|school|shop|store|blog|page|cloud|tech|zone|world|games|fun|live|news|wiki|uk|jp|cn|de|fr|eu|us|ca|au|in|br|ru)\b")


def _url_like_part(f, start: int, stop: int) -> bool:
    """이어 붙이는 조각 가운데 URL 의 일부처럼 보이는 글자가 있는가 — 평범한 키 조립과 가르기 위해."""
    pieces = [t.text for t in f.tokens[start:stop + 3] if t.kind == STRING]
    pieces += [v for t in f.tokens[start:stop + 3] if t.kind == NAME and isinstance(v := f.resolved.get(t.text), str)]
    return any(URL_PART.search(p) for p in pieces)


def _start_of(tokens, i: int) -> int:
    """.. 가 있는 식의 시작 — 앞으로 거슬러 피연산자들을 모은다."""
    k = i - 1
    while k > 0:
        prev = tokens[k - 1]
        if prev.kind == SYMBOL and prev.text in ("..", "."):
            k -= 2
            continue
        if tokens[k].kind in (STRING, NAME, NUMBER) and prev.kind == SYMBOL and prev.text in ("=", "(", ",", "{"):
            break
        if tokens[k].kind in (STRING, NAME, NUMBER):
            break
        k -= 1
    return max(0, k)


def external_call(tree, rules, config) -> list[str]:
    """런타임 외부 호출·생성형 AI 없음 (INV-16 · F15). 어떤 서비스를 가져오는지 알 수 없으면 거부한다."""
    names, out = set(config["external_call_names"]), []
    for f in tree.luau:
        out += [f"{f.rel}:{t.line} 런타임 외부 호출·생성형 AI {t.text} 를 쓴다" for t in f.tokens
                if t.kind in (NAME, STRING) and t.text in names]
        out += [f"{f.rel} 이름 {name} 가 가리키는 글자가 런타임 외부 호출·생성형 AI {value} 다 — 이름을 조립해도 같다"
                for name, value in sorted(f.resolved.items()) if isinstance(value, str) and value in names]
        for i, value in _services(f):
            if not isinstance(value, str):
                out.append(f"{f.rel}:{f.tokens[i].line} 어떤 서비스를 가져오는지 알 수 없다 — GetService 인자는 글자 그대로여야 한다")
            elif value in names:
                out.append(f"{f.rel}:{f.tokens[i].line} 런타임 외부 호출·생성형 AI {value} 를 가져온다 — 조각을 나눠 조립해도 같다")
        out += [f"{f.rel}:{f.tokens[i].line} 서비스 {name} 의 멤버를 값을 알 수 없는 방식으로 부른다 — 외부 호출인지 검사할 수 없다"
                for i, name in resolve.dynamic_member_calls(f, _service_names(f))]
    return out


def _services(f) -> list[tuple[int, object]]:
    """GetService 호출마다 (토큰 번호, 풀린 서비스 이름). 풀리지 않으면 resolve.UNRESOLVED."""
    out = []
    for i, tok in enumerate(f.tokens):
        if not (tok.kind == NAME and tok.text == "GetService" and i + 1 < len(f.tokens) and f.tokens[i + 1].text == "("):
            continue
        args = luau.call_args(f.tokens, i)
        value, _has_text = resolve.expression_value(args[0], 0, f.resolved) if args else (resolve.UNRESOLVED, False)
        out.append((i, value))
    return out


def _service_names(f) -> set[str]:
    """GetService 의 결과를 담은 이름 — 그 이름의 멤버를 동적으로 부르면 어떤 외부 호출인지 알 수 없다."""
    toks, out = f.tokens, set()
    for i in range(len(toks) - 4):
        if toks[i].kind == NAME and toks[i].text == "local" and toks[i + 1].kind == NAME and toks[i + 2].text == "=" \
                and any(t.kind == NAME and t.text == "GetService" and t.line == toks[i].line for t in toks[i + 3:i + 8]):
            out.add(toks[i + 1].text)
    return out


def free_text(tree, rules, config) -> list[str]:
    """필터 없는 자유 입력 없음 (INV-10·INV-16). 만들 인스턴스 이름은 글자 그대로여야 한다 — 조립한 이름은 검사할 수 없으므로 거부한다."""
    names, out = set(config["free_text_names"]), []
    for f in tree.luau:
        out += [f"{f.rel}:{t.line} 자유 입력 {t.text} 를 쓴다" for t in f.tokens if t.kind in (NAME, STRING) and t.text in names]
        paths = {("Instance", "new")} | {(alias,) for alias in resolve.names_for(f.resolved, ("Instance", "new")) if alias != "Instance"}
        for i in sorted({i for path in paths for i in luau.find_calls(f.tokens, path)}):
            args = luau.call_args(f.tokens, i)
            if not args:
                continue
            value, _ = resolve.expression_value(args[0], 0, f.resolved)
            if value is resolve.UNRESOLVED or not isinstance(value, str):
                out.append(f"{f.rel}:{f.tokens[i].line} Instance.new 의 클래스 이름을 글자 그대로 알 수 없다 — 조립한 이름은 쓰지 않는다")
            elif value in names:
                out.append(f"{f.rel}:{f.tokens[i].line} 자유 입력 {value} 를 만든다")
    return out + [f"{d.rel} 데이터 파일이 자유 입력 {c} 인스턴스를 만든다" for d in tree.data for c in d.class_names if c in names]


def random_or_paid_reward(tree, rules, config) -> list[str]:
    """무작위 보상·유료 보상 없음 — 난수 원천은 허용 모듈 밖에서 쓰지 않고, 결제·구독 조건을 쓰지 않는다 (INV-12 · F16 · 수익화는 DEC-5)."""
    allowed, paid, out = set(config["random_allowed_modules"]), set(config["paid_names"]), []
    for f in tree.luau:
        out += [f"{f.rel}:{t.line} 결제·구독 조건 {t.text} 를 쓴다 (DEC-5 결정 전 · INV-12)" for t in f.tokens if t.kind in (NAME, STRING) and t.text in paid]
        out += [f"{f.rel} 이름 {name} 가 가리키는 글자가 결제·구독 조건 {value} 다 — 이름을 조립해도 같다 (DEC-5 결정 전 · INV-12)"
                for name, value in sorted(f.resolved.items()) if isinstance(value, str) and value in paid]
        out += [f"{f.rel}:{f.tokens[i].line} 결제·구독 서비스 {value} 를 가져온다 — 조각을 나눠 조립해도 같다 (DEC-5 결정 전 · INV-12)"
                for i, value in _services(f) if isinstance(value, str) and value in paid]
        if f.name in allowed:
            continue
        paths = {path for path in RANDOM_PATHS} | {(alias,) for path in RANDOM_PATHS
                                                    for alias in resolve.names_for(f.resolved, path) if alias != path[0]}
        paths |= {(alias, path[1]) for path in RANDOM_PATHS for alias in resolve.names_for(f.resolved, (path[0],)) if alias != path[0]}
        for i in sorted({i for path in paths for i in luau.find_calls(f.tokens, path)}):
            out.append(f"{f.rel}:{f.tokens[i].line} 난수를 쓴다 — 보상·진행은 완주·기여로만 정한다 (허용 모듈: {sorted(allowed) or '없음'})")
        out += [f"{f.rel}:{t.line} 난수 메서드 {t.text} 를 쓴다 — 보상·진행은 완주·기여로만 정한다" for k, t in enumerate(f.tokens)
                if t.kind == NAME and t.text in RANDOM_METHODS and k and f.tokens[k - 1].text == ":"]
        roots = {path[0] for path in RANDOM_PATHS} | {alias for path in RANDOM_PATHS for alias in resolve.names_for(f.resolved, (path[0],))}
        out += [f"{f.rel}:{f.tokens[i].line} 난수 원천 {name} 의 멤버를 값을 알 수 없는 방식으로 고른다 — 난수를 쓰는지 검사할 수 없다"
                for i, name in resolve.dynamic_member_calls(f, roots)]
        out += [f"{f.rel}:{f.tokens[k].line} 난수 원천을 다른 이름({f.tokens[k].text})에 담았다 — 이름을 바꿔도 난수다" for k in range(len(f.tokens) - 4)
                if f.tokens[k].kind == NAME and f.tokens[k + 1].text == "=" and _is_random_source(f.tokens, k + 2)]
    return out


def _is_random_source(tokens, i: int) -> bool:
    """i 자리가 math.random · Random.new (호출하지 않고 이름만 꺼내는 꼴)인가."""
    return any(tokens[i].kind == NAME and tokens[i].text == head and tokens[i + 1].text == "." and tokens[i + 2].text == tail
               and tokens[i + 3].text != "(" for head, tail in RANDOM_PATHS)
