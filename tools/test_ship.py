"""자동 저장·병합 장치 시험 (tools/ship.py) — git·gh 를 부르지 않는 판단만 본다."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ship  # noqa: E402


class CandidateTest(unittest.TestCase):
    def test_tracked_changes_and_new_code_only(self):
        status = "\0".join([" M graph.json", "?? harness/checks/new.py", "?? docs/blank - 복사본 (3).md",
                            "?? outputs/harness/clean/x.txt", " M docs/02-start-here.md", "?? world/src/server/New.luau", ""])
        self.assertEqual(ship.candidates(status),
                         ["docs/02-start-here.md", "graph.json", "harness/checks/new.py", "world/src/server/New.luau"])

    def test_rename_keeps_the_new_name(self):
        status = "\0".join(["R  tools/new_name.py", "tools/old_name.py", ""])
        self.assertEqual(ship.candidates(status), ["tools/new_name.py"])


class LeakTest(unittest.TestCase):
    PRIVATE = ["/home/someone", "/mnt/d/work/rb", "someone@example.org"]

    def test_private_paths_and_mail_are_refused(self):
        real = "person" + "@" + "mail-host.kr"   # 진짜 꼴 주소도 실행 중에 조립한다 — 시험 파일이 검사에 걸리지 않게
        diff = "+path = '/mnt/d/work/rb/tools'\n+contact someone@example.org\n+real " + real + "\n"
        found = ship.leaks(diff, self.PRIVATE)
        self.assertEqual(len(found), 3, found)   # 저장소 경로 · 이 기계 계정 · 진짜 꼴 주소 (예시 도메인 꼴은 세지 않는다)

    def test_secret_shapes_are_refused(self):
        # 비밀값 꼴은 실행 중에 조립한다 — 시험 파일 자체가 비밀값 검사에 걸리지 않게
        self.assertTrue(ship.leaks("+" + "api" + "_key = 'abcdef123456'\n", []))
        self.assertTrue(ship.leaks("+" + "AKIA" + "ABCDEFGHIJKLMNOP" + "\n", []))

    def test_ordinary_lines_pass(self):
        diff = "+Co-Authored-By: Claude <noreply@anthropic.com>\n+cmd = '/mnt/c/Windows/System32/cmd.exe'\n-removed /home/someone\n"
        self.assertEqual(ship.leaks(diff, self.PRIVATE), [])


class PlanTest(unittest.TestCase):
    def pr(self, head, state="CLEAN", number=1):
        return {"number": number, "headRefName": head, "baseRefName": "main", "mergeStateStatus": state, "title": ""}

    def test_merges_only_when_every_carried_stage_is_locked(self):
        steps = ship.plan([self.pr("feat/q1-intent-spec"), self.pr("feat/q2-world-graph", number=2)],
                          {"Q1": True, "Q2": True, "Q3": False, "Q4": False})
        self.assertEqual([action for _pr, action, _r in steps], ["병합", "대기"])
        self.assertIn("Q3, Q4", steps[1][2])

    def test_waits_on_conflicts_and_unknown_branches(self):
        steps = ship.plan([self.pr("feat/q1-intent-spec", state="DIRTY"), self.pr("feat/unknown")], {"Q1": True})
        self.assertEqual([action for _pr, action, _r in steps], ["대기", "대기"])


if __name__ == "__main__":
    unittest.main()
