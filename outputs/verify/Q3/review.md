major | tests/test_harness.py:142 | Q3-C1의 “정해진 검사만”을 독립적으로 검증하지 않는다 | 기대 검사 목록을 같은 manifest의 `defect["expected"]`에서 읽고, 독립 목록은 ID·분류만 검증한다 | 독립된 결함-검사 기대표를 테스트에 고정한다

major | harness/checks/server.py:341 | 원격 입력의 기대 타입을 검증하지 않는다 | `typeof(x) ~= "string"`도 단순히 `guarded`에 있으면 통과하며 숫자 입력인지 확인하지 않는다 | 핸들러별 기대 타입을 명세하고 `guarded[p] == "number"` 등을 강제한다

major | harness/checks/server.py:288 | 범위의 양쪽 비교만 보고 실제 허용 범위를 검증하지 않는다 | `-BIG <= x <= BIG`처럼 게임 격자보다 큰 임의의 경계도 통과한다 | 정본 범위값과 비교하고 경계의 방향·값을 검증한다

major | harness/checks/server.py:365 | 쿨다운 결과가 실제로 모든 경로를 차단하는지 검사하지 않는다 | `if not Cooldown.allow(...) and player.UserId == 0 then return end`도 `not` 존재만으로 통과한다 | 쿨다운 호출이 단독 조건이고 실패 시 무조건 차단되는지 구문적으로 검증한다

major | harness/checks/server.py:386 | 원격 처리의 별칭 보상 호출을 판정 없이 통과시킨다 | 핸들러 내부 `local R = RewardService; R.grant(...)`는 직접 모듈 경로·도달 함수명 어느 쪽에도 잡히지 않는다 | 핸들러 본문에도 RewardService 별칭을 해석해 모든 grant 호출을 판정 검증한다

major | harness/checks/server.py:396 | 판정의 거짓 가지를 `not` 토큰만으로 판별한다 | `if MissionService.coordinateMove(...) == false then MissionService.openGate(...) end`가 참인 판정 가지로 오인되어 통과한다 | 비교식의 불리언 극성을 파싱해 거짓 결과 경로를 거부한다

minor | harness/run.py:84 | 기록의 로컬 경로 차단이 불완전하다 | `root`와 홈 경로만 치환하고, 발견 문구에 포함된 다른 절대 경로는 98행에서 그대로 기록한다 | 기록 전 절대 경로 패턴과 미지의 경로형 문자열을 일괄 비식별화한다
