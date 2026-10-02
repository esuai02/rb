#!/usr/bin/env python3
"""교육과정·월드 Graph 검사기 (작업 Graph Q2).

  validate_graph.py            specs/graph/neo-seoul-city-language-gate.graph.json 과 그 Graph 가 가리키는 파일 전부

Graph 가 참조하는 Q1 명세·용어집·분석 이벤트·정본 값과 원천 문서(K0 §3·K3 §4·K5 §5)를 함께 읽어
기준 Q2-C1~C7 을 검사한다. 종료 코드: 0 통과 · 1 위반 · 2 사용법·의존성 오류. 필요 라이브러리: PyYAML, jsonschema.
"""
from __future__ import annotations

import functools
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_spec  # noqa: E402  Q1 검사기 — 일상 문장 표본을 재사용한다(의존성 확인도 여기서 한다)
import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GRAPH_PATH = "specs/graph/neo-seoul-city-language-gate.graph.json"
K0_PATH, K3_PATH, K5_PATH = "docs/knowledge/K0-docs-index.md", "docs/knowledge/K3-safety-compliance.md", "docs/knowledge/K5-onboarding.md"
MAX_FIELDS_PER_EVENT = 3  # evidence F10: CustomField01~03
MAX_CUSTOM_EVENTS = 100   # evidence F10
LOCALE_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")  # IETF 언어 태그 (evidence F9 — 'ko', 'en-US', 'pt-BR')
ENUM_VALUE_RE = re.compile(r"^[a-z][a-z0-9_.]*$")
CV_ID_RE = re.compile(r"^cv\.[a-z_]+$")
# 분석 필드 이름 허용 목록 — 여기에 없는 필드는 쓸 수 없다(INV-10). 늘리려면 이 목록을 고치고 리뷰를 다시 받는다
ALLOWED_FIELDS = {"mission", "term", "context", "expression_used", "outcome", "attempt", "hint_level", "play_mode", "input", "offer_source"}
# 분석 이벤트 이름 허용 목록 — 여기에 없는 이벤트는 보낼 수 없다(INV-10, K5 §5·K3 §4 를 합친 것). 늘리려면 이 목록을 고치고 리뷰를 다시 받는다
ALLOWED_EVENTS = {"onboarding_start", "character_spawned", "first_input", "gate_visible", "movement_complete", "first_interaction",
                  "first_math_action", "first_math_success", "gate_opened", "explorer_card_earned", "zone_portal_entered", "onboarding_complete",
                  "session_start", "math_attempt", "hint_shown", "label_shown", "term_reused", "co_play_offered", "co_play_started", "session_end"}
FREQUENCIES = {"once_per_user", "every_session", "per_occurrence", "once_per_context_per_session"}
SERVER_CONFIRMED = "server_confirmed_world_response"
STRING_KEY_FIELDS = {"key", "keys", "goal_key", "line_key", "other_result_key", "situation_key", "response_key", "name_key", "npc_line_key",
                     "waiting_key", "ready_key", "object_keys", "label_choice_key", "invite_key", "retry_key", "pings", "answer_keys", "choice_keys"}
PARAM_FIELDS = {"params", "rule"}
NS_NUMERATOR, NS_DENOMINATOR = "term_reused", "session_start"  # intent §1 북극성 지표 — 이벤트를 바꾸려면 이 검사기를 고치고 리뷰를 받는다
STOP_CHOICES = ["pacing.continue", "pacing.rest"]               # K6 R7 계속·쉬기
# 금지어 하한 — ko-KR 용어집의 금지어 전부. INV-11(현실 출입국·국적·신분) · INV-8/K5 §7(시험 언어) · INV-14(압박) · 보상형 초대.
# 용어집에서 하나라도 빼면 실패한다(더하는 것은 된다). 빼려면 이 목록을 고치고 리뷰를 받는다
REQUIRED_BANNED = {"입국", "출입국", "심사", "여권", "비자", "국적", "이민", "국경", "국기", "외국인", "시민권", "난민", "망명", "추방", "체류", "신분증",
                   "passport", "visa", "citizen", "nationalit", "immigra", "foreigner", "refugee", "asylum", "deport", "border",
                   "불합격", "낙제", "오답", "정답", "틀렸", "틀린", "실패", "시험", "테스트", "진단", "순위", "연속", "매일", "서둘러", "남은 시간", "초대"}
# 사람 결정(DEC)을 근거로 decided 가 될 수 있는 정본 값과, 그 결정 행에 글자 그대로 들어 있어야 하는 값 항목
DECIDED_BY = {"cv.gate_name": ("DEC-1", "ko")}
# 단계 종류마다 반드시 있는 항목과 있어도 되는 항목 — 퀴즈·정의 카드 같은 다른 종류는 쓸 수 없다(INV-8·INV-15)
STEP_FIELDS = {"situation": ({"key"}, set()), "interaction": ({"key"}, set()), "world_response": ({"key"}, {"other_result_key"}),
               "everyday_expression": ({"keys"}, set()), "player_action": ({"keys"}, set()), "math_label": ({"key", "line_key"}, set()),
               "reward": ({"ids"}, set())}
CANONICAL_PATH, EVENTS_PATH = "specs/graph/canonical-values.yaml", "specs/analytics/events.yaml"
STRING_KEY_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
HINT_KINDS = ["world_signal", "strategy_question", "similar_example"]
STATUSES = {"decided", "proposed", "hypothesis"}
LATER_STAGES = {"Q3", "Q4", "Q5", "Q6", "Q7", "Q8"}
# 닫힌 형식 — 정해진 항목·형식만 쓴다. 모르는 항목(가격·확률·타이머 등)이나 틀린 형식이 검사를 비켜 가지 못하게 한다.
# 하위 형식(dict, '?' 로 시작하는 이름은 빠져도 됨) · [항목 형식] 목록 · ("map", 값 형식) 글자 키 사전 ·
# T 비지 않은 글자 · T0 글자 또는 null · B 참거짓 · N 정수 또는 null · I 양의 정수 · P 양수 · ONE 형식 판 1 ·
# LT 글자 목록 · LN 수 목록 · TL 글자 또는 글자 목록 · ANY 따로 검사함
T, T0, B, N, I, P, ONE, LT, LN, TL, ANY = "text", "text_or_null", "bool", "int_or_null", "positive_int", "positive", "version_1", \
    "text_list", "number_list", "text_or_text_list", "any"
STEP = {"kind": T, "?key": T, "?keys": LT, "?other_result_key": T, "?line_key": T, "?ids": LT}
GRAPH_SHAPE = {
    "schema_version": ONE, "id": T, "note": T, "world_spec": T, "world_id": T, "market_id": T, "curriculum_id": T, "glossary": T, "events": T,
    "canonical_values": T, "label_choice_key": T, "pings": LT, "invite_key": T, "retry_key": T,
    "terms": [{"term_id": T, "prerequisites": LT, "first_mission": T}],
    "missions": [{"id": T, "core": B, "signal": N, "new_term": T0, "requires": LT, "goal_key": T0, "play_modes": LT, "target_end_s": N,
                  "steps": [STEP], "?params": LT, "?hint_ladder": T, "?answer_keys": LT, "?coop": T}],
    "reuse_contexts": [{"id": T, "term_id": T, "mission": T, "situation_key": T, "action_keys": LT, "response_key": T, "accepts": LT,
                        "hint_ladder": T, "answer_keys": LT}],
    "hint_ladders": [{"id": T, "?mission": T, "?term": T, "rule": T, "keys": LT}],
    "roles": [{"id": T, "name_key": T, "contribution": T, "npc_can_fill": B}],
    "coop": [{"id": T, "mission": T, "objects": LT, "object_keys": LT, "roles": LT, "role_assignment": T, "npc_fallback": T, "npc_line_key": T,
              "waiting_key": T, "ready_key": T, "max_players": I, "params": LT}],
    "rewards": [{"id": T, "name_key": T, "mission": T, "basis": T, "granted_to": T, "granted_by": T, "kind": T}],
    "pacing": {"countdown_fail": B, "streaks": B, "autoplay_next_mission": B, "autosave": B, "long_play_notice": T, "params": LT,
               "stop_point": {"mission": T, "choice_keys": LT, "equal_size": B}},
    "scenarios": [{"id": T, "play_mode": T, "input": T, "variation": T, "path": LT, "expects_events": LT}],
}
CANONICAL_SHAPE = {"schema_version": ONE, "source": T, "values": [{"id": T, "k0_item": T, "value": ANY, "status": T, "refs": LT, "rationale": T,
                                                                     "?measure_at": T, "?q1_paths": ("map", T)}]}
CV_SHAPES = {
    "cv.gate_name": {"ko": T, "string_key": T},
    "cv.world_title": {"world": T, "world_key": T, "first_title_key": T, "citizenship_loop": T},
    "cv.first_rewards": LT,
    "cv.gate_signals": {"signal_1": T, "signal_2": T, "signal_3": T, "coop_on": T, "out_of_mvp": LT},
    "cv.gate_time": {"target_minutes": LN},
    "cv.match_wait": {"seconds": P, "then": T},
    "cv.coop_sync_window": {"seconds": P},
    "cv.server_distance": {"prompt_activation_studs": P, "server_check_studs": P},
    "cv.server_cooldown": {"seconds": P, "scope": T},
    "cv.hold_time": {"seconds": P, "accessible_alternative": T},
    "cv.hold_cancel": {"server": T, "display_tween_seconds": P},
    "cv.slope_choices": {"expressions": LT, "steps": LN, "fixed": LT},
    "cv.coordinate_expression": {"order": LT, "axes": LT, "plane": T, "origin": T, "moves_from": T, "grid": {"x": LN, "y": LN}, "numeric_form": T},
    "cv.hint_ladder": {"first_trigger": {"idle_seconds": P, "other_results": I}, "advance": T, "levels": LT, "reveals_answer": B, "tried_marker": B, "cost": T},
    "cv.label_tag_display": {"full_seconds": P, "then": T},
    "cv.events": {"allowlist": T, "naming": T, "renamed": ("map", T)},
    "cv.coop_switch_ids": LT,
    "cv.rule_source": {"authority": T, "prompt_attributes": T},
    "cv.helper_npc": {"id": T, "name_key": T},
    "cv.coop_offer_timing": {"in_gate": T, "invite_prompt": T},
    "cv.first_try": {"forced_failure": B, "success_within_two_tries": LN, "key_metrics": LT},
    "cv.color_meaning": {"purple": T, "hold_interrupted": LT, "color_only": B},
}
RATIO = {"event": T, "aggregation": T, "window_days": I}
NUMERATOR = dict(RATIO, filter=("map", LT), contexts=T)
EVENTS_SHAPE = {
    "schema_version": ONE, "transport": T, "sent_by": T, "limits": {"max_custom_events": I, "max_fields_per_event": I}, "fields": ("map", LT),
    "onboarding_funnel": [{"step": I, "name": T, "fields": LT, "frequency": T}],
    "custom_events": [{"name": T, "fields": LT, "frequency": T, "?trigger": T, "when": T}], "platform_metrics": LT,
    "north_star": {"id": T, "numerator": NUMERATOR, "denominator": RATIO, "per_player_storage": B, "secondary": {"id": T, "note": T}},
    "source_mapping": {"k5_funnel": ("map", TL), "k3_allowed": ("map", TL), "other_names": ("map", TL)},
}
GLOSSARY_SHAPE = {"schema_version": ONE, "market_id": T, "locale": T, "world_spec": T, "strings": ("map", T),
                  "banned_terms": [{"term": T, "replacement": T0, "reason": T}]}
GRANTED_TO = {"completion": "all_finishers", "role_contribution": "contributing_players"}  # INV-4 보상 기준별 수령 대상
PLAY_MODES = {"solo_npc", "duo"}
SCENARIO_VARIATIONS = {"first_try", "other_result_x3", "idle_hints", "never_uses_label", "uses_label"}
TRANSPORT = "roblox_analytics_service"  # evidence F10
MAX_CHOICE_SPAN = 5  # 좌표 격자 반폭·기울기 최대 단계 — 선택지가 작고 유한해야 정답 공개 없이도 힌트가 끝난다(cv.hint_ladder)
ID_PATTERNS = {"terms": ("term_id", r"term\.[a-z_]+"), "missions": ("id", r"m\.[a-z_]+"), "reuse_contexts": ("id", r"ctx\.[a-z_]+\.[a-z_]+"),
               "hint_ladders": ("id", r"hl\.[a-z_.]+"), "roles": ("id", r"role\.[a-z_]+"), "coop": ("id", r"coop\.[a-z_]+"),
               "rewards": ("id", r"(reward|unlock)\.[a-z_]+"), "scenarios": ("id", r"sc\.[a-z_]+")}
REF_RE = re.compile(r"^(DEC-\d+|INV-\d+|Q[1-8]|F\d+|K[0-6])$")
# 불변식에 묶인 정본 값 — 바꾸려면 불변식부터 바뀌어야 한다
CV_PINS = {
    ("cv.rule_source", "authority"): ("server_config", "INV-4"), ("cv.rule_source", "prompt_attributes"): ("display_only", "INV-4"),
    ("cv.hold_cancel", "server"): ("immediate", "INV-4"), ("cv.match_wait", "then"): ("npc_fallback", "INV-9"),
    ("cv.first_try", "forced_failure"): (False, "INV-14"), ("cv.color_meaning", "color_only"): (False, "INV-9"),
    ("cv.coordinate_expression", "order"): (["direction", "distance"], "INV-15"),
    ("cv.coordinate_expression", "moves_from"): ("origin_always", "좌표 = 기준점에서 센 위치"),
    ("cv.coordinate_expression", "numeric_form"): ("after_label_only", "INV-15"),
    ("cv.slope_choices", "fixed"): (["start_point", "run"], "기울기와 절편을 섞지 않는다"),
    ("cv.coop_offer_timing", "invite_prompt"): ("after_gate_open", "INV-14 — 첫 성공 전 초대 압박 없음"),
    ("cv.events", "naming"): ("k5_funnel_names", "cv.events"),
}
# 가설 수치는 원천 문서들이 낸 값의 범위 안에서 고른다 (docs/knowledge/K0-docs-index.md §3, 리듬 규칙은 K6). 수 목록이면 값마다 본다
CV_RANGES = {
    ("cv.match_wait", "seconds"): (10, 15), ("cv.coop_sync_window", "seconds"): (2, 4),
    ("cv.server_distance", "prompt_activation_studs"): (8, 20), ("cv.server_distance", "server_check_studs"): (8, 20),
    ("cv.server_cooldown", "seconds"): (0.35, 1.5), ("cv.hold_time", "seconds"): (0.4, 0.8), ("cv.hold_cancel", "display_tween_seconds"): (0, 0.2),
    ("cv.label_tag_display", "full_seconds"): (1, 4), ("cv.hint_ladder", "first_trigger", "idle_seconds"): (5, 25),
    ("cv.hint_ladder", "first_trigger", "other_results"): (1, 3), ("cv.first_try", "success_within_two_tries"): (0.7, 0.9),  # K6 R2
}
# 번역 금지 경계 표본 — 큰 수·음수·소수·공백. Q1 검사기의 무작위 표본(0~99)이 닿지 않는 범위 (DEFER-Q1-9c3b4caa-1)
BOUNDARY_SAMPLES = {
    "좌표": ("(100, 0)", "(0, 100)", "(-100, -250)", "(3.25, -0.5)", "( 12 ,  -7 )", "(999,999)", "(-0.75,12.5)", "(1000000, -1)"),
    "일차식": ("y = 100x + 1", "y = -12.5x - 30", "y = 100", "y=x", "y = -x", "z = 10t + 250", "y = 0.25x", "y = 1000x - 999"),
}
MATH_FRAGMENT_RES = (re.compile(r"\([^()]*\d[^()]*\)"), re.compile(r"\b[a-z]\s*=\s*-?[\w.]+(?:\s*[+-]\s*[\w.]+)*"))


@dataclass
class Bundle:
    graph: dict
    spec: dict
    glossary: dict
    events: dict
    values: dict
    k0_text: str
    k3_text: str
    k5_text: str
    decisions_text: str
    intent_text: str
    evidence_ids: frozenset


def load_bundle(root: Path = ROOT, graph_path: str = GRAPH_PATH) -> Bundle:
    graph = json.loads((root / graph_path).read_text(encoding="utf-8"))
    read_yaml = lambda rel: yaml.safe_load((root / rel).read_text(encoding="utf-8"))  # noqa: E731
    read_text = lambda rel: (root / rel).read_text(encoding="utf-8")  # noqa: E731
    return Bundle(graph, read_yaml(graph["world_spec"]), read_yaml(graph["glossary"]), read_yaml(graph["events"]),
                  read_yaml(graph["canonical_values"]), read_text(K0_PATH), read_text(K3_PATH), read_text(K5_PATH), read_text("decisions.md"),
                  read_text("intent.md"), frozenset(json.loads(line).get("id") for line in read_text("evidence.jsonl").splitlines() if line.strip()))


# ---------- 공용 ----------

def walk(node, fields: set[str]):
    """fields 에 든 이름의 값을 모두 꺼낸다(문자열 또는 문자열 목록)."""
    if isinstance(node, dict):
        for name, value in node.items():
            if name in fields:
                for item in value if isinstance(value, list) else [value]:
                    if item is not None:
                        yield name, item
            yield from walk(value, fields)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item, fields)


def squash(text) -> str:
    """띄어쓰기·대소문자를 무시하고 비교하려고 공백을 지우고 소문자로 바꾼다."""
    return re.sub(r"\s+", "", str(text)).lower()


def goals(b: Bundle) -> dict[str, dict]:
    return {g["term_id"]: g for g in b.spec.get("language_goals", [])}


def missions(b: Bundle) -> dict[str, dict]:
    return {m["id"]: m for m in b.graph.get("missions", [])}


def cv(b: Bundle) -> dict[str, dict]:
    return {v["id"]: v for v in b.values.get("values", []) if isinstance(v, dict)}


def cv_value(b: Bundle, cv_id: str):
    return cv(b).get(cv_id, {}).get("value")


def cv_dict(b: Bundle, cv_id: str) -> dict:
    """객체여야 하는 정본 값. 형식이 틀리면 빈 객체 — 형식 오류는 Q2-C4 가 알린다."""
    value = cv_value(b, cv_id)
    return value if isinstance(value, dict) else {}


def event_names(b: Bundle) -> list[str]:
    return [e["name"] for e in b.events.get("onboarding_funnel", []) + b.events.get("custom_events", [])]


def find_cycle(edges: dict[str, list[str]]) -> list[str] | None:
    state, stack = {}, []

    def visit(node):
        state[node] = 1
        stack.append(node)
        for nxt in edges.get(node, []):
            if state.get(nxt) == 1:
                return stack[stack.index(nxt):] + [nxt]
            if nxt in edges and not state.get(nxt):
                found = visit(nxt)
                if found:
                    return found
        state[node] = 2
        stack.pop()
        return None

    for node in edges:
        if not state.get(node):
            found = visit(node)
            if found:
                return found
    return None


def ancestors(mission_id: str, by_id: dict[str, dict]) -> set[str]:
    seen, todo = set(), list(by_id.get(mission_id, {}).get("requires", []))
    while todo:
        cur = todo.pop()
        if cur not in seen and cur in by_id:
            seen.add(cur)
            todo.extend(by_id[cur].get("requires", []))
    return seen


def section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1) if match else ""


def k0_items(text: str) -> list[str]:
    rows = [ln.strip() for ln in section(text, "3.").splitlines() if ln.strip().startswith("|")]
    rows = [r for r in rows if not re.fullmatch(r"\|[\s:\-|]+", r)][1:]  # 구분 줄과 머리 줄을 뺀다
    return [r.strip("|").split("|")[0].split(" — ")[0].strip().strip("*").strip() for r in rows]


def k5_funnel(text: str) -> tuple[list[str], str]:
    """K5 §5 퍼널 이름과, 이름·화살표가 아닌 남은 글자(읽지 못한 것)."""
    block = re.search(r"```text\n(.*?)```", section(text, "5."), re.S)
    body = re.sub(r"\([^)]*\)", "", block.group(1)) if block else ""
    names = re.findall(r"[a-z][a-z0-9_]*", body)
    return names, re.sub(r"[a-z][a-z0-9_]*|→|\s", "", body)


def k3_allowed(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", section(text, "4."))
    para = next((p for p in paragraphs if p.strip().startswith("수집해도 되는 이벤트")), "")
    line = " ".join(para.split())
    return [item.strip().rstrip(".") for item in line.split("): ", 1)[-1].split(" · ")] if line else []


def decided_rows(decisions_text: str) -> dict[str, str]:
    """decisions.md 상태 표에서 '결정됨' 인 ID 와 그 행 전체."""
    return {m.group(1): m.group(0) for m in re.finditer(r"^\|\s*(DEC-\d+|REVIEW)\s*\|\s*결정됨\s*\|.*$", decisions_text, re.M)}


def dotted(doc, path: str):
    for part in path.split("."):
        if not isinstance(doc, dict) or part not in doc:
            return None
        doc = doc[part]
    return doc


def value_shape_errors(value, shape, where: str) -> list[str]:
    text = lambda x: isinstance(x, str) and bool(x.strip())  # noqa: E731
    number = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)  # noqa: E731
    leaf = {
        T: (text, "비지 않은 글자여야 한다"), T0: (lambda x: x is None or text(x), "글자나 null 이어야 한다"),
        B: (lambda x: isinstance(x, bool), "true/false 여야 한다"),
        N: (lambda x: x is None or (isinstance(x, int) and not isinstance(x, bool)), "정수나 null 이어야 한다"),
        I: (lambda x: isinstance(x, int) and not isinstance(x, bool) and x > 0, "양의 정수여야 한다"),
        P: (lambda x: number(x) and x > 0, "양수여야 한다"), ONE: (lambda x: x == 1 and not isinstance(x, bool), "형식 판(schema_version)은 1 이어야 한다"),
        LT: (lambda x: isinstance(x, list) and all(text(i) for i in x) and len(set(x)) == len(x), "글자 목록이어야 한다 (겹치지 않게)"),
        LN: (lambda x: isinstance(x, list) and all(number(i) for i in x), "수 목록이어야 한다"),
        TL: (lambda x: text(x) or (isinstance(x, list) and all(text(i) for i in x)), "글자나 글자 목록이어야 한다"),
        ANY: (lambda x: True, ""),
    }
    if isinstance(shape, str):
        ok, message = leaf[shape]
        return [] if ok(value) else [f"{where}: {message}"]
    if isinstance(shape, tuple):  # ("map", 값 형식)
        if not isinstance(value, dict) or not all(text(k) for k in value):
            return [f"{where}: 글자 키 사전이어야 한다"]
        return [e for k, v in value.items() for e in value_shape_errors(v, shape[1], f"{where}.{k}")]
    if isinstance(shape, list):  # [항목 형식]
        if not isinstance(value, list):
            return [f"{where}: 목록이어야 한다"]
        return [e for i, item in enumerate(value) for e in value_shape_errors(item, shape[0], f"{where}[{i}]")]
    if not isinstance(value, dict):
        return [f"{where}: 객체여야 한다"]
    names = {k.lstrip("?"): k for k in shape}
    required = {k for k in shape if not k.startswith("?")}
    label = f"{where}<{value.get('id') or value.get('kind')}>" if isinstance(value.get("id") or value.get("kind"), str) else where
    errors = [f"{label}: 모르는 항목 {sorted(set(value) - set(names))}"] if set(value) - set(names) else []
    errors += [f"{label}: 항목 {sorted(required - set(value))} 가 없다"] if required - set(value) else []
    return errors + [e for key in set(names) & set(value) for e in value_shape_errors(value[key], shape[names[key]], f"{where}.{key}")]


def guarded(check):
    """형식이 틀린 입력에서 검사가 멈추지 않고 오류로 알리게 한다(멈추면 그 기준은 실패로 본다)."""
    @functools.wraps(check)
    def run(b: Bundle) -> list[str]:
        try:
            return check(b)
        except (TypeError, AttributeError, KeyError, ValueError, IndexError) as exc:
            return [f"{check.__name__}: 형식이 틀려 검사를 끝까지 하지 못했다 ({type(exc).__name__}: {exc})"]
    return run


# ---------- Q2-C1 형식·참조·순환 ----------

@guarded
def check_references(b: Bundle) -> list[str]:
    errors, g, spec = value_shape_errors(b.graph, GRAPH_SHAPE, "graph"), b.graph, b.spec
    market = spec.get("market", {})
    for group, (field, pattern) in ID_PATTERNS.items():
        errors += [f"{group}: id '{x.get(field)}' 가 '{pattern}' 형식이 아니다" for x in g.get(group, [])
                   if isinstance(x, dict) and not re.fullmatch(pattern, str(x.get(field)))]
        ids = [x.get(field) for x in g.get(group, []) if isinstance(x, dict)]
        if len(ids) != len(set(map(str, ids))):
            errors.append(f"{group}: id 가 중복된다")
    expected_spec = f"specs/worlds/{str(g.get('world_id')).replace('_', '-')}.yaml"
    for field, want in (("world_spec", expected_spec), ("canonical_values", CANONICAL_PATH), ("events", EVENTS_PATH)):
        if g.get(field) != want:
            errors.append(f"{field}: {want} 이어야 한다 ({g.get(field)})")
    errors += [f"reuse_contexts/{c['id']}: id 가 용어 이름(ctx.{str(c.get('term_id')).split('.')[-1]}.…)으로 시작하지 않는다" for c in g.get("reuse_contexts", [])
               if not str(c.get("id")).startswith(f"ctx.{str(c.get('term_id')).split('.')[-1]}.")]
    if g.get("id") != f"{g.get('world_id')}.graph":
        errors.append(f"id: Graph id 는 world_id 뒤에 .graph 를 붙인 것이어야 한다 ({g.get('id')})")
    for field, expected in (("world_id", spec.get("id")), ("market_id", market.get("market_id")),
                            ("curriculum_id", market.get("curriculum_id")), ("glossary", spec.get("safety", {}).get("banned_terms_ref"))):
        if g.get(field) != expected:
            errors.append(f"{field}: Q1 명세 값({expected})과 다르다 ({g.get(field)})")
    q1 = goals(b)
    terms = {t["term_id"]: t for t in g.get("terms", [])}
    if set(terms) != set(q1):
        errors.append(f"terms: Q1 명세의 용어와 다르다 (Graph {sorted(terms)} · Q1 {sorted(q1)})")
    by_id = missions(b)
    for t in terms.values():
        errors += [f"terms/{t['term_id']}: 선수 용어 {p} 가 없다" for p in t.get("prerequisites", []) if p not in terms]
        if t.get("first_mission") not in by_id:
            errors.append(f"terms/{t['term_id']}: 첫 미션 {t.get('first_mission')} 가 없다")
    reward_ids = {x["id"] for x in g.get("rewards", [])}
    ladders = {h["id"]: h for h in g.get("hint_ladders", [])}
    coops = {c["id"]: c for c in g.get("coop", [])}
    for m in by_id.values():
        errors += [f"missions/{m['id']}: 선행 미션 {r} 가 없다" for r in m.get("requires", []) if r not in by_id]
        term = m.get("new_term")
        if term is not None and term not in q1:
            errors.append(f"missions/{m['id']}: 새 용어 {term} 가 Q1 명세에 없다")
        for step in m.get("steps", []):
            allowed = {"everyday_expression": "everyday_expression_keys", "player_action": "everyday_action_keys"}.get(step.get("kind"))
            if allowed:
                errors += [f"missions/{m['id']}: {k} 는 Q1 명세의 {term} {allowed} 가 아니다"
                           for k in step.get("keys", []) if k not in q1.get(term, {}).get(allowed, [])]
            if step.get("kind") == "math_label" and step.get("key") != q1.get(term, {}).get("label_key"):
                errors.append(f"missions/{m['id']}: 이름표 {step.get('key')} 가 Q1 명세의 {term} label_key 가 아니다")
            errors += [f"missions/{m['id']}: 보상 {r} 가 없다" for r in step.get("ids", []) if r not in reward_ids]
            given = sorted(r["id"] for r in g.get("rewards", []) if r.get("mission") == m["id"] and r.get("basis") == "completion")
            if step.get("kind") == "reward" and sorted(step.get("ids", [])) != given:
                errors.append(f"missions/{m['id']}: 보상 단계 {step.get('ids')} 가 이 미션의 완주 보상 {given} 과 다르다")
        if m.get("hint_ladder") and ladders.get(m["hint_ladder"], {}).get("mission") != m["id"]:
            errors.append(f"missions/{m['id']}: 힌트 사다리 {m['hint_ladder']} 가 없거나 다른 미션의 것이다")
        if m.get("coop") and coops.get(m["coop"], {}).get("mission") != m["id"]:
            errors.append(f"missions/{m['id']}: 협동 {m['coop']} 가 없거나 다른 미션의 것이다")
    contexts = g.get("reuse_contexts", [])
    for c in contexts:
        if c.get("term_id") not in terms:
            errors.append(f"reuse_contexts/{c['id']}: 용어 {c.get('term_id')} 가 없다")
        if c.get("mission") not in by_id:
            errors.append(f"reuse_contexts/{c['id']}: 미션 {c.get('mission')} 가 없다")
        actions = q1.get(c.get("term_id"), {}).get("everyday_action_keys", [])
        errors += [f"reuse_contexts/{c['id']}: 행동 {k} 는 Q1 명세의 {c.get('term_id')} 행동이 아니다" for k in c.get("action_keys", []) if k not in actions]
    for c in contexts:
        if c.get("hint_ladder") is not None and ladders.get(c["hint_ladder"], {}).get("term") != c.get("term_id"):
            errors.append(f"reuse_contexts/{c['id']}: 힌트 사다리 {c['hint_ladder']} 가 없거나 이 용어의 재사용 사다리가 아니다")
    for h in ladders.values():
        if ("mission" in h) == ("term" in h):
            errors.append(f"hint_ladders/{h['id']}: 미션 사다리(mission)나 재사용 사다리(term) 중 하나여야 한다")
        elif "mission" in h and by_id.get(h.get("mission"), {}).get("hint_ladder") != h["id"]:
            errors.append(f"hint_ladders/{h['id']}: 미션 {h.get('mission')} 가 없거나 이 사다리를 쓰지 않는다")
        elif "term" in h and not any(c.get("hint_ladder") == h["id"] for c in contexts):
            errors.append(f"hint_ladders/{h['id']}: 이 재사용 사다리를 쓰는 맥락이 없다")
        if h.get("rule") != "cv.hint_ladder":
            errors.append(f"hint_ladders/{h['id']}: 규칙은 정본 값 cv.hint_ladder 여야 한다")
    roles = {r["id"] for r in g.get("roles", [])}
    for c in coops.values():
        if by_id.get(c.get("mission"), {}).get("coop") != c["id"]:
            errors.append(f"coop/{c['id']}: 미션 {c.get('mission')} 가 없거나 이 협동을 쓰지 않는다")
        errors += [f"coop/{c['id']}: 역할 {r} 가 없다" for r in c.get("roles", []) if r not in roles]
        if c.get("npc_fallback") != spec.get("coop", {}).get("npc_fallback"):
            errors.append(f"coop/{c['id']}: NPC {c.get('npc_fallback')} 가 Q1 명세의 npc_fallback 이 아니다")
    errors += [f"rewards/{r['id']}: 미션 {r.get('mission')} 가 없다" for r in g.get("rewards", []) if r.get("mission") not in by_id]
    if g.get("pacing", {}).get("stop_point", {}).get("mission") not in by_id:
        errors.append("pacing/stop_point: 미션이 없다")
    names = set(event_names(b))
    for s in g.get("scenarios", []):
        errors += [f"scenarios/{s['id']}: 미션 {p} 가 없다" for p in s.get("path", []) if p not in by_id]
        errors += [f"scenarios/{s['id']}: 이벤트 {e} 가 허용 목록에 없다" for e in s.get("expects_events", []) if e not in names]
        if s.get("input") not in spec.get("input_methods", []):
            errors.append(f"scenarios/{s['id']}: 입력 {s.get('input')} 가 Q1 명세 input_methods 에 없다")
    strings = b.glossary.get("strings", {})
    errors += [f"문구 키 {key} ({field}) 가 용어집에 없다" for field, key in walk(g, STRING_KEY_FIELDS | {"action_keys"}) if key not in strings]
    known_cv = cv(b)
    errors += [f"정본 값 {ref} ({field}) 가 없다" for field, ref in walk(g, PARAM_FIELDS) if ref not in known_cv]
    cycle = find_cycle({m_id: m.get("requires", []) for m_id, m in by_id.items()})
    if cycle:
        errors.append(f"missions: 선행 관계가 순환한다 ({' → '.join(cycle)})")
    cycle = find_cycle({t_id: t.get("prerequisites", []) for t_id, t in terms.items()})
    if cycle:
        errors.append(f"terms: 선수 용어가 순환한다 ({' → '.join(cycle)})")
    return errors


# ---------- Q2-C2 일상어 경로·재사용 ----------

@guarded
def check_reuse(b: Bundle) -> list[str]:
    errors, by_id, q1 = [], missions(b), goals(b)
    for m in by_id.values():
        kinds = [s.get("kind") for s in m.get("steps", [])]
        errors += [f"missions/{m['id']}: 단계 종류 {k} 는 쓸 수 없다 (퀴즈·정의 카드 금지, INV-8·INV-15)" for k in kinds if k not in STEP_FIELDS]
        for s in m.get("steps", []):
            need, extra = STEP_FIELDS.get(s.get("kind"), (set(), set()))
            have = set(s) - {"kind"}
            if s.get("kind") in STEP_FIELDS and (not need <= have or have - need - extra or any(s.get(k) in ([], "", None) for k in need)):
                errors.append(f"missions/{m['id']}: {s.get('kind')} 단계는 {sorted(need)} 가 꼭 있어야 하고 {sorted(need | extra)} 밖의 항목은 쓸 수 없다")
        if kinds.count("math_label") > 1:
            errors.append(f"missions/{m['id']}: 한 미션에 새 이름표가 {kinds.count('math_label')}개다 (INV-15 하나만)")
        if "math_label" in kinds and not m.get("new_term"):
            errors.append(f"missions/{m['id']}: 이름표가 있는데 new_term 이 없다")
        if not m.get("steps") and not any(c.get("mission") == m["id"] for c in b.graph.get("reuse_contexts", [])):
            errors.append(f"missions/{m['id']}: 단계도 재사용 맥락도 없는 빈 미션이다")
    for t in b.graph.get("terms", []):
        term, goal, first = t["term_id"], q1.get(t["term_id"], {}), by_id.get(t.get("first_mission"), {})
        introducing = [m["id"] for m in by_id.values() if m.get("new_term") == term]
        if introducing != [first.get("id")]:
            errors.append(f"{term}: 이 용어를 새로 붙이는 미션은 첫 미션 하나뿐이어야 한다 ({introducing})")
        expected = [k for k in goal.get("sequence", []) if k != "reuse"]
        kinds = [s.get("kind") for s in first.get("steps", [])]
        if kinds != expected:
            errors.append(f"{term}: 첫 미션 단계 순서가 Q1 순서 {expected} 와 다르다 ({kinds})")
        for kind, field in (("everyday_expression", "everyday_expression_keys"), ("player_action", "everyday_action_keys")):
            offered = {k for s in first.get("steps", []) if s.get("kind") == kind for k in s.get("keys", [])}
            if offered != set(goal.get(field, [])):
                errors.append(f"{term}: 첫 미션이 Q1 {field} 를 모두 제시하지 않는다")
        before = ancestors(first.get("id", ""), by_id)
        earlier = sorted(x["term_id"] for x in b.graph["terms"] if x.get("first_mission") in before)
        if sorted(t.get("prerequisites", [])) != earlier:
            errors.append(f"{term}: 선수 용어 {t.get('prerequisites')} 가 앞에서 먼저 배운 용어 {earlier} 와 다르다 (앞에서 배운 말 위에 쌓는다)")
        for pre in t.get("prerequisites", []):
            pre_first = next((x.get("first_mission") for x in b.graph["terms"] if x["term_id"] == pre), None)
            if pre_first not in before:
                errors.append(f"{term}: 선수 용어 {pre} 의 첫 미션이 이 용어의 첫 미션보다 앞서지 않는다")
        contexts = [c for c in b.graph.get("reuse_contexts", []) if c.get("term_id") == term]
        if len(contexts) < 3:
            errors.append(f"{term}: 재사용 맥락이 {len(contexts)}개다 (3개 이상)")
        for field in ("mission", "situation_key", "response_key"):
            if len({c.get(field) for c in contexts}) != len(contexts):
                errors.append(f"{term}: 재사용 맥락끼리 {field} 가 겹친다 (서로 다른 맥락이어야 한다)")
        for c in contexts:
            if first.get("id") not in ancestors(c.get("mission", ""), by_id):
                errors.append(f"{term}: 재사용 맥락 {c['id']} 가 이름표를 붙이는 첫 미션 뒤에 오지 않는다")
            if sorted(c.get("accepts", [])) != ["everyday", "label"]:
                errors.append(f"{term}: 재사용 맥락 {c['id']} 는 일상어와 수학 이름 둘 다로 진행되어야 한다 (INV-15 — 일상어로 언제나, 이름표는 고를 수 있게)")
            if not c.get("action_keys"):
                errors.append(f"{term}: 재사용 맥락 {c['id']} 에 행동이 없다 (행동과 월드 결과가 이어진 재사용만 센다)")
    return errors


# ---------- Q2-C3 분석 이벤트 ----------

@guarded
def check_events(b: Bundle) -> list[str]:
    errors, ev = value_shape_errors(b.events, EVENTS_SHAPE, "events"), b.events
    items = ev.get("onboarding_funnel"), ev.get("custom_events")
    if not isinstance(ev.get("fields"), dict) or not all(isinstance(x, list) and all(isinstance(e, dict) for e in x) for x in items):
        return errors  # 큰 틀이 틀리면 나머지는 검사할 수 없다 — 형식 오류만 알린다
    fields, limits = ev.get("fields", {}), ev.get("limits", {})
    if limits.get("max_fields_per_event", 99) > MAX_FIELDS_PER_EVENT or limits.get("max_custom_events", 999) > MAX_CUSTOM_EVENTS:
        errors.append("limits: 플랫폼 한도(필드 3개·이벤트 100개, F10)보다 크다")
    if ev.get("transport") != TRANSPORT or ev.get("sent_by") != "server":
        errors.append(f"transport: 분석은 {TRANSPORT} 로 서버에서만 보낸다 (F10)")
    errors += [f"platform_metrics: '{m}' 는 platform. 으로 시작하는 이름이어야 한다" for m in ev.get("platform_metrics", []) if not re.fullmatch(r"platform\.[a-z0-9_]+", str(m))]
    names = event_names(b)
    if len(names) != len(set(names)):
        errors.append("이벤트 이름이 중복된다")
    steps = [e.get("step") for e in ev.get("onboarding_funnel", [])]
    if steps != list(range(1, len(steps) + 1)):
        errors.append("onboarding_funnel: 단계 번호가 1부터 이어지지 않는다")
    errors += [f"onboarding_funnel/{e['name']}: 온보딩 퍼널은 사용자당 한 번만 센다 (frequency once_per_user, F11)"
               for e in ev.get("onboarding_funnel", []) if e.get("frequency") != "once_per_user"]
    for name, values in fields.items():
        if name not in ALLOWED_FIELDS:
            errors.append(f"fields/{name}: 허용 목록에 없는 필드다 (INV-10)")
        if not isinstance(values, list) or not values or len(set(values)) != len(values):
            errors.append(f"fields/{name}: 값은 중복 없는 열거형 목록이어야 한다")
        elif not all(isinstance(v, str) and ENUM_VALUE_RE.fullmatch(v) for v in values):
            errors.append(f"fields/{name}: 열거형 토큰이 아닌 값이 있다 (자유 텍스트·숫자 금지)")
    for e in ev.get("onboarding_funnel", []) + ev.get("custom_events", []):
        if e["name"] not in ALLOWED_EVENTS:
            errors.append(f"{e['name']}: 허용 목록에 없는 이벤트다 (INV-10)")
        if e.get("frequency") not in FREQUENCIES or e.get("trigger", SERVER_CONFIRMED) != SERVER_CONFIRMED:
            errors.append(f"{e['name']}: 보내는 빈도는 {sorted(FREQUENCIES)} 중 하나, 발생 조건은 {SERVER_CONFIRMED} 만")
        if len(e.get("fields", [])) > MAX_FIELDS_PER_EVENT:
            errors.append(f"{e['name']}: 필드가 {len(e['fields'])}개다 (3개 이하, F10)")
        errors += [f"{e['name']}: 필드 {f} 가 열거형 사전에 없다" for f in e.get("fields", []) if f not in fields]
    g, by_id = b.graph, missions(b)
    expected = {"mission": set(by_id), "term": {t["term_id"] for t in g.get("terms", [])},
                "context": {c["id"] for c in g.get("reuse_contexts", [])}, "input": set(b.spec.get("input_methods", [])),
                "play_mode": {p for m in g.get("missions", []) for p in m.get("play_modes", [])}, "expression_used": {"everyday", "label"},
                "hint_level": {f"level_{i + 1}" for i in range(len(cv_dict(b, "cv.hint_ladder").get("levels") or []))}}
    errors += [f"fields/{name}: 값이 Graph·Q1 의 id 와 다르다" for name, ids in expected.items() if set(fields.get(name, [])) != ids]
    errors += check_north_star(b, by_id)
    targets = set(names) | set(ev.get("platform_metrics", []))
    mapping = ev.get("source_mapping", {})
    k5_names, k5_unread = k5_funnel(b.k5_text)
    if k5_unread:
        errors.append(f"source_mapping/k5_funnel: {K5_PATH} §5 에서 읽지 못한 글자가 있다 ({k5_unread[:30]})")
    for label, source, parsed in (("k5_funnel", K5_PATH, k5_names), ("k3_allowed", K3_PATH, k3_allowed(b.k3_text))):
        if not parsed:
            errors.append(f"source_mapping/{label}: 원천 목록을 {source} 에서 읽지 못했다")
        errors += [f"source_mapping/{label}: 원천 이벤트 '{n}' 이 대응되지 않았다" for n in parsed if n not in mapping.get(label, {})]
    for label, table in mapping.items():
        errors += [f"source_mapping/{label}/{src}: 대응 대상이 비었다" for src, dst in table.items() if dst in ([], "", None)]
        for src, dst in table.items():
            errors += [f"source_mapping/{label}/{src}: {d} 가 허용 목록·플랫폼 지표에 없다" for d in (dst if isinstance(dst, list) else [dst])
                       if not (isinstance(d, str) and d in targets)]
    renamed = cv_dict(b, "cv.events").get("renamed") or {}
    errors += [f"source_mapping/k5_funnel/{src}: K5 이름을 바꿨는데 정본 값 cv.events.renamed 에 없다" for src, dst in mapping.get("k5_funnel", {}).items()
               if dst != src and renamed.get(src) != dst]
    return errors


def check_north_star(b: Bundle, by_id: dict[str, dict]) -> list[str]:
    errors, ev = [], b.events
    ns = ev.get("north_star", {})
    num, den = ns.get("numerator", {}), ns.get("denominator", {})
    custom = {e["name"]: e for e in ev.get("custom_events", [])}
    if num.get("event") != NS_NUMERATOR or den.get("event") != NS_DENOMINATOR:
        errors.append(f"north_star: 분자는 {NS_NUMERATOR}, 분모는 {NS_DENOMINATOR} 이어야 한다 (intent §1 정의)")
    if num.get("event") not in custom or num.get("aggregation") != "count" \
            or not {"term", "context", "expression_used"} <= set(custom[num["event"]].get("fields", [])):
        errors.append("north_star: 분자는 term·context·expression_used 필드를 가진 사용자 정의 이벤트의 횟수여야 한다")
    if den.get("event") not in custom or den.get("event") == num.get("event") or den.get("aggregation") != "count_unique_users":
        errors.append("north_star: 분모는 매 세션 보내는 다른 사용자 정의 이벤트의 고유 사용자 수여야 한다 (온보딩 퍼널은 한 번만 센다, F11)")
    if num.get("window_days") != 7 or den.get("window_days") != 7:
        errors.append("north_star: 주간 지표다 — 분자·분모 모두 7일")
    num_event, den_event = custom.get(num.get("event"), {}), custom.get(den.get("event"), {})
    if num_event.get("trigger") != SERVER_CONFIRMED or num_event.get("frequency") != "once_per_context_per_session":
        errors.append(f"north_star: 분자 이벤트는 서버가 월드 결과를 확인했을 때만({SERVER_CONFIRMED}), 맥락당 세션 1번만 보낸다")
    if den_event.get("frequency") != "every_session":
        errors.append("north_star: 분모 이벤트는 매 세션 보낸다 (frequency every_session)")
    if num.get("filter") != {"expression_used": ["label"]}:
        errors.append("north_star: 분자는 수학 이름표로 말한 재사용만 센다 (filter expression_used = [label])")
    if num.get("contexts") != "optional_missions":
        errors.append("north_star: 분자는 선택 미션의 맥락만 센다 (contexts optional_missions — 필수 경로는 강제 튜토리얼)")
    if "label" not in ev.get("fields", {}).get("expression_used", []):
        errors.append("north_star: expression_used 에 label 값이 없어 '용어 사용'을 셀 수 없다")
    if ns.get("per_player_storage") is not False:
        errors.append("north_star: 플레이어별 저장 없이 집계로만 잰다 (DEC-12 결정 전)")
    counted = {c["term_id"] for c in b.graph.get("reuse_contexts", []) if not by_id.get(c.get("mission"), {}).get("core", True)}
    errors += [f"north_star: {t['term_id']} 를 셀 선택 미션 맥락이 없다 (필수 경로 재사용은 세지 않는다)"
               for t in b.graph.get("terms", []) if t["term_id"] not in counted]
    return errors


# ---------- Q2-C4 정본 값 ----------

@guarded
def check_canonical(b: Bundle) -> list[str]:
    errors, entries, values = [], b.values.get("values", []), cv(b)
    errors += value_shape_errors(b.values, CANONICAL_SHAPE, "canonical")
    if b.values.get("source") != K0_PATH:
        errors.append(f"canonical: source 는 충돌 표가 있는 {K0_PATH} 이어야 한다")
    items = k0_items(b.k0_text)
    if not items:
        errors.append(f"{K0_PATH} §3 표를 읽지 못했다")
    by_item = {}
    for e in entries:
        by_item.setdefault(e.get("k0_item"), []).append(e.get("id"))
    errors += [f"K0 §3 '{i}' 의 정본 값이 없다" for i in items if i not in by_item]
    errors += [f"K0 §3 '{i}' 의 정본 값이 {len(ids)}개다 (하나만)" for i, ids in by_item.items() if i in items and len(ids) > 1]
    errors += [f"{ids[0]}: K0 §3 에 없는 항목 '{i}'" for i, ids in by_item.items() if i not in items]
    if len(values) != len(entries):
        errors.append("values: id 가 중복된다")
    decided = decided_rows(b.decisions_text)
    for e in entries:
        eid = e.get("id", "?")
        if not CV_ID_RE.fullmatch(str(eid)):
            errors.append(f"{eid}: id 는 cv.이름 형식이어야 한다")
        if eid not in CV_SHAPES:
            errors.append(f"{eid}: 검사기에 형식이 없는 정본 값이다 (CV_SHAPES 에 더하고 리뷰를 받는다)")
        else:
            errors += value_shape_errors(e.get("value"), CV_SHAPES[eid], f"{eid}.value")
        if e.get("value") in (None, "", [], {}):
            errors.append(f"{eid}: 값이 비었다")
        if e.get("status") not in STATUSES:
            errors.append(f"{eid}: status 는 {sorted(STATUSES)} 중 하나")
        q1_paths = e.get("q1_paths") or {}
        for field, path in q1_paths.items():
            if not isinstance(e.get("value"), dict) or dotted(b.spec, path) is None or e["value"].get(field) != dotted(b.spec, path):
                errors.append(f"{eid}: q1_paths {field} → {path} 의 Q1 명세 값과 다르다")
        dec, field = DECIDED_BY.get(eid, (None, None))
        by_dec = dec in e.get("refs", []) and dec in decided and isinstance(e.get("value"), dict) \
            and str(e["value"].get(field, "\0")) in decided[dec]
        if e.get("status") == "decided" and not (q1_paths or by_dec):
            errors.append(f"{eid}: 결정된 값은 decisions.md 에서 결정됨인 관련 DEC(검사기 DECIDED_BY, 값이 그 결정 행에 있음)나 잠긴 Q1 경로(q1_paths) 근거가 있어야 한다 — 불변식에서 끌어낸 값은 proposed")
        if not e.get("refs"):
            errors.append(f"{eid}: 근거 참조(refs)가 없다")
        for ref in e.get("refs") or []:
            if not REF_RE.fullmatch(str(ref)):
                errors.append(f"{eid}: 참조 '{ref}' 는 DEC-·INV-·Q·F·K 형식이 아니다")
            elif ref.startswith(("DEC-", "INV-")) and not re.search(rf"^\|\s*{re.escape(ref)}\s*\|", b.intent_text, re.M):
                errors.append(f"{eid}: 참조 {ref} 가 intent.md 에 없다")
            elif ref.startswith("F") and ref not in b.evidence_ids:
                errors.append(f"{eid}: 참조 {ref} 가 evidence.jsonl 에 없다")
        if e.get("status") != "hypothesis" and "measure_at" in e:
            errors.append(f"{eid}: measure_at 은 가설 값에만 둔다")
        if e.get("status") == "hypothesis" and e.get("measure_at") not in LATER_STAGES:
            errors.append(f"{eid}: 가설 값은 실측할 뒤 단계(measure_at: Q3~Q8)가 있어야 한다")
    g, spec = b.graph, b.spec
    val = lambda key: cv_dict(b, key)  # noqa: E731
    gate_coop = next((c for c in g.get("coop", []) if c.get("mission") == "m.signal_slope"), {})
    signal_terms = {f"signal_{m['signal']}": m.get("new_term") or "interaction" for m in g.get("missions", []) if m.get("signal")}
    consistency = [
        ("cv.first_rewards", sorted(map(str, cv_value(b, "cv.first_rewards") or [])), sorted(r["id"] for r in g.get("rewards", []) if r.get("basis") == "completion")),
        ("cv.coop_switch_ids", sorted(map(str, cv_value(b, "cv.coop_switch_ids") or [])), sorted(o for c in g.get("coop", []) for o in c.get("objects", []))),
        ("cv.slope_choices", val("cv.slope_choices").get("expressions"), goals(b).get("term.slope", {}).get("everyday_expression_keys")),
        ("cv.helper_npc", val("cv.helper_npc").get("id"), spec.get("coop", {}).get("npc_fallback")),
        ("cv.gate_time", val("cv.gate_time").get("target_minutes"), spec.get("session", {}).get("target_minutes")),
        ("cv.gate_name", val("cv.gate_name").get("string_key"), spec.get("title_key")),
        ("cv.events", val("cv.events").get("allowlist"), g.get("events")),
        ("cv.gate_signals", {k: v for k, v in val("cv.gate_signals").items() if k.startswith("signal_")}, signal_terms),
    ]
    errors += [f"{key}: 정본 값({want})과 Graph·Q1 의 실제 값({got})이 다르다" for key, want, got in consistency if want != got]
    for (cid, *path), (want, why) in CV_PINS.items():
        if dotted(val(cid), ".".join(path)) != want:
            errors.append(f"{cid}.{'.'.join(path)}: {want} 이어야 한다 ({why})")
    for (cid, *path), (low, high) in CV_RANGES.items():
        got = dotted(val(cid), ".".join(path))
        numbers = got if isinstance(got, list) else [got]
        if any(isinstance(x, (int, float)) and not isinstance(x, bool) and not low <= x <= high for x in numbers):
            errors.append(f"{cid}.{'.'.join(path)}: {got} 이 원천 문서 범위 {low}~{high} 밖이다 (K0 §3·K6)")
    grid = val("cv.coordinate_expression").get("grid") or {}
    errors += [f"cv.coordinate_expression.grid.{axis}: [음수, 양수] 두 정수여야 한다 (기준점 0 이 가운데)" for axis in ("x", "y")
               if not (isinstance(grid.get(axis), list) and len(grid[axis]) == 2 and all(isinstance(v, int) for v in grid[axis])
                       and -MAX_CHOICE_SPAN <= grid[axis][0] < 0 < grid[axis][1] <= MAX_CHOICE_SPAN)]
    steps = val("cv.slope_choices").get("steps")
    if not (isinstance(steps, list) and steps and steps[0] == 0 and steps == sorted(set(steps)) and steps[-1] <= MAX_CHOICE_SPAN):
        errors.append(f"cv.slope_choices.steps: 0(평평)에서 시작해 겹치지 않고 커지며 {MAX_CHOICE_SPAN} 이하인 단계여야 한다")
    rate = val("cv.first_try").get("success_within_two_tries")
    if not (isinstance(rate, list) and len(rate) == 2 and all(isinstance(r, (int, float)) for r in rate) and 0 < rate[0] <= rate[1] <= 1):
        errors.append("cv.first_try.success_within_two_tries: 0 과 1 사이 [하한, 상한] 이어야 한다")
    badge = next((r.get("name_key") for r in g.get("rewards", []) if r.get("kind") == "badge" and r.get("basis") == "completion"), None)
    coop_signal = next((m.get("signal") for m in g.get("missions", []) if m.get("coop") == gate_coop.get("id")), None)
    for key, want, got in (("cv.world_title.world_key", val("cv.world_title").get("world_key"), spec.get("setting", {}).get("world_name_key")),
                           ("cv.world_title.first_title_key", val("cv.world_title").get("first_title_key"), badge),
                           ("cv.helper_npc.name_key", val("cv.helper_npc").get("name_key"), f"{spec.get('coop', {}).get('npc_fallback')}.name"),
                           ("cv.gate_signals.coop_on", val("cv.gate_signals").get("coop_on"), f"signal_{coop_signal}")):
        if want != got:
            errors.append(f"{key}: 정본 값({want})과 Graph·Q1 의 실제 값({got})이 다르다")
    distance = val("cv.server_distance")
    if all(isinstance(distance.get(k), (int, float)) for k in ("prompt_activation_studs", "server_check_studs")) \
            and distance["server_check_studs"] < distance["prompt_activation_studs"]:
        errors.append("cv.server_distance: 서버 판정 거리가 화면 프롬프트 거리보다 짧으면 정상 입력을 버린다")
    return errors


# ---------- Q2-C5 용어집 ----------

@guarded
def check_glossary(b: Bundle) -> list[str]:
    errors, gl, spec = value_shape_errors(b.glossary, GLOSSARY_SHAPE, "glossary"), b.glossary, b.spec
    if not isinstance(gl.get("strings"), dict) or not isinstance(gl.get("banned_terms"), list) or not all(isinstance(x, dict) for x in gl["banned_terms"]):
        return errors  # 큰 틀이 틀리면 나머지는 검사할 수 없다
    strings = gl.get("strings", {})
    if gl.get("market_id") != spec.get("market", {}).get("market_id"):
        errors.append("market_id: Q1 명세의 시장과 다르다")
    locale = gl.get("locale")
    if not isinstance(locale, str) or not LOCALE_RE.fullmatch(locale):
        errors.append(f"locale: IETF 언어 태그가 아니다 ({locale}, F9)")
    if locale not in spec.get("localization", {}).get("planned_locales", []):
        errors.append(f"locale: Q1 명세의 planned_locales 에 없다 ({locale})")
    if gl.get("world_spec") != b.graph.get("world_spec"):
        errors.append("world_spec: Graph 가 가리키는 명세와 다르다")
    q1_keys = [spec.get("title_key"), spec.get("setting", {}).get("world_name_key"), spec.get("coop", {}).get("npc_fallback", "") + ".name"]
    for goal in spec.get("language_goals", []):
        q1_keys += [goal.get("label_key")] + goal.get("everyday_expression_keys", []) + goal.get("everyday_action_keys", [])
    errors += [f"Q1 문구 키 {k} 가 용어집에 없다" for k in q1_keys if k not in strings]
    errors += [f"strings/{k}: 문구 키는 점으로 나눈 소문자 이름이어야 한다" for k in strings if not STRING_KEY_RE.fullmatch(str(k))]
    values = cv(b)
    names = {spec.get("setting", {}).get("world_name_key"): cv_dict(b, "cv.world_title").get("world"),
             spec.get("title_key"): cv_dict(b, "cv.gate_name").get("ko")}
    errors += [f"정본 이름 {k}: 용어집 '{strings.get(k)}' 이 정본 값 '{v}' 과 다르다" for k, v in names.items() if strings.get(k) != v]
    used = {key for _, key in walk(b.graph, STRING_KEY_FIELDS | {"action_keys"})} | set(q1_keys)
    used |= {(v.get("value") or {}).get(f) for v in values.values() if isinstance(v.get("value"), dict) for f in ("string_key", "name_key", "world_key", "first_title_key")}
    errors += [f"strings/{k}: 아무도 쓰지 않는 키다" for k in strings if k not in used]
    banned = gl.get("banned_terms", [])
    terms = [x.get("term") for x in banned if isinstance(x, dict)]
    if len(terms) != len(set(terms)):
        errors.append("banned_terms: 금지어가 겹친다")
    terms = [squash(t) for t in terms if isinstance(t, str) and t.strip()]
    missing = {squash(t) for t in REQUIRED_BANNED} - set(terms)
    if missing:
        errors.append(f"banned_terms: 반드시 있어야 할 금지어가 빠졌다 ({sorted(missing)})")
    for x in banned:
        repl = x.get("replacement")
        if repl is not None and any(t in squash(repl) for t in terms):
            errors.append(f"banned_terms/{x.get('term')}: 대체어 '{repl}' 에 금지어가 들어 있다")
    for key, text in strings.items():
        hits = [t for t in terms if t in squash(text)]
        if hits:
            errors.append(f"strings/{key}: 금지어 {hits} 가 들어 있다 (INV-11·INV-8·INV-14)")
    return errors


# ---------- Q2-C6 번역 금지 경계 ----------

def boundary_misses(patterns: list[str]) -> list[str]:
    compiled = []
    for p in patterns:
        try:
            compiled.append(re.compile(p))
        except re.error as exc:
            return [f"정규식이 아니다: {p} ({exc})"]
    misses = [f"{kind} 경계 표본 '{s}' 을 전체로 잡는 패턴이 없다" for kind, samples in BOUNDARY_SAMPLES.items()
              for s in samples if not any(c.fullmatch(s) for c in compiled)]
    return misses + [f"일상 문장 '{s}' 까지 잡는다" for s in validate_spec.PLAIN_SAMPLES if any(c.search(s) for c in compiled)]


@guarded
def check_boundary(b: Bundle) -> list[str]:
    patterns = [r.get("pattern") for r in b.spec.get("do_not_translate", []) if isinstance(r, dict)]
    if not patterns:
        return ["Q1 명세에 번역 금지 패턴이 없다"]
    errors = boundary_misses(patterns)
    if errors and errors[0].startswith("정규식이 아니다"):
        return errors
    # 용어집 문구 속 좌표·식도 번역 금지 구간으로 전부 잡혀야 한다
    for key, text in b.glossary.get("strings", {}).items():
        for frag in (f.strip() for rx in MATH_FRAGMENT_RES for f in rx.findall(str(text))):
            if not any(re.fullmatch(p, frag) for p in patterns):
                errors.append(f"strings/{key}: 수식 조각 '{frag}' 이 번역 금지 패턴에 잡히지 않는다")
    return errors


# ---------- Q2-C7 설계 규칙 ----------

def answer_tie_errors(b: Bundle, owner: str, term: str, answers: list[str], ladder: dict) -> list[str]:
    """목표 표현은 그 용어의 일상 표현으로 말해야 하고(INV-15), 힌트 문구는 목표 표현을 그대로 말하지 않는다(INV-8)."""
    strings = b.glossary.get("strings", {})
    words = [squash(strings.get(k, "")) for k in goals(b).get(term, {}).get("everyday_expression_keys", []) if strings.get(k)]
    errors = [f"{owner}: 목표 표현 '{a}' 이 {term} 의 일상 표현으로 되어 있지 않다" for a in answers if not any(w and w in squash(a) for w in words)]
    # 목표 표현의 구성 요소(쉼표로 나눈 조각)를 모두 담은 힌트는 순서를 바꿔도 정답 공개다. 바꿔 말한 표현의 판단은 사람 검토
    return errors + [f"hint {k}: {owner} 의 목표 표현 '{a}' 의 구성 요소를 모두 말한다 (INV-8)" for k in ladder.get("keys", []) for a in answers
                     if all(squash(part) in squash(strings.get(k, "")) for part in a.split(",") if part.strip())]


@guarded
def check_design_rules(b: Bundle) -> list[str]:
    errors, g, spec, by_id = [], b.graph, b.spec, missions(b)
    for r in g.get("rewards", []):
        rid = r.get("id")
        if r.get("granted_by") != "server":
            errors.append(f"rewards/{rid}: 서버만 보상을 정한다 (INV-4)")
        if r.get("basis") in GRANTED_TO and r.get("granted_to") != GRANTED_TO[r["basis"]]:
            errors.append(f"rewards/{rid}: {r['basis']} 보상은 {GRANTED_TO[r['basis']]} 에게만 (INV-4 — 기본 보상은 완주한 모두에게 같게, 협동 보너스는 기여한 사람에게)")
        if r.get("basis") not in ("completion", "role_contribution"):
            errors.append(f"rewards/{rid}: 보상 기준은 완주 또는 역할 기여만 (INV-4) — {r.get('basis')}")
        if r.get("basis") == "role_contribution" and r.get("kind") != "cosmetic":
            errors.append(f"rewards/{rid}: 협동 보너스는 진행에 영향 없는 꾸미기만 (INV-9 혼자도 같은 진행)")
        if r.get("kind") not in ("card", "badge", "ability_unlock", "cosmetic"):
            errors.append(f"rewards/{rid}: 보상 종류 {r.get('kind')} 는 쓸 수 없다 (화폐·무작위·유료 없음, INV-12)")
    rule = cv_dict(b, "cv.hint_ladder")
    if rule.get("reveals_answer") is not False or rule.get("tried_marker") is not True or rule.get("cost") != "free":
        errors.append("cv.hint_ladder: 정답을 보여 주지 않고, 해 본 선택에 표시를 남기고, 무료여야 한다 (INV-8)")
    if rule.get("levels") != HINT_KINDS or rule.get("advance") != "after_one_attempt":
        errors.append(f"cv.hint_ladder: 단계는 {HINT_KINDS} 이고 다음 단계는 한 번 해 본 뒤에만 (K6 R3)")
    trigger = rule.get("first_trigger") if isinstance(rule.get("first_trigger"), dict) else {}
    if not all(isinstance(trigger.get(k), (int, float)) for k in ("idle_seconds", "other_results")):
        errors.append("cv.hint_ladder: 첫 힌트 조건(진행 없음 시간·다른 결과 횟수)이 없다")
    strings, ladders = b.glossary.get("strings", {}), {h["id"]: h for h in g.get("hint_ladders", [])}
    for m in by_id.values():
        if not m.get("new_term"):
            continue
        ladder = ladders.get(m.get("hint_ladder"), {})
        if ladder.get("mission") != m["id"]:
            errors.append(f"missions/{m['id']}: 수학 미션에 자기 힌트 사다리가 없다 (INV-8)")
        if len(ladder.get("keys", [])) != len(rule.get("levels", [])):
            errors.append(f"missions/{m['id']}: 힌트 문구 수가 힌트 단계 수와 다르다")
        answers = [strings.get(k, "") for k in m.get("answer_keys", []) if strings.get(k)]
        if not answers:
            errors.append(f"missions/{m['id']}: 목표 표현(answer_keys)이 없어 정답 공개를 검사할 수 없다")
        errors += answer_tie_errors(b, m["id"], m["new_term"], answers, ladder)
        line = next((s.get("line_key") for s in m.get("steps", []) if s.get("kind") == "math_label"), None)
        errors += [f"missions/{m['id']}: 이름표 대사가 목표 표현 '{a}' 을 담지 않는다 (방금 쓴 말에 이름을 붙인다, INV-15)"
                   for a in answers if squash(a) not in squash(strings.get(line, ""))]
    for c in g.get("reuse_contexts", []):
        ladder = ladders.get(c.get("hint_ladder"), {})
        if ladder.get("term") != c.get("term_id"):
            errors.append(f"reuse_contexts/{c.get('id')}: 재사용 맥락에 그 용어의 힌트 사다리가 없다 (INV-8·INV-9)")
        if len(ladder.get("keys", [])) != len(rule.get("levels", [])):
            errors.append(f"reuse_contexts/{c.get('id')}: 힌트 문구 수가 힌트 단계 수와 다르다")
        answers = [strings.get(k, "") for k in c.get("answer_keys", []) if strings.get(k)]
        if not answers:
            errors.append(f"reuse_contexts/{c.get('id')}: 목표 표현(answer_keys)이 없어 정답 공개를 검사할 수 없다")
        errors += answer_tie_errors(b, c.get("id"), c.get("term_id"), answers, ladder)
    core = [m for m in g.get("missions", []) if m.get("core")]
    for m in by_id.values():
        if "solo_npc" not in m.get("play_modes", []) or set(m.get("play_modes", [])) - PLAY_MODES:
            errors.append(f"missions/{m['id']}: 미션은 혼자(NPC)로 끝낼 수 있어야 하고 방식은 {sorted(PLAY_MODES)} 만 (INV-9)")
        if m.get("core") and not m.get("goal_key"):
            errors.append(f"missions/{m['id']}: 필수 미션은 현재 목표 문구(goal_key)가 있어야 한다 (K5 한 번에 하나)")
        if not m.get("core") and m.get("target_end_s") is not None:
            errors.append(f"missions/{m['id']}: 선택 미션에는 목표 시각을 두지 않는다 (시간 압박 없음)")
    if not core:
        errors.append("missions: 필수 미션이 없다 — 입장 게이트의 필수 경로가 있어야 한다")
    core_ids = {m["id"] for m in core}
    errors += [f"terms/{t['term_id']}: 용어를 처음 배우는 미션 {t.get('first_mission')} 은 필수 경로에 있어야 한다" for t in g.get("terms", [])
               if t.get("first_mission") not in core_ids]
    errors += [f"missions/{m['id']}: 게이트 신호 미션은 필수다" for m in by_id.values() if m.get("signal") is not None and not m.get("core")]
    errors += [f"missions/{m['id']}: 필수 미션은 바로 앞 필수 미션 {core[i - 1]['id']} 하나만 기다려야 한다 (필수 경로는 한 줄)"
               for i, m in enumerate(core) if i and m.get("requires") != [core[i - 1]["id"]]]
    for c in g.get("coop", []):
        if not c.get("npc_fallback"):
            errors.append(f"coop/{c['id']}: NPC 대체가 없다 (INV-9)")
        if len(c.get("object_keys", [])) != len(c.get("objects", [])) or len(c.get("roles", [])) < 2:
            errors.append(f"coop/{c['id']}: 오브젝트마다 표시 문구가 있고 역할이 둘 이상이어야 한다")
        if c.get("role_assignment") != "player_choice":
            errors.append(f"coop/{c['id']}: 역할은 플레이어가 고른다 (K3 §5 — 강제 배정 없음)")
        if c.get("max_players", 0) > spec.get("coop", {}).get("max_players", 0):
            errors.append(f"coop/{c['id']}: 인원이 Q1 명세 max_players 를 넘는다")
    errors += [f"roles/{r['id']}: NPC 가 대신 맡을 수 없다 (INV-9)" for r in g.get("roles", []) if r.get("npc_can_fill") is not True]
    pacing = g.get("pacing", {})
    errors += [f"pacing/{k}: 강박형 장치는 쓰지 않는다 (INV-14)" for k in ("countdown_fail", "streaks", "autoplay_next_mission") if pacing.get(k) is not False]
    stop = pacing.get("stop_point", {})
    if pacing.get("autosave") is not True or stop.get("equal_size") is not True or sorted(stop.get("choice_keys", [])) != STOP_CHOICES:
        errors.append("pacing: 자동 저장과, 계속·쉬기를 같은 크기로 고르는 정지점이 있어야 한다 (K6 R7)")
    session = spec.get("session", {})
    ends = [m.get("target_end_s") for m in core]
    if not all(isinstance(x, int) and not isinstance(x, bool) and x > 0 for x in ends) or ends != sorted(ends):
        errors.append("missions: 필수 미션의 목표 종료 시각은 양의 정수이고 순서대로 늘어야 한다")
    elif core:
        if core[0].get("new_term") or ends[0] > session.get("first_world_reaction_s", 0):
            errors.append("missions: 첫 필수 미션은 수학 없는 첫 월드 반응이고 Q1 first_world_reaction_s 안에 끝나야 한다")
        first_math = next((m for m in core if m.get("new_term")), None)
        if first_math and first_math["target_end_s"] > session.get("first_math_success_s", 0):
            errors.append("missions: 첫 수학 미션이 Q1 first_math_success_s 안에 끝나지 않는다")
        if ends[-1] > session.get("target_minutes", [0, 0])[-1] * 60:
            errors.append("missions: 필수 경로가 Q1 target_minutes 를 넘는다")
        if stop.get("mission") != core[-1]["id"]:
            errors.append("pacing/stop_point: 필수 경로의 마지막 미션에 정지점이 있어야 한다")
    errors += [f"missions/{m['id']}: 필수 미션이 선택 미션 {r} 를 기다린다" for m in core for r in m.get("requires", []) if not by_id.get(r, {}).get("core")]
    scenarios = g.get("scenarios", [])
    errors += [f"scenarios/{s.get('id')}: 멈춤 변형이 아니면 필수 경로 전체를 지나야 한다" for s in scenarios
               if s.get("variation") != "idle_hints" and not core_ids <= set(s.get("path", []))]
    for method in spec.get("input_methods", []):
        if not any(s.get("input") == method and s.get("play_mode") == "solo_npc" and core_ids <= set(s.get("path", [])) for s in scenarios):
            errors.append(f"scenarios: 입력 {method} 로 혼자 필수 경로를 끝까지 가는 시나리오가 없다 (INV-9)")
    if not any(s.get("play_mode") == "duo" for s in scenarios):
        errors.append("scenarios: 2인 시나리오가 없다")
    if not {"first_try", "other_result_x3", "idle_hints", "never_uses_label"} <= {s.get("variation") for s in scenarios}:
        errors.append("scenarios: 첫 시도·다른 결과 반복·멈춤·일상어만 쓰기 변형을 모두 덮어야 한다")
    for s in scenarios:
        if s.get("variation") not in SCENARIO_VARIATIONS or s.get("play_mode") not in PLAY_MODES or not s.get("expects_events") \
                or not s.get("path") or (core and s["path"][0] != core[0]["id"]):
            errors.append(f"scenarios/{s.get('id')}: 변형·방식은 정해진 값, 기대 이벤트가 있고 경로는 첫 필수 미션에서 시작해야 한다")
        seen = set()
        for step in s.get("path", []):
            missing = [r for r in by_id.get(step, {}).get("requires", []) if r not in seen]
            if missing:
                errors.append(f"scenarios/{s['id']}: {step} 앞에 선행 미션 {missing} 가 없다")
            seen.add(step)
    if g.get("market_id") != b.glossary.get("market_id"):
        errors.append("Graph·용어집의 시장이 다르다 (INV-2 원본 시장 하나)")
    return errors


CHECKS = {
    "Q2-C1": check_references, "Q2-C2": check_reuse, "Q2-C3": check_events, "Q2-C4": check_canonical,
    "Q2-C5": check_glossary, "Q2-C6": check_boundary, "Q2-C7": check_design_rules,
}


def main(argv: list[str]) -> int:
    if argv:
        print("[validate_graph] 인자를 받지 않습니다.", file=sys.stderr)
        return 2
    try:
        bundle = load_bundle()
    except (OSError, KeyError, ValueError, yaml.YAMLError) as exc:
        print(f"[validate_graph] 파일을 읽지 못했습니다: {exc}", file=sys.stderr)
        return 2
    failed = 0
    for cid, check in CHECKS.items():
        errors = check(bundle)
        print(f"{'OK  ' if not errors else 'FAIL'} {cid}")
        for error in errors:
            print(f"     - {error}")
        failed += bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
