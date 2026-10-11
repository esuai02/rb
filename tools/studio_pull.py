#!/usr/bin/env python3
"""Studio 에서 만든 것(Place 몫 — DEC-8)을 읽어 저장소 place/ 에 사본으로 남긴다. Place 는 바꾸지 않는다.

  python3 tools/studio_pull.py [--now] [--quiet]

- Studio 가 열려 있고 스테이징 Place(DEC-2)일 때만 읽는다. 저장 버튼을 누르지 않아도 지금 열린 모습을 읽는다.
  Studio 가 꺼졌거나 Play 중이면 알리고 끝낸다 — 세션을 막지 않는다(늘 0 으로 끝난다).
- 저장소가 정본인 코드(Rojo 가 넣는 자리)·보는 카메라·Play 때 코드가 짓는 월드는 빼고, 그 밖의 것을
  항목(서비스의 자식)마다 place/<서비스>/<이름>.rbxmx 로 쓴다. 조명 같은 서비스 설정값은 place/settings.json.
  Studio 에서 지운 항목은 place/ 에서도 지운다.
- 공개 저장소(DEC-3): 쓰기 전에 ship.py 누출 검사에 Studio 계정 이름·번호를 더해 검사하고, 걸린 항목은 쓰지 않는다.
  계정 이름·번호는 저장소 밖(.git/info/rb-private)에만 적어 ship.py 가 모든 커밋에서도 찾게 한다.
- 올리는 일은 ship.py save 가 한다 — Stop 훅이 이 도구 다음에 save 를 부른다. 10분에 한 번만 읽는다(--now 는 바로).
- place/ 는 이 도구만 쓰는 자리다. 사람이 넣은 .rbxmx 도 Studio 에 없으면 지운다 — 사본은 손으로 고치지 않는다.
"""
from __future__ import annotations

import argparse
import base64
import json
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ship  # noqa: E402

REPO = ship.REPO
PLACE = REPO / "place"
PROJECT = REPO / "world" / "default.project.json"
STAGING = "rb-staging.rbxlx"   # DEC-2 — 이 Place 가 열려 있을 때만 읽는다
# WSL 에서 Studio MCP 프록시를 부르는 명령 — Claude Code 에 등록한 것과 같다 (docs/02-start-here.md §2)
STUDIO = ["/init", "/mnt/c/Windows/System32/cmd.exe", "/c", r"%LOCALAPPDATA%\Roblox\mcp.bat"]
STUDIO_CWD = "/mnt/c/Windows/System32"   # cmd.exe 는 9p 마운트 작업 폴더를 싫어한다
INTERVAL_S = 600
CONNECT_TRIES = 3
CONNECT_WAIT_S = 4
BUDGET_S = 45            # Stop 훅 600초 안에서 뒤따르는 ship save(540초)와 함께 끝나게
WINDOW = 90_000          # execute_luau 결과는 약 10만 자에서 잘린다(2026-10-06 실측) — 그 아래로 나눠 받는다
MAX_ITEM_BYTES = 8_000_000   # 이보다 큰 항목은 사본에서 빼고 알린다 — 공개 저장소에 큰 덩어리를 쌓지 않는다
MAX_XML_BYTES = 20_000_000   # XML 은 바이너리보다 몇 배 크다 — GitHub 파일 한도(100MB)에 닿지 않게 따로 잰다
MAX_TOTAL_CHARS = 12_000_000   # 한 번에 옮기는 base64 글자 — 창 133개(실측 창당 0.06~0.2초)라 예산 안에 든다. 넘는 항목은 다음으로 미룬다
# 항목을 읽는 그릇 — 서비스(와 그 아래 그릇)의 자식 하나가 항목 하나다
CONTAINERS = ["Workspace", "Lighting", "ReplicatedFirst", "ReplicatedStorage", "ServerScriptService", "ServerStorage",
              "StarterGui", "StarterPack", "StarterPlayer/StarterPlayerScripts", "StarterPlayer/StarterCharacterScripts",
              "SoundService", "Teams", "MaterialService"]
# Play 때 WorldBuilder 가 짓는 월드 — 저장소 코드가 정본이다
SKIP = ["Workspace/CityLanguageGateWorld"]
SETTINGS = ["Lighting", "Workspace", "SoundService", "StarterPlayer"]
SKIP_PROPS = ["Name", "Archivable", "Capabilities", "Sandboxed"]
ENCODED = re.compile(r"<(BinaryString|SharedString)\b([^>]*)>(?:<!\[CDATA\[)?([A-Za-z0-9+/=\s]*)(?:\]\]>)?</\1>")
TEXT_BLOBS = re.compile(r'name="(?:AttributesSerialize|Tags)"')   # 글자를 담는 덩어리 — 속성 값·태그 이름
BINARY_MIN = 6   # 이진 자료에서 찾는 값의 최소 길이 — 짧은 값은 우연히 나온다
UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}

# 읽기만 한다: 내용을 담는 서비스(그릇)는 FindService 로 찾는다 — GetService 는 Teams 처럼 없는 그릇을 새로 만든다.
# 직렬화·인코딩·반사·HttpService·Players·StudioService 같은 엔진 도구 서비스는 GetService 로 부른다(Place 내용을 만들지 않는다).
# 결과가 잘리지 않게 한 번에 다 돌려주지 않고 _G 에 담아 두면 다음 호출들이 나눠 가져간다(호출 사이에 _G 가 남는다 — 실측).
MANIFEST = r"""
local http = game:GetService("HttpService")
local ARGS = http:JSONDecode([==[__ARGS__]==])
if game.Name ~= ARGS.place then
	return "!place"
end
local ser = game:GetService("SerializationService")
local enc = game:GetService("EncodingService")
local refl = game:GetService("ReflectionService")

local function owned(path)
	for _, root in ARGS.rojo do
		if path == root or string.sub(path, 1, #root + 1) == root .. "/" then
			return true
		end
	end
	return ARGS.skip[path] == true
end

local function find(spec)
	local node = nil
	for name in string.gmatch(spec, "[^/]+") do
		node = if node == nil then game:FindService(name) else node:FindFirstChild(name)
		if node == nil then
			return nil
		end
	end
	return node
end

local function number(value)
	if value ~= value or math.abs(value) == math.huge then
		return tostring(value)
	end
	return tonumber(string.format("%.6g", value))
end

local items, blobs, total = {}, {}, 0
for _, spec in ARGS.containers do
	local container = find(spec)
	if container then
		for _, child in container:GetChildren() do
			local path = spec .. "/" .. child.Name
			if child ~= workspace.CurrentCamera and not owned(path) then
				local entry = {container = spec, name = child.Name, class = child.ClassName, scripts = 0, size = 0}
				for _, item in child:GetDescendants() do
					if item:IsA("LuaSourceContainer") then
						entry.scripts += 1
					end
				end
				if child:IsA("LuaSourceContainer") then
					entry.scripts += 1
				end
				local ok, data = pcall(function()
					return ser:SerializeInstancesAsync({child})
				end)
				if not ok then
					entry.error = tostring(data)
				elseif buffer.len(data) > ARGS.maxBytes then
					entry.error = "too_big " .. buffer.len(data)
				else
					local text = buffer.tostring(enc:Base64Encode(data))
					if total + #text > ARGS.maxTotal then
						entry.error = "deferred " .. #text
					else
						total += #text
						entry.size = #text
						table.insert(blobs, text)
					end
				end
				table.insert(items, entry)
			end
		end
	end
end

local settings = {}
for _, name in ARGS.settings do
	local service = game:FindService(name)
	local okList, props = pcall(function()
		return refl:GetPropertiesOfClass(name)
	end)
	if service and okList then
		local values = {}
		for _, prop in props do
			local key = prop.Name
			if prop.Serialized and string.match(key, "^%u") and not table.find(ARGS.skipProps, key) then
				local ok, value = pcall(function()
					return (service :: any)[key]
				end)
				local kind = typeof(value)
				if not ok then
					continue
				elseif kind == "boolean" or kind == "string" then
					values[key] = value
				elseif kind == "number" then
					values[key] = number(value)
				elseif kind == "EnumItem" then
					values[key] = tostring(value)
				elseif kind == "Color3" then   -- 한 줄로 읽히게 글자로 적는다
					values[key] = string.format("#%02X%02X%02X", math.round(value.R * 255), math.round(value.G * 255), math.round(value.B * 255))
				elseif kind == "Vector3" then
					values[key] = tostring(number(value.X)) .. ", " .. tostring(number(value.Y)) .. ", " .. tostring(number(value.Z))
				end
			end
		end
		settings[name] = values
	end
end

local account, userId = "", ""
pcall(function()
	local id = game:GetService("StudioService"):GetUserId()
	userId = tostring(id)
	account = game:GetService("Players"):GetNameFromUserIdAsync(id)
end)

local head = http:JSONEncode({place = game.Name, account = account, userId = userId, items = items, settings = settings})
local headText = buffer.tostring(enc:Base64Encode(buffer.fromstring(head)))
_G.rbStudioPull = {token = ARGS.token, stream = headText .. table.concat(blobs)}
return "#" .. #headText .. ":" .. #_G.rbStudioPull.stream
"""
WINDOW_LUAU = r"""
local cache = _G.rbStudioPull
if type(cache) ~= "table" or cache.token ~= "__TOKEN__" then
	return "!cache"
end
return "=" .. string.sub(cache.stream, __FROM__, __TO__)
"""
CLEAR_LUAU = "_G.rbStudioPull = nil\nreturn 'ok'"


class Unavailable(Exception):
    """이번에는 쓰지 않는다 — 연결·전송·검사 문제. 다음 차례에 다시 한다. 조용한 실행에서도 알린다."""


class Absent(Unavailable):
    """읽을 것이 없다 — 스테이징 Place 가 열려 있지 않거나 Play 중. 조용한 실행에서는 알리지 않는다."""


class Studio:
    """Studio MCP 프록시와 stdio JSON-RPC 로 말한다. Claude Code 의 연결과 따로 붙어도 된다(2026-10-06 실측)."""

    def __init__(self, deadline: float):
        self.deadline = deadline
        self.inbox: queue.Queue[bytes] = queue.Queue()
        self.seq = 0
        self.proc: subprocess.Popen | None = None
        self.errors: deque[str] = deque(maxlen=3)   # 프록시가 끝났을 때 까닭을 알리려고 마지막 오류 몇 줄만 둔다

    def __enter__(self) -> "Studio":
        # WSL→Windows 실행 통로(/init)가 쉬었다 깨어날 때 10초쯤 막혔다가 실패한다(UtilAcceptVsock accept4 110 — 실측).
        # 몇 초 뒤에는 열리므로 사이를 두고 다시 붙는다. 세 번 다 막히면 다음 차례로 넘긴다.
        for attempt in range(CONNECT_TRIES):
            try:
                self._open()
                self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": "rb-studio-pull", "version": "1"}})
                self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                return self
            except (OSError, Unavailable) as exc:
                self.close()
                if attempt == CONNECT_TRIES - 1 or self.deadline - time.monotonic() < CONNECT_WAIT_S + 11:
                    raise Unavailable(f"Studio MCP 프록시에 붙지 못했다 ({exc})") from exc
                time.sleep(CONNECT_WAIT_S)
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _open(self) -> None:
        self.inbox = queue.Queue()
        self.proc = subprocess.Popen(STUDIO, cwd=STUDIO_CWD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        out, err, inbox, errors = self.proc.stdout, self.proc.stderr, self.inbox, self.errors
        threading.Thread(target=lambda: [inbox.put(line) for line in out], daemon=True).start()
        threading.Thread(target=lambda: [errors.append(line.decode(errors="replace").strip()) for line in err], daemon=True).start()

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.kill()   # stdin 이 닫히면 Windows 쪽 프록시도 끝난다(실측: 여러 번 돌려도 프록시 수가 늘지 않음)
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        self.proc = None

    def _send(self, message: dict) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write((json.dumps(message) + "\n").encode())
        self.proc.stdin.flush()

    def request(self, method: str, params: dict) -> dict:
        self.seq += 1
        self._send({"jsonrpc": "2.0", "id": self.seq, "method": method, "params": params})
        while True:
            left = self.deadline - time.monotonic()
            if left <= 0:
                raise Unavailable(f"Studio 가 {BUDGET_S}초 안에 답하지 않았다")
            try:
                message = json.loads(self.inbox.get(timeout=min(left, 1.0)))
            except queue.Empty:
                if self.proc is None or self.proc.poll() is not None:
                    why = next((line for line in reversed(self.errors) if line), "")
                    raise Unavailable("Studio MCP 프록시가 끝났다" + (f" — {why[:100]}" if why else ""))
                continue
            except ValueError:
                continue
            if message.get("id") == self.seq:
                if "error" in message:
                    raise Unavailable(str(message["error"])[:120])
                return message.get("result", {})

    def tool(self, name: str, arguments: dict) -> str:
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        text = "".join(c.get("text", "") for c in result.get("content", []) if isinstance(c, dict))
        if result.get("isError"):
            raise Unavailable(text[:160])
        return text


def fill(template: str, **values: str) -> str:
    """Luau 틀의 __이름__ 자리를 채운다. JSON 은 긴 괄호 [==[ ]==] 안에 들어가므로 그 닫는 꼴이 들어 있으면 거절한다."""
    for key, value in values.items():
        if "]==]" in value:
            raise ValueError(f"{key} 에 Luau 긴 괄호 닫는 꼴이 있다")
        template = template.replace(f"__{key}__", value)
    return template


def owned_paths(roots: list[str]) -> list[str]:
    """Rojo 자리를 품은 윗 폴더(서비스 아래) — 통째로 읽으면 그 안의 저장소 코드까지 사본에 들어간다 (리뷰 STUDIO-PULL 1차)."""
    found = set()
    for root in roots:
        parts = root.split("/")
        found.update("/".join(parts[:k]) for k in range(2, len(parts)))
    return sorted(found)


def rojo_roots(project: dict) -> list[str]:
    """Rojo 프로젝트에서 $path 로 저장소가 넣는 자리 — 'ServerScriptService/Gate' 꼴. 이 아래는 읽지 않는다(DEC-8)."""
    roots: list[str] = []

    def walk(node: dict, path: list[str]) -> None:
        if "$path" in node and path:
            roots.append("/".join(path))
            return
        for key, child in node.items():
            if not key.startswith("$") and isinstance(child, dict):
                walk(child, path + [key])

    walk(project.get("tree", {}), [])
    return sorted(roots)


def base_name(name: str) -> str:
    """Instance 이름 → 파일 이름 바탕. Windows 에서 못 쓰는 글자·이름도 피한다."""
    base = UNSAFE.sub("_", name).strip(" .")[:80] or "_"
    return "_" + base if base.split(".")[0].upper() in RESERVED_NAMES else base


def file_name(name: str, taken: set[str]) -> str:
    """Instance 이름 → 그릇 안에서 겹치지 않는 파일 이름(확장자 없이)."""
    base = base_name(name)
    candidate, k = base, 1
    while candidate.lower() in taken:   # 대소문자만 다른 이름도 Windows 에서는 같은 파일이다
        k += 1
        candidate = f"{base} ({k})"
    taken.add(candidate.lower())
    return candidate


def split_blobs(blobs: str, items: list[dict]) -> list[str]:
    """이어 붙여 받은 base64 를 항목 크기대로 자른다. 크기 합이 맞지 않으면 거절한다(중간에 잘렸거나 섞였다)."""
    sizes = [int(item.get("size") or 0) for item in items if not item.get("error")]
    if sum(sizes) != len(blobs):
        raise Unavailable(f"받은 길이({len(blobs)})가 항목 크기 합({sum(sizes)})과 다르다")
    out, at = [], 0
    for size in sizes:
        out.append(blobs[at:at + size])
        at += size
    return out


def extras(account: str, user_id: str) -> list[str]:
    """Studio 계정 이름·번호 가운데 검사에 쓸 만한 것 — 너무 짧으면 엉뚱한 줄이 다 걸리므로 뺀다(번호 0 = 로그인 안 함)."""
    found = []
    if len(account) >= 3:
        found.append(account)
    if user_id.isdigit() and len(user_id) >= 6:
        found.append(user_id)
    return found


def decoded(text: str) -> tuple[str, str]:
    """XML 안 base64 덩어리(BinaryString·SharedString)를 풀어 낸 글자 (글자 덩어리, 이진 덩어리).

    속성 값·태그에 든 계정 이름은 base64 로만 들어 있어 글자 검사에 보이지 않는다 (리뷰 STUDIO-PULL 1차).
    메시·지형 같은 이진 자료는 전자우편·비밀값 꼴이 우연히 생기므로 따로 돌려준다 (리뷰 STUDIO-PULL 1차).
    """
    words, binary = [], []
    for match in ENCODED.finditer(text):
        try:
            data = base64.b64decode("".join(match.group(3).split()), validate=True)
        except ValueError:
            continue
        (words if TEXT_BLOBS.search(match.group(2)) else binary).append(data.decode("utf-8", errors="replace"))
    return "\n".join(words), "\n".join(binary)


def scan(outputs: dict[str, str], private: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """쓸 것과 막을 것으로 나눈다 — 막은 것은 (상대 경로 → 첫 이유). 파일 이름도 Instance 이름이라 함께 본다.

    속성·태그 덩어리는 글자와 같은 검사를, 나머지 이진 자료는 이 사람의 값(BINARY_MIN 자 이상)만 찾는다.
    """
    clean, blocked = {}, {}
    flat_private = [(v, ship.plain(v)) for v in private if len(v) >= BINARY_MIN]
    for rel, text in outputs.items():
        small, big = decoded(text)
        bare = ENCODED.sub(lambda m: f"<{m.group(1)}/>", text)   # base64 덩어리는 풀어서 따로 본다 — 긴 덩어리를 글자 검사에 넣지 않는다
        found = ship.leaks(ship.as_added("\n".join([rel, bare, small])), private)
        flat_big = ship.plain(big)
        found += [f"로컬 경로·계정 '{v}' 가 이진 값 안에 들어 있다" for v, flat in flat_private if big and flat in flat_big]
        if found:
            blocked[rel] = found[0]
        else:
            clean[rel] = text
    return clean, blocked


def mirror(outputs: dict[str, str], keep: set[str], root: Path, staging: Path | None = None) -> list[str]:
    """outputs 를 root 아래에 쓰고, outputs·keep 에 없는 옛 사본(.rbxmx)은 지운다. 바뀐 파일(상대 경로)을 돌려준다.

    keep = 이번에 쓰지 못한 항목(누출 검사에 걸림·변환 실패) — 옛 사본을 지우면 Studio 에서 지운 것처럼 보이므로 둔다.
    staging = 먼저 써 둘 자리(같은 디스크). 거기 다 쓴 뒤 하나씩 바꿔 끼우므로 반쯤 쓴 파일이 root 에 생기지 않는다.
    """
    changed = []
    staging = staging or root.with_name(root.name + ".staging")
    staging.mkdir(parents=True, exist_ok=True)
    try:
        for rel, text in sorted(outputs.items()):
            path = root / rel
            data = text.encode("utf-8")
            if not path.is_file() or path.read_bytes() != data:
                part = staging / f"{len(changed)}.part"
                part.write_bytes(data)
                path.parent.mkdir(parents=True, exist_ok=True)
                part.replace(path)
                changed.append(rel)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    if root.is_dir():
        wanted = {rel.lower() for rel in outputs} | {rel.lower() for rel in keep}   # D: 는 대소문자를 가리지 않는다
        for path in sorted(root.rglob("*.rbxmx")):
            rel = path.relative_to(root).as_posix()
            if rel.lower() not in wanted:
                path.unlink()
                changed.append(rel)
        for folder in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(folder.iterdir()):
                folder.rmdir()
    return changed


def due(state: Path, now: float, interval: float = INTERVAL_S) -> bool:
    try:
        return now - float(json.loads(state.read_text(encoding="utf-8")).get("last", 0)) >= interval
    except (OSError, ValueError, AttributeError):
        return True


def edit_available(state: str) -> bool:
    """get_studio_state 답에서 Edit 화면을 읽을 수 있는지 — 'Available DataModels: Edit' (Play 중에는 Client, Server)."""
    line = next((row for row in state.splitlines() if "Available DataModels" in row), "")
    return "Edit" in line.split(":", 1)[-1]


def find_rojo() -> str:
    found = shutil.which("rojo") or next((str(p) for p in (Path.home() / ".local/bin/rojo", Path.home() / ".cargo/bin/rojo")
                                         if p.is_file()), "")
    if not found:
        raise Unavailable("rojo 를 찾지 못했다 — 사본을 XML 로 바꿀 수 없다")
    return found


def to_xml(rojo: str, name: str, data: bytes, tmp: Path, deadline: float) -> str:
    """직렬화한 바이너리(.rbxm) → 사람이 읽는 XML(.rbxmx). 같은 내용이면 같은 글자가 나온다(실측).

    Rojo 는 프로젝트 이름을 맨 위 Instance 이름으로 쓰므로 원래 이름을 넣는다.
    """
    left = deadline - time.monotonic()
    if left <= 0:
        raise Unavailable(f"{BUDGET_S}초 안에 끝내지 못해 이번에는 쓰지 않는다")
    (tmp / "item.rbxm").write_bytes(data)
    (tmp / "item.project.json").write_text(json.dumps({"name": name, "tree": {"$path": "item.rbxm"}}), encoding="utf-8")
    out = tmp / "item.rbxmx"
    out.unlink(missing_ok=True)
    done = subprocess.run([rojo, "build", str(tmp / "item.project.json"), "-o", str(out)], capture_output=True,
                          text=True, timeout=left)
    if done.returncode != 0 or not out.is_file():
        raise ValueError((done.stderr or done.stdout).strip().splitlines()[-1:] or ["rojo build 실패"])
    return out.read_text(encoding="utf-8")


def read_studio(deadline: float) -> tuple[dict, list[bytes]]:
    """스테이징 Place 의 항목 목록·설정값과 항목마다의 직렬화 바이너리."""
    rojo = rojo_roots(json.loads(PROJECT.read_text(encoding="utf-8")))
    args = {"place": STAGING, "rojo": rojo, "skip": {path: True for path in SKIP + owned_paths(rojo)}, "containers": CONTAINERS,
            "settings": SETTINGS, "skipProps": SKIP_PROPS, "maxBytes": MAX_ITEM_BYTES, "maxTotal": MAX_TOTAL_CHARS,
            "token": f"{time.time_ns()}"}
    with Studio(deadline) as studio:
        listed = json.loads(studio.tool("list_roblox_studios", {}) or "{}").get("studios", [])
        target = next((s["id"] for s in listed if s.get("name") == STAGING), None)
        if not target:
            raise Absent(f"스테이징 Place({STAGING})가 열려 있지 않다")
        if not edit_available(studio.tool("get_studio_state", {"studio_id": target})):
            raise Absent("Studio 가 Play 중이다 — Place 몫은 Edit 화면에서만 읽는다")
        call = {"studio_id": target, "datamodel_type": "Edit"}
        head = studio.tool("execute_luau", {**call, "code": fill(MANIFEST, ARGS=json.dumps(args, ensure_ascii=False))})
        match = re.fullmatch(r"#(\d+):(\d+)", head.strip())
        if not match:
            if head.startswith("!") or "Edit" in head:
                raise Absent("Edit 화면을 읽지 못했다(Play 중이거나 다른 Place)")
            raise Unavailable(f"뜻밖의 답: {head[:80]}")
        head_size, total = int(match.group(1)), int(match.group(2))
        parts = []
        try:
            for start in range(1, total + 1, WINDOW):
                code = fill(WINDOW_LUAU, TOKEN=args["token"], FROM=str(start), TO=str(min(total, start + WINDOW - 1)))
                piece = studio.tool("execute_luau", {**call, "code": code})
                if not piece.startswith("="):
                    raise Unavailable("Studio 쪽 임시 사본을 잃었다")
                parts.append(piece[1:])
        finally:
            studio.deadline = max(studio.deadline, time.monotonic() + 3)   # 예산 끝에 닿았어도 치우기는 잠깐 해 본다
            try:
                studio.tool("execute_luau", {**call, "code": CLEAR_LUAU})
            except (Unavailable, OSError):
                pass   # 다음 실행이 같은 자리를 덮어쓴다
    stream = "".join(parts)
    if len(stream) != total:
        raise Unavailable(f"받은 길이({len(stream)})가 보낸 길이({total})와 다르다")
    try:
        manifest = json.loads(base64.b64decode(stream[:head_size], validate=True).decode("utf-8"))
        blobs = split_blobs(stream[head_size:], manifest.get("items") or [])
        return manifest, [base64.b64decode(blob, validate=True) for blob in blobs]
    except ValueError as exc:   # base64·JSON·UTF-8 가 깨졌다 — 받는 중에 섞였다
        raise Unavailable(f"받은 사본이 깨져 있다 ({str(exc)[:60]})") from exc


def remember(values: list[str]) -> None:
    """검사에 쓸 이 사람의 값을 저장소 밖(.git/info/rb-private)에 더한다 — ship.py 가 모든 커밋에서 찾는다."""
    path = ship.local_private_path()
    known = set(ship.local_private())
    new = [v for v in values if v not in known]
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        lead = "\n" if path.is_file() and path.read_bytes()[-1:] not in (b"", b"\n") else ""   # 사람이 줄바꿈 없이 끝낸 값과 붙지 않게
        with path.open("a", encoding="utf-8") as out:
            out.write(lead + "".join(v + "\n" for v in new))


def pull(quiet: bool) -> int:
    deadline = time.monotonic() + BUDGET_S
    rojo = find_rojo()
    manifest, blobs = read_studio(deadline)
    account = str(manifest.get("account") or "")
    private_extra = extras(account, str(manifest.get("userId") or ""))
    if account not in private_extra:   # 이름을 모르면 그 이름이 든 항목을 거를 수 없다 — 쓰지 않고 다음 차례에 다시 한다
        raise Unavailable("Studio 계정 이름을 확인하지 못해 누출 검사를 다 할 수 없다 — 이번에는 쓰지 않는다")
    remember(private_extra)
    private = ship.private_values() + private_extra

    items = manifest.get("items") or []
    outputs: dict[str, str] = {}
    keep: set[str] = set()
    notes: list[str] = []
    taken: dict[str, set[str]] = {}
    scripts = 0
    readable = iter(blobs)
    pairs = [(item, None if item.get("error") else next(readable)) for item in items]
    # 같은 이름 형제는 내용 순서로 번호를 받는다 — Studio 의 자식 순서가 바뀌어도 같은 파일 이름이 나오게
    pairs.sort(key=lambda pair: (str(pair[0].get("container")), base_name(str(pair[0].get("name"))).lower(), pair[1] or b""))
    with tempfile.TemporaryDirectory(prefix="rb-studio-pull-") as tmp:
        for item, data in pairs:
            container, name = str(item.get("container")), str(item.get("name"))
            rel = f"{container}/{file_name(name, taken.setdefault(container, set()))}.rbxmx"
            if data is None:
                keep.add(rel)
                notes.append(f"{container}/{name}: 읽지 못함 ({str(item['error'])[:60]})")
                continue
            try:
                xml = to_xml(rojo, name, data, Path(tmp), deadline)
                if len(xml.encode("utf-8")) > MAX_XML_BYTES:
                    raise ValueError(f"XML 이 {MAX_XML_BYTES // 1_000_000}MB 를 넘는다")
                outputs[rel] = xml
            except (ValueError, subprocess.SubprocessError, OSError) as exc:
                keep.add(rel)
                notes.append(f"{container}/{name}: XML 로 바꾸지 못함 ({str(exc)[:60]})")
                continue
            scripts += int(item.get("scripts") or 0)
    settings = {k: (v if isinstance(v, dict) else {}) for k, v in (manifest.get("settings") or {}).items()}
    outputs["settings.json"] = json.dumps(settings, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    clean, blocked = scan(outputs, private)
    for rel, reason in blocked.items():
        keep.add(rel)
        notes.append(f"{rel}: 공개 저장소에 올리면 안 되는 값이 있어 쓰지 않음 — {reason[:80]}")
    changed = mirror(clean, keep, PLACE, ship.git_path("rb-studio-pull.staging"))
    if changed or notes or not quiet:
        line = f"[Studio 읽기] 항목 {len(items)}개 — place/ 에서 바뀐 파일 {len(changed)}개"
        if scripts:
            line += f" · Studio 에서 만든 스크립트 {scripts}개 있음(코드는 저장소 world/src 가 정본 — DEC-8)"
        print(line + "".join(f"\n  {note}" for note in notes))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Studio 에서 만든 것을 place/ 에 사본으로 남긴다 (읽기만)")
    parser.add_argument("--now", action="store_true", help="10분 간격을 기다리지 않고 바로 읽는다")
    parser.add_argument("--quiet", action="store_true", help="바뀐 것·문제가 없으면 아무것도 쓰지 않는다 (Stop 훅)")
    args = parser.parse_args(argv)
    ship.DEADLINE[0] = time.monotonic() + BUDGET_S   # ship.git() 호출도 이 도구의 예산 안에서 끝나게
    try:
        state = ship.git_path("info/rb-studio-pull.json")
        now = time.time()
        if not args.now and not due(state, now):
            return 0
        state.parent.mkdir(parents=True, exist_ok=True)
        previous = state.read_bytes() if state.is_file() else None
        state.write_text(json.dumps({"last": now}), encoding="utf-8")   # 실패해도 매 턴 오래 기다리지 않게 먼저 적는다
        try:
            return pull(args.quiet)
        except Absent:
            # 읽을 것이 없다는 답은 금방 온다 — 간격을 쓰지 않아 Play 를 끝내거나 Place 를 열면 다음 턴에 바로 읽는다
            if previous is None:
                state.unlink(missing_ok=True)
            else:
                state.write_bytes(previous)
            raise
    except Absent as exc:
        if not args.quiet:
            print(f"[Studio 읽기] 건너뜀 — {exc}")
    except Unavailable as exc:
        print(f"[Studio 읽기] 건너뜀 — {exc}")
    except Exception as exc:   # noqa: BLE001 — 뜻밖의 실패도 세션을 막지 않는다. 다음 차례에 다시 한다
        print(f"[Studio 읽기] 실패 (tools/studio_pull.py) — {type(exc).__name__}: {str(exc)[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
