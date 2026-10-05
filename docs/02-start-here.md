# 시작 문서 — Roblox Studio × Claude Code

- 옮긴 날: 2026-10-01 (내신만점.kr 세션 "로블록스"에서 이전)
- 원 가이드: `01-roblox-studio-mcp-guide.md` (원문 보존, 수정 금지)
- 이 문서는 **연결 환경과 Studio 연결 절차**의 정본이다. 상태가 바뀌면 이 문서를 고친다.
- 목표·제품 순서(Q1~Q8)·결정 항목(DEC)의 정본은 저장소 맨 위 `intent.md`, 결정 상태는 `decisions.md` 다 (2026-10-01 이관).

---

## 1. 원 가이드 대조 결과 (2026-10-01, 공식 문서 create.roblox.com/docs/studio/mcp)

| 원 가이드의 주장 | 판정 | 보정 |
|---|---|---|
| Claude Code 공식 지원 | 검증됨 | Quick connect 대상 7종: Antigravity, Codex CLI, Claude Code, Claude Desktop, Cursor, Gemini CLI, Visual Studio Code |
| 연결 방식 | 검증됨 | Studio에 들어 있는 `StudioMCP` 를 Claude Code가 stdio 로 실행한다 (아래 §5) |
| Studio가 열려 있어야 함 | 검증됨 | Windows·macOS 만 지원. Studio 최신 버전 필요 |
| 가능한 작업 목록 | 일부 누락 | 도구가 26종이다. 원 가이드에 없는 것: **화면 캡처, 키보드·마우스 입력 흉내, 캐릭터 이동, 외부 주소 조회(http_get), 메시·재질·절차 모델 생성, 이미지 업로드** |

권한 범위가 원 가이드보다 넓다. 그래서 원 가이드의 "읽기 전용 → 작은 수정 → 스테이징에서만 큰 변경" 순서를 그대로 지킨다.

## 2. 이 PC 상태 (2026-10-01 15:30 기준 실측)

- 검증됨 — Roblox Studio 설치됨. 10-01 14:56 업데이트. `StudioMCP.exe`·`%LOCALAPPDATA%\Roblox\mcp.bat` 있음
- 검증됨 — Studio 실행 중 (`RobloxStudioBeta.exe` 프로세스 있음)
- 검증됨 — **WSL 기본 경로로는 Windows 프로그램 실행 불가.** `/proc/sys/fs/binfmt_misc/WSLInterop` 등록이 없어 `cmd.exe` 를 셸 스크립트로 읽고 실패한다. `/etc/wsl.conf` 에 interop 를 끈 설정은 없고 `systemd=true` 만 있음 → systemd 가 등록을 지운 경우로 추정(미검증). 정식 복구(binfmt 재등록)는 root 가 필요하다
- 검증됨 — **우회 경로: `/init <exe> <인자>` 로 직접 부르면 실행된다 (root 불필요).** `cmd.exe /c ver` 성공, `%LOCALAPPDATA%` 확장 정상. 단 `/init` 직접 호출은 WSL 내부 동작이라 WSL 업데이트로 막힐 수 있다(추정)
- 검증됨 — WSL → `mcp.bat` → StudioMCP 프록시 왕복 성공 (initialize 응답 `RobloxStudio 1.0.0`). 그러나 `list_roblox_studios` = 빈 목록, `get_studio_state` = "No Roblox Studio instances are connected" → **Studio 쪽 "Enable Studio as MCP server" 가 꺼져 있거나 Place 가 열려 있지 않다**
- 검증됨 — WSL Claude Code 에 이 폴더 전용(local scope, `~/.claude.json` 안, 저장소 밖)으로 `Roblox_Studio` 등록함. 명령: `/init /mnt/c/Windows/System32/cmd.exe /c %LOCALAPPDATA%\Roblox\mcp.bat`. 상태 점검 결과 "Connected · tools fetch failed (timeout)" — Studio 가 붙지 않아 도구 목록이 비어 있는 것과 같은 원인
- 검증됨 — Windows용 `.claude.json` 의 Roblox 항목 0건, Studio Assistant 연결 목록(integrations)도 비어 있음. Windows용 Claude Code 는 설치돼 있음 (`%APPDATA%\npm\claude.cmd`)
- 참고 — `mcp.bat` 의 `else` 가 닫는 괄호와 다른 줄에 있어 cmd 문법상 대체 분기가 깨져 있다. 현재 버전 폴더의 exe 가 있으면 첫 분기로 실행돼 영향 없음. Studio 업데이트 때 이 파일이 다시 써지는지는 미검증

결론: **WSL 에서 연 Claude Code 도 `/init` 경유로 Studio MCP 에 닿는다.** 남은 것은 Studio 안의 스위치(1단계)뿐이다. Quick connect(Windows용 설정)는 WSL 세션에는 필요 없다.

## 3. Studio 연결 절차

| 단계 | 누가 | 내용 | 끝났다는 증거 |
|---|---|---|---|
| 0 | AI | 실행 환경 점검. 이 세션이 WSL 이면 Windows 프로그램 실행 가능 여부를 확인한다. 안 되면 "Windows용 Claude Code로 이 폴더 열기"를 결정으로 올린다 | 세션 종류와 실행 가능 여부 기록 |
| 1 | 사람 | Studio 에서 **스테이징용 Place** 를 연다 → Assistant → … → Manage MCP Servers → **Enable Studio as MCP server** 켜기. (Windows용 Claude Code 를 쓸 때만 추가로 Quick connect → Claude Code 켜기) | `list_roblox_studios` 가 Studio 1개 이상을 돌려줌 |
| 2 | AI | 연결 확인. `list_roblox_studios`·`get_studio_state` 로 왕복을 확인하고, 원 가이드의 첫 프롬프트(구조 트리 요약, 수정 금지)를 실행한다 | 트리 요약 결과 |
| 3 | AI | 읽기 전용 점검 — 원 가이드 §권장 운영 방식 1 | 점검 보고 (수정 0건) |
| 4 | AI (범위는 사람) | 작은 단위 수정 — 원 가이드 §2. 한 요청 = 한 기능. 끝나면 바뀐 경로·diff·Play 테스트 결과를 보고한다 | 테스트 결과 |
| 5 | AI (스테이징만) | 대규모 변경 — 원 가이드 §3 | Play 테스트 + 남은 위험 보고 |

진행 현황 (2026-10-05): **0·1단계 완료.** 사람이 Studio 스위치를 켠 뒤 `list_roblox_studios` 가 Studio 1개를 돌려줬다 (근거 `ENV-STUDIO-LINK-2`). Studio 의 Quick connect 화면이 보여 주는 `claude mcp add … cmd.exe …` 명령은 Windows용 Claude Code 용이다. 이 WSL 세션에는 이미 `/init` 경유로 등록돼 있으므로 다시 실행하지 않는다. **2단계 확인 사항:** 열린 Place 가 DEC-2 의 `rb-staging.rbxlx` 가 아니라 자동 복구본(`rb-staging_AutoRecovery_0.rbxl`)이다. Q4-C2 를 시작하기 전에 맞춘다.

## 4. 열린 결정

결정 항목의 정의는 `intent.md` §7, 상태(열림/결정됨)와 근거는 `decisions.md` 에 있다 (DEC-1 무엇을 만드는가 · DEC-2 스테이징 Place · DEC-3 GitHub 반영 …). 경고 장치(`tools/flow_guard.py`)가 `decisions.md` 를 읽는다.

## 5. 참고 — 연결 설정값 (공식 문서 원문)

Windows 실행 명령: `cmd.exe /c %LOCALAPPDATA%\Roblox\mcp.bat`
macOS 실행 명령: `/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP`

```json
{
  "mcpServers": {
    "Roblox_Studio": {
      "command": "cmd.exe",
      "args": ["/c", "%LOCALAPPDATA%\\Roblox\\mcp.bat"]
    }
  }
}
```

`mcp.bat` 는 현재 버전 폴더의 `StudioMCP.exe` 를 찾아 실행한다. 버전 폴더 이름은 Studio 업데이트 때마다 바뀌므로 exe 경로를 직접 적지 않는다.

노출 도구 26종: script_read, multi_edit, script_search, script_grep, generate_mesh, generate_material, generate_procedural_model, wait_job_finished, search_asset, insert_asset, upload_image, store_image, subagent, search_game_tree, inspect_instance, execute_luau, get_studio_state, start_stop_play, get_console_output, screen_capture, character_navigation, user_keyboard_input, user_mouse_input, http_get, skill, list_roblox_studios
