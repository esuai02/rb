"""Studio 사본 장치 시험 (tools/studio_pull.py) — Studio 에 붙지 않는 판단만 본다."""
import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studio_pull as pull  # noqa: E402


class RojoRootsTest(unittest.TestCase):
    def test_paths_the_repo_owns(self):
        project = json.loads((pull.REPO / "world" / "default.project.json").read_text(encoding="utf-8"))
        self.assertEqual(pull.rojo_roots(project),
                         ["ReplicatedStorage/Shared", "ServerScriptService/Gate", "StarterPlayer/StarterPlayerScripts/Gate"])

    def test_folders_holding_a_rojo_root_are_skipped_whole(self):
        roots = pull.rojo_roots({"tree": {"ServerScriptService": {"Gate": {"$className": "Folder", "Server": {"$path": "src/server"}}}}})
        self.assertEqual(roots, ["ServerScriptService/Gate/Server"])
        self.assertEqual(pull.owned_paths(roots), ["ServerScriptService/Gate"])
        self.assertEqual(pull.owned_paths(["ServerScriptService/Gate"]), [])

    def test_a_service_owned_whole_stops_the_walk(self):
        tree = {"tree": {"$className": "DataModel", "ReplicatedStorage": {"$path": "src", "X": {"$path": "x"}}}}
        self.assertEqual(pull.rojo_roots(tree), ["ReplicatedStorage"])


class FileNameTest(unittest.TestCase):
    def test_unsafe_and_reserved_names(self):
        taken: set = set()
        self.assertEqual(pull.file_name("a/b:c", taken), "a_b_c")
        self.assertEqual(pull.file_name("CON", taken), "_CON")
        self.assertEqual(pull.file_name(" . ", taken), "_")
        self.assertEqual(pull.file_name("빛 다리", taken), "빛 다리")

    def test_same_names_get_numbers_ignoring_case(self):
        taken: set = set()
        self.assertEqual([pull.file_name(n, taken) for n in ("Part", "part", "Part")], ["Part", "part (2)", "Part (3)"])


class SplitTest(unittest.TestCase):
    def test_split_by_sizes_skipping_unread_items(self):
        items = [{"size": 2}, {"error": "too_big 9", "size": 0}, {"size": 3}]
        self.assertEqual(pull.split_blobs("aabbb", items), ["aa", "bbb"])

    def test_length_mismatch_is_refused(self):
        with self.assertRaises(pull.Unavailable):
            pull.split_blobs("aab", [{"size": 2}, {"size": 3}])


class PrivateTest(unittest.TestCase):
    def test_short_or_zero_values_are_not_used(self):
        self.assertEqual(pull.extras("ab", "0"), [])
        self.assertEqual(pull.extras("someone", "1234567890"), ["someone", "1234567890"])

    def test_account_name_blocks_the_item_in_any_case(self):
        clean, blocked = pull.scan({"Workspace/A.rbxmx": '<string name="Name">SomeOne house</string>', "settings.json": "{}"},
                                   ["someone"])
        self.assertEqual(list(clean), ["settings.json"])
        self.assertIn("Workspace/A.rbxmx", blocked)


class EncodedTest(unittest.TestCase):
    """속성·태그는 XML 안에 base64 로만 들어 있다 — 풀어서 본다 (리뷰 STUDIO-PULL 1차)."""

    def blob(self, raw: bytes, name: str = "AttributesSerialize") -> str:
        text = base64.b64encode(raw).decode()
        return f'<BinaryString name="{name}"><![CDATA[{text}]]></BinaryString>'

    def test_account_name_inside_attributes_blocks_the_item(self):
        _clean, blocked = pull.scan({"Workspace/A.rbxmx": self.blob(b"\x05owner\x02\x07SomeOne")}, ["someone"])
        self.assertIn("Workspace/A.rbxmx", blocked)

    def test_account_name_in_the_file_name_blocks_the_item(self):
        _clean, blocked = pull.scan({"Workspace/someone.rbxmx": "<roblox/>"}, ["someone"])
        self.assertIn("Workspace/someone.rbxmx", blocked)

    def test_binary_data_is_checked_only_for_this_persons_values(self):
        mail_like = b"\x01U" + b"@" + b"e.8\x02"   # 메시·지형 이진 자료에 우연히 생기는 전자우편 꼴은 막지 않는다
        clean, _ = pull.scan({"Workspace/Terrain.rbxmx": self.blob(mail_like, "SmoothGrid")}, ["someone"])
        self.assertIn("Workspace/Terrain.rbxmx", clean)
        _clean, blocked = pull.scan({"Workspace/Terrain.rbxmx": self.blob(b"\x00someone\x00", "SmoothGrid")}, ["someone"])
        self.assertIn("Workspace/Terrain.rbxmx", blocked)
        _clean, blocked = pull.scan({"Workspace/A.rbxmx": self.blob(b"\x07Contact" + mail_like)}, [])
        self.assertIn("Workspace/A.rbxmx", blocked)   # 속성 값에 든 전자우편 꼴은 막는다


class MirrorTest(unittest.TestCase):
    def test_writes_changes_removes_stale_copies_and_keeps_unwritten_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in (("Workspace/Old.rbxmx", "old"), ("Workspace/Blocked.rbxmx", "kept"), ("Lighting/Gone.rbxmx", "x")):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(text, encoding="utf-8")
            outputs = {"Workspace/New.rbxmx": "new", "settings.json": "{}\n"}
            changed = pull.mirror(outputs, {"Workspace/Blocked.rbxmx"}, root)
            self.assertEqual(sorted(changed), ["Lighting/Gone.rbxmx", "Workspace/New.rbxmx", "Workspace/Old.rbxmx", "settings.json"])
            self.assertEqual((root / "Workspace" / "Blocked.rbxmx").read_text(encoding="utf-8"), "kept")
            self.assertFalse((root / "Lighting").exists())   # 빈 그릇 폴더도 지운다
            self.assertEqual(pull.mirror(outputs, {"Workspace/Blocked.rbxmx"}, root), [])   # 같은 내용이면 바꾸지 않는다
            self.assertFalse(list(root.rglob("*.part")) or (root.parent / (root.name + ".staging")).exists())
            self.assertEqual(pull.mirror({}, {"workspace/blocked.RBXMX", "Workspace/New.rbxmx", "settings.json"}, root), [])   # 대소문자만 다른 keep


class RememberTest(unittest.TestCase):
    def test_appends_on_a_new_line_and_skips_known_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rb-private"
            path.write_text("handwritten", encoding="utf-8")   # 사람이 줄바꿈 없이 끝낸 파일
            with mock.patch.object(pull.ship, "local_private_path", return_value=path):
                pull.remember(["someone", "handwritten"])
                pull.remember(["someone"])
            self.assertEqual(path.read_text(encoding="utf-8"), "handwritten\nsomeone\n")


class FillTest(unittest.TestCase):
    def test_long_bracket_close_is_refused(self):
        with self.assertRaises(ValueError):
            pull.fill("[==[__ARGS__]==]", ARGS='{"name": "a]==]b"}')
        self.assertEqual(pull.fill("x__A__y", A="1"), "x1y")


class StateTest(unittest.TestCase):
    def test_play_mode_is_read_from_the_studio_state(self):
        self.assertTrue(pull.edit_available("- Current Studio Mode: Edit\n- Available DataModels: Edit\n"))
        self.assertFalse(pull.edit_available("- Current Studio Mode: Play\n- Available DataModels: Client, Server\n"))
        self.assertFalse(pull.edit_available(""))

    def test_nothing_to_read_does_not_use_up_the_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            state.write_text(json.dumps({"last": 1.0}), encoding="utf-8")
            with mock.patch.object(pull.ship, "git_path", return_value=state), \
                    mock.patch.object(pull, "pull", side_effect=pull.Absent("Play 중")):
                self.assertEqual(pull.main(["--quiet"]), 0)
            self.assertEqual(json.loads(state.read_text(encoding="utf-8")), {"last": 1.0})   # 그대로 — 다음 턴에 바로 다시 본다
            with mock.patch.object(pull.ship, "git_path", return_value=state), \
                    mock.patch.object(pull, "pull", side_effect=pull.Unavailable("통로 막힘")):
                self.assertEqual(pull.main(["--quiet"]), 0)
            self.assertGreater(json.loads(state.read_text(encoding="utf-8"))["last"], 1.0)   # 느린 실패는 간격을 쓴다


class DueTest(unittest.TestCase):
    def test_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            self.assertTrue(pull.due(state, 1000.0))
            state.write_text(json.dumps({"last": 900.0}), encoding="utf-8")
            self.assertFalse(pull.due(state, 1000.0, interval=600))
            self.assertTrue(pull.due(state, 1600.0, interval=600))


if __name__ == "__main__":
    unittest.main()
