"""원본 월드 소스 검사 (작업 Graph Q4-C1).

저장소 소스(world/)가 Q3 Harness 를 위반 0 으로 통과하고, 미션·용어·정본 값이 잠긴 Q2 명세와 같으며,
번역표 CSV 는 용어집에서 생성한 결과와 한 글자도 다르지 않은지 본다. Studio 가 없어도 돌아간다.
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import run, source  # noqa: E402
from tools import build_localization  # noqa: E402

WORLD = ROOT / "world"
SOURCE = WORLD / "src"
GRAPH = json.loads((ROOT / "specs/graph/neo-seoul-city-language-gate.graph.json").read_text(encoding="utf-8"))
CANONICAL = {v["id"]: v.get("value") for v in source.load_rules(ROOT).canonical.get("values", []) if isinstance(v, dict)}


def luau_text(rel: str) -> str:
    return (SOURCE / rel).read_text(encoding="utf-8")


class HarnessTest(unittest.TestCase):
    """월드 소스가 Q3 검수 Harness 를 통과한다."""

    def test_no_violation(self):
        found = {check: hits for check, hits in run.run_checks(WORLD).items() if hits}
        self.assertEqual(found, {}, f"Harness 위반: {found}")

    def test_every_check_runs(self):
        results = run.run_checks(WORLD)
        self.assertEqual(sorted(results), sorted(c["id"] for c in run.load_manifest()["checks"]))


class MissionDataTest(unittest.TestCase):
    """src/shared/Missions.luau 가 잠긴 Q2 명세와 같다."""

    FIELDS = re.compile(r'\{id = "(?P<id>[^"]+)", core = (?P<core>true|false), requires = \{(?P<requires>[^}]*)\}, '
                        r'goalKey = (?P<goal>"[^"]*"|nil), newTerm = (?P<term>"[^"]*"|nil), '
                        r'targetEndSeconds = (?P<secs>\d+|nil)\}')

    @staticmethod
    def _value(text: str):
        return None if text == "nil" else text.strip('"')

    def parsed(self) -> list[dict]:
        out = []
        for m in self.FIELDS.finditer(luau_text("shared/Missions.luau")):
            out.append({
                "id": m["id"],
                "core": m["core"] == "true",
                "requires": [p.strip().strip('"') for p in m["requires"].split(",") if p.strip()],
                "goal_key": self._value(m["goal"]),
                "new_term": self._value(m["term"]),
                "target_end_s": None if m["secs"] == "nil" else int(m["secs"]),
            })
        return out

    def test_missions_match_the_locked_graph(self):
        want = [{"id": m["id"], "core": bool(m["core"]), "requires": list(m.get("requires") or []),
                 "goal_key": m.get("goal_key"), "new_term": m.get("new_term"), "target_end_s": m.get("target_end_s")}
                for m in GRAPH["missions"]]
        self.assertEqual(self.parsed(), want)

    def test_terms_match_the_locked_graph(self):
        text = luau_text("shared/Missions.luau")
        for term in GRAPH["terms"]:
            with self.subTest(term=term["term_id"]):
                self.assertIn(term["term_id"], text, "잠긴 Q2 용어가 미션 자료에 없다")


class CanonicalValueTest(unittest.TestCase):
    """코드가 쓰는 수·선택지가 잠긴 Q2 정본 값과 같다."""

    def test_grid_half_width(self):
        grid = CANONICAL["cv.coordinate_expression"]["grid"]
        self.assertEqual([grid["x"], grid["y"]], [[-2, 2], [-2, 2]], "정본 값이 바뀌면 코드도 함께 고쳐야 한다")
        self.assertIn(f"local GRID = {grid['x'][1]}", luau_text("server/Main.server.luau"))

    def test_cooldown_seconds(self):
        seconds = CANONICAL["cv.server_cooldown"]["seconds"]
        self.assertIn(f"local SECONDS = {seconds}", luau_text("server/Cooldown.luau"))

    def test_slope_choices(self):
        text = luau_text("server/MissionService.luau")
        for key in CANONICAL["cv.slope_choices"]["expressions"]:
            with self.subTest(key=key):
                self.assertIn(f'["{key}"]', text, "기울기 선택지는 잠긴 Q2 표현 키만 쓴다")

    def test_coop_switch_ids(self):
        text = luau_text("server/WorldBuilder.luau")
        for name in CANONICAL["cv.coop_switch_ids"]:
            if not name.startswith("gate_prism"):
                continue   # 광장 다리 2개는 선택 미션(Q4 범위 밖)
            with self.subTest(name=name):
                self.assertIn(f'"{name}"', text, "협동 프리즘 이름은 잠긴 Q2 목록과 같아야 한다")

    def test_server_check_distance(self):
        studs = CANONICAL["cv.server_distance"]["server_check_studs"]
        self.assertIn(f"local REACH = {studs}", luau_text("server/Main.server.luau"))

    def test_prompt_activation_distance(self):
        studs = CANONICAL["cv.server_distance"]["prompt_activation_studs"]
        self.assertIn(f"MaxActivationDistance = {studs}", luau_text("server/WorldBuilder.luau"))

    def test_hint_idle_seconds(self):
        seconds = CANONICAL["cv.hint_ladder"]["first_trigger"]["idle_seconds"]
        self.assertIn(f"local HINT_IDLE_SECONDS = {seconds}", luau_text("client/Hud.client.luau"))

    def test_grid_half_width_in_layout(self):
        grid = CANONICAL["cv.coordinate_expression"]["grid"]
        self.assertIn(f"Layout.GRID_HALF = {grid['x'][1]}", luau_text("shared/Layout.luau"))

    def test_hint_ladder_never_reveals_the_answer(self):
        """정본 값 cv.hint_ladder.reveals_answer = false — 힌트 세 단계만 쓰고 정답 문구는 없다."""
        self.assertFalse(CANONICAL["cv.hint_ladder"]["reveals_answer"])
        used = set(re.findall(r'Text\.get\("(hint\.[^"]+)"\)', luau_text("client/Hud.client.luau")))
        allowed = {key for ladder in GRAPH["hint_ladders"] for key in ladder["keys"]}
        self.assertTrue(used)
        self.assertEqual(sorted(used - allowed), [])

    def test_first_rewards(self):
        rewards = [r["id"] for r in GRAPH["rewards"] if r["mission"] == "m.gate_open"]
        self.assertEqual(sorted(rewards), sorted(CANONICAL["cv.first_rewards"]))
        granted = re.findall(r'RewardService\.grant\(player, "([^"]+)", "([^"]+)"\)', luau_text("server/MissionService.luau"))
        self.assertTrue(granted, "보상 지급 호출이 없다")
        for reward_id, mission_id in granted:
            with self.subTest(reward=reward_id):
                self.assertIn(reward_id, rewards, "Q2 가 정하지 않은 보상을 준다")
                self.assertEqual(mission_id, "m.gate_open")


class LocalizationTest(unittest.TestCase):
    """번역표는 용어집에서 생성한 결과와 같다 — 손으로 고치지 않는다."""

    def test_csv_matches_the_generator(self):
        done = subprocess.run([sys.executable, str(ROOT / "tools/build_localization.py"), "--check"],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_every_key_in_the_glossary_is_in_the_table(self):
        tree = source.load_tree(WORLD)
        self.assertEqual(sorted(tree.strings), sorted(key for key, _text, _ctx, _ex in build_localization.rows()))

    def test_keys_used_by_the_code_exist(self):
        tree = source.load_tree(WORLD)
        used = {m.group(1) for f in tree.luau
                for m in re.finditer(r'Text\.get\("([^"]+)"\)', (WORLD / f.rel).read_text(encoding="utf-8"))}
        self.assertTrue(used, "코드가 문구 키를 하나도 쓰지 않는다")
        self.assertEqual(sorted(used - set(tree.strings)), [])


class AnalyticsEventTest(unittest.TestCase):
    """코드가 보내는 분석 이벤트가 잠긴 허용 목록 안에 있다 (INV-10 · F11)."""

    def test_events_are_in_the_allowlist(self):
        events = source.load_rules(ROOT).events
        allowed = {e["name"] for e in events.get("onboarding_funnel", [])} | {e["name"] for e in events.get("custom_events", [])}
        text = "".join((SOURCE / rel).read_text(encoding="utf-8") for rel in ("server/MissionService.luau",))
        used = set(re.findall(r'Analytics\.(?:log|funnel)\(player, "([^"]+)"', text))
        self.assertTrue(used, "분석 이벤트를 하나도 보내지 않는다")
        self.assertEqual(sorted(used - allowed), [])

    def test_funnel_events_use_the_funnel_sender(self):
        funnel = {e["name"] for e in source.load_rules(ROOT).events.get("onboarding_funnel", [])}
        text = (SOURCE / "server/MissionService.luau").read_text(encoding="utf-8")
        for name in re.findall(r'Analytics\.log\(player, "([^"]+)"', text):
            with self.subTest(event=name):
                self.assertNotIn(name, funnel, "퍼널 단계는 Analytics.funnel 로 보내야 한다 (F11)")


if __name__ == "__main__":
    unittest.main()
