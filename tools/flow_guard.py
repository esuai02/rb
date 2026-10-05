#!/usr/bin/env python3
"""rb 흐름 경고 장치 — 구조·순서·절차가 꼬이면 사람에게 알린다 (intent.md §9).

  flow_guard.py scan [--event SessionStart|Stop]   상태 전체 검사 → 화면 경고 (W1·W2·W3·W5·W6·W7·W8)
  flow_guard.py pre                                PreToolUse 입력(stdin JSON) → 확인 창 (W1·W2·W3·W4·W5·W7)

정의는 intent.md(해시에 묶임), 상태는 decisions.md(해시 밖)에서 읽는다. 결정을 기록해도 Diagram·Graph 가 깨지지 않게 하기 위해서다.
경고는 작업을 막지 않는다. pre 는 'ask' 로 사람이 계속 여부를 정하게 하고, scan 은 화면 경고만 낸다.
Diagram·작업 Graph 의 구조·잠금 판정은 masterwork 헬퍼에 맡긴다 (MASTERWORK_HELPER 또는 기본 설치 경로).
장치가 고장 나도 조용히 통과하지 않는다: pre 는 확인 창, scan 은 화면 경고를 낸다.
이 장치는 실수를 잡는 안전망이지 보안 경계가 아니다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

DEFAULT_HELPER = Path(os.environ.get("MASTERWORK_HELPER") or Path.home() / ".claude/skills/masterwork/scripts/masterwork.py").expanduser()
HELPER_TIMEOUT_SEC = 15
REVIEW_HASH_LEN = 12

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
# Studio 를 바꾸지 않는 도구만 허용 목록에 둔다. 모르는 도구는 바꿀 수 있다고 본다.
STUDIO_READ_TOOLS = {
    "script_read", "script_search", "script_grep", "search_game_tree", "inspect_instance",
    "get_studio_state", "get_console_output", "screen_capture", "list_roblox_studios",
    "search_asset", "wait_job_finished",
}
STUDIO_SHELL_RE = re.compile(r"mcp\.bat|studiomcp|mcp_probe\.py", re.IGNORECASE)
# decisions.md 에 "쓰는" 셸 형태만 잡는다(읽기·다른 곳으로 복사는 통과). 놓친 경우는 응답 끝 검사가 상태 변화를 알린다.
DECISIONS_SHELL_WRITE_RE = re.compile(
    r">>?\s*\S*decisions\.md"                                   # 리다이렉트로 덮어쓰기·덧붙이기
    r"|\btee\b[^|;&]*decisions\.md"                              # tee 로 쓰기
    r"|\bsed\b[^|;&]*\s-i[^|;&]*decisions\.md"                   # sed -i
    r"|\b(rm|truncate)\b[^|;&]*decisions\.md"                    # 지우기·비우기
    r"|\b(mv|cp)\b[^|;&]*\s\S*decisions\.md\s*($|[|;&])"         # 대상 자리에 둔 mv·cp
    r"|decisions\.md['\"]\s*\)\s*\.(write_text|write_bytes|open\()"           # Path('decisions.md').write_text
    r"|open\([^)]*decisions\.md[^)]*['\"][wa]['\"]",                         # open('decisions.md', 'w')
    re.IGNORECASE)

# 작업 Graph(graph.json)가 생기기 전에 써도 되는 곳 — Intent·지식·도구. 그 밖(specs/ harness/ src/ …)은 순서 위반이다.
STAGE0_ALLOWED = {
    "intent.md", "decisions.md", "initial-view.json", "evidence.jsonl", "claude.md", "agents.md", "readme.md",
    ".gitignore", ".ignore", ".mcp.json", "docs", "wiki", "tools", "reviews", "graft",
    ".claude", ".git", ".harness-mem", "__pycache__",
}
KNOWLEDGE_DIRS = {"docs", "wiki", "reviews", ".claude"}
# Roblox 자동번역 18개 언어의 언어 코드. 한국어 원본(ko, ko-KR) 밖의 시장·언어 경로는 INV-2 대상이다.
LANG_CODES = "ar|zh|en|fr|de|hi|id|it|ja|ko|pl|pt|ru|es|th|tr|vi"
MARKET_SEGMENT_RE = re.compile(rf"^({LANG_CODES})([-_][a-z0-9]{{2,8}})*$", re.IGNORECASE)
ORIGINAL_MARKETS = {"ko", "ko-kr", "ko_kr"}

INTENT_ROW_RE = re.compile(r"^\|\s*(Q\d+|DEC-\d+|INV-\d+|W\d+|V-[A-Z]+)\s*\|(.*)$", re.MULTILINE)
DECISION_ROW_RE = re.compile(r"^\|\s*(REVIEW|DEC-\d+)\s*\|(.*)$", re.MULTILINE)
DECISION_STATES = {"열림", "결정됨"}
REVIEW_HASH_RE = re.compile(r"\b([0-9a-f]{%d})\b" % REVIEW_HASH_LEN)


# ---------- 읽기 ----------

def cells(rest: str) -> list[str]:
    return [c.strip() for c in rest.split("|")]


def parse_intent(text: str) -> dict:
    """intent.md 의 정의: 상태 표(Q, 선행), 결정 정의(DEC, 막는 범위), 형식 문제."""
    seen, duplicates, q_ids, q_deps, dec_blocks, vectors, problems = set(), [], [], {}, {}, {}, []
    for row_id, rest in INTENT_ROW_RE.findall(text):
        if row_id in seen:
            duplicates.append(row_id)
        seen.add(row_id)
        row = cells(rest)
        if row_id.startswith("Q"):
            q_ids.append(row_id)
            q_deps[row_id] = re.findall(r"\bQ\d+\b", row[2]) if len(row) > 2 else []
        elif row_id.startswith("DEC-"):
            dec_blocks[row_id] = row[1] if len(row) > 1 else ""
        elif row_id.startswith("V-"):
            cadence = row[2] if len(row) > 2 else ""
            if cadence.isdigit() and int(cadence) > 0:
                vectors[row_id] = {"name": row[0], "days": int(cadence)}
            else:
                problems.append(f"[W5] intent.md §11 {row_id} 의 주기(일) '{cadence}' 를 읽을 수 없습니다.")
    if not q_ids:
        problems.append("[W5] intent.md 에 품질 상태 표(Q1…)가 없습니다.")
    if "DEC-2" not in dec_blocks:
        problems.append("[W5] intent.md 결정 표에 DEC-2(스테이징 Place)가 없습니다 — Studio 수정 경고(W4)가 기준을 잃습니다.")
    for row_id in sorted(set(duplicates)):
        problems.append(f"[W5] intent.md 에 ID {row_id} 가 두 번 이상 있습니다.")
    return {"q_ids": q_ids, "q_deps": q_deps, "dec_blocks": dec_blocks, "vectors": vectors, "problems": problems}


def parse_decisions(text: str) -> dict:
    """decisions.md 의 상태: REVIEW·DEC 행의 상태·내용·근거."""
    rows, problems = {}, []
    for row_id, rest in DECISION_ROW_RE.findall(text):
        state, content, source = (cells(rest) + ["", "", ""])[:3]
        if row_id in rows:
            problems.append(f"[W5] decisions.md 에 {row_id} 행이 두 번 이상 있습니다.")
        if state not in DECISION_STATES:
            problems.append(f"[W5] decisions.md {row_id} 의 상태 '{state}' 를 읽을 수 없습니다 (열림/결정됨만 허용).")
        elif state == "결정됨" and not source:
            problems.append(f"[W7] decisions.md {row_id} 가 결정됨인데 근거(사람의 말·날짜)가 비어 있습니다.")
        rows[row_id] = {"state": state, "content": content, "source": source}
    if "REVIEW" not in rows:
        problems.append("[W5] decisions.md 에 REVIEW(Intent 검토) 행이 없습니다.")
    return {"rows": rows, "problems": problems}


def read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def intent_hash(root: Path) -> str | None:
    path = root / "intent.md"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def load(root: Path) -> tuple[dict | None, dict | None]:
    intent_text, decisions_text = read_text(root / "intent.md"), read_text(root / "decisions.md")
    intent = parse_intent(intent_text) if intent_text is not None else None
    decisions = parse_decisions(decisions_text) if decisions_text is not None else None
    return intent, decisions


def decision_state(decisions: dict | None, dec_id: str) -> str:
    return ((decisions or {}).get("rows", {}).get(dec_id) or {}).get("state", "열림")


def review_state(root: Path, decisions: dict | None) -> str:
    """REVIEWED: 검토 행이 결정됨이고 거기 적힌 해시가 지금 intent.md 와 같다. STALE: 결정됨이지만 그 뒤 Intent 가 바뀜."""
    row = (decisions or {}).get("rows", {}).get("REVIEW")
    if not row or row["state"] != "결정됨":
        return "DRAFT"
    match = REVIEW_HASH_RE.search(row["content"])
    current = intent_hash(root) or ""
    return "REVIEWED" if match and current.startswith(match.group(1)) else "STALE"


# ---------- masterwork 헬퍼 ----------

def run_helper(helper: Path, command: str, doc: Path) -> tuple[bool, Any]:
    proc = subprocess.run([sys.executable, str(helper), command, str(doc)],
                          capture_output=True, text=True, timeout=HELPER_TIMEOUT_SEC)
    if proc.returncode == 0:
        return True, json.loads(proc.stdout)
    try:
        message = json.loads(proc.stderr.strip().splitlines()[-1])["error"]
    except (ValueError, KeyError, IndexError):
        message = (proc.stderr or proc.stdout).strip()[:300] or f"exit {proc.returncode}"
    return False, message


def check_doc(helper: Path, doc: Path, label: str, code: str) -> list[str]:
    ok, result = run_helper(helper, "validate", doc)
    if ok:
        return []
    if "Intent changed" in result:
        return [f"[W1] {label}을(를) 만든 뒤 intent.md 가 바뀌었습니다 — {label}을(를) 다시 만들고 다시 검토해야 합니다."]
    return [f"[{code}] {label} 검사 실패: {result}"]


def graph_statuses(helper: Path, graph: Path) -> dict | None:
    ok, result = run_helper(helper, "status", graph)
    return result if ok else None


# ---------- 경로 ----------

def relative_path(root: Path, target: str | None) -> str | None:
    if not target:
        return None
    path = Path(target)
    path = path if path.is_absolute() else root / path
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def norm(path: str) -> str:
    """경로 비교용: './' 제거, 슬래시 통일, 대소문자 무시(/mnt/d 는 대소문자를 구분하지 않는다)."""
    text = PurePosixPath(path.replace("\\", "/")).as_posix()
    while text.startswith("./"):
        text = text[2:]
    return text.rstrip("/").casefold()


def stage0_allowed(rel: str) -> bool:
    return norm(rel).split("/")[0] in STAGE0_ALLOWED


def other_market(rel: str) -> str | None:
    """한국어 원본 밖의 시장·언어 경로 조각(예: en-US). 지식 폴더 안은 조사 자료라 보지 않는다."""
    parts = PurePosixPath(rel).parts
    if not parts or parts[0].casefold() in KNOWLEDGE_DIRS:
        return None
    for part in list(parts[:-1]) + [PurePosixPath(parts[-1]).stem]:
        if MARKET_SEGMENT_RE.match(part) and part.casefold() not in ORIGINAL_MARKETS:
            return part
    return None


# ---------- 작업 Graph 순서 ----------

def owners(graph_doc: dict, rel: str) -> list[dict]:
    """rel 을 산출물로 가진 작업 Graph 노드들. 산출물이 폴더면 그 아래 파일도 포함한다."""
    target, found = norm(rel), []
    for node in graph_doc.get("nodes", []):
        for artifact in node.get("artifacts", []):
            prefix = norm(artifact)
            if target == prefix or target.startswith(prefix + "/"):
                found.append(node)
                break
    return found


def ancestors(graph_doc: dict, node_id: str) -> set[str]:
    by_id = {n["id"]: n for n in graph_doc.get("nodes", [])}
    result, stack = set(), list(by_id.get(node_id, {}).get("depends_on", []))
    while stack:
        dep = stack.pop()
        if dep not in result and dep in by_id:
            result.add(dep)
            stack.extend(by_id[dep].get("depends_on", []))
    return result


def descendants(graph_doc: dict, node_id: str) -> list[str]:
    return sorted(n["id"] for n in graph_doc.get("nodes", []) if node_id in ancestors(graph_doc, n["id"]))


def order_problem(graph_doc: dict, statuses: dict, node: dict, rel: str) -> str | None:
    node_id = node["id"]
    if statuses.get(node_id) == "LOCKED":
        after = ", ".join(descendants(graph_doc, node_id)) or "없음"
        return f"[W2] 잠긴 단계 {node_id}({node['label']})의 산출물 {rel} 을(를) 고치려 합니다. 고치면 {node_id} 와 뒤 단계({after})가 다시 열립니다(REOPEN). 계속할까요?"
    unlocked = sorted(d for d in ancestors(graph_doc, node_id) if statuses.get(d) != "LOCKED")
    if unlocked:
        return f"[W2] 앞 단계 {', '.join(unlocked)} 이(가) 잠기지 않았는데 뒤 단계 {node_id}({node['label']})의 산출물 {rel} 을(를) 고치려 합니다. 순서가 꼬일 수 있습니다. 계속할까요?"
    return None


def check_order(root: Path, helper: Path, rel: str) -> dict | None:
    graph = root / "graph.json"
    if not graph.is_file():
        if not stage0_allowed(rel):
            return ask(f"[W2] 작업 Graph(graph.json, 순서 계약)가 생기기 전에 제품 산출물 {rel} 을(를) 만들려 합니다. 순서: Intent 검토 → 작업 Graph → 각 단계 산출물. 계속할까요?")
        return None
    if not helper.is_file():
        return ask(f"[W2] 검증 도구(masterwork 헬퍼)가 없어 {rel} 의 단계 순서를 판정할 수 없습니다. 계속할까요?")
    statuses = graph_statuses(helper, graph)
    if statuses is None:
        return ask(f"[W2] 작업 Graph 를 읽을 수 없어 {rel} 의 단계 순서를 판정할 수 없습니다(Intent 가 바뀌었거나 Graph 가 깨짐). 계속할까요?")
    graph_doc = json.loads(graph.read_text(encoding="utf-8"))
    for node in owners(graph_doc, rel):
        problem = order_problem(graph_doc, statuses, node, rel)
        if problem:
            return ask(problem)
    return None


# ---------- pre ----------

def ask(message: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                   "permissionDecisionReason": message, "additionalContext": message}}


def note(message: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": message}}


def is_studio_tool(tool: str) -> bool:
    """MCP 도구 이름 mcp__<서버>__<도구> 에서 서버 이름에 roblox 가 들어 있으면 Studio 도구로 본다."""
    parts = tool.split("__")
    return len(parts) >= 3 and parts[0] == "mcp" and "roblox" in parts[1].lower()


def studio_gate(decisions: dict | None, what: str) -> dict:
    if decision_state(decisions, "DEC-2") != "결정됨":
        return ask(f"[W4] 스테이징 Place(DEC-2)가 정해지기 전에 {what}. 지금 열린 Place 가 운영 Place 라면 되돌리기 어렵습니다. 계속할까요?")
    return note("[W4] DEC-2 결정됨 — Studio 를 바꾸기 전에 get_studio_state 로 열린 Place 가 decisions.md 의 스테이징 Place 인지 확인하세요.")


def pre_bash(command: str, decisions: dict | None) -> dict | None:
    if re.search(r"verify\.py\s+approve\b", command):
        return ask("[W7] 사람 승인 기록(verify.py approve)을 남기려 합니다. 사람이 대화에서 직접 승인한 내용인지 확인하세요. 계속할까요?")
    if DECISIONS_SHELL_WRITE_RE.search(command):
        return ask("[W7] 셸 명령으로 decisions.md(사람의 결정 기록)를 바꾸려 합니다. 사람이 실제로 정한 내용인지 확인하세요. 계속할까요?")
    if STUDIO_SHELL_RE.search(command):
        return studio_gate(decisions, "셸에서 Studio MCP 를 직접 부르려 합니다(어떤 도구를 부르는지 이 장치는 판단할 수 없습니다)")
    return None


def pre_edit(root: Path, helper: Path, rel: str, decisions: dict | None) -> dict | None:
    key = norm(rel)
    if key == "decisions.md":
        return ask("[W7] decisions.md(사람의 결정·검토 기록)를 고치려 합니다. 근거 칸에 사람이 실제로 한 말과 날짜가 있어야 합니다. 계속할까요?")
    if key == "graph.json":
        if review_state(root, decisions) != "REVIEWED":
            return ask("[W3] Intent 검토(decisions.md REVIEW)가 지금 버전으로 끝나지 않았는데 작업 Graph(graph.json)를 쓰려 합니다. 순서: Intent 검토 → Graph. 계속할까요?")
        return None
    if key == "intent.md":
        if (root / "graph.json").is_file():
            return ask("[W1] 작업 Graph 가 이미 있는데 intent.md 를 고치려 합니다. 고치면 Diagram·Graph 를 다시 만들어야 하고 잠긴 단계가 모두 다시 열립니다. 목표·범위·기준 변경이면 사람의 결정이 필요합니다. 계속할까요?")
        return None
    if key == "initial-view.json":
        return ask("[W1] Diagram 데이터(initial-view.json)를 직접 고치려 합니다. 사람이 본 Diagram 과 달라집니다. 계속할까요?")
    if key == "evidence.jsonl":
        return ask("[W7] 근거 원장(evidence.jsonl)은 끝에 추가만 합니다. 기존 줄을 고치거나 덮어쓰려 합니다. 계속할까요?")
    market = other_market(rel)
    if market:
        return ask(f"[W2] 한국어 원본 밖 시장·언어({market}) 경로 {rel} 을(를) 쓰려 합니다. INV-2: 한국어 원본 검증 전에는 다른 시장은 키 자리만 둡니다. 계속할까요?")
    return check_order(root, helper, rel)


def pre(payload: dict, root: Path, helper: Path) -> dict | None:
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    _, decisions = load(root)
    if is_studio_tool(tool):
        name = tool.rsplit("__", 1)[-1]
        return None if name in STUDIO_READ_TOOLS else studio_gate(decisions, f"Studio 를 바꿀 수 있는 도구 '{name}' 를 쓰려 합니다")
    if tool == "Bash":
        return pre_bash(tool_input.get("command") or "", decisions)
    if tool not in EDIT_TOOLS:
        return None
    rel = relative_path(root, tool_input.get("file_path") or tool_input.get("notebook_path"))
    return pre_edit(root, helper, rel, decisions) if rel else None


# ---------- scan ----------

def check_view_shape(view: Path, intent: dict, label: str = "Diagram") -> list[str]:
    """Diagram·작업 Graph 의 노드와 선행 관계가 intent.md §3 과 같은지 본다."""
    try:
        nodes = json.loads(view.read_text(encoding="utf-8"))["nodes"]
        shape = {n["id"]: sorted(n.get("depends_on", [])) for n in nodes}
    except (ValueError, KeyError, TypeError):
        return [f"[W5] {label} 파일({view.name})을 읽을 수 없습니다."]
    if list(shape) != intent["q_ids"]:
        return [f"[W5] {label} 노드 {list(shape)} 와 intent.md 상태 표 {intent['q_ids']} 가 다릅니다."]
    wrong = [q for q in shape if shape[q] != sorted(intent["q_deps"].get(q, []))]
    return [f"[W5] {label} 의 선행 관계가 intent.md §3 선행 칸과 다릅니다: {', '.join(wrong)}"] if wrong else []


def scan_decisions(root: Path, intent: dict, decisions: dict | None) -> list[str]:
    if decisions is None:
        return ["[W5] decisions.md 가 없습니다 — 결정·검토 상태를 읽을 수 없습니다."]
    warnings = list(decisions["problems"])
    defined = set(intent["dec_blocks"])
    recorded = {k for k in decisions["rows"] if k.startswith("DEC-")}
    if defined - recorded:
        warnings.append(f"[W5] intent.md 에 정의됐지만 decisions.md 에 없는 결정: {', '.join(sorted(defined - recorded))}")
    if recorded - defined:
        warnings.append(f"[W5] decisions.md 에만 있는 결정: {', '.join(sorted(recorded - defined))}")
    review = review_state(root, decisions)
    if review == "STALE":
        warnings.append("[W1] Intent 검토(REVIEW) 뒤에 intent.md 가 바뀌었습니다 — 바뀐 버전으로 다시 검토해야 합니다.")
    if review == "REVIEWED":
        open_blockers = sorted(d for d, blocks in intent["dec_blocks"].items()
                               if "Intent" in blocks and decision_state(decisions, d) != "결정됨")
        if open_blockers:
            warnings.append(f"[W3] Intent 검토가 끝난 것으로 기록됐지만 Intent 검토를 막는 결정이 열려 있습니다: {', '.join(open_blockers)}")
    return warnings


def scan_order(root: Path, statuses: dict | None) -> list[str]:
    graph = root / "graph.json"
    if not graph.is_file():
        early = sorted(p.name for p in root.iterdir() if p.name.casefold() not in STAGE0_ALLOWED)
        return [f"[W2] 작업 Graph 가 생기기 전에 만들어진 산출물: {', '.join(early)} — 순서: Intent 검토 → 작업 Graph → 산출물."] if early else []
    if statuses is None:
        return []
    graph_doc = json.loads(graph.read_text(encoding="utf-8"))
    warnings = []
    for node in graph_doc.get("nodes", []):
        present = [a for a in node.get("artifacts", []) if (root / a).exists()]
        unlocked = sorted(d for d in ancestors(graph_doc, node["id"]) if statuses.get(d) != "LOCKED")
        if present and unlocked:
            warnings.append(f"[W2] 앞 단계 {', '.join(unlocked)} 이(가) 잠기지 않았는데 {node['id']} 의 산출물이 이미 있습니다: {', '.join(present)}")
    return warnings


def last_vector_reviews(root: Path) -> dict[str, datetime]:
    """근거 원장의 vector_review 기록에서 방향별 가장 최근 점검 시각."""
    latest: dict[str, datetime] = {}
    path = root / "evidence.jsonl"
    if not path.is_file():
        return latest
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if row.get("kind") != "vector_review":
                continue
            when = datetime.fromisoformat(row["timestamp"])
        except (ValueError, KeyError, TypeError):
            continue
        when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        vector = row.get("vector")
        if vector and (vector not in latest or when > latest[vector]):
            latest[vector] = when
    return latest


def scan_vectors(root: Path, intent: dict, now: datetime | None = None) -> list[str]:
    """§11 6방향 점검이 주기를 넘겼거나 한 번도 없으면 알린다 (W8)."""
    now = now or datetime.now(timezone.utc)
    latest = last_vector_reviews(root)
    never, overdue = [], []
    for vector_id, spec in intent.get("vectors", {}).items():
        label = f"{vector_id}({spec['name']})"
        if vector_id not in latest:
            never.append(label)
            continue
        age = (now - latest[vector_id]).days
        if age > spec["days"]:
            overdue.append(f"{label} {age}일 전(주기 {spec['days']}일)")
    warnings = []
    if never:
        warnings.append(f"[W8] 6방향 점검 기록이 한 번도 없는 방향: {', '.join(never)} — intent.md §11")
    if overdue:
        warnings.append(f"[W8] 6방향 점검 주기를 넘긴 방향: {', '.join(overdue)} — 점검하고 evidence.jsonl 에 vector_review 로 남기세요.")
    return warnings


def scan_changes(root: Path, decisions: dict | None) -> list[str]:
    """결정 상태와 Diagram 이 지난 검사 뒤 바뀌었으면 한 번 알린다. 셸로 바꾼 경우도 여기서 잡힌다."""
    state_path = root / ".claude/state/flow_guard.json"
    view = root / "initial-view.json"
    current = {
        "decisions": {k: v["state"] for k, v in (decisions or {}).get("rows", {}).items()},
        "view": hashlib.sha256(view.read_bytes()).hexdigest() if view.is_file() else None,
    }
    try:
        previous = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = None
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
    if previous is None:
        return []
    notices = []
    for dec_id, state in current["decisions"].items():
        before = previous.get("decisions", {}).get(dec_id)
        if before and before != state:
            source = decisions["rows"][dec_id]["source"] or "근거 없음"
            notices.append(f"[W7] 결정 상태가 바뀌었습니다: {dec_id} {before} → {state} (근거: {source}) — 사람이 실제로 정한 것이 맞는지 확인하세요.")
    if previous.get("view") and current["view"] != previous.get("view"):
        notices.append("[W1] Diagram(initial-view.json)이 다시 만들어졌습니다 — 사람이 새 Diagram 을 볼 차례입니다.")
    return notices


def scan(root: Path, helper: Path) -> list[str]:
    intent, decisions = load(root)
    if intent is None:
        return ["[W5] intent.md 가 없습니다 — 목표·순서·결정의 정의가 사라졌습니다."]
    warnings = list(intent["problems"]) + scan_decisions(root, intent, decisions)
    view, graph = root / "initial-view.json", root / "graph.json"
    statuses = None
    if not helper.is_file():
        warnings.append(f"[W5] 검증 도구(masterwork 헬퍼)를 찾지 못해 Diagram·Graph 검사를 못 했습니다: {helper}")
    else:
        if view.is_file():
            warnings += check_doc(helper, view, "Diagram", "W5")
        if graph.is_file():
            graph_warnings = check_doc(helper, graph, "작업 Graph", "W6")
            warnings += graph_warnings
            statuses = graph_statuses(helper, graph) if not graph_warnings else None
            reopened = sorted(k for k, v in (statuses or {}).items() if v == "REOPENED")
            if reopened:
                warnings.append(f"[W6] 다시 열린 단계: {', '.join(reopened)} — 잠근 뒤 Intent·산출물·근거 중 무엇이 바뀌었습니다. 이 단계와 뒤 단계를 다시 검증해야 합니다.")
    if view.is_file():
        warnings += check_view_shape(view, intent)
    if graph.is_file():
        warnings += check_view_shape(graph, intent, "작업 Graph")
        if review_state(root, decisions) != "REVIEWED":
            warnings.append("[W3] 지금 버전의 Intent 가 검토되지 않았는데 작업 Graph(graph.json)가 있습니다. 순서: Intent 검토 → Graph.")
        if not view.is_file():
            warnings.append("[W3] Diagram(initial-view.json) 없이 작업 Graph 가 있습니다. 순서: Intent → Diagram → Graph.")
    warnings += scan_order(root, statuses)
    warnings += scan_vectors(root, intent)
    warnings += scan_changes(root, decisions)
    return warnings


# ---------- 출력 ----------

def emit(payload: dict | None) -> None:
    if payload:
        print(json.dumps(payload, ensure_ascii=False))


def scan_output(warnings: list[str], event: str) -> dict | None:
    if not warnings:
        return None
    message = f"⚠️ 구조·순서 경고 {len(warnings)}건 (intent.md §9)\n" + "\n".join(f"- {w}" for w in warnings)
    output = {"systemMessage": message}
    if event == "SessionStart":
        output["hookSpecificOutput"] = {"hookEventName": "SessionStart", "additionalContext": message}
    return output


def main(argv: list[str]) -> int:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parent.parent)
    helper = Path(os.environ.get("MASTERWORK_HELPER") or DEFAULT_HELPER)
    command = argv[1] if len(argv) > 1 else ""
    if command == "pre":
        try:
            emit(pre(json.loads(sys.stdin.read() or "{}"), root, helper))
        except Exception as exc:  # 판정을 못 하면 통과시키지 않고 사람에게 묻는다
            emit(ask(f"[W5] 흐름 경고 장치가 이 작업을 판정하지 못했습니다 ({type(exc).__name__}: {exc}). 계속할까요?"))
        return 0
    if command == "scan":
        event = argv[3] if len(argv) > 3 and argv[2] == "--event" else "Stop"
        try:
            emit(scan_output(scan(root, helper), event))
        except Exception as exc:  # 장치가 고장 나도 조용히 통과하지 않는다
            emit({"systemMessage": f"⚠️ [W5] 흐름 경고 장치 자체가 실패했습니다 (tools/flow_guard.py scan): {type(exc).__name__}: {exc}"})
        return 0
    print(__doc__, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
