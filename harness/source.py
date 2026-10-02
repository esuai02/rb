"""검사 대상 읽기 (작업 Graph Q3 — 검수 Harness).

대상은 Rojo 구조의 소스 트리 하나다(DEC-8 — Git 파일이 정본):
  default.project.json          Rojo 프로젝트 — 어느 폴더·파일이 어느 서비스로 들어가는지(서버/클라이언트에 보이는지)를 정한다
  <$path>/**.luau               *.server.luau = Script · *.client.luau = LocalScript · *.luau = ModuleScript (F12·F14)
  <$path>/**.csv                LocalizationTable (F13)
  <$path>/**.model.json·.meta.json·.json·.txt   Rojo 가 인스턴스·속성·문구로 싣는 데이터 — 문자열을 모아 문구·안전 검사에 넣는다
  content/math_claims.yaml      수학 대사의 구조화된 명제 — E1·E2 검사 대상 (Rojo 가 싣지 않는 검사 입력)

Rojo 가 싣는데 읽지 못한 파일(모르는 확장자·이진 모델)은 problems 로 올린다 — 읽지 못한 것을 통과로 보지 않는다.
규칙(허용 이벤트·금지어·번역 금지 패턴)은 저장소의 잠긴 명세(specs/)에서 읽는다 — 고정 데이터가 규칙을 바꾸지 못한다.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from harness import luau, resolve

REPO = Path(__file__).resolve().parent.parent
# 서버에서만 보이는 서비스. 나머지(ReplicatedStorage·StarterPlayer·StarterGui·Workspace 등)는 클라이언트가 읽거나 require 할 수 있다
SERVER_ONLY = {"ServerScriptService", "ServerStorage"}
LOCALIZATION_HEADERS = ("Key", "Source", "Context", "Example")
HARNESS_INPUT = ("content",)        # Rojo 가 싣지 않는 검사 입력 폴더
SOURCE_DIR = "src"                  # Rojo 매핑은 이 폴더 안만 가리킨다
PROJECT_FILE = "default.project.json"
DATA_SUFFIXES = (".model.json", ".meta.json", ".json", ".txt")
UNREADABLE_SUFFIXES = (".rbxm", ".rbxmx")
LUAU_SUFFIXES = ((".server.luau", "Script"), (".server.lua", "Script"), (".client.luau", "LocalScript"),
                 (".client.lua", "LocalScript"), (".luau", "ModuleScript"), (".lua", "ModuleScript"))


@dataclass
class LuauFile:
    rel: str            # 트리 기준 경로
    container: str      # 최상위 서비스 이름
    kind: str           # Script · LocalScript · ModuleScript
    tokens: list
    resolved: dict      # 이름 → 값 (harness.resolve)

    @property
    def name(self) -> str:
        return self.rel.rsplit("/", 1)[-1].split(".")[0]

    @property
    def client_visible(self) -> bool:
        """클라이언트에서 실행되거나 클라이언트가 require 할 수 있는 코드."""
        return self.kind == "LocalScript" or self.container not in SERVER_ONLY

    @property
    def server_only(self) -> bool:
        return not self.client_visible


@dataclass
class DataFile:
    rel: str
    container: str
    strings: list[str]       # 파일에 담긴 문자열 값
    class_names: list[str]   # .model.json 의 $className (인스턴스 종류)


@dataclass
class Tree:
    root: Path
    luau: list[LuauFile] = field(default_factory=list)
    data: list[DataFile] = field(default_factory=list)
    strings: dict[str, dict[str, str]] = field(default_factory=dict)   # 키 → {열 이름: 문구}
    csv_files: list[str] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    contracts: dict = field(default_factory=dict)      # 원격 이벤트 이름 → 받는 값의 계약
    problems: list[str] = field(default_factory=list)   # 읽다가 생긴 문제 — 검사 실패로 다룬다

    def texts(self):
        """(위치, 글자) — LocalizationTable 의 모든 칸, Luau 문자열, 데이터 파일 문자열."""
        for key, row in sorted(self.strings.items()):
            for col, text in row.items():
                yield f"{key}[{col}]", text
        for f in self.luau:
            for t in f.tokens:
                if t.kind == luau.STRING:
                    yield f"{f.rel}:{t.line}", t.text
        for d in self.data:
            for text in d.strings:
                yield d.rel, text


@dataclass(frozen=True)
class Rules:
    events: dict
    glossary: dict
    world_spec: dict
    canonical: dict


def load_rules(repo: Path = REPO) -> Rules:
    read = lambda rel: yaml.safe_load((repo / rel).read_text(encoding="utf-8"))  # noqa: E731
    graph = json.loads((repo / "specs/graph/neo-seoul-city-language-gate.graph.json").read_text(encoding="utf-8"))
    return Rules(read(graph["events"]), read(graph["glossary"]), read(graph["world_spec"]), read(graph["canonical_values"]))


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
    return next((kind for suffix, kind in LUAU_SUFFIXES if name.endswith(suffix)), None)


def load_tree(root: Path) -> Tree:
    tree = Tree(root)
    try:
        project = json.loads((root / PROJECT_FILE).read_text(encoding="utf-8"))
        mappings = _mappings(project["tree"], ())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        tree.problems.append(f"{PROJECT_FILE} 을 읽지 못했다 ({type(exc).__name__})")
        return tree
    owners: dict[Path, str] = {}
    places: dict[Path, tuple[str, ...]] = {}
    for rel_path, chain in mappings:
        shown = "/".join(chain) if Path(str(rel_path)).is_absolute() else rel_path
        if Path(str(rel_path)).is_absolute():
            tree.problems.append(f"Rojo 경로({shown})는 트리 기준 상대 경로여야 한다 — 절대 경로는 사람마다 달라 쓸 수 없다")
            continue
        if not (rel_path == SOURCE_DIR or str(rel_path).startswith(SOURCE_DIR + "/")):
            tree.problems.append(f"Rojo 경로 {shown} 는 소스 폴더({SOURCE_DIR}/) 안이어야 한다 — 검사 범위 밖에 코드를 두지 않는다")
            continue
        target = (root / rel_path).resolve()
        if not target.exists() or (root.resolve() not in target.parents and target != root.resolve()):
            tree.problems.append(f"Rojo 경로 {shown} 가 트리 안에 없다")
            continue
        for path in sorted(target.rglob("*")) if target.is_dir() else [target]:
            if not path.is_file():
                continue
            if path.resolve() in places:
                rel = path.relative_to(root).as_posix()
                tree.problems.append(f"{rel}: 같은 파일을 {'/'.join(places[path.resolve()])} 와 {'/'.join(chain)} 두 곳에 싣는다 — 어디에 있는지 하나여야 한다")
            places.setdefault(path.resolve(), chain)
            owners.setdefault(path.resolve(), chain[0])
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel == PROJECT_FILE:
            continue
        owner = owners.get(path.resolve())
        if rel.split("/", 1)[0] in HARNESS_INPUT:
            if owner is not None:
                tree.problems.append(f"{rel}: 검사 입력 폴더({'/'.join(HARNESS_INPUT)})는 Rojo 에 싣지 않는다 — 게임에 들어가는 파일과 섞이면 안 된다")
            continue
        if owner is None:
            tree.problems.append(f"{rel}: Rojo 프로젝트가 어디에도 넣지 않는 파일이다")
            continue
        _load_file(tree, path, rel, owner)
    _load_claims(tree, root)
    _load_contracts(tree, root)
    return tree


def _load_file(tree: Tree, path: Path, rel: str, owner: str) -> None:
    kind = _kind(path.name)
    try:
        if kind:
            folded = luau.fold_strings(luau.tokenize(path.read_text(encoding="utf-8")))
            tokens = luau.normalize_index(folded, resolve.resolve_names(folded))   # 이름이 가리키는 값을 먼저 풀어야 대괄호를 바꿀 수 있다
            tree.luau.append(LuauFile(rel, owner, kind, tokens, resolve.resolve_names(tokens)))
        elif path.suffix == ".csv":
            _load_csv(tree, path, rel)
        elif path.name.endswith(DATA_SUFFIXES):
            strings, classes = [], []
            _collect(json.loads(path.read_text(encoding="utf-8")), strings, classes) if path.suffix == ".json" \
                else strings.append(path.read_text(encoding="utf-8"))
            tree.data.append(DataFile(rel, owner, strings, classes))
        elif path.name.endswith(UNREADABLE_SUFFIXES):
            tree.problems.append(f"{rel}: Rojo 가 싣는 이진 모델이라 검사할 수 없다 — 소스는 파일로 두어야 한다(DEC-8)")
        else:
            tree.problems.append(f"{rel}: Rojo 가 싣지만 검사할 줄 모르는 파일이다")
    except (OSError, ValueError, UnicodeDecodeError, luau.LuauSyntaxError) as exc:
        tree.problems.append(f"{rel}: 읽지 못했다 ({type(exc).__name__}: {exc})")


def _collect(node, strings: list[str], classes: list[str]) -> None:
    if isinstance(node, dict):
        for name, child in node.items():
            if name == "$className" and isinstance(child, str):
                classes.append(child)
            elif isinstance(child, str) and not name.startswith("$"):
                strings.append(child)
            else:
                _collect(child, strings, classes)
    elif isinstance(node, list):
        for child in node:
            _collect(child, strings, classes)
    elif isinstance(node, str):
        strings.append(node)


def _load_claims(tree: Tree, root: Path) -> None:
    path = root / "content" / "math_claims.yaml"
    if not path.is_file():
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        tree.problems.append(f"content/math_claims.yaml: 읽지 못했다 ({type(exc).__name__})")
        return
    if not isinstance(data, dict) or not isinstance(data.get("claims", []), list):
        tree.problems.append("content/math_claims.yaml: claims 는 목록이어야 한다")
        return
    tree.claims = data.get("claims", [])


def _load_contracts(tree: Tree, root: Path) -> None:
    path = root / "content" / "remote_contracts.yaml"
    if not path.is_file():
        tree.problems.append("content/remote_contracts.yaml 이 없다 — 원격 입력이 무엇을 받는지 적어야 검사할 수 있다")
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        tree.problems.append(f"content/remote_contracts.yaml: 읽지 못했다 ({type(exc).__name__})")
        return
    remotes = data.get("remotes") if isinstance(data, dict) else None
    if not isinstance(remotes, dict):
        tree.problems.append("content/remote_contracts.yaml: remotes 는 이름 → 받는 값 목록이어야 한다")
        return
    tree.contracts = remotes


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
        if not row[1].strip():
            tree.problems.append(f"{rel}:{n} 키 {key} 의 원문(Source)이 비었다")
        tree.strings[key] = {h: v for h, v in zip(header[1:], row[1:]) if h not in ("Context", "Example")}
