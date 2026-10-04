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

    def ready(self):
        """리뷰를 받을 수 있는 상태 — 지금 버전의 자동 검사가 모두 PASS."""
        self.add_vectors("V-FWD", "V-LEFT")
        self.assertEqual(verify.cmd_run(self.root, "Q1"), 0)

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
        self.ready()
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
        self.ready()
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

    def test_copied_vector_reviews_do_not_count(self):
        """다른 버전의 6방향 기록을 글자 그대로 다시 찍으면 세지 않는다 — 검토가 아니라 복사다 (AUDIT-PROCESS-1)."""
        self.add_vectors("V-FWD", "V-LEFT")
        (self.root / "a.txt").write_text("artifact v2", encoding="utf-8")
        self.add_vectors("V-FWD", "V-LEFT")   # 같은 관찰·제안을 새 binding 에 다시 찍음
        ok, summary = verify.check_vectors(self.root, "Q1", self.gate()["binding"])
        self.assertFalse(ok)
        self.assertIn("글자 그대로 같음", summary)
        for v in ("V-FWD", "V-LEFT"):
            verify.append(self.root, {"id": f"VR-new-{v}", "kind": "vector_review", "vector": v, "stage": "Q1", "observed": "지금 상태",
                                      "proposal": "새 제안", "next": "n", "sources": ["s"], "binding": self.gate()["binding"]})
        self.assertTrue(verify.check_vectors(self.root, "Q1", self.gate()["binding"])[0])

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

    def test_review_refused_unless_current_checks_pass(self):
        """자동 검사가 없거나 실패한 상태로는 리뷰를 보내지 않는다 (AUDIT-PROCESS-1 · 22차 사고)."""
        self.fake_reviewer("NO_FINDINGS")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 2)
        self.write_graph(FAIL_CMD)
        self.add_vectors("V-FWD", "V-LEFT")
        verify.cmd_run(self.root, "Q1")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 2)
        self.assertEqual(self.rows("devil_review"), [])

    def test_minor_of_a_blocking_review_is_not_deferred(self):
        """사소 지적은 CLEAR 리뷰에서만 넘긴다(D-MINOR-LIMIT) — BLOCK 리뷰의 것은 그대로 고칠 거리다."""
        self.ready()
        self.fake_reviewer("major | a.txt:1 | 큰 것 | e | m\nminor | a.txt:2 | 작은 것 | e | m")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 1)
        self.assertEqual(self.rows("deferral"), [])

    def test_stop_rule_refuses_review_until_a_human_decision(self):
        """intent §8 — 막는 지적 수가 두 번 연속 줄지 않으면 리뷰를 더 보내지 않고 멈춤을 기록한다."""
        self.ready()
        for claim in ("하나", "둘", "셋"):
            self.fake_reviewer(f"major | a.txt:1 | {claim} | e | m")
            self.assertEqual(verify.cmd_review(self.root, "Q1"), 1)
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 2)
        self.assertTrue(any(r["id"].startswith("STOP-Q1-auto-") for r in self.rows("observation")))
        self.assertEqual(len(self.rows("devil_review")), 3)
        verify.append(self.root, {"id": "D-T", "kind": "human_decision", "node_id": "Q1", "value": "범위를 고정한다"})
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 1)

    def test_improving_rounds_keep_going(self):
        self.ready()
        for text in ("major | a:1 | a | e | m\nmajor | a:2 | b | e | m\nmajor | a:3 | c | e | m",
                     "major | a:1 | a | e | m\nmajor | a:2 | b | e | m", "major | a:1 | a | e | m"):
            self.fake_reviewer(text)
            self.assertEqual(verify.cmd_review(self.root, "Q1"), 1)
        self.fake_reviewer("NO_FINDINGS")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 0)

    def test_fixed_scope_residual_is_recorded_but_does_not_block(self):
        """고정 범위(사람 결정)에서는 새 계열을 residual 로 따로 받고, 잠금 판정을 막지 않는다."""
        graph = json.loads((self.root / "graph.json").read_text(encoding="utf-8"))
        graph["nodes"][0].update(review_policy={"scope": "fixed", "decision": "T-FIXED"}, review_question="정직한 실수를 잡는가?")
        (self.root / "graph.json").write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        verify.append(self.root, {"id": "D-T-FIXED", "kind": "human_decision", "node_id": "Q1", "decision_id": "T-FIXED", "value": "고정"})
        self.ready()
        binding = self.gate()["binding"]
        graph = verify.load_graph(self.root)
        packet = verify.review_packet(self.root, graph, verify.node_of(graph, "Q1"), binding)
        for part in ("REVIEW QUESTION: 정직한 실수를 잡는가?", "T-FIXED: 고정", "severity = critical|major|minor|residual", "고정 범위 확인 리뷰"):
            self.assertIn(part, packet)
        self.assertNotIn("우회 가능한 검사", packet)
        self.fake_reviewer("residual | a.txt:3 | 새 계열 | 정직한 코드 예 | m")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 0)
        review = self.rows("devil_review")[-1]
        self.assertEqual((review["verdict"], review["blockers"], len(review["residual"])), ("CLEAR", [], 1))
        verify.cmd_approve(self.root, "Q1", "사용자 메시지 테스트 '잠금 승인'", None)
        self.assertEqual(self.gate()["verdict"], "PASS")

    def test_review_budget_refuses_after_the_cap(self):
        """intent §8 리뷰 상한 — 줄고 있어도 마지막 사람 결정 뒤 5회를 넘으면 멈춘다."""
        self.ready()
        for n in (5, 4, 3, 2, 1):
            self.fake_reviewer("\n".join(f"major | a:{k} | 지적 {k} | e | m" for k in range(n)))
            self.assertEqual(verify.cmd_review(self.root, "Q1"), 1)
        self.fake_reviewer("NO_FINDINGS")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 2)
        self.assertTrue(any("상한" in r.get("observed", "") for r in self.rows("observation")))

    def test_lock_approval_or_applying_decision_opens_a_new_window(self):
        """잠금 승인이나 그 단계에 적용되는 사람 결정(applies_to) 뒤에는 리뷰 창을 새로 센다."""
        self.ready()
        for n in (5, 4, 3, 2, 1):
            self.fake_reviewer("\n".join(f"major | a:{k} | 지적 {k} | e | m" for k in range(n)))
            verify.cmd_review(self.root, "Q1")
        self.fake_reviewer("NO_FINDINGS")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 2)   # 상한
        verify.append(self.root, {"id": "D-P", "kind": "human_decision", "node_id": "process", "applies_to": ["Q1"], "value": "정비"})
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 0)
        verify.cmd_approve(self.root, "Q1", "사용자 메시지 테스트 '잠금 승인'", None)
        self.assertIsNone(verify.review_refusal(self.root, verify.node_of(verify.load_graph(self.root), "Q1"), self.gate()["binding"]))

    def test_vectors_are_not_required_before_review(self):
        """6방향은 잠금 조건이다 — 리뷰 전에는 다른 자동 검사만 PASS 이면 된다."""
        self.assertEqual(verify.cmd_run(self.root, "Q1"), 1)   # Q1-C1 PASS, Q1-6V FAIL
        self.fake_reviewer("NO_FINDINGS")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 0)

    def test_residual_outside_a_fixed_scope_blocks(self):
        self.ready()
        self.fake_reviewer("residual | a.txt:3 | 고정 범위가 아닌데 residual | e | m")
        self.assertEqual(verify.cmd_review(self.root, "Q1"), 1)
        self.assertEqual(self.rows("devil_review")[-1]["verdict"], "BLOCK")

    def test_observe_records_manual_criteria_only(self):
        """수동 기준은 observe 로 기록하고 게이트가 센다 — 자동 검사 기준·빈 관찰은 받지 않는다."""
        graph = json.loads((self.root / "graph.json").read_text(encoding="utf-8"))
        graph["nodes"][0]["criteria"].insert(1, {"id": "Q1-C2", "statement": "Play 관찰", "method": "m", "target": "t",
                                                 "evidence_types": ["observation"], "benchmark_required": False, "benchmark_ids": []})
        (self.root / "graph.json").write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        self.add_vectors("V-FWD", "V-LEFT")
        verify.cmd_run(self.root, "Q1")
        self.assertTrue(any("Q1-C2" in m for m in self.gate()["missing"]))
        with self.assertRaises(SystemExit):
            verify.cmd_observe(self.root, "Q1", "Q1-C1", "PASS", "봤다", "누가")   # 자동 검사 기준
        with self.assertRaises(SystemExit):
            verify.cmd_observe(self.root, "Q1", "Q1-C2", "PASS", " ", "누가")
        self.assertEqual(verify.cmd_observe(self.root, "Q1", "Q1-C2", "PASS", "게이트가 열림", "AI 가 Studio Play 에서 2026-10-04"), 0)
        record = [r for r in self.rows("verification") if r["criterion_id"] == "Q1-C2"][-1]
        self.assertEqual((record["result"], record["evidence_type"]), ("PASS", "observation"))
        self.assertFalse(any("Q1-C2" in m for m in self.gate()["missing"]))

    def test_approve_rejects_unknown_hold_and_empty_source(self):
        with self.assertRaises(SystemExit):
            verify.cmd_approve(self.root, "Q1", "말", "DEC-99")
        with self.assertRaises(SystemExit):
            verify.cmd_approve(self.root, "Q1", "  ", None)


class ParseTest(unittest.TestCase):
    def test_recorded_output_has_no_local_paths(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        code, output = verify.run_command(root, [sys.executable, "-c", "import os, pathlib; print(os.getcwd(), pathlib.Path.home())"])
        self.assertEqual(code, 0)
        self.assertNotIn(str(root), output)
        self.assertNotIn(str(Path.home()), output)
        code, output = verify.run_command(root / "missing", ["true"])  # 실행 실패 메시지에도 경로가 남지 않는다
        self.assertEqual(code, 99)
        self.assertNotIn(str(root), output)

    def test_parse_review_lines(self):
        verdict, blockers, residual = verify.parse_review("- **minor** | spec.yaml:3 | 오타 | x | y\nNO_FINDINGS")
        self.assertEqual((verdict, blockers[0]["severity"], blockers[0]["location"], residual), ("CLEAR", "minor", "spec.yaml:3", []))
        verdict, blockers, residual = verify.parse_review("residual | f:2 | 새 계열 | e | m", fixed_scope=True)
        self.assertEqual((verdict, blockers, residual[0]["claim"]), ("CLEAR", [], "새 계열"))
        verdict, blockers, residual = verify.parse_review("residual | f:2 | 새 계열 | e | m")   # 고정 범위가 아니면 막는 지적
        self.assertEqual((verdict, blockers[0]["severity"], residual), ("BLOCK", "major", []))
        self.assertEqual(verify.parse_review("critical | f:1 | c | e | m")[0], "BLOCK")
        self.assertEqual(verify.parse_review("모르겠음")[0], "UNPARSED")

    def test_guard_asks_before_human_approval_record(self):
        result = fg.pre_bash('python3 tools/verify.py approve Q1 --source "x"', None)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertIn("[W7]", result["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIsNone(fg.pre_bash("python3 tools/verify.py gate Q1", None))


if __name__ == "__main__":
    unittest.main()
