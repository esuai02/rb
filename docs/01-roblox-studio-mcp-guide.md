<!--
원문 보존본 — 2026-10-01 내신만점.kr 세션 "로블록스"에 사용자가 붙여 넣은 가이드를 그대로 옮김.
공식 문서(create.roblox.com/docs/studio/mcp)와의 대조 결과·보정은 02-start-here.md §1 참조.
이 파일은 수정하지 않는다. 보정은 02-start-here.md 에만 적는다.
-->

네. **현재 Roblox Studio는 Claude Code에서 공식적으로 접근할 수 있습니다.** Roblox Studio의 내장 MCP(Model Context Protocol) 서버를 켜고 Claude Code를 연결하면, Claude가 현재 열려 있는 Studio 세션의 게임 구조를 읽고, Luau 스크립트를 수정하고, 모델을 삽입하고, 코드를 실행하고, Play 모드 테스트까지 수행할 수 있습니다. [create.roblox](https://create.roblox.com/docs/studio/mcp)

## 가능한 작업

Claude Code는 단순히 로컬 `.lua` 파일만 고치는 수준이 아니라, 연결된 Roblox Studio의 **DataModel**을 직접 다룰 수 있습니다.

- `Workspace`, `ServerScriptService`, `ReplicatedStorage`, `StarterGui` 등의 객체 구조 탐색
- `Script`, `LocalScript`, `ModuleScript` 생성·수정·삭제
- Luau 코드 실행 및 오류·출력 로그 확인
- `RemoteEvent`, `RemoteFunction`, `Folder`, `ScreenGui`, `Part` 등 인스턴스 생성 및 속성 변경
- 모델 삽입 및 월드 구조 변경
- Play 모드에서 게임 실행 및 테스트
- Studio 상태를 읽고 오류 원인을 분석한 뒤 코드 패치
- 반복적인 “수정 → 실행 → 오류 확인 → 재수정” 루프 수행

Roblox 공식 문서는 MCP 연결 뒤 AI 클라이언트가 열린 Studio 세션과 직접 상호작용해 DataModel 탐색, 스크립트 작성, 모델 삽입, Luau 실행, Play 모드 테스트를 할 수 있다고 설명하며, 지원 클라이언트 목록에 **Claude Code**를 명시합니다. [create.roblox](https://create.roblox.com/docs/studio/mcp)

## 연결 방식

가장 쉬운 방법은 Roblox Studio의 **Quick connect**를 쓰는 것입니다.

1. PC 또는 Mac에 최신 Roblox Studio와 Claude Code를 설치합니다.
2. Roblox Studio를 열고 개발 중인 Experience 또는 Place를 엽니다.
3. Studio에서 **Assistant**를 엽니다.
4. `…` 메뉴에서 **Manage MCP Servers**를 엽니다.
5. **Enable Studio as MCP server**를 켭니다.
6. **Assistant Settings → MCP Servers → Quick connect**로 이동합니다.
7. 설치된 클라이언트 목록에서 **Claude Code**를 활성화합니다.
8. Claude Code에서 Studio MCP 도구 사용 권한 요청이 나오면, 대상 Studio 세션인지 확인한 뒤 허용합니다.

Roblox의 공식 안내에 따르면 Quick connect는 Claude Code, Claude Desktop, Codex CLI, Cursor, Gemini CLI, VS Code 등을 지원합니다. [create.roblox](https://create.roblox.com/docs/studio/mcp)

연결이 잘 됐는지는 Claude Code에 다음처럼 요청해서 확인할 수 있습니다.

```text
현재 열려 있는 Roblox Studio의 DataModel을 읽고,
Workspace / ReplicatedStorage / ServerScriptService /
StarterGui 구조를 트리 형태로 요약해줘.
수정은 하지 마.
```

그 다음 작은 변경부터 시키는 것이 좋습니다.

```text
ReplicatedStorage에 Remotes 폴더가 없으면 만들고,
그 안에 QuestStarted라는 RemoteEvent를 생성해줘.
기존 객체는 삭제하거나 이름을 바꾸지 마.
변경한 객체와 경로를 마지막에 보고해줘.
```

## Claude Code와 Studio의 역할

가장 좋은 작업 방식은 둘을 경쟁 관계로 보지 않는 것입니다.

| 도구 | 주 역할 |
|---|---|
| Claude Code | 요구사항 해석, 코드 생성·수정, 파일 구조 관리, Git, 테스트 계획, 로그 분석, MCP 도구 호출 |
| Roblox Studio MCP | 실제 Studio 세션의 객체 구조와 엔진에 접근하는 통로 |
| Roblox Studio | 월드·GUI·물리·카메라를 실행하고 시각적으로 확인하는 런타임 환경 |
| Creator Hub | Experience 관리, 권한, 분석, 퍼널, 유지율, A/B 실험, 운영 배포 |
| Git/CI | 코드 버전관리, 자동 검사, 스테이징 빌드와 배포 통제 |

즉, Claude Code가 Studio에 “원격 조종” 명령을 내리고, Studio MCP가 그 명령을 Roblox 엔진 안에서 수행하는 형태입니다.

## 권장 운영 방식

초기에는 Claude Code에 무제한 수정 권한을 주기보다, 아래 단계로 권한을 좁게 운영하세요.

### 1. 읽기·분석 단계

먼저 현재 Studio 구조와 코드 상태만 읽게 합니다.

```text
이 Roblox Place를 읽기 전용으로 점검해줘.
다음만 보고해줘.
- ServerScriptService의 스크립트별 역할
- ReplicatedStorage의 RemoteEvent/RemoteFunction 목록
- 클라이언트가 서버 권한 없이 보상을 지급할 수 있는 경로
- 모바일 UI에서 위험해 보이는 구조
- 오류 가능성이 높은 코드 10개

어떤 파일이나 Instance도 수정하지 마.
```

### 2. 작은 단위 수정 단계

한 기능을 하나의 요청 단위로 제한합니다.

```text
첫 NPC와 대화한 뒤 QuestStarted 이벤트를 서버에서만 발사하도록 수정해줘.
- 기존 저장 데이터 형식은 바꾸지 마.
- 클라이언트가 보상량을 지정할 수 없게 해.
- 수정 후 Play 모드에서 NPC 상호작용 테스트를 실행해.
- 바뀐 Script 경로, diff 요약, 테스트 결과를 보고해.
```

### 3. 테스트 Place에서만 대규모 변경

운영 Place가 아니라 별도의 개발/스테이징 Place에서만 AI가 월드 생성·대규모 리팩터링·GUI 개편을 하도록 합니다.

```text
이 Place는 스테이징 환경이다.
'중2 일차함수 레이싱' 프로토타입을 추가해줘.

제약:
- 2~4명 협동
- 모바일 우선
- 10분 세션
- 기울기 오개념 3개를 행동 기반 미션으로 설계
- 수학 시험 화면처럼 보이는 퀴즈 UI는 만들지 말 것
- 기존 로비 및 저장 시스템은 절대 변경하지 말 것

작업 순서:
1. 구현 계획과 수정 대상 목록 제시
2. 기존 구조와 충돌 검사
3. 구현
4. Play 테스트
5. 실패한 항목과 남은 위험요소 보고
```

## 주의할 점

Claude Code가 Studio에 접근 가능하다는 것은 “완전 자율 배포”를 뜻하지는 않습니다.

- Studio MCP는 **열려 있는 로컬 Studio 세션**에 연결하는 방식입니다. 보통 Studio가 실행 중이어야 하고, 해당 Place를 열어둬야 합니다. [create.roblox](https://create.roblox.com/docs/studio/mcp)
- AI가 코드·객체·맵을 빠르게 바꿀 수 있으므로, Git 커밋 또는 Place 버전 복원을 통해 되돌릴 수 있는 구조가 필요합니다.
- 운영 Place에서 대량 삭제, 권한 수정, DataStore 구조 변경, 결제·보상 경제 변경을 직접 허용하지 않는 것이 안전합니다.
- MCP가 Studio 엔진 접근을 제공해도, 실제 모바일 기기, 라이브 서버, Roblox 게시 권한, 연령등급·모더레이션, 실제 학생 반응까지 자동으로 해결해 주지는 않습니다.
- Claude의 Computer Use 기능은 별도로 데스크톱 앱 조작을 지원할 수 있지만, Studio 제어에는 화면 좌표를 클릭하는 방식보다 **공식 Studio MCP**가 훨씬 안정적이고 재현성이 높습니다. Computer Use는 MCP로 처리할 수 없는 대시보드 설정·시각 확인을 보조하는 정도로 한정하는 편이 좋습니다. [create.roblox](https://create.roblox.com/docs/studio/mcp)

## 가장 짧은 답

**가능합니다.** Roblox Studio에서 MCP 서버를 켠 뒤 Claude Code를 Quick connect로 연결하면, Claude Code가 Studio 안의 게임 구조와 Luau 코드를 직접 읽고 수정하고 실행·테스트할 수 있습니다. [create.roblox](https://create.roblox.com/docs/studio/mcp)

다만 실전에서는 다음 원칙이 좋습니다.

```text
Claude Code: 제작·수정·테스트
Studio MCP: 실제 Roblox 엔진 조작
Creator Hub: 분석·실험·운영
사람: 승인·재미·교육·안전 판단
```

이 구조라면 Claude Code를 Roblox 게임 생산 에이전트로 활용하면서도, 운영 게임을 AI의 실수로 망가뜨릴 위험은 크게 줄일 수 있습니다.
