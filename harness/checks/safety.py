"""안전 검사 — 금지어(INV-11) · URL·런타임 외부 호출·자유 입력(INV-16) · 무작위·유료 보상(INV-12)."""
from __future__ import annotations

import re
import unicodedata

from harness import luau
from harness.luau import NAME, STRING

URL = re.compile(r"(?i)\b(?:https?://|www\.)|\b[a-z0-9-]+\.(?:com|net|org|gg|io|kr|ly|me|co)\b")
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


def url(tree, rules, config) -> list[str]:
    """게임 안 외부 링크 없음 — 문구·코드·데이터에 URL·도메인이 없다 (INV-16)."""
    return [f"{where} URL 이나 도메인 '{m.group()}' 이 있다" for where, text in tree.texts()
            for m in [URL.search(unicodedata.normalize("NFKC", text))] if m]


def external_call(tree, rules, config) -> list[str]:
    """런타임 외부 호출·생성형 AI 없음 — HttpService·TextGenerator 계열을 쓰지 않는다 (INV-16 · F15)."""
    names = set(config["external_call_names"])
    return [f"{f.rel}:{t.line} 런타임 외부 호출·생성형 AI {t.text} 를 쓴다" for f in tree.luau for t in f.tokens
            if t.kind in (NAME, STRING) and t.text in names]


def free_text(tree, rules, config) -> list[str]:
    """필터 없는 자유 입력 없음 — 코드에서도 데이터 파일에서도 TextBox 를 만들지 않는다 (INV-10·INV-16)."""
    names = set(config["free_text_names"])
    out = [f"{f.rel}:{t.line} 자유 입력 {t.text} 를 쓴다" for f in tree.luau for t in f.tokens if t.kind in (NAME, STRING) and t.text in names]
    return out + [f"{d.rel} 데이터 파일이 자유 입력 {c} 인스턴스를 만든다" for d in tree.data for c in d.class_names if c in names]


def random_or_paid_reward(tree, rules, config) -> list[str]:
    """무작위 보상·유료 보상 없음 — 난수 원천은 허용 모듈 밖에서 쓰지 않고, 결제·구독 조건을 쓰지 않는다 (INV-12 · F16 · 수익화는 DEC-5)."""
    allowed, paid, out = set(config["random_allowed_modules"]), set(config["paid_names"]), []
    for f in tree.luau:
        out += [f"{f.rel}:{t.line} 결제·구독 조건 {t.text} 를 쓴다 (DEC-5 결정 전 · INV-12)" for t in f.tokens if t.kind in (NAME, STRING) and t.text in paid]
        if f.name in allowed:
            continue
        for i in [i for path in RANDOM_PATHS for i in luau.find_calls(f.tokens, path)]:
            out.append(f"{f.rel}:{f.tokens[i].line} 난수를 쓴다 — 보상·진행은 완주·기여로만 정한다 (허용 모듈: {sorted(allowed) or '없음'})")
        out += [f"{f.rel}:{t.line} 난수 메서드 {t.text} 를 쓴다 — 보상·진행은 완주·기여로만 정한다" for k, t in enumerate(f.tokens)
                if t.kind == NAME and t.text in RANDOM_METHODS and k and f.tokens[k - 1].text == ":"]
        out += [f"{f.rel}:{f.tokens[k].line} 난수 원천을 다른 이름({f.tokens[k].text})에 담았다 — 이름을 바꿔도 난수다" for k in range(len(f.tokens) - 4)
                if f.tokens[k].kind == NAME and f.tokens[k + 1].text == "=" and _is_random_source(f.tokens, k + 2)]
    return out


def _is_random_source(tokens, i: int) -> bool:
    """i 자리가 math.random · Random.new (호출하지 않고 이름만 꺼내는 꼴)인가."""
    return any(tokens[i].kind == NAME and tokens[i].text == head and tokens[i + 1].text == "." and tokens[i + 2].text == tail
               and tokens[i + 3].text != "(" for head, tail in RANDOM_PATHS)
