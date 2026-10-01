"""flow_guard 회귀 테스트 — 실행: python3 -m unittest discover -s tools -v

테스트 전용 Intent·결정 기록을 임시 폴더에 만들어 검사한다. 저장소의 실제 파일은 RepoConsistencyTest 만 읽고, 상태 기록은 바꾸지 않는다.
"""
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_guard as fg  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
HELPER = fg.DEFAULT_HELPER
NEEDS_HELPER = unittest.skipUnless(HELPER.is_file(), "masterwork 헬퍼 없음 — Diagram·Graph 검사 테스트를 건너뜀")

INTENT = """# 테스트 Intent

## 3. 상태
| ID | 상태 | 증거 | 선행 |
|---|---|---|---|
| Q1 | 명세 | e | — |
| Q2 | 그래프 | e | Q1 |
| Q3 | 검수 | e | Q2 |

## 7. 결정
| ID | 결정 | 막는 범위 | 메모 |
|---|---|---|---|
| DEC-1 | 첫 월드 | Intent 검토 | |
| DEC-2 | 스테이징 Place | Studio 수정 전부 | |
"""

DECISIONS = """# 결정 기록
| ID | 상태 | 결정 내용 | 근거 |
|---|---|---|---|
| REVIEW | 열림 | | |
| DEC-1 | 열림 | | |
| DEC-2 | 열림 | | |
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def criterion(cid):
    return {"id": cid, "statement": "s", "method": "m", "target": "t", "evidence_types": ["test"],
            "benchmark_required": False, "benchmark_ids": []}


def exec_node(node_id, deps, artifact):
    return {"id": node_id, "label": f"단계 {node_id}", "outcome": "o", "depends_on": deps,
            "artifacts": [artifact], "maker": "test", "review": "separated", "human_holds": [],
            "minor_limit": 0, "criteria": [criterion("C" + node_id)]}


class Workspace(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "intent.md").write_text(INTENT, encoding="utf-8")
        (self.root / "decisions.md").write_text(DECISIONS, encoding="utf-8")
        self.write_view()

    # --- 고정 데이터 조작 ---
    def replace(self, name, old, new):
        path = self.root / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def decide(self, row_id, content="", source="사용자 메시지 2026-10-01"):
        self.replace("decisions.md", f"| {row_id} | 열림 | | |", f"| {row_id} | 결정됨 | {content} | {source} |")

    def review(self):
        self.decide("REVIEW", f"intent sha256 {sha(self.root / 'intent.md')[:fg.REVIEW_HASH_LEN]}")

    def write_view(self, deps=None):
        deps = deps or {"Q1": [], "Q2": ["Q1"], "Q3": ["Q2"]}
        view = {"schema_version": 1, "kind": "intent_view", "run_id": "t", "revision": 1,
                "intent_file": "intent.md", "intent_sha256": sha(self.root / "intent.md"), "mission": "m",
                "focus": "Q1", "nodes": [{"id": q, "label": q, "outcome": "o", "depends_on": d} for q, d in deps.items()]}
        (self.root / "initial-view.json").write_text(json.dumps(view, ensure_ascii=False), encoding="utf-8")

    def write_graph(self, nodes):
        graph = {"schema_version": 1, "kind": "execution_graph", "run_id": "t", "revision": 1,
                 "intent_file": "intent.md", "intent_sha256": sha(self.root / "intent.md"),
                 "mission": "m", "focus": nodes[0]["id"], "nodes": nodes}
        (self.root / "graph.json").write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

    # --- 호출 ---
    def pre(self, tool, **tool_input):
        return fg.pre({"tool_name": tool, "tool_input": tool_input}, self.root, HELPER)

    def path(self, rel):
        return str(self.root / rel)

    def scan_codes(self):
        return [w[:4] for w in fg.scan(self.root, HELPER)]

    def assert_ask(self, result, code, contains=None):
        self.assertIsNotNone(result, f"{code} 확인 창이 나와야 합니다")
        out = result["hookSpecificOutput"]
        self.assertEqual(out.get("permissionDecision"), "ask", out)
        self.assertIn(f"[{code}]", out["permissionDecisionReason"])
        if contains:
            self.assertIn(contains, out["permissionDecisionReason"])


class ParseTest(unittest.TestCase):
    def test_intent_definitions(self):
        intent = fg.parse_intent(INTENT)
        self.assertEqual(intent["q_ids"], ["Q1", "Q2", "Q3"])
        self.assertEqual(intent["q_deps"], {"Q1": [], "Q2": ["Q1"], "Q3": ["Q2"]})
        self.assertEqual(intent["dec_blocks"]["DEC-1"], "Intent 검토")
        self.assertEqual(intent["problems"], [])

    def test_intent_format_breaks(self):
        broken = INTENT.replace("| Q2 |", "| Q1 |").replace("| DEC-2 |", "| DEC-3 |")
        problems = "\n".join(fg.parse_intent(broken)["problems"])
        self.assertIn("ID Q1 가 두 번", problems)
        self.assertIn("DEC-2", problems)

    def test_decision_format_breaks(self):
        text = DECISIONS.replace("| REVIEW | 열림 | | |\n", "").replace("| DEC-1 | 열림 |", "| DEC-1 | 보류 |")
        text = text.replace("| DEC-2 | 열림 | | |", "| DEC-2 | 결정됨 | 스테이징 A | |")
        problems = "\n".join(fg.parse_decisions(text)["problems"])
        self.assertIn("REVIEW", problems)
        self.assertIn("'보류'", problems)
        self.assertIn("[W7] decisions.md DEC-2 가 결정됨인데 근거", problems)


class ReviewTest(Workspace):
    def test_review_is_bound_to_intent_version(self):
        self.assertEqual(fg.review_state(self.root, fg.load(self.root)[1]), "DRAFT")
        self.review()
        self.assertEqual(fg.review_state(self.root, fg.load(self.root)[1]), "REVIEWED")
        self.replace("intent.md", "# 테스트 Intent", "# 테스트 Intent (수정)")
        self.assertEqual(fg.review_state(self.root, fg.load(self.root)[1]), "STALE")


@NEEDS_HELPER
class ScanTest(Workspace):
    def test_clean_state_has_no_warnings(self):
        self.assertEqual(fg.scan(self.root, HELPER), [])

    def test_intent_change_after_diagram_warns_w1(self):
        self.replace("intent.md", "| Q1 | 명세 |", "| Q1 | 명세(수정) |")
        self.assertIn("[W1]", self.scan_codes())

    def test_stale_review_warns_w1(self):
        self.review()
        self.replace("intent.md", "# 테스트 Intent", "# 테스트 Intent (수정)")
        self.write_view()
        self.assertTrue(any("검토(REVIEW) 뒤에" in w for w in fg.scan(self.root, HELPER)))

    def test_review_with_open_intent_blocker_warns_w3(self):
        self.review()
        self.assertTrue(any(w.startswith("[W3]") and "DEC-1" in w for w in fg.scan(self.root, HELPER)))

    def test_recording_a_decision_does_not_invalidate_diagram(self):
        self.decide("DEC-2", "스테이징 Place A")
        self.assertNotIn("[W1]", self.scan_codes())

    def test_graph_before_review_warns_w3(self):
        self.write_graph([exec_node("M1", [], "a.txt")])
        self.assertIn("[W3]", self.scan_codes())

    def test_graph_cycle_warns_w6(self):
        self.write_graph([exec_node("M1", ["M2"], "a.txt"), exec_node("M2", ["M1"], "b.txt")])
        self.assertIn("[W6]", self.scan_codes())

    def test_view_dependencies_must_match_intent_w5(self):
        self.write_view({"Q1": [], "Q2": ["Q1"], "Q3": ["Q1"]})
        self.assertTrue(any("선행 관계" in w for w in fg.scan(self.root, HELPER)))

    def test_undefined_and_unrecorded_decisions_warn_w5(self):
        self.replace("decisions.md", "| DEC-2 | 열림 | | |", "| DEC-9 | 열림 | | |")
        joined = "\n".join(fg.scan(self.root, HELPER))
        self.assertIn("decisions.md 에 없는 결정: DEC-2", joined)
        self.assertIn("decisions.md 에만 있는 결정: DEC-9", joined)

    def test_decision_change_by_any_means_is_announced_once_w7(self):
        fg.scan(self.root, HELPER)  # 기준 상태 기록
        self.decide("DEC-1", "후보 B")  # 셸·외부 편집과 같은 직접 변경
        first = fg.scan(self.root, HELPER)
        self.assertTrue(any(w.startswith("[W7]") and "DEC-1 열림 → 결정됨" in w for w in first))
        self.assertFalse(any(w.startswith("[W7]") for w in fg.scan(self.root, HELPER)))

    def test_regenerated_diagram_is_announced_w1(self):
        fg.scan(self.root, HELPER)
        self.replace("intent.md", "| Q1 | 명세 |", "| Q1 | 명세(수정) |")
        self.write_view()
        self.assertTrue(any("다시 만들어졌습니다" in w for w in fg.scan(self.root, HELPER)))

    def test_graph_must_follow_intent_states_w5(self):
        self.review()
        self.decide("DEC-1", "후보 B")
        self.write_graph([exec_node("M1", [], "a.txt")])
        self.assertTrue(any("작업 Graph 노드" in w for w in fg.scan(self.root, HELPER)))
        self.write_graph([exec_node("Q1", [], "a.txt"), exec_node("Q2", ["Q1"], "b.txt"), exec_node("Q3", ["Q1"], "c.txt")])
        self.assertTrue(any("작업 Graph 의 선행 관계" in w for w in fg.scan(self.root, HELPER)))
        self.write_graph([exec_node("Q1", [], "a.txt"), exec_node("Q2", ["Q1"], "b.txt"), exec_node("Q3", ["Q2"], "c.txt")])
        self.assertFalse(any("작업 Graph" in w and w.startswith("[W5]") for w in fg.scan(self.root, HELPER)))

    def test_product_output_before_graph_warns_w2(self):
        (self.root / "specs").mkdir()
        self.assertTrue(any(w.startswith("[W2]") and "specs" in w for w in fg.scan(self.root, HELPER)))

    def test_artifact_present_before_predecessor_lock_warns_w2(self):
        self.review()
        self.decide("DEC-1", "후보 B")
        self.write_graph([exec_node("M1", [], "spec.json"), exec_node("M2", ["M1"], "harness")])
        (self.root / "harness").mkdir()
        self.assertTrue(any(w.startswith("[W2]") and "M2" in w for w in fg.scan(self.root, HELPER)))

    def test_missing_files_and_helper_warn_w5(self):
        self.assertTrue(any("검증 도구" in w for w in fg.scan(self.root, self.root / "no-helper.py")))
        (self.root / "decisions.md").unlink()
        self.assertTrue(any("decisions.md 가 없습니다" in w for w in fg.scan(self.root, HELPER)))
        (self.root / "intent.md").unlink()
        self.assertTrue(fg.scan(self.root, HELPER)[0].startswith("[W5]"))


class PreTest(Workspace):
    def test_studio_write_tools_ask_until_staging_decided_w4(self):
        self.assert_ask(self.pre("mcp__Roblox_Studio__multi_edit"), "W4")
        self.assert_ask(self.pre("mcp__roblox-studio__unknown_new_tool"), "W4")
        self.assertIsNone(self.pre("mcp__Roblox_Studio__search_game_tree"))
        self.decide("DEC-2", "스테이징 Place A")
        result = self.pre("mcp__Roblox_Studio__multi_edit")
        self.assertNotIn("permissionDecision", result["hookSpecificOutput"])
        self.assertIn("get_studio_state", result["hookSpecificOutput"]["additionalContext"])

    def test_studio_through_shell_asks_w4(self):
        self.assert_ask(self.pre("Bash", command="/init cmd.exe /c %LOCALAPPDATA%\\Roblox\\mcp.bat"), "W4")
        self.assert_ask(self.pre("Bash", command="python3 mcp_probe.py list_roblox_studios"), "W4")
        self.assertIsNone(self.pre("Bash", command="ls -la"))

    def test_decision_record_changes_ask_w7(self):
        self.assert_ask(self.pre("Edit", file_path=self.path("decisions.md")), "W7")
        self.assert_ask(self.pre("Bash", command="sed -i 's/열림/결정됨/' decisions.md"), "W7")
        self.assert_ask(self.pre("Bash", command="python3 - <<EOF\nopen('decisions.md','w')\nEOF"), "W7")
        self.assert_ask(self.pre("Bash", command="echo x >> decisions.md"), "W7")
        self.assert_ask(self.pre("Bash", command="cp /tmp/new.md decisions.md"), "W7")
        self.assert_ask(self.pre("Bash", command="python3 -c \"Path('decisions.md').write_text(s)\""), "W7")
        for harmless in ("cat decisions.md", "cp intent.md decisions.md /tmp/copy/", "grep 결정됨 decisions.md | wc -l",
                         "python3 -c \"print(open('decisions.md').read())\"",
                         # 2026-10-01 실제 오탐: 문자열에 decisions.md 가 들어 있고 다른 파일을 쓰는 스크립트
                         "python3 - <<EOF\ns = s.replace('`decisions.md` 에서', 'x')\nPath('intent.md').write_text(s)\nEOF"):
            self.assertIsNone(self.pre("Bash", command=harmless), harmless)

    def test_review_and_diagram_inputs_ask(self):
        self.assert_ask(self.pre("Edit", file_path=self.path("initial-view.json")), "W1")
        self.assert_ask(self.pre("Edit", file_path=self.path("evidence.jsonl")), "W7")

    def test_graph_before_review_asks_w3_case_insensitive(self):
        self.assert_ask(self.pre("Write", file_path=self.path("graph.json")), "W3")
        self.assert_ask(self.pre("Write", file_path=self.path("Graph.JSON")), "W3")
        self.review()
        self.assertIsNone(self.pre("Write", file_path=self.path("graph.json")))

    def test_intent_edit_asks_only_after_graph_exists(self):
        self.assertIsNone(self.pre("Edit", file_path=self.path("intent.md")))
        self.write_graph([exec_node("M1", [], "a.txt")])
        self.assert_ask(self.pre("Edit", file_path=self.path("intent.md")), "W1")

    def test_product_paths_before_graph_ask_w2(self):
        self.assert_ask(self.pre("Write", file_path=self.path("specs/worlds/gate.yaml")), "W2")
        self.assert_ask(self.pre("Write", file_path=self.path("harness/checks.lua")), "W2")
        for allowed in ("docs/notes.md", "wiki/00-constitution/charter.md", "tools/x.py", "README.md"):
            self.assertIsNone(self.pre("Write", file_path=self.path(allowed)), allowed)

    def test_other_market_paths_ask_w2(self):
        self.assert_ask(self.pre("Write", file_path=self.path("specs/packs/en-US/units.json")), "W2", "en-US")
        self.assert_ask(self.pre("Write", file_path=self.path("specs/localization/ja-JP.yaml")), "W2", "ja-JP")
        self.assertIsNone(self.pre("Write", file_path=self.path("docs/knowledge/en-US-notes/en-US.md")))
        self.assertIsNone(fg.other_market("wiki/10-patterns/ui-ux/mobile-hud.md"))
        self.assertIsNone(fg.other_market("specs/packs/ko-KR/units.json"))

    def test_paths_outside_repo_ignored(self):
        self.assertIsNone(self.pre("Write", file_path="/tmp/elsewhere/graph.json"))
        self.assertIsNone(self.pre("Read", file_path=self.path("decisions.md")))


@NEEDS_HELPER
class OrderTest(Workspace):
    def setUp(self):
        super().setUp()
        self.review()
        self.write_graph([exec_node("M1", [], "spec/world.json"),
                          exec_node("M2", ["M1"], "./curriculum/"),
                          exec_node("M3", ["M2"], "harness/checks.py")])

    def test_later_stage_before_earlier_lock_asks_w2(self):
        self.assert_ask(self.pre("Write", file_path=self.path("curriculum/ko-KR/units.json")), "W2", "M1")
        self.assert_ask(self.pre("Edit", file_path=self.path("Harness/Checks.py")), "W2")

    def test_first_stage_and_unowned_files_pass(self):
        self.assertIsNone(self.pre("Write", file_path=self.path("spec/world.json")))
        self.assertIsNone(self.pre("Write", file_path=self.path("docs/notes.md")))

    def test_locked_stage_edit_asks_w2_reopen(self):
        original = fg.graph_statuses
        fg.graph_statuses = lambda helper, graph: {"M1": "LOCKED", "M2": "FOCUS", "M3": "PENDING"}
        try:
            self.assert_ask(self.pre("Edit", file_path=self.path("spec/world.json")), "W2", "M2, M3")
            self.assertIsNone(self.pre("Write", file_path=self.path("curriculum/ko-KR/units.json")))
        finally:
            fg.graph_statuses = original

    def test_unreadable_graph_asks_instead_of_passing(self):
        self.replace("intent.md", "# 테스트 Intent", "# 테스트 Intent (수정)")
        self.assert_ask(self.pre("Write", file_path=self.path("harness/checks.py")), "W2", "판정할 수 없습니다")


VECTORS = """
## 11. 6방향
| ID | 방향 | 묻는 것 | 주기(일) | 할 일 | 가드레일 |
|---|---|---|---|---|---|
| V-FWD | 전방 | 다음 방향 | 7 | a | b |
| V-LEFT | 좌 | 벤치마킹 | 30 | a | b |
"""


class VectorTest(Workspace):
    def setUp(self):
        super().setUp()
        (self.root / "intent.md").write_text(INTENT + VECTORS, encoding="utf-8")
        self.write_view()

    def record(self, vector, when, rid):
        row = {"id": rid, "kind": "vector_review", "vector": vector, "timestamp": when.isoformat(), "observed": "o"}
        with (self.root / "evidence.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    def vector_warnings(self, now):
        return fg.scan_vectors(self.root, fg.load(self.root)[0], now)

    def test_vectors_are_parsed_with_cadence(self):
        vectors = fg.parse_intent(INTENT + VECTORS)["vectors"]
        self.assertEqual(vectors["V-FWD"], {"name": "전방", "days": 7})
        self.assertEqual(vectors["V-LEFT"]["days"], 30)
        broken = fg.parse_intent(INTENT + VECTORS.replace("| 7 |", "| 매주 |"))
        self.assertTrue(any("V-FWD 의 주기" in p for p in broken["problems"]))

    def test_never_reviewed_vectors_warn_w8(self):
        warnings = self.vector_warnings(datetime.now(timezone.utc))
        self.assertTrue(warnings and warnings[0].startswith("[W8]"))
        self.assertIn("V-FWD(전방)", warnings[0])
        self.assertIn("V-LEFT(좌)", warnings[0])

    def test_overdue_only_after_cadence(self):
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        self.record("V-FWD", start, "VR1")
        self.record("V-LEFT", start, "VR2")
        (self.root / "evidence.jsonl").open("a", encoding="utf-8").write("not json\n")
        self.assertEqual(self.vector_warnings(start + timedelta(days=5)), [])
        later = self.vector_warnings(start + timedelta(days=10))
        self.assertEqual(len(later), 1)
        self.assertIn("V-FWD(전방) 10일 전", later[0])
        self.assertNotIn("V-LEFT", later[0])

    @NEEDS_HELPER
    def test_scan_includes_w8(self):
        self.assertIn("[W8]", self.scan_codes())


class OutputTest(unittest.TestCase):
    def test_scan_output_shapes(self):
        self.assertIsNone(fg.scan_output([], "Stop"))
        stop = fg.scan_output(["[W1] x"], "Stop")
        self.assertIn("구조·순서 경고 1건", stop["systemMessage"])
        self.assertNotIn("hookSpecificOutput", stop)  # Stop 에 문맥을 넣으면 대화가 저절로 이어진다
        start = fg.scan_output(["[W1] x"], "SessionStart")
        self.assertEqual(start["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def run_main(self, argv, broken_name):
        buffer, original = io.StringIO(), getattr(fg, broken_name)
        setattr(fg, broken_name, lambda *a, **k: 1 / 0)
        stdin = sys.stdin
        sys.stdin = io.StringIO('{"tool_name": "Write", "tool_input": {}}')
        try:
            with redirect_stdout(buffer):
                code = fg.main(argv)
        finally:
            setattr(fg, broken_name, original)
            sys.stdin = stdin
        self.assertEqual(code, 0)
        return json.loads(buffer.getvalue())

    def test_pre_failure_asks_instead_of_passing(self):
        out = self.run_main(["flow_guard.py", "pre"], "pre")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertIn("[W5]", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_scan_failure_is_loud(self):
        out = self.run_main(["flow_guard.py", "scan", "--event", "Stop"], "scan")
        self.assertIn("장치 자체가 실패", out["systemMessage"])


class RepoConsistencyTest(unittest.TestCase):
    """저장소의 실제 intent.md·decisions.md·initial-view.json 이 서로 맞는지 (상태 기록은 건드리지 않는다)."""

    def test_live_files_are_consistent(self):
        intent, decisions = fg.load(REPO)
        self.assertIsNotNone(intent, "intent.md 없음")
        self.assertEqual(intent["problems"], [])
        self.assertEqual(fg.scan_decisions(REPO, intent, decisions), [])
        self.assertEqual(fg.check_view_shape(REPO / "initial-view.json", intent), [])
        self.assertEqual(sorted(intent["vectors"]), ["V-BWD", "V-DOWN", "V-FWD", "V-LEFT", "V-RIGHT", "V-UP"])

    def test_live_graph_follows_intent(self):
        intent, _ = fg.load(REPO)
        if (REPO / "graph.json").is_file():
            self.assertEqual(fg.check_view_shape(REPO / "graph.json", intent, "작업 Graph"), [])

    @NEEDS_HELPER
    def test_live_diagram_matches_intent(self):
        self.assertEqual(fg.check_doc(HELPER, REPO / "initial-view.json", "Diagram", "W5"), [])


if __name__ == "__main__":
    unittest.main()
