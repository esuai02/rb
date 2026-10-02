"""verify.py 회귀 테스트 — 3층 게이트(자동 검사 → 독립 리뷰 → 사람 승인 → 잠금)를 임시 작업공간에서 끝까지 돌린다."""
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_guard as fg  # noqa: E402
import verify  # noqa: E402

NEEDS_HELPER = unittest.skipUnless(fg.DEFAULT_HELPER.is_file(), "masterwork 헬퍼 없음")

INTENT = """# 테스트 Intent
| ID | 상태 | 증거 | 선행 |
|---|---|---|---|
| Q1 | 명세 | e | — |

| ID | 결정 | 막는 범위 | 메모 |
|---|---|---|---|
| DEC-2 | 스테이징 | Studio | |

| ID | 방향 | 묻는 것 | 주기(일) | 할 일 | 가드레일 |
|---|---|---|---|---|---|
| V-FWD | 전방 | a | 7 | b | c |
| V-LEFT | 좌 | a | 30 | b | c |
"""
PASS_CMD = [sys.executable, "-c", "print('Ran 1 test'); print('OK')"]
FAIL_CMD = [sys.executable, "-c", "import sys; print('FAILED'); sys.exit(1)"]


def graph_for(root, first_check):
    criteria = [
        {"id": "Q1-C1", "statement": "s", "method": "m", "target": "t", "evidence_types": ["test"],
         "benchmark_required": False, "benchmark_ids": [], "check": {"type": "command", "argv": first_check}},
        {"id": "Q1-6V", "statement": "6방향", "method": "m", "target": "t", "evidence_types": ["observation"],
         "benchmark_required": False, "benchmark_ids": [], "check": {"type": "vectors"}},
    ]
    node = {"id": "Q1", "label": "명세", "outcome": "o", "depends_on": [], "artifacts": ["a.txt"], "maker": verify.MAKER,
            "review": "independent", "human_holds": ["LOCK-Q1"], "minor_limit": 0, "criteria": criteria}
    return {"schema_version": 1, "kind": "execution_graph", "run_id": "t", "revision": 1, "intent_file": "intent.md",
            "intent_sha256": hashlib.sha256((root / "intent.md").read_bytes()).hexdigest(), "mission": "m",
            "focus": "Q1", "nodes": [node]}


@NEEDS_HELPER
class GateFlowTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "intent.md").write_text(INTENT, encoding="utf-8")
        (self.root / "a.txt").write_text("artifact v1", encoding="utf-8")
        (self.root / "evidence.jsonl").write_text("", encoding="utf-8")
        self.write_graph(PASS_CMD)
        self.original_reviewer = verify.run_reviewer
        self.addCleanup(setattr, verify, "run_reviewer", self.original_reviewer)

    def write_graph(self, check):
        (self.root / "graph.json").write_text(json.dumps(graph_for(self.root, check), ensure_ascii=False), encoding="utf-8")

    def rows(self, kind):
        return [r for r in verify.ledger(self.root) if r["kind"] == kind]

    def add_vectors(self, *vectors):
        for v in vectors:
            verify.append(self.root, {"id": f"VR-{v}", "kind": "vector_review", "vector": v, "stage": "Q1", "observed": "o",
                                      "proposal": "p", "next": "n", "sources": ["s"], "binding": self.gate()["binding"]})

    def fake_reviewer(self, text, tool="codex"):
        def reviewer(root, packet, out):
            out.write_text(text, encoding="utf-8")
            return True, tool, "OK"
        verify.run_reviewer = reviewer

    def gate(self):
        return verify.helper_gate(self.root, "Q1")

    def test_run_records_pass_and_fail_with_intact_records(self):
        self.assertEqual(verify.cmd_run(self.root, "Q1"), 1)  # 6방향 기록이 없어 FAIL 포함
        by_id = {r["criterion_id"]: r for r in self.rows("verification")}
        self.assertEqual(by_id["Q1-C1"]["result"], "PASS")
        self.assertEqual(by_id["Q1-6V"]["result"], "FAIL")
        record = self.root / by_id["Q1-C1"]["record"]
        self.assertEqual(hashlib.sha256(record.read_bytes()).hexdigest(), by_id["Q1-C1"]["record_sha256"])
        self.write_graph(FAIL_CMD)
        verify.cmd_run(self.root, "Q1")
        latest = [r for r in self.rows("verification") if r["criterion_id"] == "Q1-C1"][-1]
        self.assertEqual(latest["result"], "FAIL")

    def test_review_verdicts(self):
        self.fake_reviewer("NO_FINDINGS")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 0)
        review = self.rows("devil_review")[-1]
        self.assertEqual((review["verdict"], review["independence"], review["blockers"]), ("CLEAR", "external", []))
        self.fake_reviewer("minor | a.txt:2 | 사소한 것 | 근거 | 고칠 것")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 0)
        deferral = self.rows("deferral")[-1]
        self.assertEqual((deferral["node_id"], deferral["to"], deferral["claim"]), ("Q1", "후속 개정", "사소한 것"))
        self.fake_reviewer("major | a.txt:1 | 기준이 거짓이다 | 근거 | 고칠 것")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 1)
        self.assertEqual(self.rows("devil_review")[-1]["verdict"], "BLOCK")
        self.fake_reviewer("리뷰어가 형식을 지키지 않음")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 2)

    def test_packet_shows_only_the_latest_result_per_criterion(self):
        verify.cmd_run(self.root, "Q1")  # Q1-C1 PASS, Q1-6V FAIL
        binding = self.gate()["binding"]
        verify.append(self.root, {"id": "V-stale", "kind": "verification", "node_id": "Q1", "binding": binding,
                                  "criterion_id": "Q1-C1", "result": "FAIL", "observed": "일시적 오류"})
        verify.cmd_run(self.root, "Q1")  # 같은 binding 을 다시 검사
        graph = verify.load_graph(self.root)
        packet = verify.review_packet(self.root, graph, verify.node_of(graph, "Q1"), binding)
        section = packet.split("EVIDENCE:", 1)[1].split("STAGE SCOPE:", 1)[0]
        lines = [l for l in section.splitlines() if l.startswith("- Q1-C1:")]
        self.assertEqual(lines, ["- Q1-C1: PASS — exit 0; OK"])
        self.assertNotIn("일시적 오류", packet)

    def test_claude_fallback_is_fresh_context_not_external(self):
        self.fake_reviewer("NO_FINDINGS", tool="claude")
        verify.cmd_review(self.root, "Q1")
        self.assertEqual(self.rows("devil_review")[-1]["independence"], "fresh_context")

    def test_full_three_layer_gate_then_reopen_on_change(self):
        self.add_vectors("V-FWD", "V-LEFT")
        self.assertEqual(verify.cmd_run(self.root, "Q1"), 0)
        self.fake_reviewer("NO_FINDINGS")
        verify.cmd_review(self.root, "Q1")
        before = self.gate()
        self.assertEqual(before["verdict"], "ESCALATE")
        self.assertTrue(any("LOCK-Q1" in m for m in before["missing"]))  # ③ 사람 승인 전에는 잠기지 않는다
        verify.cmd_approve(self.root, "Q1", "사용자 메시지 테스트 '잠금 승인'", None)
        self.assertEqual(self.gate()["verdict"], "PASS")
        locked = verify.helper_gate(self.root, "Q1", lock=True)
        self.assertTrue(locked["locked"])
        (self.root / "a.txt").write_text("artifact v2", encoding="utf-8")  # 산출물이 바뀌면 이전 기록은 무효
        after = self.gate()
        self.assertNotEqual(after["verdict"], "PASS")
        self.assertTrue(any("no verification for this artifact" in m for m in after["missing"]))

    def test_dependent_stage_needs_prerequisite_locked_at_current_version(self):
        # Q2 검사기가 쓰는 Q1 명세 값(q1_paths)이 잠긴 판인지는 게이트가 보장한다 — Q1 산출물이 바뀌면 Q2 게이트가 막힌다
        self.add_vectors("V-FWD", "V-LEFT")
        verify.cmd_run(self.root, "Q1")
        self.fake_reviewer("NO_FINDINGS")
        verify.cmd_review(self.root, "Q1")
        verify.cmd_approve(self.root, "Q1", "사용자 메시지 테스트 '잠금 승인'", None)
        self.assertTrue(verify.helper_gate(self.root, "Q1", lock=True)["locked"])
        graph = json.loads((self.root / "graph.json").read_text(encoding="utf-8"))
        q2 = json.loads(json.dumps(graph["nodes"][0]).replace("Q1", "Q2"))
        q2.update(depends_on=["Q1"], artifacts=["b.txt"])
        graph["nodes"].append(q2)
        (self.root / "b.txt").write_text("stage 2", encoding="utf-8")
        (self.root / "graph.json").write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        blocked = "Dependency Q1 is not currently locked"
        self.assertNotIn(blocked, verify.helper_gate(self.root, "Q2")["missing"])
        (self.root / "a.txt").write_text("artifact v2", encoding="utf-8")
        self.assertIn(blocked, verify.helper_gate(self.root, "Q2")["missing"])

    def test_empty_vector_reviews_do_not_count(self):
        for v in ("V-FWD", "V-LEFT"):
            verify.append(self.root, {"id": f"VR-empty-{v}", "kind": "vector_review", "vector": v, "stage": "Q1"})
        ok, summary = verify.check_vectors(self.root, "Q1", self.gate()["binding"])
        self.assertFalse(ok)
        self.assertIn("세지 않은 기록", summary)

    def test_vector_reviews_need_valid_past_timestamp(self):
        binding = self.gate()["binding"]
        base = {"kind": "vector_review", "stage": "Q1", "observed": "o", "proposal": "p", "next": "n", "sources": ["s"], "binding": binding}
        with (self.root / "evidence.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({**base, "id": "bad-time", "vector": "V-FWD", "timestamp": "어제"}) + "\n")
            f.write(json.dumps({**base, "id": "future", "vector": "V-LEFT", "timestamp": "2999-01-01T00:00:00+00:00"}) + "\n")
        ok, summary = verify.check_vectors(self.root, "Q1", binding)
        self.assertFalse(ok)
        self.assertIn("bad-time", summary)
        self.assertIn("future", summary)

    def test_vector_reviews_of_an_older_version_do_not_count(self):
        self.add_vectors("V-FWD", "V-LEFT")
        self.assertTrue(verify.check_vectors(self.root, "Q1", self.gate()["binding"])[0])
        (self.root / "a.txt").write_text("artifact v2", encoding="utf-8")
        self.assertFalse(verify.check_vectors(self.root, "Q1", self.gate()["binding"])[0])

    def test_lock_refuses_evidence_recorded_after_approval(self):
        self.add_vectors("V-FWD", "V-LEFT")
        verify.cmd_run(self.root, "Q1")
        self.fake_reviewer("NO_FINDINGS")
        verify.cmd_review(self.root, "Q1")
        verify.cmd_approve(self.root, "Q1", "사용자 메시지 테스트 '잠금 승인'", None)
        self.assertEqual(verify.evidence_after_approval(self.root, "Q1"), [])
        verify.cmd_run(self.root, "Q1")  # 승인 뒤에 다시 돌린 검증 — 사람이 보지 못한 기록
        self.assertNotEqual(verify.evidence_after_approval(self.root, "Q1"), [])
        self.add_vectors("V-FWD")  # 승인 뒤 6방향 기록은 세지 않는다
        late = [r for r in verify.ledger(self.root) if r["id"].startswith("VR-V-FWD-")]
        self.assertTrue(late)

    def test_approve_rejects_unknown_hold_and_empty_source(self):
        with self.assertRaises(SystemExit):
            verify.cmd_approve(self.root, "Q1", "말", "DEC-99")
        with self.assertRaises(SystemExit):
            verify.cmd_approve(self.root, "Q1", "  ", None)


class ParseTest(unittest.TestCase):
    def test_parse_review_lines(self):
        verdict, blockers = verify.parse_review("- **minor** | spec.yaml:3 | 오타 | x | y\nNO_FINDINGS")
        self.assertEqual((verdict, blockers[0]["severity"], blockers[0]["location"]), ("CLEAR", "minor", "spec.yaml:3"))
        self.assertEqual(verify.parse_review("critical | f:1 | c | e | m")[0], "BLOCK")
        self.assertEqual(verify.parse_review("모르겠음")[0], "UNPARSED")

    def test_guard_asks_before_human_approval_record(self):
        result = fg.pre_bash('python3 tools/verify.py approve Q1 --source "x"', None)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertIn("[W7]", result["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIsNone(fg.pre_bash("python3 tools/verify.py gate Q1", None))


if __name__ == "__main__":
    unittest.main()
