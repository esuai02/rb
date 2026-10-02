"""교육과정·월드 Graph 검사 (작업 Graph Q2 기준별 테스트).

각 테스트 묶음은 저장소의 실제 산출물이 그 기준을 통과하는지(기준선)와, 산출물을 메모리에서 일부러 망가뜨리면
검사기가 잡는지(변이)를 함께 본다. 저장소 파일은 쓰지 않는다.
"""
import copy
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_graph as vg  # noqa: E402
import validate_spec  # noqa: E402

BASE = vg.load_bundle(ROOT)


def bundle():
    return copy.deepcopy(BASE)


def mission(b, mission_id):
    return next(m for m in b.graph["missions"] if m["id"] == mission_id)


def value(b, cv_id):
    return next(v for v in b.values["values"] if v["id"] == cv_id)


def setv(obj, key, val):
    obj[key] = val


def dup_first(items):
    items.append(copy.deepcopy(items[0]))


class CheckCase(unittest.TestCase):
    check = None
    cases = ()  # (검사기가 내야 할 메시지 조각, 변이) — 검사 한 줄마다 하나. 줄을 지우면 이 테스트가 실패한다

    def test_listed_mutations_are_caught(self):
        for fragment, mutate in type(self).cases:
            with self.subTest(fragment=fragment):
                b = bundle()
                mutate(b)
                self.assertCaught(b, fragment)

    def errors(self, b):
        return type(self).check(b)

    def assertCaught(self, b, fragment):
        errors = self.errors(b)
        self.assertTrue(any(fragment in e for e in errors), f"'{fragment}' 를 잡지 못함: {errors}")

    def test_baseline_passes(self):
        if type(self).check is not None:
            self.assertEqual(self.errors(bundle()), [])


class ReferenceTest(CheckCase):
    check = staticmethod(vg.check_references)
    cases = (
        ("terms: Q1 명세의 용어와 다르다", lambda b: b.graph["terms"].pop()),
        ("missions: id 가 중복된다", lambda b: dup_first(b.graph["missions"])),
        ("선수 용어 term.ghost 가 없다", lambda b: setv(b.graph["terms"][1], "prerequisites", ["term.ghost"])),
        ("첫 미션 m.ghost 가 없다", lambda b: setv(b.graph["terms"][0], "first_mission", "m.ghost")),
        ("새 용어 term.ghost 가 Q1", lambda b: setv(mission(b, "m.zone_portal"), "new_term", "term.ghost")),
        ("label_key 가 아니다", lambda b: setv(mission(b, "m.signal_coordinate")["steps"][4], "key", "term.slope.name")),
        ("action.slope.increase 는 Q1 명세의 term.coordinate", lambda b: mission(b, "m.signal_coordinate")["steps"][2]["keys"].append("action.slope.increase")),
        ("보상 reward.ghost 가 없다", lambda b: mission(b, "m.gate_open")["steps"][1]["ids"].append("reward.ghost")),
        ("협동 coop.plaza_bridge 가 없거나", lambda b: setv(mission(b, "m.signal_slope"), "coop", "coop.plaza_bridge")),
        ("reuse_contexts: id 가 중복된다", lambda b: dup_first(b.graph["reuse_contexts"])),
        ("용어 term.ghost 가 없다", lambda b: setv(b.graph["reuse_contexts"][0], "term_id", "term.ghost")),
        ("ctx.coordinate.slope_anchor: 미션 m.ghost 가 없다", lambda b: setv(b.graph["reuse_contexts"][0], "mission", "m.ghost")),
        ("행동 action.slope.increase 는 Q1", lambda b: b.graph["reuse_contexts"][0]["action_keys"].append("action.slope.increase")),
        ("hint_ladders/hl.coordinate: 미션", lambda b: setv(b.graph["hint_ladders"][0], "mission", "m.signal_slope")),
        ("규칙은 정본 값", lambda b: setv(b.graph["hint_ladders"][0], "rule", "cv.gate_time")),
        ("coop/coop.plaza_bridge: 미션", lambda b: setv(b.graph["coop"][1], "mission", "m.signal_slope")),
        ("역할 role.ghost 가 없다", lambda b: b.graph["coop"][0]["roles"].append("role.ghost")),
        ("rewards/reward.explorer_card: 미션 m.ghost", lambda b: setv(b.graph["rewards"][0], "mission", "m.ghost")),
        ("sc.solo_touch_first_try: 미션 m.ghost", lambda b: b.graph["scenarios"][0]["path"].append("m.ghost")),
        ("입력 vr_headset 가 Q1", lambda b: setv(b.graph["scenarios"][0], "input", "vr_headset")),
        ("terms: id 가 중복된다", lambda b: dup_first(b.graph["terms"])),
        ("rewards: id 가 중복된다", lambda b: dup_first(b.graph["rewards"])),
        ("hint_ladders: id 가 중복된다", lambda b: dup_first(b.graph["hint_ladders"])),
        ("roles: id 가 중복된다", lambda b: dup_first(b.graph["roles"])),
        ("scenarios: id 가 중복된다", lambda b: dup_first(b.graph["scenarios"])),
        ("coop: id 가 중복된다", lambda b: dup_first(b.graph["coop"])),
        ("world_spec: specs/worlds/", lambda b: setv(b.graph, "world_spec", "specs/worlds/other.yaml")),
        ("canonical_values: specs/graph/canonical-values.yaml", lambda b: setv(b.graph, "canonical_values", "garbage.yaml")),
        ("events: specs/analytics/events.yaml", lambda b: setv(b.graph, "events", "other.yaml")),
        ("겹치지 않게", lambda b: setv(b.graph["hint_ladders"][0], "keys", ["hint.coordinate.l1"] * 3)),
        ("id 'garbage' 가", lambda b: setv(b.graph["scenarios"][0], "id", "garbage")),
        ("id 가 용어 이름(ctx.coordinate.", lambda b: setv(b.graph["reuse_contexts"][0], "id", "ctx.slope.anchor_x")),
        ("Graph id 는 world_id", lambda b: setv(b.graph, "id", "garbage")),
        ("형식이 틀려 검사를 끝까지 하지 못했다", lambda b: setv(b.spec, "language_goals", 5)),  # 멈추지 않고 실패로 알린다
        ("보상 단계", lambda b: setv(mission(b, "m.gate_open")["steps"][1], "ids", [])),
        ("graph.missions[5].core: true/false", lambda b: setv(mission(b, "m.plaza_drone_delivery"), "core", "false")),
        ("graph.missions[0].target_end_s: 정수나 null", lambda b: setv(mission(b, "m.signal_wake"), "target_end_s", "60")),
        ("항목 ['requires'] 가 없다", lambda b: mission(b, "m.gate_open").pop("requires")),
        ("graph.missions[3].steps: 목록이어야", lambda b: setv(mission(b, "m.gate_open"), "steps", {})),
        ("graph.pacing.stop_point: 모르는 항목", lambda b: setv(b.graph["pacing"]["stop_point"], "auto_continue_s", 5)),
        ("이 용어의 재사용 사다리가 아니다", lambda b: setv(b.graph["reuse_contexts"][0], "hint_ladder", "hl.reuse.slope")),
        ("미션 사다리(mission)나 재사용 사다리(term) 중 하나", lambda b: setv(b.graph["hint_ladders"][2], "mission", "m.signal_coordinate")),
        ("이 재사용 사다리를 쓰는 맥락이 없다", lambda b: [setv(c, "hint_ladder", None) for c in b.graph["reuse_contexts"] if c["term_id"] == "term.slope"]),
    )

    def test_unknown_term_in_reuse_context(self):
        b = bundle()
        b.graph["reuse_contexts"][0]["term_id"] = "term.unknown"
        self.assertCaught(b, "term.unknown")

    def test_string_key_missing_from_glossary(self):
        b = bundle()
        mission(b, "m.signal_wake")["steps"][0]["key"] = "sit.not_written"
        self.assertCaught(b, "sit.not_written")

    def test_action_key_outside_q1_spec(self):
        b = bundle()
        mission(b, "m.signal_coordinate")["steps"][2]["keys"].append("action.position.teleport")
        self.assertCaught(b, "action.position.teleport")

    def test_unknown_canonical_value(self):
        b = bundle()
        b.graph["coop"][0]["params"].append("cv.not_defined")
        self.assertCaught(b, "cv.not_defined")

    def test_unknown_event_in_scenario(self):
        b = bundle()
        b.graph["scenarios"][0]["expects_events"].append("player_name_logged")
        self.assertCaught(b, "player_name_logged")

    def test_world_identity_must_match_q1(self):
        b = bundle()
        b.graph["market_id"] = "en-US"
        self.assertCaught(b, "market_id")

    def test_mission_cycle(self):
        b = bundle()
        mission(b, "m.signal_wake")["requires"] = ["m.zone_portal"]
        self.assertCaught(b, "순환")

    def test_term_prerequisite_cycle(self):
        b = bundle()
        b.graph["terms"][0]["prerequisites"] = ["term.slope"]
        self.assertCaught(b, "선수 용어가 순환")

    def test_npc_must_be_q1_fallback(self):
        b = bundle()
        b.graph["coop"][0]["npc_fallback"] = "npc.other_drone"
        self.assertCaught(b, "npc.other_drone")

    def test_unknown_keys_cannot_bypass_rules(self):
        for path, key, val in ((("rewards", 3), "robux_price", 49), (("rewards", 0), "drop_rate", 0.1),
                               (("missions", 1), "time_limit_s", 20), (("coop", 0), "min_players", 2)):
            b = bundle()
            b.graph[path[0]][path[1]][key] = val
            self.assertCaught(b, key)
        b = bundle()
        b.graph["pacing"]["daily_login_reward"] = True
        self.assertCaught(b, "daily_login_reward")

    def test_missing_prerequisite_mission(self):
        b = bundle()
        mission(b, "m.signal_slope")["requires"] = ["m.ghost"]
        self.assertCaught(b, "m.ghost")

    def test_ladder_of_another_mission(self):
        b = bundle()
        mission(b, "m.signal_coordinate")["hint_ladder"] = "hl.slope"
        self.assertCaught(b, "hl.slope")

    def test_stop_point_must_resolve(self):
        b = bundle()
        b.graph["pacing"]["stop_point"]["mission"] = "m.ghost"
        self.assertCaught(b, "stop_point")


class ReuseTest(CheckCase):
    check = staticmethod(vg.check_reuse)
    cases = (
        ("이름표가 있는데 new_term 이 없다", lambda b: mission(b, "m.gate_open")["steps"].append({"kind": "math_label", "key": "term.slope.name"})),
        ("빈 미션", lambda b: setv(b.graph, "reuse_contexts", [c for c in b.graph["reuse_contexts"] if c["mission"] != "m.plaza_drone_delivery"])),
        ("에 행동이 없다", lambda b: setv(b.graph["reuse_contexts"][0], "action_keys", [])),
        ("일상어와 수학 이름 둘 다", lambda b: b.graph["reuse_contexts"][0]["accepts"].append("quiz")),
        ("앞에서 먼저 배운 용어", lambda b: setv(b.graph["terms"][1], "prerequisites", [])),
        ("situation 단계는 ['key'] 가 꼭", lambda b: mission(b, "m.signal_wake")["steps"][0].pop("key")),
        ("interaction 단계는 ['key'] 가 꼭", lambda b: setv(mission(b, "m.signal_wake")["steps"][1], "keys", ["prompt.signal_panel.activate"])),
        ("everyday_expression 단계는 ['keys'] 가 꼭", lambda b: setv(mission(b, "m.signal_coordinate")["steps"][1], "keys", [])),
        ("math_label 단계는 ['key', 'line_key'] 가 꼭", lambda b: mission(b, "m.signal_slope")["steps"][4].pop("line_key")),
    )

    def test_two_reuse_contexts_are_not_enough(self):
        b = bundle()
        b.graph["reuse_contexts"] = [c for c in b.graph["reuse_contexts"] if c["id"] != "ctx.slope.partner_bridge"]
        self.assertCaught(b, "재사용 맥락이 2개")

    def test_label_before_action_breaks_language_first(self):
        b = bundle()
        steps = mission(b, "m.signal_coordinate")["steps"]
        steps.insert(1, steps.pop())  # 이름표를 상황 바로 뒤로
        self.assertCaught(b, "단계 순서")

    def test_reuse_before_label_does_not_count(self):
        b = bundle()
        b.graph["reuse_contexts"][0]["mission"] = "m.signal_wake"  # 좌표 이름표보다 앞
        self.assertCaught(b, "첫 미션 뒤에 오지 않는다")

    def test_reuse_must_accept_everyday_language(self):
        b = bundle()
        b.graph["reuse_contexts"][3]["accepts"] = ["label"]
        self.assertCaught(b, "일상어와 수학 이름 둘 다")

    def test_duplicate_context_is_not_a_different_context(self):
        b = bundle()
        b.graph["reuse_contexts"][1]["mission"] = b.graph["reuse_contexts"][0]["mission"]
        self.assertCaught(b, "mission 가 겹친다")

    def test_one_new_label_per_mission(self):
        b = bundle()
        mission(b, "m.signal_slope")["steps"].append({"kind": "math_label", "key": "term.coordinate.name"})
        self.assertCaught(b, "새 이름표가 2개")

    def test_prerequisite_term_must_come_first(self):
        b = bundle()
        mission(b, "m.signal_slope")["requires"] = ["m.signal_wake"]
        mission(b, "m.signal_coordinate")["requires"] = ["m.signal_slope"]
        self.assertCaught(b, "선수 용어 term.coordinate")

    def test_quiz_step_is_not_allowed(self):
        b = bundle()
        mission(b, "m.gate_open")["steps"].insert(0, {"kind": "multiple_choice_quiz", "keys": ["term.slope.name"]})
        self.assertCaught(b, "multiple_choice_quiz")

    def test_label_cannot_be_introduced_twice(self):
        b = bundle()
        m = mission(b, "m.zone_portal")
        m["new_term"] = "term.coordinate"
        m["steps"].insert(0, {"kind": "math_label", "key": "term.coordinate.name"})
        self.assertCaught(b, "첫 미션 하나뿐")

    def test_all_q1_everyday_expressions_offered(self):
        b = bundle()
        mission(b, "m.signal_slope")["steps"][1]["keys"].remove("expr.slope.flat")
        self.assertCaught(b, "everyday_expression_keys")


class EventsTest(CheckCase):
    check = staticmethod(vg.check_events)
    cases = (
        ("limits: 플랫폼 한도", lambda b: setv(b.events["limits"], "max_fields_per_event", 5)),
        ("limits: 플랫폼 한도", lambda b: setv(b.events["limits"], "max_custom_events", 500)),
        ("이벤트 이름이 중복된다", lambda b: dup_first(b.events["custom_events"])),
        ("단계 번호가 1부터", lambda b: setv(b.events["onboarding_funnel"][1], "step", 5)),
        ("중복 없는 열거형", lambda b: setv(b.events["fields"], "outcome", ["target_reached", "target_reached"])),
        ("필드 ghost 가 열거형 사전에 없다", lambda b: setv(b.events["custom_events"][1], "fields", ["mission", "ghost"])),
        ("원천 목록을", lambda b: setattr(b, "k3_text", "")),
        ("주간 지표", lambda b: setv(b.events["north_star"]["numerator"], "window_days", 30)),
        ("label 값이 없어", lambda b: setv(b.events["fields"], "expression_used", ["everyday"])),
        ("플레이어별 저장 없이", lambda b: setv(b.events["north_star"], "per_player_storage", True)),
        ("분자는 term_reused", lambda b: (setv(b.events["north_star"]["numerator"], "event", "label_shown"),
                                         setv(next(e for e in b.events["custom_events"] if e["name"] == "label_shown"), "fields", ["term", "context", "expression_used"]))),
        ("분모는 session_start", lambda b: setv(b.events["north_star"]["denominator"], "event", "hint_shown")),
        ("분모는 매 세션 보내는", lambda b: setv(b.events["north_star"]["denominator"], "aggregation", "count")),
        ("분자 이벤트는 서버가", lambda b: next(e for e in b.events["custom_events"] if e["name"] == "term_reused").pop("trigger")),
        ("분자 이벤트는 서버가", lambda b: setv(next(e for e in b.events["custom_events"] if e["name"] == "term_reused"), "frequency", "per_occurrence")),
        ("분모 이벤트는 매 세션", lambda b: setv(next(e for e in b.events["custom_events"] if e["name"] == "session_start"), "frequency", "once_per_user")),
        ("온보딩 퍼널은 사용자당 한 번만", lambda b: setv(b.events["onboarding_funnel"][0], "frequency", "every_session")),
        ("보내는 빈도는", lambda b: setv(b.events["custom_events"][1], "trigger", "client_reported")),
        ("transport:", lambda b: setv(b.events, "sent_by", "client")),
        ("student_fullname_logged: 허용 목록에 없는 이벤트", lambda b: b.events["custom_events"].append({"name": "student_fullname_logged", "fields": [], "frequency": "per_occurrence", "when": "w"})),
        ("events.north_star.numerator: 모르는 항목", lambda b: setv(b.events["north_star"]["numerator"], "sample_rate", 0.5)),
        ("events: 모르는 항목", lambda b: setv(b.events, "extra_events", [])),
        ("events.custom_events[0]: 모르는 항목", lambda b: setv(b.events["custom_events"][0], "sample_rate", 1)),
        ("events.source_mapping.k5_funnel.session_start", lambda b: setv(b.events["source_mapping"]["k5_funnel"], "session_start", {"x": 1})),
        ("글자 키 사전이어야", lambda b: setv(b.events, "fields", [])),
        ("events.custom_events: 목록이어야", lambda b: setv(b.events, "custom_events", {})),
        ("fields/hint_level", lambda b: setv(b.events["fields"], "hint_level", ["level_1", "level_2"])),
        ("fields/expression_used", lambda b: b.events["fields"]["expression_used"].append("guess")),
        ("transport:", lambda b: setv(b.events, "transport", "third_party_sdk")),
        ("platform. 으로 시작", lambda b: setv(b.events, "platform_metrics", ["d1_retention"])),
        ("대응 대상이 비었다", lambda b: setv(b.events["source_mapping"]["k3_allowed"], "튜토리얼 시작/완료", [])),
    )

    def test_field_outside_allowlist(self):
        for name in ("roblox_user_id", "year_group", "homeroom", "region"):
            b = bundle()
            b.events["fields"][name] = ["a1"]
            b.events["custom_events"][0]["fields"] = [name]
            self.assertCaught(b, f"fields/{name}")

    def test_pii_event_name(self):
        for name in ("userName_logged", "child_nickname", "student_fullname_logged"):
            b = bundle()
            b.events["custom_events"][0]["name"] = name
            self.assertCaught(b, f"{name}: 허용 목록에 없는 이벤트")

    def test_numeric_value(self):
        b = bundle()
        b.events["fields"]["attempt"] = ["1", "2", "3"]
        self.assertCaught(b, "열거형 토큰")

    def test_denominator_cannot_be_one_time_funnel(self):
        b = bundle()
        b.events["north_star"]["denominator"]["event"] = "onboarding_start"
        self.assertCaught(b, "분모")

    def test_numerator_must_count_events(self):
        b = bundle()
        b.events["north_star"]["numerator"]["aggregation"] = "count_unique_users"
        self.assertCaught(b, "분자")

    def test_core_path_reuse_is_not_counted(self):
        b = bundle()
        for m in b.graph["missions"]:
            m["core"] = True  # 선택 미션이 없으면 셀 맥락이 없다
        self.assertCaught(b, "셀 선택 미션 맥락이 없다")

    def test_label_used_condition(self):
        b = bundle()
        b.events["north_star"]["numerator"]["filter"] = {"expression_used": ["label", "everyday"]}
        self.assertCaught(b, "filter expression_used = [label]")

    def test_renamed_k5_event_needs_canonical_value(self):
        b = bundle()
        b.events["source_mapping"]["k5_funnel"]["gate_visible"] = "first_interaction"
        self.assertCaught(b, "cv.events.renamed")

    def test_unread_k5_text(self):
        b = bundle()
        b.k5_text = b.k5_text.replace("→ first_input", "→ 첫입력 first_input", 1)
        self.assertCaught(b, "읽지 못한 글자")

    def test_free_text_value(self):
        b = bundle()
        b.events["fields"]["outcome"] = ["target_reached", "다른 곳에 내렸어요"]
        self.assertCaught(b, "열거형 토큰이 아닌 값")

    def test_more_than_three_fields(self):
        b = bundle()
        b.events["custom_events"][0]["fields"] = ["mission", "outcome", "attempt", "input"]
        self.assertCaught(b, "3개 이하")

    def test_north_star_required(self):
        b = bundle()
        b.events["north_star"] = {}
        self.assertCaught(b, "north_star")

    def test_north_star_must_exclude_forced_tutorial(self):
        b = bundle()
        b.events["north_star"]["numerator"]["contexts"] = [c["id"] for c in b.graph["reuse_contexts"]]
        self.assertCaught(b, "분자가 세는 맥락은 선택 미션의 맥락")

    def test_enum_must_match_graph_ids(self):
        b = bundle()
        b.events["fields"]["context"].pop()
        self.assertCaught(b, "fields/context")

    def test_every_k5_funnel_event_is_mapped(self):
        b = bundle()
        del b.events["source_mapping"]["k5_funnel"]["co_play_offered"]
        self.assertCaught(b, "co_play_offered")

    def test_every_k3_allowed_event_is_mapped(self):
        b = bundle()
        del b.events["source_mapping"]["k3_allowed"]["힌트 사용"]
        self.assertCaught(b, "힌트 사용")

    def test_mapping_target_must_exist(self):
        b = bundle()
        b.events["source_mapping"]["k5_funnel"]["day_1_return"] = "day_1_return_custom"
        self.assertCaught(b, "day_1_return_custom")


class CanonicalValuesTest(CheckCase):
    check = staticmethod(vg.check_canonical)
    cases = (
        ("§3 표를 읽지 못했다", lambda b: setattr(b, "k0_text", "")),
        ("source 는 충돌 표", lambda b: setv(b.values, "source", "anything.md")),
        ("measure_at 은 가설 값에만", lambda b: setv(value(b, "cv.hold_cancel"), "measure_at", "Q4")),
        ("서버 판정 거리가", lambda b: setv(value(b, "cv.server_distance")["value"], "server_check_studs", 8)),
        ("cv.match_wait.then: npc_fallback", lambda b: setv(value(b, "cv.match_wait")["value"], "then", "keep_waiting")),
        ("cv.rule_source.authority: server_config", lambda b: setv(value(b, "cv.rule_source")["value"], "authority", "client")),
        ("cv.first_try.forced_failure: False", lambda b: setv(value(b, "cv.first_try")["value"], "forced_failure", True)),
        ("원천 문서 범위 10~15", lambda b: setv(value(b, "cv.match_wait")["value"], "seconds", 10000)),
        ("원천 문서 범위 0.4~0.8", lambda b: setv(value(b, "cv.hold_time")["value"], "seconds", 600.0)),
        ("원천 문서 범위 0.7~0.9", lambda b: setv(value(b, "cv.first_try")["value"], "success_within_two_tries", [0.1, 0.2])),
        ("grid.x: [음수, 양수]", lambda b: setv(value(b, "cv.coordinate_expression")["value"]["grid"], "x", [0, 2])),
        ("grid.y: [음수, 양수]", lambda b: setv(value(b, "cv.coordinate_expression")["value"]["grid"], "y", [-2000, 2000])),
        ("이하인 단계", lambda b: setv(value(b, "cv.slope_choices")["value"], "steps", [0, 1, 3000])),
        ("cv.slope_choices.steps: 0(평평)", lambda b: setv(value(b, "cv.slope_choices")["value"], "steps", [1, 2])),
        ("success_within_two_tries: 0 과 1", lambda b: setv(value(b, "cv.first_try")["value"], "success_within_two_tries", [0.9, 0.7])),
        ("cv.world_title.world_key", lambda b: setv(value(b, "cv.world_title")["value"], "world_key", "world.other.name")),
        ("cv.world_title.first_title_key", lambda b: setv(value(b, "cv.world_title")["value"], "first_title_key", "reward.explorer_card.name")),
        ("cv.helper_npc.name_key", lambda b: setv(value(b, "cv.helper_npc")["value"], "name_key", "npc.other.name")),
        ("cv.gate_signals.coop_on", lambda b: setv(value(b, "cv.gate_signals")["value"], "coop_on", "signal_2")),
        ("근거 참조(refs)가 없다", lambda b: setv(value(b, "cv.match_wait"), "refs", [])),
        ("DEC-·INV-·Q·F·K 형식", lambda b: value(b, "cv.match_wait")["refs"].append("garbage")),
        ("INV-99 가 intent.md 에 없다", lambda b: value(b, "cv.match_wait")["refs"].append("INV-99")),
        ("F999 가 evidence.jsonl 에 없다", lambda b: value(b, "cv.match_wait")["refs"].append("F999")),
        ("cv.match_wait.value.seconds: 양수", lambda b: setv(value(b, "cv.match_wait")["value"], "seconds", -10)),
        ("cv.hint_ladder.value.reveals_answer: true/false", lambda b: setv(value(b, "cv.hint_ladder")["value"], "reveals_answer", "no")),
        ("K0 §3 에 없는 항목", lambda b: b.values["values"].append({"id": "cv.extra", "k0_item": "없는 항목", "value": 1, "status": "proposed", "rationale": "r"})),
        ("values: id 가 중복된다", lambda b: dup_first(b.values["values"])),
        ("id 는 cv.이름 형식", lambda b: setv(value(b, "cv.hold_cancel"), "id", "hold-cancel")),
        ("값이 비었다", lambda b: setv(value(b, "cv.hold_cancel"), "value", {})),
        ("cv.hold_time.value: 모르는 항목 ['price']", lambda b: setv(value(b, "cv.hold_time")["value"], "price", 1)),
        ("cv.hint_ladder.value.first_trigger: 모르는 항목", lambda b: setv(value(b, "cv.hint_ladder")["value"]["first_trigger"], "chance", 0.5)),
        ("항목 ['then'] 가 없다", lambda b: value(b, "cv.match_wait")["value"].pop("then")),
        ("cv.first_rewards.value: 글자 목록이어야", lambda b: setv(value(b, "cv.first_rewards"), "value", [{"id": "reward.explorer_card", "price": 10}])),
        ("cv.events.value.renamed.a: 비지 않은 글자", lambda b: setv(value(b, "cv.events")["value"], "renamed", {"a": ["b"]})),
        ("cv.match_wait.value.then: 비지 않은 글자", lambda b: setv(value(b, "cv.match_wait")["value"], "then", {"x": 1})),
        ("객체여야 한다", lambda b: setv(value(b, "cv.gate_time"), "value", [3, 5])),
        ("<cv.hold_time>: 모르는 항목 ['price']", lambda b: setv(value(b, "cv.hold_time"), "price", 1)),
        ("검사기에 형식이 없는 정본 값", lambda b: b.values["values"].append({"id": "cv.extra", "k0_item": "게이트 이름", "value": 1, "status": "proposed", "rationale": "r"})),
        ("q1_paths target_minutes → session.first_world_reaction_s", lambda b: setv(value(b, "cv.gate_time"), "q1_paths", {"target_minutes": "session.first_world_reaction_s"})),
        ("결정됨인 관련 DEC", lambda b: setv(value(b, "cv.match_wait"), "status", "decided") or setv(value(b, "cv.match_wait"), "refs", ["Q1"])),
        ("결정됨인 관련 DEC", lambda b: setv(value(b, "cv.hold_cancel"), "status", "decided") or setv(value(b, "cv.hold_cancel"), "refs", ["DEC-2"])),
        ("cv.match_wait: 결정된 값은", lambda b: setv(value(b, "cv.match_wait"), "status", "decided") or setv(value(b, "cv.match_wait"), "refs", ["DEC-1"])),
        ("cv.gate_name: 결정된 값은", lambda b: setv(value(b, "cv.gate_name")["value"], "ko", "도시 언어 심사")),
        ("canonical: 모르는 항목", lambda b: setv(b.values, "owner", "ai")),
        ("cv.coop_switch_ids:", lambda b: setv(b.graph["coop"][1], "objects", ["x_left", "x_right"])),
    )

    def test_every_k0_row_is_read(self):
        self.assertEqual(len(vg.k0_items(BASE.k0_text)), len(re.findall(r"^\| (?!항목|---)", vg.section(BASE.k0_text, "3."), re.M)))

    def test_missing_row(self):
        b = bundle()
        b.values["values"] = [v for v in b.values["values"] if v["k0_item"] != "홀드 시간"]
        self.assertCaught(b, "홀드 시간")

    def test_missing_rationale(self):
        b = bundle()
        value(b, "cv.match_wait")["rationale"] = " "
        self.assertCaught(b, "rationale: 비지 않은 글자")

    def test_hypothesis_needs_later_measurement(self):
        b = bundle()
        del value(b, "cv.coop_sync_window")["measure_at"]
        self.assertCaught(b, "measure_at")

    def test_two_values_for_one_row(self):
        b = bundle()
        b.values["values"].append(dict(value(b, "cv.hold_time"), id="cv.hold_time_b"))
        self.assertCaught(b, "하나만")

    def test_value_must_match_graph(self):
        b = bundle()
        value(b, "cv.coop_switch_ids")["value"] = ["prism_left_ready", "prism_right_ready"]
        self.assertCaught(b, "cv.coop_switch_ids")

    def test_every_range_row_is_enforced(self):
        for (cid, *path), (low, high) in vg.CV_RANGES.items():
            with self.subTest(cv=cid, path=path):
                b = bundle()
                node = value(b, cid)["value"]
                for key in path[:-1]:
                    node = node[key]
                outside = high * 10 + 1
                node[path[-1]] = [outside, outside] if isinstance(node[path[-1]], list) else outside
                self.assertCaught(b, f"{cid}.{'.'.join(path)}: ")

    def test_every_pin_row_is_enforced(self):
        for (cid, *path), (want, _) in vg.CV_PINS.items():
            with self.subTest(cv=cid, path=path):
                b = bundle()
                node = value(b, cid)["value"]
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = ["changed"] if isinstance(want, list) else (not want if isinstance(want, bool) else "changed")
                self.assertCaught(b, f"{cid}.{'.'.join(path)}: ")

    def test_decided_needs_human_decision_or_q1(self):
        b = bundle()
        v = value(b, "cv.match_wait")
        v.update(status="decided", refs=["INV-9"])
        del v["measure_at"]
        self.assertCaught(b, "결정됨인 관련 DEC")

    def test_unknown_status(self):
        b = bundle()
        value(b, "cv.hold_cancel")["status"] = "final"
        self.assertCaught(b, "status")

    def test_k0_row_without_spaces_is_read(self):
        text = BASE.k0_text.replace("| 홀드 시간 |", "|홀드 시간|")
        self.assertIn("홀드 시간", vg.k0_items(text))

    def test_first_rewards_must_match_graph(self):
        b = bundle()
        value(b, "cv.first_rewards")["value"].append("reward.atlas")
        self.assertCaught(b, "cv.first_rewards")


class GlossaryTest(CheckCase):
    check = staticmethod(vg.check_glossary)
    cases = (
        ("market_id: Q1 명세의 시장과 다르다", lambda b: setv(b.glossary, "market_id", "en-US")),
        ("planned_locales 에 없다", lambda b: setv(b.glossary, "locale", "en")),
        ("world_spec: Graph", lambda b: setv(b.glossary, "world_spec", "specs/worlds/other.yaml")),
        ("glossary.strings.retry.again: 비지 않은 글자", lambda b: setv(b.glossary["strings"], "retry.again", " ")),
        ("금지어가 겹친다", lambda b: dup_first(b.glossary["banned_terms"])),
        ("banned_terms[0].reason: 비지 않은 글자", lambda b: setv(b.glossary["banned_terms"][0], "reason", "")),
        ("glossary: 모르는 항목", lambda b: setv(b.glossary, "allow_terms", [])),
        ("점으로 나눈 소문자 이름", lambda b: setv(b.glossary["strings"], "Bad Key", "문구")),
        ("glossary.strings: 글자 키 사전이어야", lambda b: setv(b.glossary, "strings", [])),
        ("glossary.banned_terms[0]: 모르는 항목", lambda b: setv(b.glossary["banned_terms"][0], "severity", "low")),
    )

    def test_banned_term_with_spaces(self):
        b = bundle()
        b.glossary["strings"]["sit.gate_dark"] = "Neo Seoul 입 국 게이트가 꺼져 있어."
        self.assertCaught(b, "금지어")

    def test_every_required_banned_term_cannot_be_removed(self):
        for term in sorted(vg.REQUIRED_BANNED):
            with self.subTest(term=term):
                b = bundle()
                b.glossary["banned_terms"] = [x for x in b.glossary["banned_terms"] if x["term"].lower() != term]
                b.glossary["strings"]["retry.again"] = f"{term} 다시 해 보자."
                self.assertCaught(b, "빠졌다")

    def test_banned_term_inside_string(self):
        b = bundle()
        b.glossary["strings"]["resp.coordinate.other_spot"] = "오답이야. 다시 골라 보자."
        self.assertCaught(b, "금지어")

    def test_q1_key_missing(self):
        b = bundle()
        del b.glossary["strings"]["expr.slope.flat"]
        self.assertCaught(b, "expr.slope.flat")

    def test_canonical_name_must_match(self):
        b = bundle()
        b.glossary["strings"]["world.city_language_gate.title"] = "도시 언어 심사"
        self.assertCaught(b, "정본 이름")

    def test_required_banned_term_cannot_be_removed(self):
        b = bundle()
        b.glossary["banned_terms"] = [x for x in b.glossary["banned_terms"] if x["term"] != "여권"]
        self.assertCaught(b, "여권")

    def test_locale_must_be_planned_ietf_tag(self):
        b = bundle()
        b.glossary["locale"] = "ko_KR"
        b.spec["localization"]["planned_locales"].append("ko_KR")  # 계획에 있어도 형식이 틀리면 실패
        self.assertCaught(b, "IETF")

    def test_real_world_identity_words(self):
        for key, text in (("reward.explorer_badge.name", "Seoul Cyber Citizen 배지"), ("sit.gate_dark", "Neo Seoul 입국을 위해 패널을 켜 보자."),
                          ("reward.explorer_card.name", "Neo Seoul Passport"), ("sit.gate_dark", "도시 언어 심사가 멈췄어.")):
            b = bundle()
            b.glossary["strings"][key] = text
            self.assertCaught(b, "금지어")

    def test_unused_key(self):
        b = bundle()
        b.glossary["strings"]["orphan.key"] = "아무도 안 씀"
        self.assertCaught(b, "orphan.key")

    def test_replacement_must_not_be_banned(self):
        b = bundle()
        b.glossary["banned_terms"][0]["replacement"] = "입국 거부 없음"
        self.assertCaught(b, "대체어")


class DoNotTranslateBoundaryTest(CheckCase):
    check = staticmethod(vg.check_boundary)

    def narrowed(self, kind):
        b = bundle()
        rule = next(r for r in b.spec["do_not_translate"] if r["id"] == kind)
        rule["pattern"] = rule["pattern"].replace(r"\d+", r"\d{1,2}")  # 두 자리 수까지만 잡는 좁은 패턴
        return b

    def test_narrow_coordinate_pattern_passes_q1_random_check_but_not_boundary(self):
        b = self.narrowed("coordinate_pair")
        self.assertFalse([e for e in validate_spec.extra_rules(b.spec) if "do_not_translate" in e])  # Q1 의 무작위 표본(0~99)으로는 못 잡는다
        self.assertCaught(b, "(100, 0)")

    def test_narrow_linear_pattern(self):
        self.assertCaught(self.narrowed("linear_expression"), "y = 100x + 1")

    def test_no_negative_numbers(self):
        b = bundle()
        rule = next(r for r in b.spec["do_not_translate"] if r["id"] == "coordinate_pair")
        rule["pattern"] = rule["pattern"].replace("-?", "")
        self.assertCaught(b, "(-100, -250)")

    def test_invalid_regex(self):
        b = bundle()
        b.spec["do_not_translate"][0]["pattern"] = "(unclosed"
        self.assertCaught(b, "정규식이 아니다")

    def test_unparenthesised_expression_is_protected(self):
        b = bundle()
        b.glossary["strings"]["label.slope.line"] = "y = x² + 1 은 기울기가 아니야."
        self.assertCaught(b, "y = x² + 1")

    def test_glossary_math_fragment_is_protected(self):
        b = bundle()
        b.glossary["strings"]["label.coordinate.line"] = "좌표 (2; 1) 이야."
        self.assertCaught(b, "(2; 1)")


class DesignRulesTest(CheckCase):
    check = staticmethod(vg.check_design_rules)
    cases = (
        ("첫 힌트 조건", lambda b: setv(value(b, "cv.hint_ladder")["value"], "first_trigger", {})),
        ("힌트 문구 수가", lambda b: b.graph["hint_ladders"][0]["keys"].pop()),
        ("수학 미션에 목표(target)가 없어", lambda b: mission(b, "m.signal_slope").pop("target")),
        ("max_players 를 넘는다", lambda b: setv(b.graph["coop"][0], "max_players", 8)),
        ("순서대로 늘어야", lambda b: setv(mission(b, "m.gate_open"), "target_end_s", 100)),
        ("마지막 미션에 정지점", lambda b: setv(b.graph["pacing"]["stop_point"], "mission", "m.gate_open")),
        ("선택 미션 m.plaza_drone_delivery 를 기다린다", lambda b: setv(mission(b, "m.zone_portal"), "requires", ["m.gate_open", "m.plaza_drone_delivery"])),
        ("Graph·용어집의 시장이 다르다", lambda b: setv(b.glossary, "market_id", "en-US")),
        ("플레이어가 고른다", lambda b: setv(b.graph["coop"][0], "role_assignment", "forced")),
        ("양의 정수", lambda b: setv(mission(b, "m.signal_wake"), "target_end_s", -1)),
        ("m.plaza_drone_delivery: 미션은 혼자(NPC)", lambda b: setv(mission(b, "m.plaza_drone_delivery"), "play_modes", [])),
        ("현재 목표 문구(goal_key)", lambda b: setv(mission(b, "m.gate_open"), "goal_key", None)),
        ("선택 미션에는 목표 시각", lambda b: setv(mission(b, "m.plaza_partner_bridge"), "target_end_s", 7)),
        ("바로 앞 필수 미션 m.signal_wake", lambda b: setv(mission(b, "m.signal_coordinate"), "requires", [])),
        ("표시 문구가 있고 역할이 둘 이상", lambda b: setv(b.graph["coop"][0], "roles", ["role.map_reader"])),
        ("scenarios/sc.solo_touch_first_try: 변형·방식", lambda b: setv(b.graph["scenarios"][0], "variation", "garbage")),
        ("scenarios/sc.solo_touch_idle: 변형·방식", lambda b: setv(next(s for s in b.graph["scenarios"] if s["id"] == "sc.solo_touch_idle"), "expects_events", [])),
        ("재사용 맥락에 그 용어의 힌트 사다리가 없다", lambda b: b.graph["reuse_contexts"][4].pop("hint_ladder")),
        ("ctx.slope.booster_ramp: 힌트 문구 수가", lambda b: b.graph["hint_ladders"][3]["keys"].pop()),
        ("ctx.slope.partner_bridge: 목표 {}", lambda b: setv(b.graph["reuse_contexts"][5], "target", {})),
        ("ctx.slope.metro_preview 의 정답 '더 올라가게'", lambda b: setv(b.glossary["strings"], "hint.reuse.slope.l2", "레일을 더 올라가게 바꿔 봐.")),
        ("정답 '오른쪽 2, 위 1' 의 구성 요소", lambda b: setv(b.glossary["strings"], "hint.coordinate.l2", "오른쪽 2,   위 1 일까?")),
        ("정답 '오른쪽 2, 위 1' 의 구성 요소", lambda b: setv(b.glossary["strings"], "hint.coordinate.l2", "위 1, 오른쪽 2로 보내면 돼.")),
        ("목표 칸 [9, 9] 이 정본 격자", lambda b: setv(mission(b, "m.signal_coordinate"), "target", {"cell": [9, 9]})),
        ("기준점(0, 0)이 아닌", lambda b: setv(b.graph["reuse_contexts"][1], "target", {"cell": [0, 0]})),
        ("Q1 일상 표현 키 하나여야", lambda b: setv(b.graph["reuse_contexts"][3], "target", {"expression": "expr.slope.zigzag"})),
        ("Q1 일상 표현에 필요한 방향이 없다", lambda b: b.spec["language_goals"][0]["everyday_expression_keys"].remove("expr.position.left")),
        ("목표에 필요한 행동 ['action.position.move_left']", lambda b: setv(b.graph["reuse_contexts"][0], "target", {"cell": [-1, 1]})),
        ("목표에 필요한 행동 ['action.slope.set_zero']", lambda b: setv(b.graph["reuse_contexts"][3], "target", {"expression": "expr.slope.flat"})),
        ("목표 칸의 좌표 (2, 1)", lambda b: setv(b.glossary["strings"], "label.coordinate.line", "출발 칸에서 오른쪽 2, 위 1 → (1, 2). 방금 쓴 말이 좌표야.")),
        ("역할 기여는", lambda b: setv(b.graph["roles"][0], "contribution", "does_not_exist")),
        ("역할 기여는", lambda b: setv(b.graph["roles"][1], "contribution", "ping_anchor_cell")),
        ("변형 first_try 과 맞지 않는다", lambda b: setv(b.graph["scenarios"][0], "attempts_before_target", 2)),
        ("변형 other_result_x3 과 맞지 않는다", lambda b: setv(b.graph["scenarios"][1], "attempts_before_target", 1)),
        ("변형 idle_hints 과 맞지 않는다", lambda b: setv(b.graph["scenarios"][3], "idle_s", 3)),
        ("변형 never_uses_label 과 맞지 않는다", lambda b: setv(b.graph["scenarios"][4], "expression", "label")),
        ("변형 uses_label 과 맞지 않는다", lambda b: setv(b.graph["scenarios"][5], "path", [p for p in b.graph["scenarios"][5]["path"] if not p.startswith("m.plaza")])),
        ("끝난 지점은 경로의 마지막", lambda b: setv(b.graph["scenarios"][3], "stops_after", "m.signal_wake")),
        ("시도 수·멈춘 시간은 0 이상", lambda b: setv(b.graph["scenarios"][0], "attempts_before_target", -1)),
        ("반드시 내는 이벤트 ['hint_shown']", lambda b: b.graph["scenarios"][1]["expects_events"].remove("hint_shown")),
        ("반드시 내는 이벤트 ['co_play_started']", lambda b: b.graph["scenarios"][2]["expects_events"].remove("co_play_started")),
        ("반드시 내는 이벤트 ['session_end']", lambda b: b.graph["scenarios"][3]["expects_events"].remove("session_end")),
        ("반드시 내는 이벤트 ['term_reused']", lambda b: b.graph["scenarios"][4]["expects_events"].remove("term_reused")),
        ("반드시 내는 이벤트 ['gate_opened']", lambda b: b.graph["scenarios"][0]["expects_events"].remove("gate_opened")),
        ("반드시 내는 이벤트 ['onboarding_complete']", lambda b: b.graph["scenarios"][0]["expects_events"].remove("onboarding_complete")),
        ("반드시 내는 이벤트 ['first_math_action', 'first_math_success', 'math_attempt']", lambda b: setv(b.graph["scenarios"][0], "expects_events",
            [e for e in b.graph["scenarios"][0]["expects_events"] if e not in ("first_math_action", "first_math_success", "math_attempt")])),
        ("반드시 내는 이벤트 ['explorer_card_earned']", lambda b: b.graph["scenarios"][0]["expects_events"].remove("explorer_card_earned")),
        ("반드시 내는 이벤트 ['co_play_offered']", lambda b: b.graph["scenarios"][2]["expects_events"].remove("co_play_offered")),
        ("생기지 않는 이벤트 ['session_end']", lambda b: b.graph["scenarios"][0]["expects_events"].append("session_end")),
        ("반드시 내는 이벤트 ['session_start']", lambda b: b.graph["scenarios"][0]["expects_events"].remove("session_start")),
        ("필수 미션이 없다", lambda b: [m.update(core=False, target_end_s=None) for m in b.graph["missions"]]),
        ("필수 경로에 있어야 한다", lambda b: setv(mission(b, "m.signal_slope"), "core", False)),
        ("게이트 신호 미션은 필수다", lambda b: mission(b, "m.signal_wake").update(core=False, target_end_s=None)),
        ("멈춤 변형이 아니면 필수 경로 전체", lambda b: setv(b.graph["scenarios"][0], "path", ["m.signal_wake", "m.signal_coordinate"])),
        ("이름표 대사가 방금 쓴 말", lambda b: setv(b.glossary["strings"], "label.coordinate.line", "방금 쓴 말을 수학에서는 좌표라고 불러.")),
        ("계속·쉬기", lambda b: setv(b.graph["pacing"]["stop_point"], "choice_keys", ["pacing.continue", "pacing.continue"])),
    )

    def test_client_granted_reward(self):
        b = bundle()
        b.graph["rewards"][0]["granted_by"] = "client"
        self.assertCaught(b, "서버만")

    def test_base_reward_by_correct_count(self):
        b = bundle()
        b.graph["rewards"][1]["basis"] = "correct_count"
        self.assertCaught(b, "보상 기준")

    def test_coop_bonus_must_be_cosmetic(self):
        b = bundle()
        b.graph["rewards"][3]["kind"] = "ability_unlock"
        self.assertCaught(b, "꾸미기만")

    def test_currency_reward(self):
        b = bundle()
        b.graph["rewards"][0]["kind"] = "currency"
        self.assertCaught(b, "INV-12")

    def test_base_reward_for_some_players_only(self):
        b = bundle()
        b.graph["rewards"][0]["granted_to"] = "first_try_players"
        self.assertCaught(b, "완주한 모두")

    def test_hint_text_states_the_answer(self):
        b = bundle()
        b.glossary["strings"]["hint.coordinate.l3"] = "루미를 오른쪽 2, 위 1로 보내면 돼."
        self.assertCaught(b, "구성 요소를 모두 말한다")

    def test_math_mission_needs_own_ladder(self):
        b = bundle()
        mission(b, "m.signal_slope").pop("hint_ladder")
        self.assertCaught(b, "자기 힌트 사다리")

    def test_hint_advance_after_attempt(self):
        b = bundle()
        value(b, "cv.hint_ladder")["value"]["advance"] = "idle_only"
        self.assertCaught(b, "R3")

    def test_coop_needs_npc(self):
        b = bundle()
        b.graph["coop"][0]["npc_fallback"] = None
        self.assertCaught(b, "NPC 대체")

    def test_role_npc_can_fill(self):
        b = bundle()
        b.graph["roles"][0]["npc_can_fill"] = False
        self.assertCaught(b, "NPC 가 대신")

    def test_stop_point_equal_choice(self):
        b = bundle()
        b.graph["pacing"]["stop_point"]["equal_size"] = False
        self.assertCaught(b, "R7")

    def test_first_world_reaction_time(self):
        b = bundle()
        mission(b, "m.signal_wake")["target_end_s"] = 90
        self.assertCaught(b, "first_world_reaction_s")

    def test_each_input_has_solo_full_path(self):
        b = bundle()
        next(s for s in b.graph["scenarios"] if s["id"] == "sc.solo_gamepad_other_results")["play_mode"] = "duo"
        self.assertCaught(b, "입력 gamepad")

    def test_duo_and_idle_scenarios_required(self):
        b = bundle()
        b.graph["scenarios"] = [s for s in b.graph["scenarios"] if s["play_mode"] != "duo"]
        self.assertCaught(b, "2인 시나리오")
        b = bundle()
        b.graph["scenarios"] = [s for s in b.graph["scenarios"] if s["variation"] != "idle_hints"]
        self.assertCaught(b, "멈춤")

    def test_every_event_rule_is_pinned_by_a_scenario(self):
        """허용 이벤트마다 그 이벤트를 내는 시나리오가 있고, 기대 이벤트에서 빼거나 생기지 않는 이벤트를 더하면 잡힌다."""
        covered = {e for s in BASE.graph["scenarios"] for e in s["expects_events"]}
        self.assertEqual(covered, vg.ALLOWED_EVENTS)
        for i, s in enumerate(BASE.graph["scenarios"]):
            for event in sorted(vg.ALLOWED_EVENTS):
                with self.subTest(scenario=s["id"], event=event):
                    b = bundle()
                    events = b.graph["scenarios"][i]["expects_events"]
                    if event in events:
                        events.remove(event)
                        self.assertCaught(b, f"{s['id']}: 이 행동이 반드시 내는 이벤트 ['{event}']")
                    else:
                        events.append(event)
                        self.assertCaught(b, f"{s['id']}: 이 행동으로는 생기지 않는 이벤트 ['{event}']")

    def test_hint_reveals_answer(self):
        b = bundle()
        value(b, "cv.hint_ladder")["value"]["reveals_answer"] = True
        self.assertCaught(b, "정답을 보여 주지 않고")

    def test_core_mission_needs_solo_path(self):
        b = bundle()
        mission(b, "m.signal_slope")["play_modes"] = ["duo"]
        self.assertCaught(b, "혼자(NPC)")

    def test_streak(self):
        b = bundle()
        b.graph["pacing"]["streaks"] = True
        self.assertCaught(b, "INV-14")

    def test_first_math_success_time(self):
        b = bundle()
        mission(b, "m.signal_coordinate")["target_end_s"] = 200
        self.assertCaught(b, "first_math_success_s")

    def test_core_path_over_target_minutes(self):
        b = bundle()
        mission(b, "m.zone_portal")["target_end_s"] = 420
        self.assertCaught(b, "target_minutes")

    def test_scenarios_cover_inputs(self):
        b = bundle()
        b.graph["scenarios"] = [s for s in b.graph["scenarios"] if s["input"] != "gamepad"]
        self.assertCaught(b, "입력 gamepad")

    def test_scenario_path_respects_order(self):
        b = bundle()
        b.graph["scenarios"][0]["path"] = ["m.signal_wake", "m.signal_slope"]
        self.assertCaught(b, "선행 미션")


if __name__ == "__main__":
    unittest.main()
