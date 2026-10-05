#!/usr/bin/env python3
"""한 번의 로컬 검증. 건너뛴 테스트는 통과로 세지 않는다. 설치·승인·잠금은 하지 않는다."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import flow_guard


def main():
    try:
        import yaml, jsonschema  # noqa: F401
    except ImportError as exc:
        print(f"ESCALATE 의존성 없음: {exc.name}; requirements.txt 를 사용하세요.")
        return 2
    if not flow_guard.DEFAULT_HELPER.is_file():
        print("ESCALATE 검증 런타임 없음. MASTERWORK_HELPER 를 설정하세요. 검사를 생략해서 PASS 시키지 않습니다.")
        return 2
    ok, message = flow_guard.run_helper(flow_guard.DEFAULT_HELPER, "validate", ROOT / "graph.json")
    if not ok:
        print(f"FAIL Graph: {message}")
        return 1
    entrypoints = ("tools/test_flow_guard.py", "tools/test_verify.py", "tests/test_validate_spec.py", "tests/test_q2_graph.py", "tests/test_harness.py", "tests/test_world_source.py", "tools/test_ship.py")
    missing = [p for p in entrypoints if not (ROOT / p).is_file()]
    if missing:
        print("ESCALATE required test entrypoints missing: " + ", ".join(missing))
        return 2
    results = []
    for directory in ("tools", "tests"):
        suite = unittest.TestLoader().discover(str(ROOT / directory))
        if suite.countTestCases() == 0:
            print(f"ESCALATE no tests discovered: {directory}")
            return 2
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        results.append(result)
    skipped = sum(len(r.skipped) for r in results)
    print(f"tests={sum(r.testsRun for r in results)} skipped={skipped}")
    if skipped:
        print("ESCALATE 생략한 검사가 있습니다.")
        return 2
    return 0 if all(r.wasSuccessful() for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
