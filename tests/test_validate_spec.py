"""Q1 합격 기준 검사 — 실행: python3 -m unittest tests.test_validate_spec -v

각 TestCase 가 graph.json 의 Q1 기준 하나에 대응한다 (Q1-C1 ~ Q1-C4).
"""
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_spec as vs  # noqa: E402

SPEC_PATH = ROOT / "specs/worlds/neo-seoul-city-language-gate.yaml"
SCHEMA = vs.load_schema()
SPEC = vs.load_spec(SPEC_PATH)


def without(spec, path):
    """path(점으로 구분)의 마지막 칸을 지운 복사본."""
    data = copy.deepcopy(spec)
    *parents, last = path.split(".")
    target = data
    for key in parents:
        target = target[int(key)] if isinstance(target, list) else target[key]
    if isinstance(target, list):
        del target[int(last)]
    else:
        del target[last]
    return data


def with_value(spec, path, value):
    data = copy.deepcopy(spec)
    *parents, last = path.split(".")
    target = data
    for key in parents:
        target = target[int(key)] if isinstance(target, list) else target[key]
    target[int(last) if isinstance(target, list) else last] = value
    return data


class BaselineTest(unittest.TestCase):
    def test_original_spec_is_valid(self):
        self.assertEqual(vs.validate(SPEC, SCHEMA), [])


class RequiredFieldsTest(unittest.TestCase):
    """Q1-C1: 명세 형식이 필수 항목을 모두 요구한다.

    기대 목록은 명세 형식에서 가져오지 않고 여기서 따로 선언한다 — 형식에서 필수 항목을 지우면 이 테스트가 실패해야 한다
    (Codex 리뷰 R-Q1 3차 major).
    """

    EXPECTED = {
        "": ["schema_version", "id", "title_key", "world_role", "setting", "audience", "maturity", "localization", "market",
             "session", "coop", "input_methods", "language_goals", "do_not_translate", "safety"],
        "setting": ["world_id", "world_name_key"],
        "audience": ["age_min", "age_max", "grade_band"],
        "maturity": ["target_label", "questionnaire"],
        "maturity.questionnaire": ["social_hangout", "free_form_user_creation", "sensitive_issues",
                                   "generative_ai_extended_interaction", "paid_random_items", "paid_item_trading"],
        "localization": ["source_locale", "planned_locales"],
        "market": ["market_id", "curriculum_id", "resolution"],
        "session": ["target_minutes", "first_world_reaction_s", "first_math_success_s"],
        "coop": ["mandatory", "npc_fallback", "max_players", "free_text_required"],
        "safety": ["runtime_generative_ai", "free_text_input", "external_links", "banned_terms_ref"],
        "language_goals.0": ["term_id", "concept", "everyday_expression_keys", "everyday_action_keys", "label_key", "sequence", "reuse_contexts"],
        "do_not_translate.0": ["id", "pattern"],
    }

    @staticmethod
    def schema_required(section):
        node = SCHEMA
        for part in [p for p in section.split(".") if p]:
            if part == "0":
                node = node["items"]
            else:
                node = node["properties"][part]
            if "$ref" in node:
                node = SCHEMA["$defs"][node["$ref"].split("/")[-1]]
        return node.get("required", [])

    def test_schema_matches_declared_expectations(self):
        for section, fields in self.EXPECTED.items():
            with self.subTest(section=section or "(root)"):
                self.assertEqual(sorted(self.schema_required(section)), sorted(fields))

    def test_each_required_field_is_enforced(self):
        paths = [f"{section}.{field}" if section else field for section, fields in self.EXPECTED.items() for field in fields]
        self.assertEqual(len(paths), 53)
        for path in paths:
            with self.subTest(path=path):
                self.assertNotEqual(vs.validate(without(SPEC, path), SCHEMA), [], f"{path} 를 빼도 통과함")

    def test_unknown_fields_are_rejected(self):
        self.assertNotEqual(vs.validate({**SPEC, "free_chat": True}, SCHEMA), [])

    def test_world_role_input_methods_and_session_limits(self):
        self.assertNotEqual(vs.validate(with_value(SPEC, "world_role", "hangout"), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "input_methods", ["touch", "keyboard_mouse"]), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "session.first_world_reaction_s", 75), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "session.first_math_success_s", 240), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "coop.mandatory", True), SCHEMA), [])


class OriginalWorldTest(unittest.TestCase):
    """Q1-C2: 원본 명세가 검사를 통과하고, 성숙도 설문의 16세 이상 항목이 모두 false 다 (INV-16)."""

    def test_cli_passes_on_original_world(self):
        proc = subprocess.run([sys.executable, str(ROOT / "tools/validate_spec.py"), str(SPEC_PATH)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_questionnaire_all_false(self):
        questionnaire = SPEC["maturity"]["questionnaire"]
        self.assertEqual(len(questionnaire), 6)
        self.assertTrue(all(value is False for value in questionnaire.values()))

    def test_any_age_gating_answer_fails(self):
        for key in SPEC["maturity"]["questionnaire"]:
            with self.subTest(key=key):
                self.assertNotEqual(vs.validate(with_value(SPEC, f"maturity.questionnaire.{key}", True), SCHEMA), [])

    def test_safety_flags_cannot_be_enabled(self):
        for key in ("runtime_generative_ai", "free_text_input", "external_links"):
            with self.subTest(key=key):
                self.assertNotEqual(vs.validate(with_value(SPEC, f"safety.{key}", True), SCHEMA), [])

    def test_dec9_audience_and_maturity_are_fixed(self):
        """Codex 리뷰 R-Q1 major: DEC-9(9~14세·Minimal)가 고정되지 않았다."""
        self.assertNotEqual(vs.validate(with_value(SPEC, "audience.age_min", 5), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "audience.age_max", 18), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "maturity.target_label", "Mild"), SCHEMA), [])
        narrower = with_value(with_value(SPEC, "audience.age_min", 11), "audience.grade_band", "gb_age_11_14")
        self.assertNotEqual(vs.validate(narrower, SCHEMA), [], "Codex 리뷰 R-Q1 2차 major: 입장 게이트는 9~14 전체")
        self.assertEqual(vs.validate(with_value(narrower, "world_role", "unit_world"), SCHEMA), [])  # 단원 월드는 범위 안 일부 허용

    def test_grade_band_matches_ages(self):
        self.assertNotEqual(vs.validate(with_value(SPEC, "audience.grade_band", "gb_age_11_14"), SCHEMA), [])

    def test_banned_terms_ref_must_be_this_market(self):
        """Codex 리뷰 R-Q1 minor: 용어집 참조가 아무 경로나 통과했다."""
        self.assertNotEqual(vs.validate(with_value(SPEC, "safety.banned_terms_ref", "specs/localization/terms/zz-ZZ.yaml"), SCHEMA), [])

    def test_do_not_translate_patterns_are_regex(self):
        """Codex 리뷰 R-Q1 minor: 잘못된 정규식이 통과했다."""
        self.assertNotEqual(vs.validate(with_value(SPEC, "do_not_translate.0.pattern", "["), SCHEMA), [])

    def test_cli_fails_on_broken_spec(self):
        # 저장소에 쓰지 않는다 — 읽기 전용 환경에서도 돌아야 한다 (Codex 리뷰 R-Q1 4차 minor)
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken_spec.yaml"
            broken.write_text("schema_version: 1\nid: x\n", encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ROOT / "tools/validate_spec.py"), str(broken)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)

    def test_do_not_translate_semantics(self):
        """Codex 리뷰 R-Q1 4차 minor: '.' 패턴·빈 id 가 통과했다."""
        self.assertNotEqual(vs.validate(with_value(SPEC, "do_not_translate.0.pattern", "."), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "do_not_translate.0.id", ""), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "do_not_translate.1.id", "coordinate_pair"), SCHEMA), [])
        self.assertNotEqual(vs.validate(without(SPEC, "do_not_translate.1"), SCHEMA), [], "일차식 표본을 잡는 패턴이 없어도 통과함")

    def test_enumerated_literals_cannot_pass(self):
        """Codex 리뷰 R-Q1 6차 minor: 고정 표본 전체를 리터럴 나열해도 통과했다."""
        import re as _re
        for kind, index in (("일차식", 1), ("좌표", 0)):
            with self.subTest(kind=kind):
                enumerated = "|".join(_re.escape(s) for s in vs.MATH_SAMPLES[kind])
                self.assertNotEqual(vs.validate(with_value(SPEC, f"do_not_translate.{index}.pattern", enumerated), SCHEMA), [])

    def test_generated_samples_are_matched_by_original_patterns(self):
        import random as _random
        import re as _re
        patterns = [_re.compile(r["pattern"]) for r in SPEC["do_not_translate"]]
        for seed in range(20):
            for kind, samples in vs.generated_math_samples(_random.Random(seed)).items():
                for sample in samples:
                    self.assertTrue(any(p.fullmatch(sample) for p in patterns), f"{kind} 표본 '{sample}' (seed {seed})")

    def test_do_not_translate_not_literal_and_not_overbroad(self):
        """Codex 리뷰 R-Q1 5차 minor 2건: 표본 리터럴 패턴 우회, 'x = today' 과검출."""
        literal = with_value(SPEC, "do_not_translate.1.pattern", "y = 2x \\+ 1")
        self.assertNotEqual(vs.validate(literal, SCHEMA), [])
        overbroad = with_value(SPEC, "do_not_translate.1.pattern", "\\b[a-z]\\s*=\\s*-?\\d*\\s*[a-z]?\\s*([+-]\\s*\\d+)?")
        self.assertNotEqual(vs.validate(overbroad, SCHEMA), [])
        import re
        patterns = [re.compile(r["pattern"]) for r in SPEC["do_not_translate"]]
        for sentence in vs.PLAIN_SAMPLES:
            with self.subTest(sentence=sentence):
                self.assertFalse(any(p.search(sentence) for p in patterns))


class KeySeparationTest(unittest.TestCase):
    """Q1-C3: 언어·시장·교육과정 키가 나뉜다 (INV-3)."""

    def test_locale_is_language_only(self):
        self.assertNotEqual(vs.validate(with_value(SPEC, "localization.source_locale", "ko-KR"), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "localization.planned_locales", ["ko", "en-US"]), SCHEMA), [])
        self.assertEqual(vs.validate(with_value(SPEC, "localization.planned_locales", ["ko", "zh-Hans"]), SCHEMA), [])

    def test_locale_subset_boundaries(self):
        """Codex 리뷰 R-Q1 4차 minor: 언어 전용 BCP-47 부분집합의 경계."""
        for tag in ("ko", "en", "fil", "zh-Hans", "zh-Hant"):
            with self.subTest(valid=tag):
                self.assertEqual(vs.validate(with_value(SPEC, "localization.planned_locales", ["ko", tag] if tag != "ko" else ["ko"]), SCHEMA), [])
        for tag in ("ko-KR", "en-x-private", "sl-nedis", "EN", "zh-hans", "zh-Hans-CN", "k", ""):
            with self.subTest(invalid=tag):
                self.assertNotEqual(vs.validate(with_value(SPEC, "localization.planned_locales", ["ko", tag]), SCHEMA), [])

    def test_market_needs_region_and_curriculum_is_market_scoped(self):
        self.assertNotEqual(vs.validate(with_value(SPEC, "market.market_id", "ko"), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "market.curriculum_id", "math_language.v1"), SCHEMA), [])

    def test_engine_grade_band_is_market_neutral(self):
        self.assertNotEqual(vs.validate(with_value(SPEC, "audience.grade_band", "중2"), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "audience.grade_band", "ko-KR_middle_2"), SCHEMA), [])

    def test_market_coded_grade_band_rejected(self):
        """Codex 리뷰 R-Q1 major: gb_ko_kr_middle_2 가 통과했다."""
        for band in ("gb_ko_kr_middle_2", "gb_middle_2", "gb_age_ko_14"):
            with self.subTest(band=band):
                self.assertNotEqual(vs.validate(with_value(SPEC, "audience.grade_band", band), SCHEMA), [])

    def test_curriculum_must_match_market(self):
        """Codex 리뷰 R-Q1 major: market en-US + curriculum ko-KR 가 통과했다."""
        mismatch = with_value(with_value(SPEC, "market.market_id", "en-US"), "safety.banned_terms_ref", "specs/localization/terms/en-US.yaml")
        self.assertNotEqual(vs.validate(mismatch, SCHEMA), [])

    def test_source_locale_must_be_planned(self):
        self.assertNotEqual(vs.validate(with_value(SPEC, "localization.planned_locales", ["en"]), SCHEMA), [])


class LanguageFirstTest(unittest.TestCase):
    """Q1-C4: 용어마다 일상 표현 → 행동 → 이름표 순서와 재사용 맥락 자리가 있다 (INV-15)."""

    def test_sequence_order_is_fixed(self):
        wrong = ["situation", "math_label", "everyday_expression", "player_action", "world_response", "reuse"]
        self.assertNotEqual(vs.validate(with_value(SPEC, "language_goals.0.sequence", wrong), SCHEMA), [])

    def test_everyday_actions_required_and_keyed(self):
        self.assertNotEqual(vs.validate(with_value(SPEC, "language_goals.0.everyday_action_keys", []), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "language_goals.0.everyday_action_keys", ["오른쪽으로"]), SCHEMA), [])

    def test_everyday_expressions_are_separate_and_required(self):
        """Codex 리뷰 R-Q1 major: 일상 표현 필드가 없고 행동 키만 있었다."""
        self.assertNotEqual(vs.validate(with_value(SPEC, "language_goals.0.everyday_expression_keys", []), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "language_goals.0.everyday_expression_keys", ["더 올라가게"]), SCHEMA), [])
        self.assertNotEqual(vs.validate(with_value(SPEC, "language_goals.0.everyday_expression_keys", ["action.position.move_right"]), SCHEMA), [])
        self.assertTrue(all(g["everyday_expression_keys"] for g in SPEC["language_goals"]))

    def test_label_matches_term_and_terms_unique(self):
        self.assertNotEqual(vs.validate(with_value(SPEC, "language_goals.0.label_key", "term.slope.name"), SCHEMA), [])
        dup = copy.deepcopy(SPEC)
        dup["language_goals"].append(copy.deepcopy(dup["language_goals"][0]))
        self.assertNotEqual(vs.validate(dup, SCHEMA), [])

    def test_original_world_terms(self):
        concepts = [g["concept"] for g in SPEC["language_goals"]]
        self.assertEqual(concepts, ["position", "change"])
        self.assertTrue(all("reuse_contexts" in g for g in SPEC["language_goals"]))


if __name__ == "__main__":
    unittest.main()
