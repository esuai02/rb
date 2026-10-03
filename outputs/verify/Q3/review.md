major | harness/checks/safety.py:11,35-38 | 허용 목록 밖의 bare domain이 통과한다 | `example.museum`은 URL 검사 결과가 `[]`이며, 테스트는 `.education`만 검증한다 | 일반 hostname 판별을 사용하고 미등록 TLD 회귀 테스트를 추가

major | harness/checks/safety.py:46-52 | 해석 불가능한 URL 조립을 거부하지 않는다 | `getScheme() .. getHost()`는 URL 조각이 없어 `_url_like_part`를 통과한다 | URL 문맥의 미해석 연결식은 항상 실패 처리

major | harness/checks/analytics.py:126-130,178-180 | 분석 모듈의 플레이어 매개변수 이름을 바꾸면 개인정보가 통과한다 | `function Analytics.log(p: Player, ...)`에서 `p.Name`을 써도 `analytics.calls`가 `[]`이다 | `Player` 매개변수와 그 별칭을 추적해 identity 속성을 거부

major | harness/checks/server.py:105-108 | 미해석 서비스·메서드로 저장 권한을 우회할 수 있다 | `game:GetService(getServiceName())[getMethod()]("x", 1)`이 `server.reward_authority`에서 `[]`이다 | 미해석 서비스·동적 멤버를 보상·저장 권한 가능성으로 거부
