"""검증 환경의 생략·빈 검사·코드 변경을 실제 경로에서 확인한다."""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import check
import flow_guard
import verify

ROOT=Path(__file__).resolve().parents[1]


class CompletenessTest(unittest.TestCase):
    def test_missing_entrypoints_escalate(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(check,'ROOT',Path(directory)), patch.object(flow_guard,'run_helper',return_value=(True,{})):
            output=io.StringIO()
            with redirect_stdout(output): self.assertEqual(check.main(),2)
            self.assertIn('entrypoints missing',output.getvalue())

    def test_empty_suites_escalate(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(check,'ROOT',Path(directory)), patch.object(flow_guard,'run_helper',return_value=(True,{})):
            for name in ('tools/test_flow_guard.py','tools/test_verify.py','tests/test_validate_spec.py','tests/test_q2_graph.py','tests/test_harness.py','tests/test_world_source.py','tools/test_ship.py'):
                path=Path(directory)/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('')
            with patch.object(unittest.TestLoader,'discover',return_value=unittest.TestSuite()):
                output=io.StringIO()
                with redirect_stdout(output): self.assertEqual(check.main(),2)
                self.assertIn('no tests discovered',output.getvalue())

    def test_runtime_absent_does_not_skip_to_success(self):
        with patch.object(flow_guard,'DEFAULT_HELPER',ROOT/'missing-runtime.py'):
            with redirect_stdout(io.StringIO()): self.assertEqual(check.main(),2)



if __name__ == "__main__": unittest.main()
