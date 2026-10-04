#!/usr/bin/env python3
"""rb 단계 검증 — 3층 게이트(근거 원장 D-VERIFY)를 명령 하나로 돌리고 근거 원장에 기록한다.

  verify.py run <Q>                        ① 자동 검사: 기준의 check(명령·6방향)를 실행하고 verification 으로 기록
  verify.py review <Q>                     ② 독립 리뷰: 3도구 어댑터(tri_tool review → Codex)에 패킷을 보내 devil_review 로 기록
  verify.py gate <Q>                       잠금 조건 점검만(기록 없음): 남은 것과 실패를 보여 준다
  verify.py approve <Q> --source "<말>" [--hold ID]   ③ 사람 승인 기록 — 사람이 대화에서 승인한 뒤에만 쓴다(경고 장치 W7 확인 창)
  verify.py lock <Q>                       잠금 시도(masterwork gate --lock, PASS 일 때만 잠긴다)

모든 기록은 그 단계의 현재 binding(계약·Intent·산출물 해시)에 묶인다. 산출물이 바뀌면 기록이 낡으므로 run·review 를 다시 돌린다.
원본 출력은 outputs/verify/<Q>/ 에 남기고 해시를 기록에 적는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_guard  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HELPER = flow_guard.DEFAULT_HELPER
TRI_TOOL = Path.home() / ".claude/scripts/tri_tool.py"
MAKER = "claude-code main session"
CHECK_TIMEOUT_SEC = 600
REVIEW_TIMEOUT_SEC = 900
VECTOR_FIELDS = ("observed", "proposal", "next", "sources")
BLOCKER_RE = re.compile(r"^\s*[-*]?\s*\**(critical|major|minor|residual)\**\s*\|\s*([^|]*)\|\s*([^|]+)", re.IGNORECASE | re.MULTILINE)


# ---------- 공통 ----------

def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_graph(root: Path) -> dict:
    return json.loads((root / "graph.json").read_text(encoding="utf-8"))


def node_of(graph: dict, node_id: str) -> dict:
    for node in graph["nodes"]:
        if node["id"] == node_id:
            return node
    raise SystemExit(f"[verify] graph.json 에 단계 {node_id} 가 없습니다.")


def helper_gate(root: Path, node_id: str, lock: bool = False) -> dict:
    argv = [sys.executable, str(HELPER), "gate", str(root / "graph.json"), "--node", node_id] + (["--lock"] if lock else [])
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    if proc.stdout.strip():
        return json.loads(proc.stdout)
    raise SystemExit(f"[verify] masterwork gate 실패: {(proc.stderr or '').strip()[:300]}")


def ledger(root: Path) -> list[dict]:
    path = root / "evidence.jsonl"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def append(root: Path, row: dict) -> dict:
    taken = {r.get("id") for r in ledger(root)}
    base, n = row["id"], 1
    while row["id"] in taken:
        n += 1
        row["id"] = f"{base}-{n}"
    row = {"timestamp": now(), **row}
    with (root / "evidence.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def write_record(root: Path, node_id: str, name: str, text: str) -> tuple[str, str]:
    out = root / "outputs" / "verify" / node_id / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out.relative_to(root).as_posix(), sha(out)


# ---------- ① 자동 검사 ----------

def scrub(root: Path, text: str) -> str:
    """기록(공개 저장소)에 로컬 경로가 남지 않게 저장소 경로·홈 경로를 바꿔 쓴다 (INV-6)."""
    for local, alias in ((str(root.resolve()), "<repo>"), (str(root), "<repo>"), (str(Path.home()), "~")):
        text = text.replace(local, alias)
    return text


def run_command(root: Path, argv: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=CHECK_TIMEOUT_SEC)
        return proc.returncode, scrub(root, proc.stdout + proc.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 99, scrub(root, f"{type(exc).__name__}: {exc}")


def valid_time(value: object) -> bool:
    try:
        when = datetime.fromisoformat(str(value))
    except ValueError:
        return False
    return when.tzinfo is not None and when <= datetime.now(timezone.utc)


def complete(row: dict) -> bool:
    if not valid_time(row.get("timestamp")):  # Codex 리뷰 R-Q1 4차 minor
        return False
    texts = all(isinstance(row.get(f), str) and row[f].strip() for f in ("observed", "proposal", "next"))
    sources = isinstance(row.get("sources"), list) and row["sources"] and all(isinstance(s, str) and s.strip() for s in row["sources"])
    return bool(texts and sources)


def approval_time(root: Path, node_id: str, binding: str) -> str | None:
    """이 버전에 대한 사람의 잠금 승인 시각. 없으면 None."""
    times = [r["timestamp"] for r in ledger(root) if r.get("kind") == "decision" and r.get("node_id") == node_id
             and r.get("binding") == binding and r.get("decision_id") == f"LOCK-{node_id}" and r.get("value") == "APPROVE"]
    return max(times) if times else None


def check_vectors(root: Path, node_id: str, binding: str) -> tuple[bool, str]:
    intent, _ = flow_guard.load(root)
    wanted = sorted((intent or {}).get("vectors", {}))
    found = {}
    incomplete = []
    for row in ledger(root):
        if row.get("kind") != "vector_review" or row.get("stage") != node_id:
            continue
        approved = approval_time(root, node_id, binding)
        before_approval = approved is None or str(row.get("timestamp", "")) <= approved  # "잠그기 전에" (Codex 리뷰 R-Q1 3차 minor)
        if row.get("binding") == binding and row.get("vector") in wanted and complete(row) and before_approval:  # 2차 minor
            found.setdefault(row.get("vector"), []).append(row.get("id"))
        else:
            incomplete.append(row.get("id"))
    missing = [v for v in wanted if v not in found]
    lines = [f"{v}: {', '.join(found.get(v, [])) or '없음'}" for v in wanted]
    if incomplete:
        lines.append(f"세지 않은 기록(다른 버전이거나 내용이 빠짐): {', '.join(incomplete)} (필수: 지금 binding, {', '.join(VECTOR_FIELDS)})")
    return (not missing and bool(wanted)), "\n".join(lines) + (f"\n빠진 방향: {', '.join(missing)}" if missing else "")


def last_line(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[-1][:200] if lines else "(출력 없음)"


def cmd_run(root: Path, node_id: str) -> int:
    graph = load_graph(root)
    node = node_of(graph, node_id)
    binding = helper_gate(root, node_id)["binding"]
    results = []
    for crit in node["criteria"]:
        check = crit.get("check")
        if not check:
            results.append((crit["id"], "수동", "check 없음 — 사람이 관찰해 기록"))
            continue
        if check.get("type") == "command":
            code, output = run_command(root, check["argv"])
            ok, source = code == 0, " ".join(check["argv"])
            body = f"criterion: {crit['id']} — {crit['statement']}\ncommand: {source}\nexit: {code}\nbinding: {binding}\ntime: {now()}\n\n{output}"
            observed = f"exit {code}; {last_line(output)}"
            etype = "test" if "test" in crit["evidence_types"] else crit["evidence_types"][0]
        elif check.get("type") == "vectors":
            ok, summary = check_vectors(root, node_id, binding)
            source = f"evidence.jsonl vector_review stage={node_id}"
            body = f"criterion: {crit['id']} — {crit['statement']}\nbinding: {binding}\ntime: {now()}\n\n{summary}\n"
            observed = summary.splitlines()[-1] if not ok else "6방향 모두 기록됨"
            etype = "observation"
        else:
            results.append((crit["id"], "수동", f"알 수 없는 check 형식 {check.get('type')}"))
            continue
        record, digest = write_record(root, node_id, f"{crit['id']}.txt", body)
        append(root, {"id": f"V-{crit['id']}-{binding[:8]}", "kind": "verification", "node_id": node_id, "binding": binding,
                      "criterion_id": crit["id"], "result": "PASS" if ok else "FAIL", "evidence_type": etype,
                      "source": source, "observed": observed, "record": record, "record_sha256": digest})
        results.append((crit["id"], "PASS" if ok else "FAIL", observed))
    for cid, result, note in results:
        print(f"{result:5} {cid}  {note}")
    return 0 if all(r[1] != "FAIL" for r in results) else 1


# ---------- ② 독립 리뷰 ----------

def review_packet(root: Path, graph: dict, node: dict, binding: str) -> str:
    latest = {r["criterion_id"]: r for r in ledger(root)  # 같은 binding 을 여러 번 검사했으면 기준마다 마지막 결과만 — 리뷰어에게 모순된 상태를 주지 않는다
              if r.get("kind") == "verification" and r.get("node_id") == node["id"] and r.get("binding") == binding}
    evidence = [latest[c["id"]] for c in node["criteria"] if c["id"] in latest]
    crit_lines = "\n".join(f"- {c['id']}: {c['statement']} (목표: {c['target']})" for c in node["criteria"])
    ev_lines = "\n".join(f"- {r['criterion_id']}: {r['result']} — {r['observed']}" for r in evidence) or "- (자동 검사 기록 없음)"
    scope = node.get("invariant_scope", {})
    owned = ", ".join(scope.get("owned", [])) or "합격 기준에 적힌 것"
    later = "\n".join(f"- {k} → {v}" for k, v in scope.get("later", {}).items()) or "- (없음)"
    rows = ledger(root)
    decisions = "\n".join(f"- {r.get('decision_id', r['id'])}: {r.get('value', '')}" for r in rows
                          if r.get("kind") == "human_decision" and r.get("node_id") == node["id"]) or "- (없음)"
    question = node.get("review_question") or "이 단계의 산출물이 합격 기준을 만족하는가?"
    policy = node.get("review_policy") or {}
    if policy.get("scope") == "fixed":
        last = latest_review(rows, node["id"])
        fixed = "\n".join(f"- {b['severity']} | {b['location']} | {b['claim']}" for b in (last or {}).get("blockers", [])) or "- (없음)"
        known = "\n".join(f"- {r.get('claim', '')}" for r in rows if r.get("kind") == "residual_risk" and r.get("node_id") == node["id"]) or "- (없음)"
        ask = (f"고정 범위 확인 리뷰다(사람 결정 {policy.get('decision', '?')}). 막는 지적(critical·major·minor)은 다음 셋에만 쓴다: "
               "① 고정된 합격 기준이 실제로 거짓이거나 테스트가 기준이 말하는 것을 검사하지 않는다 "
               "② 합격 기준에 이름이 있는 결함 종류가 다시 잡히지 않는다(회귀) "
               "③ 아래 '직전 리뷰 지적' 의 수정이 실제로 효과가 없다. "
               "합격 기준에 없는 새 계열의 빈틈은 severity=residual 로 따로 적는다 — 막지 않고 남은 위험 목록에 기록된다. "
               "residual 의 evidence 칸에는 정직한 저자가 실제로 쓸 법한 코드 예를 적는다. 이미 남은 위험 목록에 있는 것은 다시 적지 않는다.")
        extra = f"""직전 리뷰 지적(이번에 고친 것 — 수정이 실제로 효과 있는지 본다):
{fixed}
이미 남은 위험 목록에 있는 것(다시 적지 말 것):
{known}
"""
        severities = "critical|major|minor|residual"
    else:
        ask = ("각 합격 기준이 실제로 참인지, 테스트가 기준이 말하는 것을 정말로 검사하는지(빈 검사, 정직한 실수로 나올 꼴을 놓치는 검사 포함), "
               "이 단계가 맡는 불변식을 산출물이 어기는지 찾아라. 넘긴 항목은 지적하지 말고, 넘긴 단계의 기준으로 덮이지 않는 빈틈만 지적하라. 추측은 근거와 함께만.")
        extra, severities = "", "critical|major|minor"
    return f"""GOAL: rb 저장소 작업 Graph 단계 {node['id']}({node['label']})의 산출물이 합격 기준과 Intent 불변식을 실제로 만족하는지 독립적으로 검토한다. 단계 결과: {node['outcome']}
SCOPE: 산출물 파일 {', '.join(node['artifacts'])} (저장소 루트 기준). 계약은 graph.json 의 {node['id']} 노드, 불변식은 intent.md §5(INV-1~16), 용어는 intent.md §0.
INVARIANTS: 수정하지 말 것(읽기 전용). 합격 기준:
{crit_lines}
EVIDENCE: 자동 검사 결과(binding {binding[:12]}):
{ev_lines}
STAGE SCOPE: 이 단계가 맡는 불변식: {owned}
다음 단계로 넘긴 것(이 단계의 결함이 아니다 — 넘긴 단계의 기준이 검사한다):
{later}
REVIEW QUESTION: {question}
HUMAN DECISIONS(이 단계에 대한 사람 결정 — 리뷰 범위를 정한다):
{decisions}
{extra}ASK: {ask}
RETURN: lines of `severity | file:line | claim | evidence | minimal fix` (severity = {severities}), or exactly NO_FINDINGS
"""


def run_reviewer(root: Path, packet: Path, out: Path) -> tuple[bool, str, str]:
    """(성공, 실제 리뷰 도구, 메시지). 테스트에서는 이 함수를 바꿔 끼운다."""
    argv = [sys.executable, str(TRI_TOOL), "ask", "review", "--packet", str(packet), "--out", str(out),
            "--cwd", str(root), "--timeout", str(REVIEW_TIMEOUT_SEC)]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=REVIEW_TIMEOUT_SEC + 120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "-", f"{type(exc).__name__}: {exc}"
    match = re.search(r"OK tool=(\S+)", proc.stdout)
    return proc.returncode == 0 and match is not None, match.group(1) if match else "-", (proc.stdout + proc.stderr).strip()[:400]


def parse_review(text: str) -> tuple[str, list[dict], list[dict]]:
    """(판정, 막는 지적, 남은 위험). residual 은 고정 범위 밖의 새 계열 — 잠금을 막지 않고 따로 기록한다(사람 결정 Q3-FIXED-SCOPE)."""
    found = [{"severity": m.group(1).lower(), "location": m.group(2).strip(), "claim": m.group(3).strip()} for m in BLOCKER_RE.finditer(text)]
    blockers = [b for b in found if b["severity"] != "residual"]
    residual = [b for b in found if b["severity"] == "residual"]
    if not found and "NO_FINDINGS" not in text:
        return "UNPARSED", [], []
    return ("BLOCK" if any(b["severity"] in {"critical", "major"} for b in blockers) else "CLEAR"), blockers, residual


def latest_review(rows: list[dict], node_id: str) -> dict | None:
    reviews = [r for r in rows if r.get("kind") == "devil_review" and r.get("node_id") == node_id]
    return reviews[-1] if reviews else None


def review_refusal(root: Path, node: dict, binding: str) -> str | None:
    """리뷰를 받기 전에 기계로 지키는 규칙 — 지키지 못하면 이유를 돌려준다 (근거 원장 AUDIT-PROCESS-1).

    ① 지금 binding 의 자동 검사가 기준마다 있고 모두 PASS 여야 한다 — 실패한 상태로 리뷰를 보내지 않는다.
    ② intent §8 멈춤: 마지막 사람 결정 뒤의 리뷰가 BLOCK 으로 세 번 이어지면서 막는 지적 수가 두 번 연속 줄지 않았으면
       리뷰를 더 보내지 않고 멈춤 기록을 남긴다. 사람 결정이 다음 창을 연다.
    """
    rows = ledger(root)
    latest = {r["criterion_id"]: r for r in rows
              if r.get("kind") == "verification" and r.get("node_id") == node["id"] and r.get("binding") == binding}
    checked = [c["id"] for c in node["criteria"] if c.get("check")]
    missing = [c for c in checked if c not in latest]
    failing = [c for c in checked if c in latest and latest[c].get("result") != "PASS"]
    if missing or failing:
        return f"지금 버전의 자동 검사가 {'없거나 ' if missing else ''}실패했다({', '.join(missing + failing)}) — verify.py run 을 먼저 통과시킨다"
    decided = max((str(r.get("timestamp", "")) for r in rows if r.get("kind") == "human_decision" and r.get("node_id") == node["id"]), default="")
    window = [r for r in rows if r.get("kind") == "devil_review" and r.get("node_id") == node["id"] and str(r.get("timestamp", "")) > decided]
    counts = [sum(b.get("severity") in {"critical", "major"} for b in r.get("blockers", [])) for r in window[-3:]]
    if len(counts) == 3 and all(r.get("verdict") == "BLOCK" for r in window[-3:]) and counts[1] >= counts[0] and counts[2] >= counts[1]:
        return f"intent §8 멈춤 — 막는 지적 수 {counts[0]}→{counts[1]}→{counts[2]} 로 두 번 연속 줄지 않았다. 사람 결정이 있어야 다음 리뷰를 보낸다"
    return None


def cmd_review(root: Path, node_id: str) -> int:
    graph = load_graph(root)
    node = node_of(graph, node_id)
    binding = helper_gate(root, node_id)["binding"]
    refusal = review_refusal(root, node, binding)
    if refusal:
        if refusal.startswith("intent §8"):
            append(root, {"id": f"STOP-{node_id}-auto-{binding[:8]}", "kind": "observation", "node_id": node_id, "binding": binding,
                          "rule": "intent §8 — 한 격차에서 2번 연속 개선이 없으면 멈춘다", "observed": refusal, "applies_to": [node_id]})
        print(f"ESCALATE {refusal}")
        return 2
    packet_rel, _ = write_record(root, node_id, "review-packet.md", review_packet(root, graph, node, binding))
    out = root / "outputs" / "verify" / node_id / "review.md"
    ok, tool, message = run_reviewer(root, root / packet_rel, out)
    if not ok or not out.is_file():
        print(f"ESCALATE 독립 리뷰를 받지 못했습니다: {message}")
        return 2
    verdict, blockers, residual = parse_review(out.read_text(encoding="utf-8"))
    if verdict == "UNPARSED":
        print(f"ESCALATE 리뷰 결과 형식을 읽을 수 없습니다 — {out.relative_to(root)} 를 사람이 보고 판단해야 합니다.")
        return 2
    independence = "external" if tool in {"codex", "gemini"} else "fresh_context"
    append(root, {"id": f"R-{node_id}-{binding[:8]}", "kind": "devil_review", "node_id": node_id, "binding": binding,
                  "reviewer": f"{tool} via tri_tool review (read-only)", "independence": independence, "verdict": verdict,
                  "blockers": blockers, "residual": residual, "record": out.relative_to(root).as_posix(), "record_sha256": sha(out)})
    successors = [n["id"] for n in graph["nodes"] if node_id in n.get("depends_on", [])]
    minors = [b for b in blockers if b["severity"] == "minor"] if verdict == "CLEAR" else []   # D-MINOR-LIMIT: CLEAR 리뷰의 사소 지적만 넘긴다
    for i, b in enumerate(minors):
        append(root, {"id": f"DEFER-{node_id}-{binding[:8]}-{i + 1}", "kind": "deferral", "node_id": node_id, "binding": binding,
                      "to": successors[0] if successors else "후속 개정", "claim": b["claim"], "location": b["location"],
                      "rule": "근거 원장 D-MINOR-LIMIT: CLEAR 리뷰의 사소 지적은 다음 단계로 넘겨 기록"})
    print(f"{verdict} 리뷰어={tool} 지적={len(blockers)}건" + (f" · 남은 위험 후보={len(residual)}건" if residual else ""))
    for b in blockers + residual:
        print(f"  {b['severity']:8} {b['location']}  {b['claim'][:150]}")
    return 0 if verdict == "CLEAR" else 1


# ---------- 게이트·승인·잠금 ----------

def evidence_after_approval(root: Path, node_id: str) -> list[str]:
    """잠그기 전 확인: 지금 버전의 검증·리뷰·6방향 기록은 모두 사람의 잠금 승인보다 먼저여야 한다."""
    binding = helper_gate(root, node_id)["binding"]
    approved = approval_time(root, node_id, binding)
    if approved is None:
        return []
    kinds = {"verification", "devil_review", "vector_review"}
    return [r["id"] for r in ledger(root) if r.get("kind") in kinds and r.get("binding") == binding
            and (r.get("node_id") == node_id or r.get("stage") == node_id) and str(r.get("timestamp", "")) > approved]


def print_gate(result: dict) -> None:
    print(f"{result['verdict']} {result['node_id']} binding={result['binding'][:12]} locked={result.get('locked')}")
    for item in result.get("failures", []):
        print(f"  실패: {item}")
    for item in result.get("missing", []):
        print(f"  남음: {item}")


def cmd_approve(root: Path, node_id: str, source: str, hold: str | None) -> int:
    graph = load_graph(root)
    node = node_of(graph, node_id)
    hold = hold or f"LOCK-{node_id}"
    if hold not in node["human_holds"]:
        raise SystemExit(f"[verify] {node_id} 의 사람 결정 대기에 {hold} 가 없습니다: {node['human_holds']}")
    if not source.strip():
        raise SystemExit("[verify] --source 에 사람이 실제로 한 말과 날짜를 적어야 합니다.")
    binding = helper_gate(root, node_id)["binding"]
    record, digest = write_record(root, node_id, f"{hold}.txt", f"hold: {hold}\nnode: {node_id}\nbinding: {binding}\ntime: {now()}\nsource: {source}\n")
    append(root, {"id": f"D-{hold}-{binding[:8]}", "kind": "decision", "node_id": node_id, "binding": binding, "decision_id": hold,
                  "value": "APPROVE", "origin": "verified_host_user", "source": source, "record": record, "record_sha256": digest})
    print(f"기록됨: {hold} APPROVE ({node_id}, binding {binding[:12]})")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "review", "gate", "lock"):
        sub.add_parser(name).add_argument("node")
    approve = sub.add_parser("approve")
    approve.add_argument("node")
    approve.add_argument("--source", required=True)
    approve.add_argument("--hold")
    args = parser.parse_args(argv)
    if args.command == "run":
        return cmd_run(ROOT, args.node)
    if args.command == "review":
        return cmd_review(ROOT, args.node)
    if args.command == "approve":
        return cmd_approve(ROOT, args.node, args.source, args.hold)
    if args.command == "lock":
        late = evidence_after_approval(ROOT, args.node)
        if late:
            print(f"ESCALATE 사람 승인 뒤에 생긴 기록이 있습니다 — 사람에게 다시 보이고 승인을 다시 받아야 합니다: {', '.join(late)}")
            return 2
    result = helper_gate(ROOT, args.node, lock=args.command == "lock")
    print_gate(result)
    if args.command == "lock" and result["verdict"] == "PASS":
        shipped = ship_locked(args.node)
        if shipped:
            print(f"잠금은 됐지만 내보내기가 끝나지 않았다(코드 {shipped}) — tools/ship.py 의 알림을 보고 다시 돌린다")
            return 3
    return 0 if result["verdict"] == "PASS" else 2


def ship_locked(node: str) -> int:
    """사람이 잠근 단계는 바로 내보낸다 — 잠금 기록을 커밋·푸시하고, 그것이 성공했을 때만 잠긴 단계의 PR 을 병합한다."""
    ship = [sys.executable, str(ROOT / "tools" / "ship.py")]
    saved = subprocess.run([*ship, "save", "-m", f"chore: {node} 잠금 기록"], cwd=ROOT).returncode
    if saved:   # 1 멈춤 · 2 보호 브랜치라 저장하지 않음 — 어느 쪽이든 잠금 기록이 원격에 없으므로 병합하지 않는다
        print("저장·푸시가 끝나지 않아 병합하지 않았다")
        return saved
    return subprocess.run([*ship, "merge", "--yes"], cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
