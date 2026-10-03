critical | harness/checks/server.py:16-30 | 테이블/객체 경유 보상 호출이 서버 권위·중복 보상 검사 우회 | `services.RewardService.grant(...)`는 직접 별칭만 추적하므로 `reward_authority`, `duplicate_reward`, `reward_after_verdict` 모두 빈 결과가 됨. 클라이언트 코드에서도 동일 | 검증된 RewardService 경로가 아닌 미해석 멤버 체인은 거부하거나 테이블 별칭까지 해석

major | harness/checks/analytics.py:19-20 | 테이블 경유 분석 호출이 허용 이벤트 검사를 우회 | `_aliases`가 직접 모듈 별칭만 추적한다. `services.Analytics.log(player, "not_allowed", {})`를 넣어 `analytics.calls`를 실행하면 발견이 없음 | 분석 모듈 경로의 테이블 별칭을 해석하고, 미해석 체인은 거부

major | harness/source.py:152-159 | `src/../outside` 매핑이 src 밖 경로인데 통과 | `$path`를 문자열 접두사로만 검사한 뒤 `resolve()` 결과가 저장소 안이면 허용한다. 이후 159행에서 해당 외부-src 파일을 정상 소스로 로드함 | 정규화된 대상이 `(root/src).resolve()` 내부인지 검사하고, 하위 파일·심볼릭 링크도 저장소/src 밖이면 거부
