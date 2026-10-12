"""현재 Q4 심사대 소스 검사. 과거 게이트 계약은 Q2 및 Harness 고정 시험에 남긴다."""
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness import run, source
from tools import build_localization

WORLD = ROOT / "world"
SOURCE = WORLD / "src"

class HarnessTest(unittest.TestCase):
    def test_no_violation(self):
        found = {k: v for k, v in run.run_checks(WORLD).items() if v}
        self.assertEqual(found, {})

    def test_every_check_runs(self):
        self.assertEqual(set(run.run_checks(WORLD)), {c['id'] for c in run.load_manifest()['checks']})

class InspectionTest(unittest.TestCase):
    def test_runtime(self):
        executable = os.environ.get('LUAU_BIN') or shutil.which('luau')
        if not executable:
            self.skipTest('Luau CLI required: run luau tests/test_inspection.luau')
        result = subprocess.run([executable, 'tests/test_inspection.luau'], cwd=ROOT, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS inspection runtime:', result.stdout)

    def test_build(self):
        executable = os.environ.get('ROJO_BIN') or shutil.which('rojo')
        if not executable:
            self.skipTest('Rojo CLI required for a Place build')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'inspection.rbxlx'
            result = subprocess.run([executable, 'build', 'world/default.project.json', '-o', str(out)],
                                    cwd=ROOT, text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            from xml.etree import ElementTree
            tree = ElementTree.parse(out)
            names = {p.text for p in tree.findall('.//Properties/string[@name="Name"]')}
            self.assertTrue({'SpawnLocation', 'MissionService', 'Missions', 'Hud', 'Localization'} <= names)

    def test_compile(self):
        executable = os.environ.get('LUAU_COMPILE_BIN') or shutil.which('luau-compile')
        if not executable:
            self.skipTest('Luau compiler required for syntax verification')
        for path in SOURCE.rglob('*.luau'):
            result = subprocess.run([executable, '--null', str(path)], text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, path.name + ': ' + result.stdout + result.stderr)

    def test_answers_are_server_only(self):
        project = json.loads((WORLD / 'default.project.json').read_text())['tree']
        self.assertEqual(project['ServerScriptService']['Gate']['$path'], 'src/server')
        self.assertFalse((SOURCE / 'shared/Missions.luau').exists())
        self.assertNotRegex(''.join(p.read_text() for p in (SOURCE / 'shared').glob('*.luau')), r'verdict\s*=\s*"')
        self.assertNotIn('evidence = "match"', ''.join(p.read_text() for p in (SOURCE / 'client').glob('*.luau')))

    def test_no_legacy_entry_remotes(self):
        text = (SOURCE / 'server/Main.server.luau').read_text()
        self.assertNotIn('SignalRemote', text)
        self.assertNotIn('SlopeRemote', text)
        self.assertIn('InspectionRemote.OnServerEvent:Connect(onInspection)', text)

    def test_cooldown_retains_canonical_value(self):
        canonical = {v['id']: v['value'] for v in source.load_rules(ROOT).canonical['values']}
        self.assertIn(f"local SECONDS = {canonical['cv.server_cooldown']['seconds']}", (SOURCE / 'server/Cooldown.luau').read_text())

class LocalizationTest(unittest.TestCase):
    def test_generated_csv_matches(self):
        self.assertEqual((SOURCE / 'shared/Localization.csv').read_text(), build_localization.render())

    def test_all_keys_are_translatable(self):
        keys = {r['Key'] for r in csv.DictReader(io.StringIO(build_localization.render()))}
        for p in SOURCE.rglob('*.luau'):
            for key in re.findall(r'Text\.get\("([^"\n]+)"', p.read_text()):
                self.assertIn(key, keys)

class AnalyticsTest(unittest.TestCase):
    def test_only_active_inspection_event_is_sent(self):
        text = (SOURCE / 'server/Main.server.luau').read_text()
        calls = re.findall(r'Analytics\.log\(player, "([^"]+)", \{inspection_step = "([^"]+)"\}\)', text)
        self.assertTrue(calls)
        self.assertEqual({event for event, _ in calls}, {'inspection_progress'})
        events = source.load_rules(ROOT).events
        definition = next(e for e in events['custom_events'] if e['name'] == 'inspection_progress')
        self.assertEqual(definition['fields'], ['inspection_step'])
        self.assertEqual({step for _, step in calls}, set(events['fields']['inspection_step']))
        # one result opportunity, one voluntary next action. Replays/resumes cannot inflate either.
        self.assertEqual(text.count('inspection_step = "result_shown"'), 1)
        self.assertEqual(text.count('inspection_step = "next_chosen"'), 1)

class WorkshopSourceTest(unittest.TestCase):
    """워크숍 순회(2026-10-12) — 정적 계약. 실제 동작은 tests/test_inspection.luau 와 Studio Play 로 본다."""

    def test_numbers_use_integer_format(self):
        import yaml
        strings = yaml.safe_load(build_localization.GLOSSARY.read_text(encoding='utf-8'))['strings']
        for key, text in strings.items():
            if key.startswith('inspection.'):
                self.assertNotRegex(str(text), r'\{[a-z]+\}', f'{key}: Translator 는 숫자를 0.00 으로 찍는다 — {{x:int}} 로 쓴다')

    def test_new_actions_are_whitelisted_on_server(self):
        text = (SOURCE / 'server/Main.server.luau').read_text()
        for action in ('help', 'restart'):
            self.assertIn(f'action ~= "{action}"', text)
        self.assertNotIn('UserId % 2', text)

    def test_snapshot_never_carries_expected_evidence(self):
        service = (SOURCE / 'server/MissionService.luau').read_text()
        self.assertNotRegex(service, r'evidence\s*=\s*case\.evidence')
        self.assertIn('verdict = if phase == "resolved" or phase == "rest" then case.verdict else nil', service)

    def test_camera_and_avatar_rebind_without_accumulating(self):
        hud = (SOURCE / 'client/Hud.client.luau').read_text()
        self.assertIn('GetPropertyChangedSignal("CurrentCamera")', hud)
        self.assertIn('if cameraWatch then cameraWatch:Disconnect() end', hud)
        self.assertIn('if avatarWatch then avatarWatch:Disconnect() end', hud)
        self.assertIn('DescendantAdded:Connect(hide)', hud)
        self.assertIn('if current.CameraType ~= Enum.CameraType.Scriptable then', hud)

    def test_answer_graphic_is_optional_help(self):
        hud = (SOURCE / 'client/Hud.client.luau').read_text()
        self.assertIn('local open = s.help == true', hud)
        self.assertNotIn('replayPath', hud)

    def test_fold_line_and_checkable_tables(self):
        hud = (SOURCE / 'client/Hud.client.luau').read_text()
        service = (SOURCE / 'server/MissionService.luau').read_text()
        # 반 칸(1.5) 접는 선은 칸을 칠하지 않고 얇은 세로선 하나로 그린다
        self.assertNotIn('paint(s.line', hud)
        self.assertIn('foldLine.Visible = open and s.theme == "symmetry" and s.line ~= nil', hud)
        # gamepad 판단은 UIPadding 이 아니라 GamepadEnabled 로 한다
        self.assertNotIn('if pad then', hud)
        self.assertNotIn('commands[b][2]', hud)
        # 기록 표는 한 번 만든 표를 비우고 다시 채운다 — 함수 결과로 다시 묶지 않는다
        self.assertNotRegex(service, r'(?m)^\s*records\s*=')
        self.assertNotIn('table.clone(pack)', service)


if __name__ == '__main__':
    unittest.main()
