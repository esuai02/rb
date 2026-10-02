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
BLOCKER_RE = re.compile(r"^\s*[-*]?\s*\**(critical|major|minor)\**\s*\|\s*([^|]*)\|\s*([^|]+)", re.IGNORECASE | re.MULTILINE)


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
    return f"""GOAL: rb 저장소 작업 Graph 단계 {node['id']}({node['label']})의 산출물이 합격 기준과 Intent 불변식을 실제로 만족하는지 독립적으로 검토한다. 단계 결과: {node['outcome']}
SCOPE: 산출물 파일 {', '.join(node['artifacts'])} (저장소 루트 기준). 계약은 graph.json 의 {node['id']} 노드, 불변식은 intent.md §5(INV-1~16), 용어는 intent.md §0.
INVARIANTS: 수정하지 말 것(읽기 전용). 합격 기준:
{crit_lines}
EVIDENCE: 자동 검사 결과(binding {binding[:12]}):
{ev_lines}
STAGE SCOPE: 이 단계가 맡는 불변식: {owned}
다음 단계로 넘긴 것(이 단계의 결함이 아니다 — 넘긴 단계의 기준이 검사한다):
{later}
ASK: 각 합격 기준이 실제로 참인지, 테스트가 기준이 말하는 것을 정말로 검사하는지(빈 검사·우회 가능한 검사 포함), 이 단계가 맡는 불변식을 산출물이 어기는지 찾아라. 넘긴 항목은 지적하지 말고, 넘긴 단계의 기준으로 덮이지 않는 빈틈만 지적하라. 추측은 근거와 함께만.
RETURN: lines of `severity | file:line | claim | evidence | minimal fix` (severity = critical|major|minor), or exactly NO_FINDINGS
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


def parse_review(text: str) -> tuple[str, list[dict]]:
    blockers = [{"severity": m.group(1).lower(), "location": m.group(2).strip(), "claim": m.group(3).strip()} for m in BLOCKER_RE.finditer(text)]
    if not blockers and "NO_FINDINGS" not in text:
        return "UNPARSED", []
    return ("BLOCK" if any(b["severity"] in {"critical", "major"} for b in blockers) else "CLEAR"), blockers


def cmd_review(root: Path, node_id: str) -> int:
    graph = load_graph(root)
    node = node_of(graph, node_id)
    binding = helper_gate(root, node_id)["binding"]
    packet_rel, _ = write_record(root, node_id, "review-packet.md", review_packet(root, graph, node, binding))
    out = root / "outputs" / "verify" / node_id / "review.md"
    ok, tool, message = run_reviewer(root, root / packet_rel, out)
    if not ok or not out.is_file():
        print(f"ESCALATE 독립 리뷰를 받지 못했습니다: {message}")
        return 2
    verdict, blockers = parse_review(out.read_text(encoding="utf-8"))
    if verdict == "UNPARSED":
        print(f"ESCALATE 리뷰 결과 형식을 읽을 수 없습니다 — {out.relative_to(root)} 를 사람이 보고 판단해야 합니다.")
        return 2
    independence = "external" if tool in {"codex", "gemini"} else "fresh_context"
    append(root, {"id": f"R-{node_id}-{binding[:8]}", "kind": "devil_review", "node_id": node_id, "binding": binding,
                  "reviewer": f"{tool} via tri_tool review (read-only)", "independence": independence, "verdict": verdict,
                  "blockers": blockers, "record": out.relative_to(root).as_posix(), "record_sha256": sha(out)})
    successors = [n["id"] for n in graph["nodes"] if node_id in n.get("depends_on", [])]
    for i, b in enumerate(b for b in blockers if b["severity"] == "minor"):
        append(root, {"id": f"DEFER-{node_id}-{binding[:8]}-{i + 1}", "kind": "deferral", "node_id": node_id, "binding": binding,
                      "to": successors[0] if successors else "후속 개정", "claim": b["claim"], "location": b["location"],
                      "rule": "근거 원장 D-MINOR-LIMIT: CLEAR 리뷰의 사소 지적은 다음 단계로 넘겨 기록"})
    print(f"{verdict} 리뷰어={tool} 지적={len(blockers)}건")
    for b in blockers:
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
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
