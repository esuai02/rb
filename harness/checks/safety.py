"""안전 검사 — 금지어(INV-11) · URL·외부 호출·자유 입력(INV-16) · 무작위·유료 보상(INV-12)."""
from __future__ import annotations

import re

from harness import luau
from harness.luau import NAME, STRING

URL = re.compile(r"(?i)\b(?:https?://|www\.)|\b[a-z0-9-]+\.(?:com|net|org|gg|io|kr|ly|me|co)\b")


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _texts(tree):
    """(위치, 글자) — LocalizationTable 의 모든 칸과 Luau 문자열."""
    for key, row in sorted(tree.strings.items()):
        for col, text in row.items():
            yield f"{key}[{col}]", text
    for f in tree.luau:
        for t in f.tokens:
            if t.kind == STRING:
                yield f"{f.rel}:{t.line}", t.text


def banned_terms(tree, rules, config) -> list[str]:
    """화면 문구와 코드 문자열에 ko-KR 용어집의 금지어가 없다(띄어쓰기·대소문자 무시)."""
    terms = [_squash(x["term"]) for x in rules.glossary.get("banned_terms", []) if isinstance(x, dict) and x.get("term")]
    if not terms:
        return ["금지어 목록을 읽지 못했다 (specs/localization/terms/ko-KR.yaml)"]
    out = []
    for where, text in _texts(tree):
        hits = [t for t in terms if t in _squash(text)]
        if hits:
            out.append(f"{where} 금지어 {hits}")
    return out


def url(tree, rules, config) -> list[str]:
    """게임 안 외부 링크 없음 — 문구·코드에 URL·도메인이 없다 (INV-16)."""
    return [f"{where} URL 이나 도메인 '{m.group()}' 이 있다" for where, text in _texts(tree) for m in [URL.search(text)] if m]


def external_call(tree, rules, config) -> list[str]:
    """런타임 외부 호출(생성형 AI·웹) 없음 — HttpService 를 쓰지 않는다 (INV-16)."""
    names = set(config["external_call_names"])
    return [f"{f.rel}:{t.line} 런타임 외부 호출 {t.text} 를 쓴다" for f in tree.luau for t in f.tokens
            if t.kind in (NAME, STRING) and t.text in names]


def free_text(tree, rules, config) -> list[str]:
    """필터 없는 자유 입력 없음 — TextBox 를 만들지 않는다. 협동은 미리 정한 핑만 (INV-10·INV-16)."""
    names = set(config["free_text_names"])
    return [f"{f.rel}:{t.line} 자유 입력 {t.text} 를 쓴다" for f in tree.luau for t in f.tokens if t.kind in (NAME, STRING) and t.text in names]


def random_or_paid_reward(tree, rules, config) -> list[str]:
    """무작위 보상·유료 보상 없음 — 보상 코드에 난수가 없고, 어디에도 결제(MarketplaceService)가 없다 (INV-12 · 수익화는 DEC-5)."""
    module, out = config["reward_module"], []
    for f in tree.luau:
        out += [f"{f.rel}:{t.line} 결제 {t.text} 를 쓴다 (DEC-5 결정 전)" for t in f.tokens if t.kind in (NAME, STRING) and t.text in config["paid_names"]]
        touches_reward = any(t.kind == NAME and t.text == module for t in f.tokens) or f.rel.rsplit("/", 1)[-1].split(".")[0] == module
        if not touches_reward:
            continue
        randoms = luau.find_calls(f.tokens, ("math", "random")) + luau.find_calls(f.tokens, ("Random", "new"))
        out += [f"{f.rel}:{f.tokens[i].line} 보상 코드가 난수를 쓴다 — 보상은 완주·기여로만 정한다" for i in randoms]
    return out
