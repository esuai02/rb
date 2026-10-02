"""정적 검사 모음 (작업 Graph Q3). 검사 하나 = 함수 하나: check(tree, rules, config) -> ["파일:행 내용", ...]

검사 id 와 함수는 여기 REGISTRY 한 곳에서만 잇는다. harness/manifest.json 은 이 id 로 검사를 가리킨다.
"""
from __future__ import annotations

from harness.checks import analytics, i18n, math_claims, safety, server

REGISTRY = {
    "server.reward_authority": server.reward_authority,
    "server.duplicate_reward": server.duplicate_reward,
    "server.remote_validation": server.remote_validation,
    "server.remote_cooldown": server.remote_cooldown,
    "server.reward_after_verdict": server.reward_after_verdict,
    "i18n.missing_key": i18n.missing_key,
    "i18n.length_budget": i18n.length_budget,
    "i18n.do_not_translate": i18n.do_not_translate,
    "i18n.hardcoded_text": i18n.hardcoded_text,
    "text.readability": i18n.readability,
    "math.truth": math_claims.truth,
    "math.conditions": math_claims.conditions,
    "safety.banned_terms": safety.banned_terms,
    "safety.url": safety.url,
    "safety.external_call": safety.external_call,
    "safety.free_text": safety.free_text,
    "safety.random_or_paid_reward": safety.random_or_paid_reward,
    "analytics.calls": analytics.calls,
}
