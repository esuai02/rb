#!/usr/bin/env python3
"""결함마다 나오는 진단 전부를 tests/defect-diagnoses.json 에 다시 적는다 (작업 Graph Q3).

  python3 tools/freeze_diagnoses.py          # 다시 적고 바뀐 줄 수를 알려 준다
  python3 tools/freeze_diagnoses.py --check  # 다른지만 본다 (다르면 종료 코드 1)

검사기의 진단 문구를 일부러 고쳤을 때만 다시 적고, git diff 로 바뀐 줄을 눈으로 확인한 뒤 커밋한다.
시험(tests/test_harness.py)은 이 파일을 읽어 대조만 한다 — 환경변수로 건너뛸 수 없다 (리뷰 R-Q3 26차).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness import run, source  # noqa: E402

CLEAN = REPO / "harness" / "fixtures" / "clean"
OUT = REPO / "tests" / "defect-diagnoses.json"


def diagnoses() -> dict[str, dict[str, list[str]]]:
    manifest, rules = run.load_manifest(), source.load_rules(REPO)
    base = Path(tempfile.mkdtemp(prefix="rb-freeze-"))
    try:
        local = base / "clean"
        shutil.copytree(CLEAN, local)
        out = {}
        for defect in sorted(manifest["defects"], key=lambda d: d["id"]):
            work = base / defect["id"]
            found = run.run_checks(run.build_defect(local, defect, work), manifest, rules)
            out[defect["id"]] = {check: hits for check, hits in sorted(found.items()) if hits}
            shutil.rmtree(work, ignore_errors=True)
        return out
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 tools/freeze_diagnoses.py")
    parser.add_argument("--check", action="store_true", help="다시 적지 않고 다른지만 본다")
    args = parser.parse_args(argv)
    text = json.dumps(diagnoses(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    if args.check:
        print(f"OK {OUT.relative_to(REPO)}" if current == text else f"FAIL {OUT.relative_to(REPO)} 가 지금 진단과 다르다")
        return 0 if current == text else 1
    OUT.write_text(text, encoding="utf-8")
    lines = sum(len(v) for checks in json.loads(text).values() for v in checks.values())
    print(f"{OUT.relative_to(REPO)} — 결함 {len(json.loads(text))}종, 진단 {lines}줄{' (바뀜)' if current != text else ' (그대로)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
