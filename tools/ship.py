#!/usr/bin/env python3
"""작업을 잃지 않고 내보내는 장치 — 자동 저장(커밋·푸시)과 잠긴 단계의 자동 병합.

  python3 tools/ship.py save [-m 메시지] [--quiet]   # 검사가 통과하면 커밋하고 지금 브랜치로 푸시한다
  python3 tools/ship.py merge [--yes]                # 사람이 잠근 단계만 담은 PR 을 병합한다(기본은 계획만 보인다)
  python3 tools/ship.py status                       # 무엇이 올라가 있고 무엇이 남았는지

원칙 (3층 게이트 D-VERIFY · 공개 저장소 DEC-3)
- 저장: 올라가는 것 전부(새 커밋 + 아직 안 올린 커밋 + 커밋 메시지)에 로컬 경로·계정·비밀값이 없어야 하고,
  코드가 바뀌었으면 자동 검사가 통과해야 한다. 못 하면 이유만 알리고 멈추며 인덱스를 처음 상태로 돌린다.
- 푸시: 지금 작업 브랜치로만, 강제 푸시 없이. main 에는 직접 커밋하지 않는다.
- 병합: 같은 저장소의 PR 이고, 그 PR 머리 커밋에서 담은 단계가 모두 사람이 잠갔을 때만.
  병합은 확인한 머리 커밋으로 못박는다(--match-head-commit) — 확인 뒤에 바뀐 PR 은 병합되지 않는다.
- 자동 실행: Stop 훅이 save --quiet 를 돌린다(시간 예산 안에서 끝나고 세션을 막지 않는다).
  verify.py lock 이 성공하면 save 가 성공했을 때만 merge 를 돌린다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 새로 만든(아직 추적하지 않는) 파일 가운데 자동으로 올리는 자리. 그 밖의 새 파일은 사람이 정한다.
CODE_ROOTS = ("harness/", "tests/", "tools/", "world/", "specs/", "outputs/verify/")
# 자동 검사가 필요한 변경 — 이 자리가 바뀌면 시험을 통과해야 올린다.
GATED_ROOTS = ("harness/", "tests/", "tools/", "world/", "specs/", "graph.json")
# PR 의 머리 브랜치 → 그 PR 이 담은 단계. 담은 단계가 모두 잠겨야 병합한다.
STAGES_BY_BRANCH = {
    "feat/q1-intent-spec": ["Q1"],
    "feat/q2-world-graph": ["Q2", "Q3", "Q4"],   # Q2 잠금 뒤 Q3·Q4 작업도 이 브랜치에 쌓였다
}
PROTECTED = {"main", "master"}
SAVE_BUDGET_S = 540       # Stop 훅 시간 제한(600초) 안에 save 전체가 반드시 끝나게
GATE_BUDGET_S = 420       # 그 가운데 자동 검사 몫 — 넘으면 검사 실패로 본다
SECRET = re.compile(
    r"AKIA[0-9A-Z]{16}"                                   # AWS 접근 키
    r"|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,}"   # GitHub 토큰
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"                      # Slack 토큰
    r"|sk-[A-Za-z0-9_-]{20,}"                             # API 비밀 키 꼴
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"                # 개인 키
    r"|\bBearer\s+[A-Za-z0-9._~+/=-]{20,}"                # 인증 머리
    r"|(?:\b|_)(?:api[_-]?key|passwd|password|secret|token|key)\s*[:=]\s*(?:['\"][^'\"]{6,}|[A-Za-z0-9_\-+/=]{16,})",
    re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
# Windows 사용자 폴더 경로 — 계정 이름을 드러낸다 (드라이브 문자 다음 Users 폴더, JSON 안 이중 역슬래시 꼴, WSL 의 /mnt/<드라이브>/Users 꼴)
USER_DIR = re.compile(r"\b[A-Za-z]:\\{1,2}Users\\{1,2}[^\\\s\"'`]+|/mnt/[a-z]/Users/[^/\s\"'`]+", re.I)
ATTRIBUTION = "noreply@anthropic.com"   # 커밋 메시지의 공동 작성자 표기 — 이 주소 하나만 허용한다
RESERVED = re.compile(r"@(?:[\w-]+\.)*(?:example\.(?:com|org|net)|[\w-]+\.(?:example|test|invalid))$", re.I)   # RFC 2606: 실제로 없는 주소


DEADLINE = [time.monotonic() + SAVE_BUDGET_S]   # save 를 시작할 때 다시 잡는다


def git(*args: str, check: bool = True) -> str:
    left = max(5.0, DEADLINE[0] - time.monotonic())
    done = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=left)
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
    """더하는 줄에 섞인 로컬 경로·계정·비밀값 — 하나라도 있으면 올리지 않는다."""
    found = []
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for value in private:
            if value and value in line:
                found.append(f"로컬 경로·계정 '{value}' 가 들어 있다: {line[:80]}")
        if SECRET.search(line):
            found.append(f"비밀값처럼 보이는 줄: {line[:80]}")
        for folder in USER_DIR.findall(line):
            found.append(f"Windows 사용자 폴더 경로 '{folder[:40]}' 가 들어 있다")
        for mail in EMAIL.findall(line):
            if mail.lower() == ATTRIBUTION or RESERVED.search(mail):
                continue
            found.append(f"전자우편 주소 '{mail}' 가 들어 있다")
    return found


def as_added(text: str) -> str:
    """커밋 메시지 같은 글을 '더하는 줄' 꼴로 — 같은 누출 검사를 받게."""
    return "\n".join("+" + line for line in text.splitlines())


def windows_forms(path: str) -> list[str]:
    """WSL 경로(/mnt/d/…)를 Windows 쪽에서 쓰는 꼴 — D:\\… 와 JSON·문자열 안의 D:\\\\… 도 같은 로컬 경로다."""
    match = re.match(r"/mnt/([a-z])(/.*)?$", path)
    if not match:
        return []
    rest = (match.group(2) or "").replace("/", "\\")
    forms = []
    for drive in (match.group(1).upper(), match.group(1)):
        forms += [drive + ":" + rest, (drive + ":" + rest).replace("\\", "\\\\")]
    return forms


def private_values() -> list[str]:
    """올리면 안 되는 이 기계의 값 — 저장소 경로(WSL·Windows 꼴)·홈 경로·커밋 계정의 전자우편."""
    values = [str(REPO), str(Path.home())] + windows_forms(str(REPO))
    mail = git("config", "user.email", check=False).strip()
    return [v for v in values + [mail] if v and v not in ("/", "~")]


def gates(changed: list[str], budget_s: float = GATE_BUDGET_S) -> list[str]:
    """코드가 바뀌었으면 자동 검사를 돌린다. 시간 예산을 넘기면 실패로 본다. 실패한 검사의 이름과 첫 줄을 돌려준다."""
    if not any(p.startswith(GATED_ROOTS) or p in GATED_ROOTS for p in changed):
        return []
    deadline = time.monotonic() + budget_s
    with tempfile.TemporaryDirectory(prefix="rb-ship-") as tmp:
        steps = [("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]),
                 ("tools", [sys.executable, "-m", "unittest", "discover", "-s", "tools", "-q"]),
                 ("명세", [sys.executable, "tools/validate_spec.py"]),
                 ("월드 소스 Harness", [sys.executable, "-m", "harness.run", "world", "--out", tmp])]
        for name, cmd in steps:
            left = deadline - time.monotonic()
            if left <= 0:
                return [f"{name}: 시간 예산({budget_s:.0f}초)을 넘었다"]
            try:
                done = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=left,
                                      env={**os.environ, "RB_SHIP_RUNNING": "1"})
            except subprocess.TimeoutExpired:
                return [f"{name}: 시간 예산({budget_s:.0f}초)을 넘었다"]
            if done.returncode != 0:
                text = (done.stderr or done.stdout).strip().splitlines()
                return [f"{name}: {next((t for t in text if 'FAIL' in t or 'Error' in t), text[-1] if text else '실패')[:120]}"]
    return []


def summary(paths: list[str]) -> str:
    areas = sorted({p.split("/", 1)[0] for p in paths})
    return f"chore(자동 저장): {'·'.join(areas)} — 파일 {len(paths)}개"


def outgoing(branch: str) -> tuple[str, list[str], int]:
    """아직 올리지 않은 것 전부 — (커밋마다의 patch 와 메시지를 '더하는 줄' 꼴로, 커밋들이 건드린 파일 전부, 커밋 수).

    최종 결과의 차이만 보면 중간 커밋에 넣었다가 지운 비밀값을 놓친다 — 그래도 이력에는 남는다 (리뷰 SHIP 2차).
    원격 브랜치가 없으면 main 부터 센다.
    """
    base = f"origin/{branch}" if git("rev-parse", "--verify", "-q", f"origin/{branch}", check=False).strip() else "origin/main"
    count = int(git("rev-list", "--count", f"{base}..HEAD").strip() or "0")
    if not count:
        return "", [], 0
    patches = git("log", "-p", "--text", "--format=", f"{base}..HEAD")
    messages = git("log", "--format=%B", f"{base}..HEAD")
    added = patches + "\n" + as_added(messages)   # 메시지는 따로 — '-' 로 시작하는 메시지 줄도 빠짐없이 검사받게
    files = sorted({p for p in git("log", "--name-only", "--format=", "-z", f"{base}..HEAD").replace("\n", "\0").split("\0") if p})
    return added, files, count


def save(message: str | None, quiet: bool) -> int:
    """돌려주는 값: 0 올라가 있음(이번에 올렸거나 이미 올라가 있음) · 1 멈춤 · 2 보호 브랜치라 하지 않음."""
    DEADLINE[0] = time.monotonic() + SAVE_BUDGET_S
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch in PROTECTED:
        print(f"[자동 저장] {branch} 에는 직접 커밋하지 않는다 — 작업 브랜치에서 한다")
        return 2
    if git("diff", "--cached", "--name-only").strip():
        print("[자동 저장] 사람이 미리 staging 한 변경이 있어 건드리지 않는다 — 직접 커밋하거나 staging 을 풀면 이어서 한다")
        return 1
    private = private_values()
    paths = candidates(git("status", "--porcelain", "-z"))
    before, before_files, _ = outgoing(branch)
    # 올라갈 것 전부(이미 있는 커밋들 + 이번 변경)에 코드가 하나라도 있으면 최종 상태로 검사를 돌린다 — 커밋하기 전에
    failed = gates(sorted(set(paths) | set(before_files)), min(GATE_BUDGET_S, DEADLINE[0] - time.monotonic() - 60))
    if failed:
        print("[자동 저장] 멈춤 — 자동 검사가 통과하지 않아 커밋·푸시하지 않았다:\n  " + "\n  ".join(failed))
        return 1
    found = leaks(before, private)
    if paths:
        msg = message or summary(paths)
        committed = False
        try:
            git("add", "--", *paths)
            found += leaks(git("diff", "--cached", "--text"), private) + leaks(as_added(msg), private)
            if not found:
                checked_tree = git("write-tree").strip()
                git("commit", "-q", "-m", msg)   # 커밋 훅은 건너뛰지 않는다(사용자 정책)
                committed = True
                if git("rev-parse", "HEAD^{tree}").strip() != checked_tree:   # 훅이 내용을 바꿨다면 검사한 것이 아니다
                    raise RuntimeError("커밋된 내용이 검사한 내용과 다르다(커밋 훅이 바꿨다) — 올리지 않는다")
        finally:
            if not committed:
                try:
                    git("reset", "-q", check=False)   # 시작할 때 인덱스가 비어 있었으므로 통째로 되돌려도 남의 것을 지우지 않는다
                except (subprocess.SubprocessError, OSError) as exc:
                    print(f"[자동 저장] 인덱스를 되돌리지 못했다 — git status 로 확인한다 ({exc})")
    if found:
        print("[자동 저장] 멈춤 — 공개 저장소에 올리면 안 되는 값이 있다(커밋하거나 올리지 않았다):\n  " + "\n  ".join(found[:5]))
        return 1
    _after, _files, count = outgoing(branch)
    if not count:
        if not quiet:
            print("[자동 저장] 바뀐 것이 없다 — 원격과 같다")
        return 0
    has_upstream = git("rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}", check=False).strip()
    git("push", "-q", *([] if has_upstream else ["-u"]), "origin", branch)
    head = git("log", "--oneline", "-1").strip()
    print(f"[자동 저장] {branch} 에 올림 — {head} (커밋 {count}개)")
    return 0


def locked_at(sha: str, stages: list[str]) -> tuple[bool, str]:
    """그 커밋에서 담은 단계가 모두 사람이 잠갔는가.

    PR 머리 커밋을 임시 작업 폴더로 꺼내되, 판정은 PR 쪽 코드가 아니라 이 저장소의 신뢰하는 검증기
    (verify.helper_gate → 저장소 밖 masterwork 도구)로 한다 — PR 은 데이터만 내놓는다 (리뷰 SHIP 2차).
    """
    sys.path.insert(0, str(REPO / "tools"))
    import verify   # noqa: E402 — 이 저장소의 검증기
    with tempfile.TemporaryDirectory(prefix="rb-ship-pr-") as tmp:
        tree = Path(tmp) / "head"
        git("worktree", "add", "-q", "--detach", str(tree), sha)
        try:
            for stage in stages:
                try:
                    result = verify.helper_gate(tree, stage)
                except (SystemExit, subprocess.SubprocessError, ValueError) as exc:
                    return False, f"머리 커밋 {sha[:8]} 의 {stage} 잠금을 판정하지 못했다 ({exc})"
                if not (result.get("verdict") == "PASS" and result.get("locked") is True):
                    return False, f"머리 커밋 {sha[:8]} 에서 {stage} 가 잠기지 않았다"
            return True, f"머리 커밋 {sha[:8]} 에서 {', '.join(stages)} 가 모두 사람이 잠갔다"
        finally:
            git("worktree", "remove", "--force", str(tree), check=False)


def plan(prs: list[dict], verdicts: dict[int, tuple[bool, str]]) -> list[tuple[dict, str, str]]:
    """PR 마다 (PR, 병합|대기, 이유). 같은 저장소 · 담은 단계가 머리 커밋에서 모두 잠김 · 깨끗함 — 셋이 다 맞아야 병합한다."""
    out = []
    for pr in prs:
        if pr.get("isCrossRepository", True):
            out.append((pr, "대기", "다른 저장소(포크)에서 온 PR — 자동으로 병합하지 않는다"))
            continue
        if not STAGES_BY_BRANCH.get(pr["headRefName"]):
            out.append((pr, "대기", "어느 단계를 담았는지 모르는 브랜치 — 사람이 정한다"))
            continue
        ok, reason = verdicts.get(pr["number"], (False, "잠금을 확인하지 못했다"))
        if not ok:
            out.append((pr, "대기", reason))
        elif pr.get("mergeStateStatus") != "CLEAN":
            out.append((pr, "대기", f"GitHub 병합 상태가 {pr.get('mergeStateStatus')} — 충돌·검사를 먼저 푼다"))
        else:
            out.append((pr, "병합", reason))
    return out


def open_prs() -> list[dict]:
    done = subprocess.run(["gh", "pr", "list", "--state", "open", "--json",
                           "number,title,headRefName,headRefOid,baseRefName,mergeStateStatus,isCrossRepository"],
                          cwd=REPO, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.strip() or "gh pr list 실패")
    return json.loads(done.stdout)


TRUSTED = ("tools/verify.py", "tools/flow_guard.py", "tools/ship.py")
ALLOWED_BASES = {"main"}


def merge(yes: bool) -> int:
    dirty = git("status", "--porcelain", "--", *TRUSTED).strip()
    if dirty:
        print("[병합] 잠금을 판정하는 도구가 작업 폴더에서 바뀌어 있다 — 커밋한 뒤에 병합한다")
        return 1
    git("fetch", "-q", "origin")
    prs = open_prs()
    verdicts = {}
    for pr in prs:
        stages = STAGES_BY_BRANCH.get(pr["headRefName"])
        if stages and not pr.get("isCrossRepository", True):
            verdicts[pr["number"]] = locked_at(pr["headRefOid"], stages)
    steps = plan(prs, verdicts)
    for pr, action, reason in steps:
        print(f"[병합] #{pr['number']} {pr['headRefName']} → {pr['baseRefName']}: {action} — {reason}")
    if not yes:
        return 0
    failed = 0
    for pr, action, _reason in steps:
        if action != "병합":
            continue
        now = subprocess.run(["gh", "pr", "view", str(pr["number"]), "--json", "baseRefName,headRefOid,mergeStateStatus"],
                             cwd=REPO, capture_output=True, text=True, timeout=60)
        fresh = json.loads(now.stdout) if now.returncode == 0 else {}
        if (fresh.get("baseRefName") not in ALLOWED_BASES or fresh.get("headRefOid") != pr["headRefOid"]
                or fresh.get("mergeStateStatus") != "CLEAN"):
            print(f"[병합] #{pr['number']} 병합 직전에 바탕·머리·상태가 달라졌다(또는 허용한 바탕이 아니다) — 병합하지 않는다")
            failed += 1
            continue
        done = subprocess.run(["gh", "pr", "merge", str(pr["number"]), "--merge", "--match-head-commit", pr["headRefOid"]],
                              cwd=REPO, capture_output=True, text=True, timeout=120)
        if done.returncode != 0:
            print(f"[병합] #{pr['number']} 병합 실패 — {done.stderr.strip()[:160]}")
            failed += 1
            continue
        print(f"[병합] #{pr['number']} 병합함 (머리 커밋 {pr['headRefOid'][:8]})")
        for child in prs:   # 쌓인 PR 은 병합된 PR 의 바탕으로 옮겨 단다
            if child["baseRefName"] == pr["headRefName"]:
                subprocess.run(["gh", "pr", "edit", str(child["number"]), "--base", pr["baseRefName"]], cwd=REPO, check=True)
                print(f"[병합] #{child['number']} 의 바탕을 {pr['baseRefName']} 로 옮겼다")
    return 1 if failed else 0


def status() -> int:
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    _added, _files, count = outgoing(branch)
    paths = candidates(git("status", "--porcelain", "-z"))
    print(f"[상태] 브랜치 {branch} · 올리지 않은 커밋 {count}개 · 올릴 변경 {len(paths)}개")
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
    if os.environ.get("RB_SHIP_RUNNING") and args.command == "save":
        return 0   # 검사 안에서 다시 불리면(시험이 훅을 부르는 경우) 아무것도 하지 않는다
    try:
        if args.command == "save":
            code = save(args.message, args.quiet)
            return 0 if args.quiet else code
        if args.command == "merge":
            return merge(args.yes)
        return status()
    except (RuntimeError, subprocess.SubprocessError, subprocess.TimeoutExpired, OSError) as exc:
        print(f"[ship] 멈춤 — {exc}")
        return 0 if getattr(args, "quiet", False) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
