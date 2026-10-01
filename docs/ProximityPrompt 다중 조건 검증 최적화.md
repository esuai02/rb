ProximityPrompt 다중 조건 검증은 단순히 `PromptTriggered`가 발생했다고 처리하는 것이 아니라, \*\*서버가 “이 플레이어가 지금 이 Prompt를, 이 거리에서, 이 순서로, 이 속도로, 이 팀 상태에서 실행할 자격이 있는가?”를 짧은 파이프라인으로 판정하는 구조\*\*입니다.



Roblox는 ProximityPrompt도 클라이언트가 악용할 수 있는 상호작용 표면으로 보며, `Enabled`, 거리, 가시성, 홀드 관련 클라이언트 상태를 신뢰하지 말고 서버에서 플레이어 상태·거리·권한·빈도를 검증하라고 명시합니다. 특히 `PromptButtonHoldBegan` 같은 일부 이벤트에는 서버 거리 검증이 없으며, `Triggered`만 서버 측 거리 검사가 적용되더라도 보상·진도에 영향을 주는 상호작용은 독립적인 서버 검증이 필요합니다. \[create.roblox](https://create.roblox.com/docs/scripting/security/client-server-boundary)



\## 검증 순서



최적화의 핵심은 \*\*가볍고 싼 검사부터, 비싸고 상태 변경이 큰 검사로\*\* 진행하는 것입니다.



```text

1\. Prompt 식별 가능?

2\. 서버에서 Enabled 상태인가?

3\. InteractionId가 허용 목록에 있는가?

4\. 플레이어 기본 상태가 유효한가?

5\. 쿨다운·중복 처리 제한을 통과하는가?

6\. 캐릭터·RootPart가 존재하고 살아 있는가?

7\. 서버 계산 거리 안에 있는가?

8\. 현재 퀘스트/온보딩 상태가 맞는가?

9\. 팀·역할·동시성 조건이 맞는가?

10\. 이미 완료/보상 지급된 상호작용인가?

11\. 트랜잭션 방식으로 상태 변경·보상 지급

12\. 텔레메트리 기록

```



앞 단계에서 실패하면 즉시 반환합니다. 예를 들어 거리 밖 요청은 팀 상태·DataStore·보상 조회를 하기 전에 차단해야 합니다.



\## 권장 검증 매트릭스



| 조건 | 예 | 서버 검증 | 실패 시 |

|---|---|---|---|

| 식별 | `InteractionId` 존재 | Attribute가 허용된 값인지 | 무시·보안 로그 |

| 활성화 | Prompt 사용 가능 | `prompt.Enabled == true` | 무시 |

| 플레이어 상태 | 살아 있고 캐릭터 존재 | Humanoid/RootPart 확인 | 무시 |

| 거리 | 8 studs 이내 | 서버 좌표로 거리 계산 | 무시·이상 기록 |

| 순서 | 신호 2 전에 신호 3 불가 | 서버 상태 머신 비교 | 피드백 또는 무시 |

| 권한 | 필요한 자격 보유 | 서버 저장 상태에서 확인 | 잠김 안내 |

| 소유권 | 자기 팀/자기 인스턴스인지 | Team/Party/Instance ID 확인 | 무시 |

| 쿨다운 | 0.5초 안에 반복 요청 | 서버 시간 기반 제한 | 무시 |

| 시간 | 0.6초 홀드가 너무 빠르지 않은가 | 서버 시작/완료 시간 비교 | 무시·플래그 |

| 협동 | 양측 3초 안에 준비 | 서버 타임스탬프 비교 | 대기 또는 NPC 대체 |

| 중복 보상 | 이미 탐험 카드 수령 | 서버 완료 레코드/원자적 플래그 | 이전 결과 반환 |

| 입력 값 | 경사 값이 -3\~3인지 | 타입·범위·현재 퍼즐 규칙 | 거절 |



\## 절대 신뢰하면 안 되는 것



다음은 클라이언트에서 보이는 값이라도 보안 근거로 쓰면 안 됩니다.



```text

prompt.Enabled

prompt.MaxActivationDistance

prompt.RequiresLineOfSight

클라이언트의 HoldDuration

클라이언트가 “나는 가까이에 있다”고 보낸 정보

클라이언트가 보낸 보상량·정답 여부·퀘스트 단계

클라이언트가 보낸 targetId·Instance 경로

클라이언트의 타이머·점수·팀 준비 상태

```



Roblox 공식 보안 문서는 ProximityPrompt의 `Enabled`, `MaxActivationDistance`, `RequiresLineOfSight`가 클라이언트에서 변경될 수 있고, Prompt 관련 이벤트도 악용될 수 있다고 설명합니다. 따라서 서버가 “게이트키퍼”가 되어 모든 상태 변화 전 검증해야 합니다. \[create.roblox](https://create.roblox.com/docs/scripting/security/client-server-boundary)



\## 최적화된 Validator



아래는 재사용 가능한 다중 조건 검증 모듈 예시입니다.



```lua

\-- ServerScriptService/Services/PromptValidator.lua



local Players = game:GetService("Players")



local PromptValidator = {}



local ALLOWED\_INTERACTIONS = {

&#x20;   signal\_1\_activate = true,

&#x20;   drone\_console\_open = true,

&#x20;   prism\_left\_ready = true,

&#x20;   prism\_right\_ready = true,

&#x20;   lumi\_help = true,

&#x20;   metro\_portal\_enter = true,

}



local recentTriggers = {}



local function getRootPart(player)

&#x20;   local character = player.Character

&#x20;   if not character then

&#x20;       return nil

&#x20;   end



&#x20;   return character:FindFirstChild("HumanoidRootPart")

end



local function getPromptWorldPosition(prompt)

&#x20;   local parent = prompt.Parent



&#x20;   if parent:IsA("Attachment") then

&#x20;       return parent.WorldPosition

&#x20;   end



&#x20;   if parent:IsA("BasePart") then

&#x20;       return parent.Position

&#x20;   end



&#x20;   if parent:IsA("Model") and parent.PrimaryPart then

&#x20;       return parent.PrimaryPart.Position

&#x20;   end



&#x20;   return nil

end



local function getCooldownKey(player, interactionId)

&#x20;   return string.format("%d:%s", player.UserId, interactionId)

end



function PromptValidator.validate(player, prompt, options)

&#x20;   options = options or {}



&#x20;   -- 1. Prompt 타입

&#x20;   if not prompt or not prompt:IsA("ProximityPrompt") then

&#x20;       return false, "invalid\_prompt"

&#x20;   end



&#x20;   -- 2. 서버 기준 활성 상태

&#x20;   if not prompt.Enabled then

&#x20;       return false, "disabled"

&#x20;   end



&#x20;   -- 3. InteractionId 허용 목록

&#x20;   local interactionId = prompt:GetAttribute("InteractionId")

&#x20;   if type(interactionId) \~= "string"

&#x20;       or not ALLOWED\_INTERACTIONS\[interactionId] then

&#x20;       return false, "unknown\_interaction"

&#x20;   end



&#x20;   -- 4. 캐릭터·생존 상태

&#x20;   local character = player.Character

&#x20;   local root = getRootPart(player)

&#x20;   local humanoid = character and character:FindFirstChildOfClass("Humanoid")



&#x20;   if not root or not humanoid or humanoid.Health <= 0 then

&#x20;       return false, "invalid\_character"

&#x20;   end



&#x20;   -- 5. 서버 쿨다운

&#x20;   local cooldown = options.cooldown or 0.35

&#x20;   local cooldownKey = getCooldownKey(player, interactionId)

&#x20;   local now = os.clock()

&#x20;   local last = recentTriggers\[cooldownKey]



&#x20;   if last and now - last < cooldown then

&#x20;       return false, "rate\_limited"

&#x20;   end



&#x20;   -- 6. 서버 거리 계산

&#x20;   local targetPosition = getPromptWorldPosition(prompt)

&#x20;   if not targetPosition then

&#x20;       return false, "missing\_target\_position"

&#x20;   end



&#x20;   local maxDistance = options.maxDistance or prompt.MaxActivationDistance

&#x20;   local slack = options.distanceSlack or 3



&#x20;   if (root.Position - targetPosition).Magnitude > maxDistance + slack then

&#x20;       return false, "too\_far"

&#x20;   end



&#x20;   -- 쿨다운은 여기까지 통과했을 때만 소비

&#x20;   recentTriggers\[cooldownKey] = now



&#x20;   -- 7. 서버 퀘스트 상태

&#x20;   if options.requiredState and options.getPlayerState then

&#x20;       local currentState = options.getPlayerState(player)

&#x20;       if currentState \~= options.requiredState then

&#x20;           return false, "wrong\_state"

&#x20;       end

&#x20;   end



&#x20;   -- 8. 서버 권한/자격 검사

&#x20;   if options.authorize and not options.authorize(player, prompt) then

&#x20;       return false, "not\_authorized"

&#x20;   end



&#x20;   -- 9. 팀/인스턴스 검사

&#x20;   if options.validateTeam and not options.validateTeam(player, prompt) then

&#x20;       return false, "invalid\_team"

&#x20;   end



&#x20;   -- 10. 이미 완료됐는지 검사

&#x20;   if options.isCompleted and options.isCompleted(player, prompt) then

&#x20;       return false, "already\_completed"

&#x20;   end



&#x20;   return true, {

&#x20;       interactionId = interactionId,

&#x20;       root = root,

&#x20;       targetPosition = targetPosition,

&#x20;       now = now,

&#x20;   }

end



function PromptValidator.clearPlayer(player)

&#x20;   local prefix = tostring(player.UserId) .. ":"



&#x20;   for key in pairs(recentTriggers) do

&#x20;       if string.sub(key, 1, #prefix) == prefix then

&#x20;           recentTriggers\[key] = nil

&#x20;       end

&#x20;   end

end



return PromptValidator

```



\### 중요한 수정 포인트



위 예시의 `options.maxDistance or prompt.MaxActivationDistance`는 \*\*편의상 Prompt 서버 속성\*\*을 읽는 것입니다. 서버에 복제된 `prompt.MaxActivationDistance` 자체는 서버가 관리하는 값이므로 참고할 수 있지만, 보안 정책상 중요한 상호작용은 값까지 Config에서 고정하는 편이 더 좋습니다.



```lua

local INTERACTION\_CONFIG = {

&#x20;   prism\_left\_ready = {

&#x20;       maxDistance = 8,

&#x20;       cooldown = 0.6,

&#x20;       requiredState = "COOP\_SIGNAL\_3",

&#x20;   },

&#x20;   metro\_portal\_enter = {

&#x20;       maxDistance = 10,

&#x20;       cooldown = 1.5,

&#x20;       requiredState = "GATE\_OPENED",

&#x20;   },

}

```



즉, `InteractionId`에 따라 \*\*서버 Config가 거리·쿨다운·필요 상태를 결정\*\*하고, Prompt 인스턴스는 UI 표시용으로만 취급하세요.



\## 서버 라우터 적용



```lua

\-- ServerScriptService/PromptRouter.server.lua



local ProximityPromptService = game:GetService("ProximityPromptService")

local Players = game:GetService("Players")



local PromptValidator = require(script.Parent.Services.PromptValidator)

local PlayerStateService = require(script.Parent.Services.PlayerStateService)

local GateService = require(script.Parent.Services.GateService)

local RewardService = require(script.Parent.Services.RewardService)



local INTERACTION\_CONFIG = {

&#x20;   signal\_1\_activate = {

&#x20;       maxDistance = 10,

&#x20;       cooldown = 0.4,

&#x20;       requiredState = "MOVE\_TO\_SIGNAL\_1",

&#x20;   },



&#x20;   prism\_left\_ready = {

&#x20;       maxDistance = 8,

&#x20;       cooldown = 0.7,

&#x20;       requiredState = "COOP\_SIGNAL\_3",

&#x20;   },



&#x20;   prism\_right\_ready = {

&#x20;       maxDistance = 8,

&#x20;       cooldown = 0.7,

&#x20;       requiredState = "COOP\_SIGNAL\_3",

&#x20;   },



&#x20;   metro\_portal\_enter = {

&#x20;       maxDistance = 10,

&#x20;       cooldown = 1.2,

&#x20;       requiredState = "GATE\_OPENED",

&#x20;   },

}



local handlers = {}



handlers.signal\_1\_activate = function(player)

&#x20;   if GateService:activateSignalOnce(player, "signal\_1") then

&#x20;       PlayerStateService:setState(player, "SIGNAL\_1\_DONE")

&#x20;   end

end



handlers.prism\_left\_ready = function(player)

&#x20;   local result = GateService:markCoopReady(player, "left")



&#x20;   if result == "success" then

&#x20;       GateService:openGateForTeam(player)

&#x20;       RewardService:grantGateCompletionOnce(player)

&#x20;   end

end



handlers.prism\_right\_ready = function(player)

&#x20;   local result = GateService:markCoopReady(player, "right")



&#x20;   if result == "success" then

&#x20;       GateService:openGateForTeam(player)

&#x20;       RewardService:grantGateCompletionOnce(player)

&#x20;   end

end



handlers.metro\_portal\_enter = function(player)

&#x20;   GateService:teleportToMetroOnce(player)

end



ProximityPromptService.PromptTriggered:Connect(function(prompt, player)

&#x20;   local interactionId = prompt:GetAttribute("InteractionId")

&#x20;   local config = INTERACTION\_CONFIG\[interactionId]



&#x20;   if not config then

&#x20;       return

&#x20;   end



&#x20;   local ok, result = PromptValidator.validate(player, prompt, {

&#x20;       maxDistance = config.maxDistance,

&#x20;       cooldown = config.cooldown,

&#x20;       requiredState = config.requiredState,

&#x20;       getPlayerState = function(targetPlayer)

&#x20;           return PlayerStateService:getState(targetPlayer)

&#x20;       end,



&#x20;       authorize = function(targetPlayer)

&#x20;           return GateService:canUseInteraction(targetPlayer, interactionId)

&#x20;       end,



&#x20;       validateTeam = function(targetPlayer)

&#x20;           return GateService:isCorrectTeamForInteraction(

&#x20;               targetPlayer,

&#x20;               interactionId

&#x20;           )

&#x20;       end,



&#x20;       isCompleted = function(targetPlayer)

&#x20;           return GateService:isInteractionCompleted(

&#x20;               targetPlayer,

&#x20;               interactionId

&#x20;           )

&#x20;       end,

&#x20;   })



&#x20;   if not ok then

&#x20;       GateService:recordRejectedInteraction(player, interactionId, result)

&#x20;       return

&#x20;   end



&#x20;   handlers\[result.interactionId](player)

end)



Players.PlayerRemoving:Connect(PromptValidator.clearPlayer)

```



\## 홀드 시간 검증



`HoldDuration`은 UX 신호이지, 보안의 유일한 근거로 쓰면 안 됩니다. Roblox는 클라이언트가 홀드 관련 이벤트나 로컬 `HoldDuration`을 조작할 수 있는 특성을 설명합니다. 시간이 중요한 상호작용—예: 3초간 발전기를 수리해야 하는 미션—은 서버에서 시작 시각과 완료 시각을 기록해 최소 시간을 검증하세요. \[create.roblox](https://create.roblox.com/docs/scripting/security/client-server-boundary)



```lua

local holdStartedAt = {}



local function holdKey(player, interactionId)

&#x20;   return string.format("%d:%s", player.UserId, interactionId)

end



ProximityPromptService.PromptButtonHoldBegan:Connect(function(prompt, player)

&#x20;   local interactionId = prompt:GetAttribute("InteractionId")



&#x20;   if interactionId == "power\_generator\_repair" then

&#x20;       holdStartedAt\[holdKey(player, interactionId)] = os.clock()

&#x20;   end

end)



local function validateMinimumHold(player, interactionId, requiredDuration)

&#x20;   local key = holdKey(player, interactionId)

&#x20;   local startedAt = holdStartedAt\[key]



&#x20;   if not startedAt then

&#x20;       return false

&#x20;   end



&#x20;   local elapsed = os.clock() - startedAt

&#x20;   holdStartedAt\[key] = nil



&#x20;   return elapsed >= requiredDuration \* 0.85

end

```



그러나 Roblox 보안 문서에 따르면 `PromptButtonHoldBegan` 자체에는 서버 거리 검증이 없을 수 있으므로, 여기서도 시작 이벤트를 신뢰해 보상하지 말고, \*\*최종 `Triggered` 시점에 거리·상태·권한·최소 시간\*\*을 모두 다시 검증해야 합니다. \[create.roblox](https://create.roblox.com/docs/scripting/security/client-server-boundary)



\### 더 안전한 방식



상호작용 시작 조건이 중요한 경우, Prompt 홀드 이벤트를 서버 권한 근거로 쓰기보다:



```text

Triggered

→ 서버가 유효성 검증

→ 서버가 “수리 진행” 상태로 전환

→ 서버 자체 타이머/상태로 완료 처리

```



처럼 서버가 자체적으로 진행 시간을 관리하는 편이 더 강합니다. 다만 “플레이어가 계속 누르고 있어야 한다”는 경험 자체가 중요하다면 서버 측 거리 재검사와 지속 상태 검증을 일정 간격으로 추가해야 합니다.



\## 협동 동기화 검증



협동 스위치는 서버 시간으로만 판정하세요.



```lua

local coopReadyAt = {}



local function markReady(player, side)

&#x20;   local partyId = PartyService:getPartyId(player)

&#x20;   if not partyId then

&#x20;       return "npc\_fallback"

&#x20;   end



&#x20;   coopReadyAt\[partyId] = coopReadyAt\[partyId] or {}

&#x20;   coopReadyAt\[partyId]\[side] = {

&#x20;       userId = player.UserId,

&#x20;       time = os.clock(),

&#x20;   }



&#x20;   local left = coopReadyAt\[partyId].left

&#x20;   local right = coopReadyAt\[partyId].right



&#x20;   if not left or not right then

&#x20;       return "waiting"

&#x20;   end



&#x20;   if math.abs(left.time - right.time) > 3 then

&#x20;       return "out\_of\_window"

&#x20;   end



&#x20;   if left.userId == right.userId then

&#x20;       return "invalid\_same\_player"

&#x20;   end



&#x20;   return "success"

end

```



추가 검증:



\- 좌측/우측 역할이 실제 다른 Prompt에서 왔는지

\- 두 플레이어가 같은 파티·같은 서버·같은 미션 인스턴스인지

\- 각 플레이어가 해당 스위치 근처인지

\- 성공 처리 뒤 동일 팀이 다시 보상을 받지 않는지

\- 팀원 이탈 시 준비 상태를 무효화하고 NPC 대체가 되는지



\## 중복 보상 방지: 멱등성



“검증 통과”와 “보상 지급”을 분리하면 중간에 재접속·동시 이벤트가 들어올 때 중복 보상이 생깁니다. 보상은 항상 \*\*멱등적\*\*으로 구현하세요.



```lua

\-- 예시: 서버 세션 상태

local granted = {}



local function grantGateCompletionOnce(player)

&#x20;   local userId = player.UserId



&#x20;   if granted\[userId] then

&#x20;       return false

&#x20;   end



&#x20;   granted\[userId] = true



&#x20;   -- 실제로는 DataStore UpdateAsync 등 영속 저장과 결합

&#x20;   RewardService:addExplorerCard(player, "central\_gate")

&#x20;   RewardService:addCitizenProgress(player, 1)



&#x20;   return true

end

```



실제 운영에서는 서버 세션 테이블만으로 충분하지 않습니다. 서버 이동·재접속 후에도 중복 지급이 없어야 하므로, 영속 데이터 저장에서 “이미 지급됨”을 원자적으로 확인하고 갱신해야 합니다.



```lua

\-- 개념적 예시

DataStore:UpdateAsync("player:" .. player.UserId, function(data)

&#x20;   data = data or { rewards = {} }



&#x20;   if data.rewards.central\_gate then

&#x20;       return data

&#x20;   end



&#x20;   data.rewards.central\_gate = true

&#x20;   data.citizenProgress = (data.citizenProgress or 0) + 1

&#x20;   return data

end)

```



\## 성능 최적화



다중 검증이 많다고 매 Prompt마다 무거운 저장소 호출을 하면 안 됩니다.



\### 빠른 경로와 느린 경로 분리



```text

빠른 인메모리 검사:

\- Prompt ID

\- Enabled

\- 캐릭터/생존

\- 거리

\- 쿨다운

\- 현재 상태

\- 팀/역할

\- 세션 완료 플래그



느린 영속 검사:

\- DataStore 보상 중복 확인

\- 시민권 영구 자격 확인

\- 희귀 아이템·유료 보상 지급

\- 서버 이동을 넘는 중요한 진행 저장

```



\### 거리 계산 최적화



\- `HumanoidRootPart.Position`과 Prompt 위치를 한 번만 구합니다.

\- `Magnitude` 대신 제곱 거리 비교를 쓰면 `sqrt`를 피할 수 있습니다.

\- 거리 검사는 `PromptTriggered` 같은 이벤트 시에만 수행합니다.

\- 매 프레임 모든 Prompt와 플레이어 거리를 검사하지 마세요.



```lua

local function withinDistanceSquared(a, b, maxDistance)

&#x20;   local delta = a - b

&#x20;   return delta:Dot(delta) <= maxDistance \* maxDistance

end

```



\### Prompt 위치 캐시



정적 오브젝트라면 `Attachment.WorldPosition`을 매번 탐색하지 말고 초기화 시 캐시할 수 있습니다. 다만 움직이는 기차·드론·플랫폼의 Prompt는 매 상호작용 때 최신 위치를 읽어야 합니다.



\### 쿨다운 자료구조 정리



플레이어가 나갈 때, 퀘스트가 끝날 때, 라운드가 초기화될 때 해당 플레이어/상호작용 키를 지우세요. 메모리 누적을 막을 수 있습니다.



\## 실패 메시지 정책



보안 실패는 대부분 플레이어에게 노출하지 않는 것이 좋습니다.



| 검증 실패 | 플레이어 UI | 서버 로그 |

|---|---|---|

| 너무 빠른 연타 | 없음 또는 짧은 입력 무시 | rate-limit 카운트 |

| 거리 밖 요청 | 없음 | suspicious-distance |

| 알 수 없는 InteractionId | 없음 | unknown-interaction |

| 잘못된 퀘스트 순서 | `아직 다른 신호를 먼저 복구해야 해.` | wrong-state |

| 자격 부족 | `이 구역은 다음 자격이 필요해.` | no-permission |

| 이미 완료 | `이미 복구된 신호야.` | duplicate |

| 팀원 대기 | `팀 신호를 기다리는 중` | 정상 운영 로그 |

| 반복적 이상 요청 | 없음 | 보안 플래그·속도 제한 |



치터에게 검증 로직을 상세히 설명하지 말고, 일반 플레이어의 정상적인 순서 오류에만 친절한 안내를 제공하세요.



\## 자동 QA Harness



```text

V01: Prompt.Enabled=false면 처리되지 않는다.

V02: 서버 Config에 없는 InteractionId면 처리되지 않는다.

V03: 캐릭터/HumanoidRootPart가 없으면 처리되지 않는다.

V04: 사망 상태면 처리되지 않는다.

V05: 설정 거리+여유값 밖에서는 처리되지 않는다.

V06: 0.35초 내 같은 Prompt 연타는 한 번만 처리된다.

V07: 필요 상태가 아니면 신호/보상이 진행되지 않는다.

V08: 다른 파티·다른 인스턴스 플레이어는 협동 성공 조건을 채우지 못한다.

V09: 좌/우 스위치를 같은 플레이어가 채워도 성공하지 않는다.

V10: 협동 3초 창을 넘으면 성공하지 않는다.

V11: 이미 보상을 받은 뒤 재접속해도 중복 지급되지 않는다.

V12: 서버 저장 실패 시 보상을 “지급 성공”으로 표시하지 않는다.

V13: 비정상 거리·속도·호출 반복은 텔레메트리에 기록된다.

V14: 정상 모바일/PC/게임패드 상호작용은 모든 검증을 통과한다.

```



\## 결론



최적화된 ProximityPrompt 다중 조건 검증은 이 공식으로 정리됩니다.



```text

서버 Config

\+ 빠른 실패 처리

\+ 서버 거리 계산

\+ 상태 머신

\+ 권한/팀 검증

\+ 서버 쿨다운

\+ 멱등적 보상

\+ 필요한 경우 영속 저장

\+ 이상 텔레메트리

```



그리고 가장 중요한 보안 원칙은 다음입니다.



> \*\*Prompt UI, 홀드 게이지, 클라이언트 거리, 클라이언트 상태는 모두 ‘사용자 경험’이다.  

> 게임 진도·자격증·보상·시민권을 바꾸는 근거는 서버가 독립적으로 확인한 상태뿐이다.\*\*

