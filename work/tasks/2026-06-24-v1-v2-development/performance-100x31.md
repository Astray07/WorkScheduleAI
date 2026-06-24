# 100 Employees / 31 Days Performance Record

확인일: 2026-06-24

## 목적

1차 릴리즈 이후 hardening 범위였던 직원 100명, 생성 기간 31일 조건에서 현재 OR-Tools solver 경로가 안정적으로 동작하는지 확인합니다.

## 방법

- fixture: `make_large_schedule_request(employee_count=100, day_count=31)`
- roles: `role_senior`, `role_junior`
- slots: 31 daily slots
- requirements: 62 total requirements, one senior and one junior per day
- unavailable/block pair constraints: none
- solver mode: deterministic baseline, `num_search_workers=1`, `random_seed=1`
- command: inline Python timer around `solve_schedule(request)`

## 결과

- elapsed_seconds: 0.0543
- solver status: succeeded
- assignments: 62
- issues: 0
- slots: 31
- requirements: 62
- employees: 100

## 판단

현재 100명/31일 baseline에서는 병목이 확인되지 않았습니다. 임의 최적화나 fast mode 추가는 보류하고, `tests/solver/test_large_schedule_performance.py`로 10초 미만 회귀 기준만 고정합니다.

## 한계

- 제약이 없는 baseline입니다.
- 다수 휴가, blocked pair, manual lock이 섞인 최악 케이스는 별도 성능 케이스가 필요합니다.
- 이 로컬 측정은 Windows 개발 환경 기준이며 Railway 리소스에서의 smoke는 마지막 통합 점검 단계로 미룹니다.
