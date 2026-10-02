#!/usr/bin/env python3
"""검수 Harness 실행기 (작업 Graph Q3).

  python3 -m harness.run <소스 트리> [--out 기록 폴더]

매니페스트의 정적 검사를 모두 돌리고 검사마다 기록 파일 하나(명령·결과·시각·대상 지문·발견 목록)를 남긴다.
종료 코드: 0 위반 없음 · 1 위반 있음 · 2 사용법·읽기 오류. 기록에는 로컬 경로를 쓰지 않는다(INV-6).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness import source  # noqa: E402
from harness.checks import REGISTRY  # noqa: E402

MANIFEST = REPO / "harness" / "manifest.json"


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint(root: Path) -> str:
    """대상 트리의 지문 — 상대 경로와 내용의 sha256."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def fixture_index(fixtures: Path = REPO / "harness" / "fixtures") -> dict[str, str]:
    """고정 시험 데이터 파일 → sha256. harness/fixtures/index.json 이 이 값과 같아야 한다(작업 Graph 가 색인으로 데이터를 고정)."""
    return {p.relative_to(fixtures).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(fixtures.rglob("*")) if p.is_file() and p.name != "index.json"}


def run_checks(root: Path, manifest: dict | None = None, rules: source.Rules | None = None) -> dict[str, list[str]]:
    """검사 id → 발견 목록. 트리를 읽다 생긴 문제는 모든 검사의 발견으로 넣는다(읽지 못한 것을 통과로 보지 않는다)."""
    manifest = manifest or load_manifest()
    rules = rules or source.load_rules(REPO)
    tree = source.load_tree(root)
    results = {}
    for check in manifest["checks"]:
        func = REGISTRY.get(check["id"])
        if func is None:
            results[check["id"]] = [f"검사 {check['id']} 의 구현이 없다"]
            continue
        try:
            found = func(tree, rules, manifest["config"])
        except Exception as exc:  # 검사가 멈추면 그 검사는 실패로 기록한다
            found = [f"검사가 끝까지 돌지 못했다 ({type(exc).__name__}: {exc})"]
        results[check["id"]] = [f"트리 읽기: {p}" for p in tree.problems] + found
    return results


def write_records(root: Path, results: dict[str, list[str]], out: Path, label: str) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    when, tree_sha = datetime.now(timezone.utc).isoformat(), fingerprint(root)
    paths = []
    for check_id, found in results.items():
        record = out / f"{check_id}.txt"
        body = [f"check: {check_id}", f"command: python3 -m harness.run {label}", f"result: {'FAIL' if found else 'PASS'}",
                f"time: {when}", f"target_sha256: {tree_sha}", f"findings: {len(found)}", ""] + [f"- {x}" for x in found]
        record.write_text("\n".join(body) + "\n", encoding="utf-8")
        paths.append(record)
    return paths


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m harness.run")
    parser.add_argument("tree", nargs="?")
    parser.add_argument("--out", default=None)
    parser.add_argument("--write-index", action="store_true", help="고정 시험 데이터 색인(harness/fixtures/index.json)을 다시 쓴다")
    args = parser.parse_args(argv)
    if args.write_index:
        index = REPO / "harness" / "fixtures" / "index.json"
        index.write_text(json.dumps({"files": fixture_index()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[harness] 색인을 다시 썼습니다: {len(fixture_index())}개 파일")
        return 0
    if not args.tree:
        parser.error("소스 트리 경로가 필요합니다")
    root = Path(args.tree)
    if not (root / "default.project.json").is_file():
        print(f"[harness] Rojo 프로젝트(default.project.json)가 없습니다: {args.tree}", file=sys.stderr)
        return 2
    label = root.resolve().relative_to(REPO).as_posix() if REPO in root.resolve().parents else root.name
    out = Path(args.out) if args.out else REPO / "outputs" / "harness" / root.name
    results = run_checks(root)
    write_records(root, results, out, label)
    for check_id, found in results.items():
        print(f"{'FAIL' if found else 'OK  '} {check_id}")
        for x in found:
            print(f"     - {x}")
    return 1 if any(results.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
