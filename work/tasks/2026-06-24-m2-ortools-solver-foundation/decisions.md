# M2 OR-Tools Solver Foundation Decisions

## 1. API 연결 전 solver 단위 테스트

ScheduleRun API는 현재 mock result 계약을 가지고 있습니다. OR-Tools 제약 모델을 먼저 독립 모듈로 고정한 뒤 다음 증분에서 API translation을 연결합니다.

## 2. 미배정은 soft penalty

기획 원칙에 따라 미배정은 hard infeasible이 아니라 soft penalty와 `unfilled_requirement` issue로 표현합니다.

## 3. 결정적 출력 우선

같은 입력에서 같은 assignment 순서를 얻도록 입력과 출력 정렬을 고정합니다. CP-SAT 내부 탐색은 단일 worker와 고정 seed로 제한합니다.

## 4. 개인정보 없음

solver input은 employee id/code 수준 식별자만 다룹니다. LLM payload나 설명 문장은 이번 범위에 없습니다.

## 5. OR-Tools 문서 확인

2026-06-24에 Google Developers OR-Tools 설치 문서와 CP-SAT 문서를 확인했습니다. Python 설치는 `python -m pip install ortools`, CP-SAT Python import는 `from ortools.sat.python import cp_model` 경로를 사용합니다. CP-SAT는 정수 기반 제약 모델이므로 미배정 수와 penalty도 정수 변수/계수로 모델링합니다.
