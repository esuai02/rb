#!/usr/bin/env python3
"""월드 의도 명세 검사기 (작업 Graph Q1).

  validate_spec.py [명세.yaml ...]     인자가 없으면 specs/worlds/*.yaml 전부

specs/templates/world-intent.schema.json 과 형식만으로는 표현하기 어려운 추가 규칙으로 검사한다.
종료 코드: 0 통과 · 1 위반 · 2 사용법·의존성 오류. 필요 라이브러리: PyYAML, jsonschema.
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

try:
    import jsonschema
    import yaml
except ImportError as exc:  # 조용히 통과하지 않는다
    print(f"[validate_spec] 필요한 라이브러리가 없습니다: {exc.name} (pip install pyyaml jsonschema)", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "specs/templates/world-intent.schema.json"
WORLDS_DIR = ROOT / "specs/worlds"
DEC9_AGES = (9, 14)  # decisions.md DEC-9: 전 세계 9~14세 — 입장 게이트는 대상 전체가 거쳐 간다
# 번역 금지 구간이 반드시 잡아야 하는 표본(종류마다 여러 형태 — 표본 하나를 글자 그대로 적은 패턴은 통과 못 한다)
MATH_SAMPLES = {
    "좌표": ("(3, -2)", "(0,0)", "( -10 , 7 )"),
    "일차식": ("y = 2x + 1", "y=-x+3", "y = 3x", "y = 4", "y = -0.5x - 2"),
}
GENERATED_SAMPLES = 40  # 실행할 때마다 새로 만드는 표본 수 — 고정 표본을 글자 그대로 나열한 패턴으로는 통과할 수 없다 (Codex 리뷰 R-Q1 6차)


def _num(rng: random.Random, allow_decimal: bool = True) -> str:
    value = str(rng.randint(0, 99))
    return value + (f".{rng.randint(1, 99)}" if allow_decimal and rng.random() < 0.3 else "")


def generated_math_samples(rng: random.Random | None = None) -> dict[str, list[str]]:
    rng = rng or random.Random()
    sp = lambda: rng.choice(["", " ", "  "])  # noqa: E731
    sign = lambda: rng.choice(["", "-"])  # noqa: E731
    coords = [f"({sp()}{sign()}{_num(rng)}{sp()},{sp()}{sign()}{_num(rng)}{sp()})" for _ in range(GENERATED_SAMPLES)]
    lines = []
    for _ in range(GENERATED_SAMPLES):
        var, x = rng.choice("yz"), rng.choice("xt")
        rhs = rng.choice([f"{sign()}{_num(rng)}{x}", f"{sign()}{x}", f"{sign()}{_num(rng)}"])
        tail = rng.choice(["", f"{sp()}{rng.choice('+-')}{sp()}{_num(rng)}"]) if not rhs.lstrip("-")[:1].isdigit() or rhs.endswith(x) else ""
        lines.append(f"{var}{sp()}={sp()}{rhs}{tail}")
    return {"좌표": coords, "일차식": lines}


# 잡으면 안 되는 일상 문장 — 수식처럼 보이는 근접 사례 포함 (Codex 리뷰 R-Q1 5차)
PLAIN_SAMPLES = ("도시 신호를 복구하자", "Restore the city signal", "Please explain why x = today", "(3 apples, 2 pears)", "plan = tomorrow")


def load_schema(path: Path = SCHEMA_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_spec(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def extra_rules(spec: dict) -> list[str]:
    """형식으로 표현하기 어려운 규칙. 형식 오류가 있는 칸은 건너뛴다(형식 검사가 이미 알린다)."""
    errors = []
    audience = spec.get("audience") if isinstance(spec, dict) else None
    if isinstance(audience, dict) and isinstance(audience.get("age_min"), int) and isinstance(audience.get("age_max"), int):
        if audience["age_min"] > audience["age_max"]:
            errors.append("audience: age_min 이 age_max 보다 크다")
    if isinstance(audience, dict) and isinstance(audience.get("age_min"), int) and isinstance(audience.get("age_max"), int):
        band = f"gb_age_{audience['age_min']}_{audience['age_max']}"
        if isinstance(audience.get("grade_band"), str) and audience["grade_band"] != band:
            errors.append(f"audience/grade_band: 나이 범위와 맞는 {band} 이어야 한다")
        if spec.get("world_role") == "onboarding_gate" and (audience["age_min"], audience["age_max"]) != DEC9_AGES:
            errors.append(f"audience: 입장 게이트는 DEC-9 대상 전체({DEC9_AGES[0]}~{DEC9_AGES[1]}세)를 받아야 한다")
    session = spec.get("session") if isinstance(spec, dict) else None
    minutes = session.get("target_minutes") if isinstance(session, dict) else None
    if isinstance(minutes, list) and len(minutes) == 2 and all(isinstance(m, int) for m in minutes) and minutes[0] > minutes[1]:
        errors.append("session/target_minutes: 최소가 최대보다 크다")
    if isinstance(session, dict) and all(isinstance(session.get(k), int) for k in ("first_world_reaction_s", "first_math_success_s")):
        if session["first_world_reaction_s"] > session["first_math_success_s"]:
            errors.append("session: 첫 월드 반응이 첫 수학 행동 성공보다 늦다")
    goals = spec.get("language_goals") if isinstance(spec, dict) else None
    seen = set()
    for i, goal in enumerate(goals if isinstance(goals, list) else []):
        if not isinstance(goal, dict):
            continue
        term = goal.get("term_id")
        if term in seen:
            errors.append(f"language_goals/{i}: term_id {term} 가 중복된다")
        seen.add(term)
        if isinstance(term, str) and isinstance(goal.get("label_key"), str) and goal["label_key"] != f"{term}.name":
            errors.append(f"language_goals/{i}: label_key 는 {term}.name 이어야 한다")
    market = spec.get("market") if isinstance(spec, dict) else None
    market_id = market.get("market_id") if isinstance(market, dict) else None
    if isinstance(market_id, str) and isinstance(market.get("curriculum_id"), str) and not market["curriculum_id"].startswith(market_id + "."):
        errors.append(f"market: curriculum_id 는 market_id({market_id}) 로 시작해야 한다")
    safety = spec.get("safety") if isinstance(spec, dict) else None
    if isinstance(market_id, str) and isinstance(safety, dict) and isinstance(safety.get("banned_terms_ref"), str):
        expected = f"specs/localization/terms/{market_id}.yaml"
        if safety["banned_terms_ref"] != expected:
            errors.append(f"safety/banned_terms_ref: 이 명세의 시장 용어집 {expected} 이어야 한다")
    rules = spec.get("do_not_translate") if isinstance(spec, dict) else None
    compiled, ids = [], []
    for i, rule in enumerate(rules if isinstance(rules, list) else []):
        if not isinstance(rule, dict):
            continue
        ids.append(rule.get("id"))
        if isinstance(rule.get("pattern"), str):
            try:
                compiled.append(re.compile(rule["pattern"]))
            except re.error as exc:
                errors.append(f"do_not_translate/{i}: 정규식이 아니다 ({exc})")
    if len(ids) != len(set(ids)):
        errors.append("do_not_translate: id 가 중복된다")
    if compiled:
        generated = generated_math_samples()
        for name, samples in MATH_SAMPLES.items():
            missed = [s for s in list(samples) + generated[name] if not any(c.fullmatch(s) for c in compiled)]
            if missed:
                errors.append(f"do_not_translate: {name} 표본 {len(missed)}개를 전체로 잡는 패턴이 없다 (예: '{missed[0]}')")
        for sample in PLAIN_SAMPLES:
            if any(c.search(sample) for c in compiled):
                errors.append(f"do_not_translate: 일상 문장 '{sample}' 까지 잡는 패턴이 있다 (너무 넓음)")
    localization = spec.get("localization") if isinstance(spec, dict) else None
    if isinstance(localization, dict) and isinstance(localization.get("planned_locales"), list):
        if localization.get("source_locale") not in localization["planned_locales"]:
            errors.append("localization: planned_locales 에 source_locale 이 없다")
    return errors


def validate(spec: object, schema: dict) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    errors = [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}" for e in validator.iter_errors(spec)]
    if isinstance(spec, dict):
        errors += extra_rules(spec)
    return sorted(errors)


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] or sorted(WORLDS_DIR.glob("*.yaml"))
    if not paths:
        print("[validate_spec] 검사할 명세가 없습니다.", file=sys.stderr)
        return 2
    schema, failed = load_schema(), 0
    for path in paths:
        try:
            errors = validate(load_spec(path), schema)
        except (OSError, yaml.YAMLError) as exc:
            errors = [f"읽기 실패: {exc}"]
        print(f"{'OK  ' if not errors else 'FAIL'} {path}")
        for error in errors:
            print(f"     - {error}")
        failed += bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
