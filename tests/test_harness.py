"""검수 Harness 검사 (작업 Graph Q3 기준별 테스트).

깨끗한 고정 데이터는 모든 정적 검사를 통과하고, 심은 결함은 정해진 검사가 정확히 잡는지(기준선 + 변이)를 본다.
저장소 파일은 쓰지 않는다 — 결함 데이터는 임시 폴더에 덧씌워 만든다.
"""
import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import luau, run, source  # noqa: E402
from harness.checks import REGISTRY, math_claims  # noqa: E402

FIXTURES = ROOT / "harness" / "fixtures"
CLEAN = FIXTURES / "clean"
MANIFEST = run.load_manifest()
RULES = source.load_rules(ROOT)
GRAPH = json.loads((ROOT / "graph.json").read_text(encoding="utf-8"))
# intent §3 Q3 와 작업 Graph Q3-C1 이 이름으로 요구하는 결함 종류 — 매니페스트의 결함이 이것을 모두 덮어야 한다
REQUIRED_CLASSES = {"클라이언트가 보상을 정하는 코드", "중복 보상", "끊긴 번역 키", "넘치는 긴 번역문", "틀린 수학 대사", "금지어",
                    "무작위 보상 코드", "URL 문자열", "런타임 외부 호출(LLM)", "필터 없는 자유 입력", "커스텀 필드 개인정보"}
ITEM_IDS = {f"E{i}" for i in range(1, 7)} | {f"U{i}" for i in range(1, 15)}
MODES = {"static", "runtime", "human", "covered", "static_later"}


class TreeCase(unittest.TestCase):
    """깨끗한 트리를 임시 폴더에 복사해 고친 뒤 검사한다."""

    def make_tree(self, overlay: str | None = None) -> Path:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copytree(CLEAN, tmp, dirs_exist_ok=True)
        if overlay:
            shutil.copytree(FIXTURES / "defects" / overlay, tmp, dirs_exist_ok=True)
        return tmp

    def edit(self, tree: Path, rel: str, old: str, new: str) -> None:
        path = tree / rel
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1, f"{rel}: '{old}' 가 한 번 있어야 한다")
        path.write_text(text.replace(old, new), encoding="utf-8")

    def failing(self, tree: Path) -> dict[str, list[str]]:
        return {k: v for k, v in run.run_checks(tree, MANIFEST, RULES).items() if v}

    def assertCaught(self, tree: Path, check_id: str, fragment: str = "") -> None:
        found = run.run_checks(tree, MANIFEST, RULES)[check_id]
        self.assertTrue(any(fragment in x for x in found), f"{check_id} 가 '{fragment}' 를 잡지 못함: {found}")


class PlantedDefectTest(TreeCase):
    """Q3-C1 — 깨끗한 데이터는 통과, 심은 결함은 정해진 검사가 정확히 잡는다."""

    def test_clean_fixture_passes_every_static_check(self):
        self.assertEqual(self.failing(self.make_tree()), {})

    def test_each_planted_defect_is_caught_by_exactly_its_checks(self):
        for defect in MANIFEST["defects"]:
            with self.subTest(defect=defect["id"]):
                failing = self.failing(self.make_tree(defect["id"]))
                self.assertEqual(sorted(failing), sorted(defect["expected"]))

    def test_required_defect_classes_are_planted(self):
        self.assertEqual(REQUIRED_CLASSES - {d["class"] for d in MANIFEST["defects"]}, set())

    def test_every_defect_has_overlay_and_every_overlay_is_listed(self):
        overlays = {p.name for p in (FIXTURES / "defects").iterdir() if p.is_dir()}
        self.assertEqual(overlays, {d["id"] for d in MANIFEST["defects"]})

    def test_every_static_check_has_a_planted_defect(self):
        caught = {c for d in MANIFEST["defects"] for c in d["expected"]}
        self.assertEqual(set(REGISTRY) - caught, set())


class MathClaimTest(TreeCase):
    """Q3-C2 — E1·E2 는 정확한 유리수 계산의 결정론 관문이다."""

    TRUE = [
        {"kind": "coordinate", "origin": [0, 0], "moves": [{"dir": "right", "n": 2}, {"dir": "up", "n": 1}], "states": [2, 1]},
        {"kind": "coordinate", "origin": [1, 1], "moves": [{"dir": "left", "n": 3}, {"dir": "down", "n": 2}], "states": [-2, -1]},
        {"kind": "slope", "rise": 1, "run": 3, "states": "1/3"},
        {"kind": "slope", "rise": 0, "run": 4, "states": 0},
        {"kind": "slope_compare", "this": {"rise": 3, "run": 1}, "other": {"rise": 1, "run": 1}, "states": "steeper"},
        {"kind": "slope_compare", "this": {"rise": 2, "run": 4}, "other": {"rise": 1, "run": 2}, "states": "equal"},
        {"kind": "line_point", "line": {"m": 2, "b": 1}, "point": [2, 5], "states": True},
        {"kind": "line_point", "line": {"m": "1/2", "b": 0}, "point": [3, 1], "states": False},
    ]
    FALSE = [
        {"kind": "coordinate", "origin": [0, 0], "moves": [{"dir": "right", "n": 2}, {"dir": "up", "n": 1}], "states": [1, 2]},
        {"kind": "slope", "rise": 1, "run": 3, "states": "0.333"},       # 근삿값은 같지 않다 — 정확한 유리수
        {"kind": "slope_compare", "this": {"rise": 4, "run": 4}, "other": {"rise": 3, "run": 1}, "states": "steeper"},  # 큰 수가 더 가파른 게 아니다(K2 오개념)
        {"kind": "line_point", "line": {"m": 2, "b": 1}, "point": [2, 4], "states": True},
    ]
    ERRORS = [
        {"kind": "slope", "rise": 1, "run": 0, "states": 1},
        {"kind": "coordinate", "origin": [0, 0], "moves": [{"dir": "forward", "n": 1}], "states": [0, 1]},
        {"kind": "slope", "rise": 1.5, "run": 1, "states": 1},           # 실수는 근삿값이라 받지 않는다
        {"kind": "parabola", "states": 1},
        {"kind": "slope", "rise": "a", "run": 1, "states": 1},           # 수로 읽을 수 없다
        {"kind": "coordinate", "origin": [0], "moves": [], "states": [0, 0]},   # 점은 [x, y]
        {"kind": "slope_compare", "this": {"rise": 1, "run": 1}, "other": {"rise": 1, "run": 1}, "states": "bigger"},
        {"kind": "line_point", "line": {"m": 1, "b": 0}, "point": [1, 1], "states": "yes"},
    ]

    def test_true_and_false_claims(self):
        for claim in self.TRUE:
            with self.subTest(claim=claim):
                self.assertIs(math_claims.evaluate(claim), True)
        for claim in self.FALSE:
            with self.subTest(claim=claim):
                self.assertIs(math_claims.evaluate(claim), False)

    def test_undecidable_claims_raise(self):
        for claim in self.ERRORS:
            with self.subTest(claim=claim):
                with self.assertRaises(math_claims.ClaimError):
                    math_claims.evaluate(claim)

    def test_deterministic(self):
        tree = self.make_tree("D-wrong-math")
        first = run.run_checks(tree, MANIFEST, RULES)["math.truth"]
        self.assertTrue(first)
        self.assertEqual([run.run_checks(tree, MANIFEST, RULES)["math.truth"] for _ in range(3)], [first] * 3)

    def test_line_must_state_the_claimed_value(self):
        tree = self.make_tree()
        self.edit(tree, "src/shared/Localization.csv", "출발 칸에서 오른쪽 2, 위 1 → (2, 1).", "출발 칸에서 오른쪽 2, 위 1 → (1, 2).")
        self.edit(tree, "src/shared/Localization.csv", "→ (2, 1). Ĉööŕðïñàţē.", "→ (1, 2). Ĉööŕðïñàţē.")
        self.assertCaught(tree, "math.truth", "명제와 대사가 따로 논다")

    def test_missing_and_inconsistent_conditions(self):
        cases = [("    conditions: {origin: [0, 0], axes: x_right_y_up}\n", "    conditions: {axes: x_right_y_up}\n", "조건 origin 가 빠졌다"),
                 ("    conditions: {origin: [0, 0], axes: x_right_y_up}\n", "    conditions: {origin: [1, 0], axes: x_right_y_up}\n", "기준점과 다르다"),
                 ("    conditions: {origin: [0, 0], axes: x_right_y_up}\n", "    conditions: {origin: [0, 0], axes: x_right_y_down}\n", "축 방향"),
                 ("    conditions: {domain: real}\n", "    conditions: {domain: complex}\n", "정의역"),
                 ("    this: {rise: 3, run: 1}\n", "    this: {rise: 3, run: 0}\n", "가로 변화가 0 이 아니라는 조건"),
                 ("    states: steeper\n    conditions: {run_nonzero: true, same_unit: grid_cell}\n",
                  "    states: steeper\n    conditions: {run_nonzero: true, same_unit: meter}\n", "단위"),
                 ("    kind: line_point\n", "    kind: circle\n", "명제 종류")]
        for old, new, fragment in cases:
            with self.subTest(fragment=fragment):
                tree = self.make_tree()
                self.edit(tree, "content/math_claims.yaml", old, new)
                self.assertCaught(tree, "math.conditions", fragment)

    def test_claim_problems_inside_a_tree(self):
        cases = [("    rise: 2\n    run: 1\n", "    rise: 2\n    run: 0\n", "math.truth", "판정할 수 없다"),
                 ("    line_key: label.line.point\n", "    line_key: label.line.missing\n", "math.truth", "LocalizationTable 에 없다"),
                 ("claims:\n", "claims:\n  - just text\n", "math.conditions", "명제는 객체여야 한다")]
        for old, new, check, fragment in cases:
            with self.subTest(fragment=fragment):
                tree = self.make_tree()
                self.edit(tree, "content/math_claims.yaml", old, new)
                self.assertCaught(tree, check, fragment)

    def test_claims_required(self):
        tree = self.make_tree()
        (tree / "content" / "math_claims.yaml").unlink()
        self.assertCaught(tree, "math.truth", "수학 명제")


class RecordTest(TreeCase):
    """Q3-C3 — 검사마다 기록 하나(명령·결과·시각·대상 지문), 로컬 경로 없음."""

    def test_one_record_per_check_without_local_paths(self):
        tree = self.make_tree("D-banned-term")
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out)
        results = run.run_checks(tree, MANIFEST, RULES)
        paths = run.write_records(tree, results, out, "harness/fixtures/defects/D-banned-term")
        self.assertEqual(len(paths), len(MANIFEST["checks"]))
        self.assertEqual(sorted(p.stem for p in out.iterdir()), sorted(c["id"] for c in MANIFEST["checks"]))
        for p in paths:
            body = p.read_text(encoding="utf-8")
            for field in ("check:", "command: python3 -m harness.run", "result:", "time:", "target_sha256:", "findings:"):
                self.assertIn(field, body)
            self.assertNotIn(str(tree), body)
            self.assertNotIn(str(Path.home()), body)
        self.assertIn("result: FAIL", (out / "safety.banned_terms.txt").read_text(encoding="utf-8"))
        self.assertIn("result: PASS", (out / "safety.url.txt").read_text(encoding="utf-8"))

    def test_fingerprint_changes_with_content(self):
        tree = self.make_tree()
        before = run.fingerprint(tree)
        self.edit(tree, "src/client/Hud.client.luau", "sendCell(2, 1)", "sendCell(2, 2)")
        self.assertNotEqual(before, run.fingerprint(tree))

    def test_cli_exit_codes(self):
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run.main([str(self.make_tree()), "--out", str(out)]), 0)
            self.assertEqual(run.main([str(self.make_tree("D-url")), "--out", str(out)]), 1)
            self.assertEqual(run.main([str(out), "--out", str(out)]), 2)   # Rojo 프로젝트가 아님

    def test_broken_check_is_recorded_as_failure(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest["checks"].append({"id": "missing.check"})
        self.assertIn("구현이 없다", run.run_checks(self.make_tree(), manifest, RULES)["missing.check"][0])
        manifest = copy.deepcopy(MANIFEST)
        del manifest["config"]["reward_module"]
        self.assertIn("끝까지 돌지 못했다", run.run_checks(self.make_tree(), manifest, RULES)["server.client_reward"][0])


class ManifestTest(unittest.TestCase):
    """Q3-C4 — 매니페스트가 E1~E6·U1~U14 와 안전 불변식을 빠짐없이, 방식·이유와 함께 담는다. 고정 데이터 지문이 맞다."""

    def test_items_cover_math_and_ui_lists(self):
        self.assertEqual(ITEM_IDS - {i["id"] for i in MANIFEST["items"]}, set())

    def test_each_item_has_mode_stage_and_reason_or_checks(self):
        q2 = {c["id"] for n in GRAPH["nodes"] if n["id"] == "Q2" for c in n["criteria"]}
        for item in MANIFEST["items"]:
            with self.subTest(item=item["id"]):
                self.assertIn(item["mode"], MODES)
                self.assertRegex(item["stage"], r"^Q[2-8]$")
                if item["mode"] == "static":
                    self.assertEqual(item["stage"], "Q3")
                    self.assertTrue(item["checks"])
                    self.assertEqual(set(item["checks"]) - set(REGISTRY), set())
                else:
                    self.assertTrue(item.get("reason", "").strip())
                if item["mode"] == "covered":
                    self.assertTrue(item["covered_by"])
                    self.assertEqual(set(item["covered_by"]) - q2, set())

    def test_safety_invariants_have_static_checks(self):
        static = {i["id"] for i in MANIFEST["items"] if i["mode"] == "static"}
        self.assertEqual({"INV-3", "INV-4", "INV-10", "INV-11", "INV-12", "INV-16"} - static, set())

    def test_registry_and_manifest_checks_match(self):
        self.assertEqual({c["id"] for c in MANIFEST["checks"]}, set(REGISTRY))
        used = {c for i in MANIFEST["items"] for c in i.get("checks", [])}
        self.assertEqual(set(REGISTRY) - used, set())

    def test_fixture_index_matches_files(self):
        index = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))["files"]
        self.assertEqual(index, run.fixture_index(FIXTURES))

    def test_fixture_index_detects_change(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copytree(FIXTURES, tmp, dirs_exist_ok=True)
        (tmp / "clean" / "src" / "client" / "Hud.client.luau").write_text("-- 바뀜\n", encoding="utf-8")
        index = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))["files"]
        self.assertNotEqual(index, run.fixture_index(tmp))


class LuauTest(unittest.TestCase):
    """토크나이저 — 주석·문자열에 속지 않고 블록을 바로 센다."""

    SRC = '''
-- 주석 RewardService.grant("x")
--[==[ 긴 주석 https://example.com ]==]
local M = {}
local s = "a -- not comment"
local t = [[ long
string ]]
function M.grant(player: Player, rewardId: string, opts: {x: number}?)
  if not claimOnce(player, rewardId) then return end
  local v = if rewardId then 1 else 2
  for i = 1, 3 do
    while false do end
  end
  repeat local x = 1 until true
  if a then if b then c() end elseif d then e() else f() end
  local g = function(y) return y end
  return `hi {player}`
end
return M
'''

    def test_comments_dropped_strings_kept(self):
        toks = luau.tokenize(self.SRC)
        self.assertEqual([t.text for t in toks if t.kind == luau.STRING], ["a -- not comment", " long\nstring ", "hi {player}"])
        self.assertFalse(any(t.text == "RewardService" for t in toks))

    def test_function_bodies_and_typed_params(self):
        bodies = luau.function_bodies(luau.tokenize(self.SRC))
        self.assertEqual([b[0] for b in bodies], [["player", "rewardId", "opts"], ["y"]])
        self.assertEqual([t.text for t in bodies[0][1][-2:]], ["return", "hi {player}"])

    def test_calls_exclude_definitions(self):
        toks = luau.tokenize("function M.grant(a) end\nM.grant(1, 2)\nx.M.grant(3)\n")
        self.assertEqual(len(luau.find_calls(toks, ("M", "grant"))), 1)
        self.assertEqual([[t.text for t in a] for a in luau.call_args(toks, luau.find_calls(toks, ("M", "grant"))[0])], [["1"], ["2"]])

    def test_syntax_errors(self):
        for src in ('local s = "unterminated', "local t = [[ open", "function f(a)\n  if a then\nend"):
            with self.subTest(src=src):
                with self.assertRaises(luau.LuauSyntaxError):
                    luau.function_bodies(luau.tokenize(src))


class CheckBranchTest(TreeCase):
    """검사 함수의 갈래마다 — 결함 데이터 20종이 닿지 않는 경우를 변이로 본다."""

    def test_server_branches(self):
        cases = [
            ("src/server/RewardService.luau", "\tif not claimOnce(player, missionId .. \"|\" .. rewardId) then return end\n", "", "server.duplicate_reward", "중복 지급을 막지 않는다"),
            ("src/server/RewardService.luau", "function RewardService.grant(", "function RewardService.give(", "server.duplicate_reward", "grant 함수가 없다"),
            ("src/server/MissionService.luau", 'RewardService.grant(player, "reward.explorer_card", "m.gate_open")',
             'RewardService.grant(player, rewardName, "m.gate_open")', "server.duplicate_reward", "글자 그대로"),
            ("src/server/Main.server.luau", "SignalRemote.OnServerEvent:Connect(onSignal)", "SignalRemote.OnServerEvent:Connect(missingHandler)",
             "server.remote_validation", "처리 함수를 찾지 못했다"),
            ("src/server/Main.server.luau", "SignalRemote.OnServerEvent:Connect(onSignal)",
             'SignalRemote.OnServerEvent:Connect(function(player, x)\n\tif not Cooldown.allow(player, "signal") then return end\nend)',
             "server.remote_validation", "원격 입력 x 의 형식"),
        ]
        for rel, old, new, check, fragment in cases:
            with self.subTest(fragment=fragment):
                tree = self.make_tree()
                self.edit(tree, rel, old, new)
                self.assertCaught(tree, check, fragment)

    def test_server_module_in_client_visible_place(self):
        tree = self.make_tree()
        shutil.move(tree / "src/server/RewardService.luau", tree / "src/shared/RewardService.luau")
        self.assertCaught(tree, "server.client_reward", "보상 모듈 RewardService 이 클라이언트가 볼 수 있는 곳")
        tree = self.make_tree()
        (tree / "src/server/RewardService.luau").unlink()
        self.assertCaught(tree, "server.duplicate_reward", "보상 모듈 RewardService 이 없다")
        tree = self.make_tree()
        shutil.copy(tree / "src/server/Main.server.luau", tree / "src/shared/Remote.luau")
        self.assertCaught(tree, "server.remote_validation", "클라이언트가 볼 수 있는 코드")

    def test_i18n_branches(self):
        tree = self.make_tree()
        self.edit(tree, "src/client/Hud.client.luau", 'Text.get("goal.signal_2")', "Text.get(goalKey)")
        self.assertCaught(tree, "i18n.missing_key", "글자 그대로")
        tree = self.make_tree()
        self.edit(tree, "src/client/Hud.client.luau", 'goal.Text = Text.get("goal.signal_2")',
                  'goal.Text = game:GetService("LocalizationService"):GetTranslatorForPlayerAsync(nil):FormatByKey("goal.missing")')
        self.assertCaught(tree, "i18n.missing_key", "goal.missing")
        tree = self.make_tree()
        (tree / "src/shared/Localization.csv").unlink()
        self.assertCaught(tree, "i18n.missing_key", "LocalizationTable(CSV)이 없다")
        tree = self.make_tree()
        self.edit(tree, "src/client/Hud.client.luau", "sendCell(2, 1)", 'sendCell(2, 1)\ngoal.Text = "Open the gate"')
        self.assertCaught(tree, "i18n.hardcoded_text", "Open the gate")
        tree = self.make_tree()
        self.edit(tree, "src/shared/Localization.csv", "도시 언어 게이트가 열렸어!", "열렸어! 정말로. 진짜로. 와!")
        self.assertCaught(tree, "text.readability", "문장이 4개다")

    def test_source_reading_problems_fail_every_check(self):
        cases = [("src/shared/Localization.csv", "Key,Source,Context,Example,qps-ploc", "Id,Text", "머리줄"),
                 ("src/server/Cooldown.luau", "return Cooldown\n", 'return "unterminated\n', "Luau 를 읽지 못했다"),
                 ("default.project.json", '"$path": "src/client"', '"$path": "src/missing"', "트리 안의 폴더가 아니다")]
        for rel, old, new, fragment in cases:
            with self.subTest(fragment=fragment):
                tree = self.make_tree()
                self.edit(tree, rel, old, new)
                results = run.run_checks(tree, MANIFEST, RULES)
                self.assertTrue(all(any(fragment in x for x in found) for found in results.values()), fragment)
        unmapped = "Rojo 프로젝트가 어디에도 넣지 않는 파일"
        tree = self.make_tree()
        (tree / "src/stray").mkdir()
        (tree / "src/stray/Loose.luau").write_text("return {}\n", encoding="utf-8")
        self.assertTrue(all(any(unmapped in x for x in v) for v in run.run_checks(tree, MANIFEST, RULES).values()))
        tree = self.make_tree()
        self.edit(tree, "default.project.json", '"StarterPlayer": {"StarterPlayerScripts": {"Gate": {"$path": "src/client"}}}', '"Workspace": {}')
        self.assertTrue(all(any(unmapped in x for x in v) for v in run.run_checks(tree, MANIFEST, RULES).values()))
        tree = self.make_tree()
        (tree / "default.project.json").write_text("{", encoding="utf-8")
        self.assertTrue(all(any("default.project.json 을 읽지 못했다" in x for x in v) for v in run.run_checks(tree, MANIFEST, RULES).values()))

    def test_analytics_branches(self):
        cases = [('Analytics.log(player, "gate_opened", {play_mode = "solo_npc"})', 'Analytics.log(player, "gate_opened")', "꼴이어야 한다"),
                 ('Analytics.log(player, "gate_opened", {play_mode = "solo_npc"})', 'Analytics.log(player, "gate_opened", {mission = "m.gate_open"})', "필드 mission 는 허용되지 않는다"),
                 ('Analytics.log(player, "gate_opened", {play_mode = "solo_npc"})', 'Analytics.log(player, "gate_opened", fields)', "표 글자 그대로"),
                 ('Analytics.log(player, "gate_opened", {play_mode = "solo_npc"})', 'Analytics.log(player, "gate_opened", {"solo_npc"})', "이름 = 값 꼴"),
                 ('Analytics.log(player, "gate_opened", {play_mode = "solo_npc"})', 'Analytics.log(player, "gate_opened", {play_mode = "trio"})', "열거형 글자 그대로가 아니다")]
        for old, new, fragment in cases:
            with self.subTest(fragment=fragment):
                tree = self.make_tree()
                self.edit(tree, "src/server/MissionService.luau", old, new)
                self.assertCaught(tree, "analytics.calls", fragment)
        tree = self.make_tree()
        shutil.move(tree / "src/server/Analytics.luau", tree / "src/shared/Analytics.luau")
        self.assertCaught(tree, "analytics.calls", "분석 모듈이 클라이언트가 볼 수 있는 곳")
        tree = self.make_tree()
        self.edit(tree, "src/client/Hud.client.luau", "sendCell(2, 1)", 'sendCell(2, 1)\nAnalytics.log(player, "gate_opened", {play_mode = "solo_npc"})')
        self.assertCaught(tree, "analytics.calls", "클라이언트 코드가 분석을 보낸다")

    def test_safety_branches(self):
        tree = self.make_tree()
        rules = source.Rules(RULES.events, {**RULES.glossary, "banned_terms": []}, RULES.world_spec)
        self.assertIn("금지어 목록을 읽지 못했다", run.run_checks(tree, MANIFEST, rules)["safety.banned_terms"][0])
        tree = self.make_tree()
        self.edit(tree, "src/server/RewardService.luau", "\t\towned:SetAttribute(rewardId, true)\n",
                  "\t\towned:SetAttribute(rewardId, true)\n\t\tlocal r = Random.new()\n")
        self.assertCaught(tree, "safety.random_or_paid_reward", "난수")
        tree = self.make_tree()
        self.edit(tree, "src/client/Hud.client.luau", "sendCell(2, 1)", 'sendCell(2, 1)\nlocal link = "see www.example.org"')
        self.assertCaught(tree, "safety.url", "www.")


if __name__ == "__main__":
    unittest.main()
