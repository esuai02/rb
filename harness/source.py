"""검사 대상 읽기 (작업 Graph Q3 — 검수 Harness).

대상은 Rojo 구조의 소스 트리 하나다(DEC-8 — Git 파일이 정본):
  default.project.json          Rojo 프로젝트 — 폴더가 어느 서비스로 들어가는지(서버/클라이언트에 보이는지)를 정한다
  src/**.luau                   *.server.luau = Script · *.client.luau = LocalScript · *.luau = ModuleScript (F12·F14)
  src/**.csv                    LocalizationTable (F13)
  content/math_claims.yaml      수학 대사의 구조화된 명제 — E1·E2 검사 대상

규칙(허용 이벤트·금지어·번역 금지 패턴)은 저장소의 잠긴 명세(specs/)에서 읽는다 — 고정 데이터가 규칙을 바꾸지 못한다.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from harness import luau

REPO = Path(__file__).resolve().parent.parent
# 서버에서만 보이는 서비스. 나머지(ReplicatedStorage·StarterPlayer·StarterGui·Workspace 등)는 클라이언트가 읽거나 require 할 수 있다
SERVER_ONLY = {"ServerScriptService", "ServerStorage"}
LOCALIZATION_HEADERS = ("Key", "Source", "Context", "Example")


@dataclass
class LuauFile:
    rel: str            # 트리 기준 경로
    container: str      # 최상위 서비스 이름
    kind: str           # Script · LocalScript · ModuleScript
    tokens: list

    @property
    def client_visible(self) -> bool:
        """클라이언트에서 실행되거나 클라이언트가 require 할 수 있는 코드."""
        return self.kind == "LocalScript" or self.container not in SERVER_ONLY

    @property
    def server_only(self) -> bool:
        return not self.client_visible


@dataclass
class Tree:
    root: Path
    luau: list[LuauFile] = field(default_factory=list)
    strings: dict[str, dict[str, str]] = field(default_factory=dict)   # 키 → {열 이름: 문구}
    csv_files: list[str] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)   # 읽다가 생긴 문제 — 검사 실패로 다룬다


@dataclass(frozen=True)
class Rules:
    events: dict
    glossary: dict
    world_spec: dict


def load_rules(repo: Path = REPO) -> Rules:
    read = lambda rel: yaml.safe_load((repo / rel).read_text(encoding="utf-8"))  # noqa: E731
    graph = json.loads((repo / "specs/graph/neo-seoul-city-language-gate.graph.json").read_text(encoding="utf-8"))
    return Rules(read(graph["events"]), read(graph["glossary"]), read(graph["world_spec"]))


def _mappings(node: dict, chain: tuple[str, ...]) -> list[tuple[str, tuple[str, ...]]]:
    out = []
    for name, child in node.items():
        if name.startswith("$") or not isinstance(child, dict):
            continue
        if "$path" in child:
            out.append((child["$path"], chain + (name,)))
        out += _mappings(child, chain + (name,))
    return out


def _kind(name: str) -> str | None:
    for suffix, kind in ((".server.luau", "Script"), (".server.lua", "Script"), (".client.luau", "LocalScript"),
                         (".client.lua", "LocalScript"), (".luau", "ModuleScript"), (".lua", "ModuleScript")):
        if name.endswith(suffix):
            return kind
    return None


def load_tree(root: Path) -> Tree:
    tree = Tree(root)
    project_path = root / "default.project.json"
    try:
        project = json.loads(project_path.read_text(encoding="utf-8"))
        mappings = _mappings(project["tree"], ())
    except (OSError, ValueError, KeyError) as exc:
        tree.problems.append(f"default.project.json 을 읽지 못했다 ({type(exc).__name__})")
        return tree
    mapped = []
    for rel_dir, chain in mappings:
        base = (root / rel_dir).resolve()
        if not base.is_dir() or root.resolve() not in base.parents and base != root.resolve():
            tree.problems.append(f"Rojo 경로 {rel_dir} 가 트리 안의 폴더가 아니다")
            continue
        mapped.append((base, chain[0]))
    for path in sorted(p for p in (root / "src").rglob("*") if p.is_file()) if (root / "src").is_dir() else []:
        rel = path.relative_to(root).as_posix()
        owner = next((container for base, container in mapped if base in path.resolve().parents), None)
        if owner is None:
            tree.problems.append(f"{rel}: Rojo 프로젝트가 어디에도 넣지 않는 파일이다")
            continue
        kind = _kind(path.name)
        if kind:
            try:
                tokens = luau.tokenize(path.read_text(encoding="utf-8"))
            except (luau.LuauSyntaxError, UnicodeDecodeError) as exc:
                tree.problems.append(f"{rel}: Luau 를 읽지 못했다 ({exc})")
                continue
            tree.luau.append(LuauFile(rel, owner, kind, tokens))
        elif path.suffix == ".csv":
            _load_csv(tree, path, rel)
    claims_path = root / "content" / "math_claims.yaml"
    if claims_path.is_file():
        data = yaml.safe_load(claims_path.read_text(encoding="utf-8")) or {}
        tree.claims = data.get("claims", []) if isinstance(data, dict) else []
    return tree


def _load_csv(tree: Tree, path: Path, rel: str) -> None:
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    if not rows or tuple(rows[0][:4]) != LOCALIZATION_HEADERS:
        tree.problems.append(f"{rel}: LocalizationTable 머리줄은 {', '.join(LOCALIZATION_HEADERS)} 로 시작해야 한다")
        return
    header = rows[0]
    tree.csv_files.append(rel)
    for n, row in enumerate(rows[1:], start=2):
        if len(row) != len(header):
            tree.problems.append(f"{rel}:{n} 칸 수가 머리줄과 다르다")
            continue
        key = row[0]
        if key in tree.strings:
            tree.problems.append(f"{rel}:{n} 키 {key} 가 겹친다")
        tree.strings[key] = {h: v for h, v in zip(header[1:], row[1:]) if h not in ("Context", "Example")}
