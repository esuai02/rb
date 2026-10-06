"""자동 저장·병합 장치 시험 (tools/ship.py) — git·gh 를 부르지 않는 판단만 본다."""
import sys
import tempfile
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

    def test_studio_copies_are_picked_up(self):
        self.assertEqual(ship.candidates("?? place/Workspace/Baseplate.rbxmx\0"), ["place/Workspace/Baseplate.rbxmx"])


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

    def test_more_secret_shapes_are_refused(self):
        """토큰·인증 머리·개인 키 꼴 (리뷰 SHIP 2차). 꼴은 실행 중에 조립한다."""
        for shape in ("gh" + "p_" + "a" * 36, "Bear" + "er " + "b" * 24, "-----BEGIN " + "RSA PRIVATE KEY-----",
                      "tok" + "en=" + "c" * 20, "xo" + "xb-" + "1234567890ab", "s" + "k-" + "d" * 24):
            with self.subTest(shape=shape[:12]):
                self.assertTrue(ship.leaks("+" + shape + "\n", []))

    def test_underscored_token_names_are_refused(self):
        self.assertTrue(ship.leaks("+ACCESS_" + "TOKEN=" + "e" * 20 + "\n", []))

    def test_message_lines_starting_with_a_dash_are_scanned(self):
        self.assertTrue(ship.leaks(ship.as_added("- /home/private/" + "notes.txt"), ["/home/private"]))

    def test_code_words_are_not_secrets(self):
        self.assertEqual(ship.leaks("+token = tokens[j]\n+local tokens = luau.tokenize(src)\n", []), [])

    def test_windows_form_of_the_repo_path_is_refused(self):
        """WSL 저장소 경로의 Windows 꼴(D:\\…, JSON 안 D:\\\\…)도 같은 로컬 경로다 (2026-10-06 문서·근거 기록으로 새어 나감)."""
        sep = "\\"
        forms = ship.windows_forms("/mnt/d/work/rb")
        self.assertIn("D:" + sep + "work" + sep + "rb", forms)
        self.assertIn("D:" + sep * 2 + "work" + sep * 2 + "rb", forms)
        for form in forms:
            with self.subTest(form=form):
                self.assertTrue(ship.leaks("+serve in " + form + sep + "world\n", forms))
        self.assertEqual(ship.windows_forms("/home/someone"), [])

    def test_windows_user_folders_are_refused(self):
        """Windows 사용자 폴더 경로는 계정 이름을 드러낸다. 꼴은 실행 중에 조립한다 — 시험 파일이 검사에 걸리지 않게."""
        sep = "\\"
        for shape in ("C:" + sep + "Users" + sep + "someone" + sep + "AppData",
                      "C:" + sep * 2 + "Users" + sep * 2 + "someone",
                      "/mnt/c/" + "Users/someone/AppData"):
            with self.subTest(shape=shape):
                self.assertTrue(ship.leaks("+" + shape + "\n", []))

    def test_private_values_match_in_any_case(self):
        self.assertTrue(ship.leaks("+path = '/MNT/D/WORK/RB/tools'\n", self.PRIVATE))

    def test_other_separator_and_unc_forms_are_refused(self):
        """빗금 꼴(D:/…)·섞인 구분자·WSL UNC 꼴(\\\\wsl$\\…)도 같은 경로다 (리뷰 SHIP 3차). 꼴은 실행 중에 조립한다."""
        sep = "\\"
        private = ship.windows_forms("/mnt/d/work/rb") + ["/mnt/d/work/rb", "/home/someone"]
        for shape in ("D:/work/rb/x", "d:" + sep + "work/rb", sep * 2 + "wsl$" + sep + "Ubuntu" + sep + "mnt" + sep + "d" + sep + "work" + sep + "rb",
                      sep * 2 + "wsl.localhost" + sep + "Ubuntu" + sep + "home" + sep + "someone" + sep + "notes"):
            with self.subTest(shape=shape):
                self.assertTrue(ship.leaks("+" + shape + "\n", private))

    def test_user_folders_with_forward_slashes_are_refused_but_shared_ones_pass(self):
        sep = "\\"
        self.assertTrue(ship.leaks("+C:/" + "Users/someone/AppData\n", []))
        for shared in ("C:" + sep + "Users" + sep + "Public" + sep + "Documents", "/mnt/c/" + "Users/Default/x",
                       "C:/" + "Users/All Users/x"):
            with self.subTest(shared=shared):
                self.assertEqual(ship.leaks("+" + shared + "\n", []), [])

    def test_local_private_values_are_read_from_outside_the_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rb-private"
            path.write_text("\ufeffsomeone\n\n 1234567890 \n", encoding="utf-8")   # 메모장 BOM 은 값이 아니다
            self.assertEqual(ship.local_private(path), ["someone", "1234567890"])
            self.assertEqual(ship.local_private(Path(tmp) / "missing"), [])

    def test_content_lines_that_look_like_headers_or_hold_line_separators_are_scanned(self):
        """'++' 로 시작하는 내용 줄 · U+2028 뒤의 글자 · 몇 겹의 역슬래시 꼴도 검사받는다 (리뷰 STUDIO-PULL 1차)."""
        sep = "\\"
        self.assertTrue(ship.leaks(ship.as_added("++ built by someone"), ["someone"]))
        self.assertTrue(ship.leaks("+note\u2028 /home/someone/x\n", ["/home/someone"]))
        self.assertEqual(ship.leaks("+++ b/notes/someone.md\n", ["someone"]), [])   # 진짜 파일 머리 줄은 건너뛴다
        for shape in ("C:" + sep * 4 + "Users" + sep * 4 + "someone", "C:" + sep + "/Users" + sep + "/someone",
                      sep + "/mnt" + sep + "/c" + sep + "/Users" + sep + "/someone"):
            with self.subTest(shape=shape):
                self.assertTrue(ship.leaks("+" + shape + "\n", []))

    def test_ordinary_lines_pass(self):
        diff = "+Co-Authored-By: Claude <noreply@anthropic.com>\n+cmd = '/mnt/c/Windows/System32/cmd.exe'\n-removed /home/someone\n"
        self.assertEqual(ship.leaks(diff, self.PRIVATE), [])


class PlanTest(unittest.TestCase):
    def pr(self, head, state="CLEAN", number=1, fork=False):
        return {"number": number, "headRefName": head, "baseRefName": "main", "mergeStateStatus": state,
                "title": "", "headRefOid": "a" * 40, "isCrossRepository": fork}

    def test_merges_only_when_locked_at_the_head_commit(self):
        steps = ship.plan([self.pr("feat/q1-intent-spec"), self.pr("feat/q2-world-graph", number=2)],
                          {1: (True, "잠김"), 2: (False, "머리 커밋에서 Q3 가 잠기지 않았다")})
        self.assertEqual([action for _pr, action, _r in steps], ["병합", "대기"])
        self.assertIn("Q3", steps[1][2])

    def test_waits_on_forks_conflicts_unknown_branches_and_missing_verdicts(self):
        steps = ship.plan([self.pr("feat/q1-intent-spec", fork=True, number=1),
                           self.pr("feat/q1-intent-spec", state="DIRTY", number=2),
                           self.pr("feat/unknown", number=3),
                           self.pr("feat/q1-intent-spec", number=4)],
                          {1: (True, ""), 2: (True, ""), 4: (True, "")} | {})
        self.assertEqual([action for _pr, action, _r in steps], ["대기", "대기", "대기", "병합"])
        self.assertEqual(ship.plan([self.pr("feat/q1-intent-spec")], {})[0][1], "대기")   # 잠금을 확인하지 못하면 기다린다


class MessageLeakTest(unittest.TestCase):
    def test_commit_messages_get_the_same_scan(self):
        self.assertTrue(ship.leaks(ship.as_added("feat: 무엇\n\n경로 /mnt/d/work/rb/x"), ["/mnt/d/work/rb"]))
        self.assertEqual(ship.leaks(ship.as_added("Co-Authored-By: Claude <noreply@anthropic.com>"), []), [])

    def test_only_the_exact_attribution_address_is_allowed(self):
        other = "someone" + "@" + "anthropic.com"
        self.assertTrue(ship.leaks("+" + other + "\n", []))


if __name__ == "__main__":
    unittest.main()
