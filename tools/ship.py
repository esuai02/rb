#!/usr/bin/env python3
"""작업을 잃지 않고 내보내는 장치 — 자동 저장(커밋·푸시)과 잠긴 단계의 자동 병합.

  python3 tools/ship.py save [-m 메시지] [--quiet]   # 검사가 통과하면 커밋하고 지금 브랜치로 푸시한다
  python3 tools/ship.py merge [--yes]                # 사람이 잠근 단계만 담은 PR 을 병합한다(기본은 계획만 보인다)
  python3 tools/ship.py status                       # 무엇이 올라가 있고 무엇이 남았는지

원칙 (3층 게이트 D-VERIFY · 공개 저장소 DEC-3)
- 저장: 로컬 경로·계정·비밀값이 섞이면 커밋하지 않는다. 코드가 바뀌었으면 자동 검사가 통과해야 커밋한다.
  커밋하지 못하면 이유만 알리고 멈춘다 — 깨진 상태를 올리지 않는다.
- 푸시: 지금 작업 브랜치로만, 강제 푸시 없이. main 에는 직접 커밋하지 않는다.
- 병합: 사람이 잠근(verify.py lock) 단계만. PR 이 담은 단계가 모두 잠겼고 깨끗할 때만 병합한다.
- 자동 실행: Stop 훅이 save 를 돌리고, verify.py lock 이 성공하면 save → merge 를 돌린다.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 새로 만든(아직 추적하지 않는) 파일 가운데 자동으로 올리는 자리. 그 밖의 새 파일은 사람이 정한다.
CODE_ROOTS = ("harness/", "tests/", "tools/", "world/", "specs/", "outputs/verify/")
# 자동 검사가 필요한 변경 — 이 자리가 바뀌면 시험을 통과해야 커밋한다.
GATED_ROOTS = ("harness/", "tests/", "tools/", "world/", "specs/", "graph.json")
# PR 의 머리 브랜치 → 그 PR 이 담은 단계. 담은 단계가 모두 잠겨야 병합한다.
STAGES_BY_BRANCH = {
    "feat/q1-intent-spec": ["Q1"],
    "feat/q2-world-graph": ["Q2", "Q3", "Q4"],   # Q2 잠금 뒤 Q3·Q4 작업도 이 브랜치에 쌓였다
}
PROTECTED = {"main", "master"}
SECRET = re.compile(r"AKIA[0-9A-Z]{16}|\b(?:api[_-]?key|passwd|password|secret|token)\s*[:=]\s*['\"][^'\"]{6,}", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
EXAMPLE_DOMAIN = re.compile(r"@(?:[\w-]+\.)*(?:example\.(?:com|org|net)|[\w-]+\.(?:example|test|invalid))$", re.I)


def git(*args: str, check: bool = True) -> str:
    done = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if check and done.returncode != 0:
        raise RuntimeError(done.stderr.strip() or f"git {' '.join(args)} 실패")
    return done.stdout


def candidates(porcelain_z: str) -> list[str]:
    """올릴 파일 — 추적 중인 파일의 변경 전부와, 정해진 자리에 새로 만든 파일. 나머지 새 파일은 건드리지 않는다.

    `git status --porcelain -z` 를 읽는다(한글 파일 이름이 이스케이프되지 않게). 이름 바꾸기는 새 이름만 쓴다.
    """
    out, entries, k = [], porcelain_z.split("\0"), 0
    while k < len(entries):
        entry = entries[k]
        k += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if status[0] in "RC":
            k += 1   # 다음 칸은 옛 이름
        if status == "??":
            if path.startswith(CODE_ROOTS):
                out.append(path)
        else:
            out.append(path)
    return sorted(set(out))


def leaks(diff: str, private: list[str]) -> list[str]:
    """더하는 줄에 섞인 로컬 경로·계정·비밀값 — 하나라도 있으면 커밋하지 않는다."""
    found = []
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for value in private:
            if value and value in line:
                found.append(f"로컬 경로·계정 '{value}' 가 들어 있다: {line[:80]}")
        if SECRET.search(line):
            found.append(f"비밀값처럼 보이는 줄: {line[:80]}")
        for mail in EMAIL.findall(line):
            if mail.endswith("@anthropic.com") or EXAMPLE_DOMAIN.search(mail):
                continue   # 커밋 메시지의 공동 작성자 표기 · 예시 전용 도메인(RFC 2606)은 진짜 주소가 아니다
            found.append(f"전자우편 주소 '{mail}' 가 들어 있다")
    return found


def private_values() -> list[str]:
    """올리면 안 되는 이 기계의 값 — 저장소 경로·홈 경로·커밋 계정의 전자우편."""
    values = [str(REPO), str(Path.home())]
    mail = git("config", "user.email", check=False).strip()
    return [v for v in values + [mail] if v and v not in ("/", "~")]


def gates(paths: list[str]) -> list[str]:
    """코드가 바뀌었으면 자동 검사를 돌린다. 실패한 검사의 이름과 첫 줄을 돌려준다."""
    if not any(p.startswith(GATED_ROOTS) or p in GATED_ROOTS for p in paths):
        return []
    with tempfile.TemporaryDirectory(prefix="rb-ship-") as tmp:
        steps = [("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]),
                 ("tools", [sys.executable, "-m", "unittest", "discover", "-s", "tools", "-q"]),
                 ("명세", [sys.executable, "tools/validate_spec.py"]),
                 ("월드 소스 Harness", [sys.executable, "-m", "harness.run", "world", "--out", tmp])]
        failed = []
        for name, cmd in steps:
            done = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=900)
            if done.returncode != 0:
                text = (done.stderr or done.stdout).strip().splitlines()
                failed.append(f"{name}: {next((t for t in text if 'FAIL' in t or 'Error' in t), text[-1] if text else '실패')[:120]}")
        return failed


def summary(paths: list[str]) -> str:
    areas = sorted({p.split("/", 1)[0] for p in paths})
    return f"chore(자동 저장): {'·'.join(areas)} — 파일 {len(paths)}개"


def save(message: str | None, quiet: bool) -> int:
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch in PROTECTED:
        print(f"[자동 저장] {branch} 에는 직접 커밋하지 않는다 — 작업 브랜치에서 한다")
        return 0
    paths = candidates(git("status", "--porcelain", "-z"))
    if paths:
        git("add", "--", *paths)
        found = leaks(git("diff", "--cached"), private_values())
        if found:
            git("reset", "-q", "--", *paths)
            print("[자동 저장] 멈춤 — 공개 저장소에 올리면 안 되는 값이 있다:\n  " + "\n  ".join(found[:5]))
            return 1
        failed = gates(paths)
        if failed:
            git("reset", "-q", "--", *paths)
            print("[자동 저장] 멈춤 — 자동 검사가 통과하지 않아 커밋하지 않았다:\n  " + "\n  ".join(failed))
            return 1
        git("commit", "-q", "-m", message or summary(paths))
    ahead = git("rev-list", "--count", f"origin/{branch}..HEAD", check=False).strip()
    if not paths and ahead in ("", "0"):
        if not quiet:
            print("[자동 저장] 바뀐 것이 없다")
        return 0
    has_upstream = git("rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}", check=False).strip()
    git("push", "-q", *([] if has_upstream else ["-u"]), "origin", branch)
    head = git("log", "--oneline", "-1").strip()
    print(f"[자동 저장] {branch} 에 올림 — {head}" + (f" (새 파일·변경 {len(paths)}개)" if paths else ""))
    return 0


def stage_locked(stage: str) -> bool:
    done = subprocess.run([sys.executable, "tools/verify.py", "gate", stage], cwd=REPO, capture_output=True, text=True)
    return "locked=True" in done.stdout


def plan(prs: list[dict], locked: dict[str, bool]) -> list[tuple[dict, str, str]]:
    """PR 마다 (PR, 병합|대기, 이유). 담은 단계가 모두 잠기고 깨끗한 PR 만 병합한다."""
    out = []
    for pr in prs:
        stages = STAGES_BY_BRANCH.get(pr["headRefName"])
        if not stages:
            out.append((pr, "대기", "어느 단계를 담았는지 모르는 브랜치 — 사람이 정한다"))
            continue
        waiting = [s for s in stages if not locked.get(s)]
        if waiting:
            out.append((pr, "대기", f"아직 잠기지 않은 단계: {', '.join(waiting)}"))
        elif pr.get("mergeStateStatus") != "CLEAN":
            out.append((pr, "대기", f"GitHub 병합 상태가 {pr.get('mergeStateStatus')} — 충돌·검사를 먼저 푼다"))
        else:
            out.append((pr, "병합", f"담은 단계 {', '.join(stages)} 가 모두 사람이 잠갔다"))
    return out


def open_prs() -> list[dict]:
    done = subprocess.run(["gh", "pr", "list", "--state", "open", "--json",
                           "number,title,headRefName,baseRefName,mergeStateStatus"], cwd=REPO, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip() or "gh pr list 실패")
    return json.loads(done.stdout)


def merge(yes: bool) -> int:
    prs = open_prs()
    stages = sorted({s for pr in prs for s in STAGES_BY_BRANCH.get(pr["headRefName"], [])})
    locked = {s: stage_locked(s) for s in stages}
    steps = plan(prs, locked)
    for pr, action, reason in steps:
        print(f"[병합] #{pr['number']} {pr['headRefName']} → {pr['baseRefName']}: {action} — {reason}")
    if not yes:
        return 0
    for pr, action, _reason in steps:
        if action != "병합":
            continue
        subprocess.run(["gh", "pr", "merge", str(pr["number"]), "--merge"], cwd=REPO, check=True)
        for child in prs:   # 쌓인 PR 은 병합된 PR 의 바탕으로 옮겨 단다
            if child["baseRefName"] == pr["headRefName"]:
                subprocess.run(["gh", "pr", "edit", str(child["number"]), "--base", pr["baseRefName"]], cwd=REPO, check=True)
                print(f"[병합] #{child['number']} 의 바탕을 {pr['baseRefName']} 로 옮겼다")
        print(f"[병합] #{pr['number']} 병합함")
    return 0


def status() -> int:
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    ahead = git("rev-list", "--count", f"origin/{branch}..HEAD", check=False).strip() or "?"
    paths = candidates(git("status", "--porcelain", "-z"))
    print(f"[상태] 브랜치 {branch} · 올리지 않은 커밋 {ahead}개 · 올릴 변경 {len(paths)}개")
    return merge(yes=False)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 tools/ship.py")
    sub = parser.add_subparsers(dest="command", required=True)
    p_save = sub.add_parser("save")
    p_save.add_argument("-m", "--message")
    p_save.add_argument("--quiet", action="store_true", help="훅에서 부를 때 — 한 줄만 알리고 실패해도 세션을 막지 않는다")
    p_merge = sub.add_parser("merge")
    p_merge.add_argument("--yes", action="store_true", help="계획만 보이지 않고 실제로 병합한다")
    sub.add_parser("status")
    args = parser.parse_args(argv)
    try:
        if args.command == "save":
            code = save(args.message, args.quiet)
            return 0 if args.quiet else code
        if args.command == "merge":
            return merge(args.yes)
        return status()
    except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
        print(f"[ship] 멈춤 — {exc}")
        return 0 if getattr(args, "quiet", False) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
