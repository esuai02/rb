critical | harness/checks/server.py:249-307 | 불가능한 `and` 범위 조건도 유효한 범위 검증으로 통과시킨다 | `x < -GRID and x > GRID` 원격 입력이 `remote_validation`에서 발견 없이 통과했다 | 비교식의 논리 구조를 검증하고 OR 형태의 하한·상한 조건만 허용

critical | harness/checks/server.py:325-333 | 쿨다운 조건의 극성을 확인하지 않는다 | `if Cooldown.allow(...) then return end`가 `remote_cooldown`을 통과해 쿨다운 거부 시 처리를 허용한다 | `if not Cooldown.allow(...) then return end` 형태 또는 동등한 의미만 인정

critical | harness/checks/server.py:133-158 | 대괄호 방식의 `OnServerEvent`·`OnServerInvoke` 등록을 검사하지 않는다 | `R["OnServerEvent"]:Connect(function(...) ...)`에 대해 원격 검사가 모두 빈 결과를 반환했다 | 대괄호 속성 접근을 파싱하거나 미인식 원격 등록을 실패 처리

critical | harness/checks/server.py:355-374 | 서버 판정의 결과가 거짓인 분기도 보상 허용으로 판정한다 | `if not MissionService.coordinateMove(...) then MissionService.openGate(...) end`가 `reward_after_verdict`를 통과했다 | 판정 호출의 긍정 결과 분기만 보상 경로로 인정

critical | harness/checks/server.py:27-40,345-347 | `RewardService["grant"]` 호출은 중복·우회 보상 검사에서 보이지 않는다 | 대괄호 호출을 원격 핸들러 안에 넣어도 `duplicate_reward`와 `reward_after_verdict`가 모두 빈 결과였다 | `find_calls`에 대괄호 경로를 추가하거나 보상 모듈의 모든 인덱스 호출을 보수적으로 실패 처리

major | harness/checks/math_claims.py:103-129,153-156 | `slope_compare`의 비교 결과가 대사에 없어도 통과한다 | 비교 명제를 `"이 문장은 수학을 말하지 않아."`에 연결해도 `math.truth`가 빈 결과를 반환했다 | steeper·less_steep·equal의 잠긴 다국어 표현을 명제 패턴에 포함하고 미확인 시 실패

major | harness/checks/math_claims.py:80-84,115-120 | 분수 값은 대사에 존재하는지 검사하지 않는다 | `1/3` 기울기 명제를 `"기울기라고만 말한다."`에 연결해도 `math.truth`가 통과했다 | 분수의 정규·현지화 표현을 검사하거나 숫자 연결 불가 명제를 실패 처리

major | harness/checks/analytics.py:19-24,66-68 | 분석 메서드 별칭을 추적하지 않아 개인정보·허용 밖 이벤트를 우회한다 | `local send = Analytics.log; send(player, "player_profile", {name = player.Name})`가 빈 결과였다 | `Analytics.log`·`Analytics.funnel` 함수값 별칭을 추적하거나 미인식 별칭 호출을 실패 처리

major | harness/checks/i18n.py:125-135 | 식별자처럼 보이는 하드코딩 문구와 UI 대입 흐름을 놓친다 | `local label = "Open_Gate"; goal.Text = label`은 직접 UI 문자열도 일반 문자열도 검출하지 않는다 | UI 속성에 도달하는 변수의 상수 문자열을 추적하고 키 조회 결과가 아닌 값은 실패 처리

major | harness/source.py:139-147 | `content/`를 Rojo에 매핑해도 전체 파일을 무조건 건너뛴다 | `content`가 런타임 경로로 매핑된 경우에도 `rel.split(...)[0] in HARNESS_INPUT`에서 코드 검사가 생략된다 | `content` 매핑을 명시적으로 금지하거나, 매핑된 파일은 검사하고 `math_claims.yaml`만 입력 예외로 처리
