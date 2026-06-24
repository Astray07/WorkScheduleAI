# Decisions

## 1. 다음 단계 범위

M1 전체 CRUD로 바로 들어가지 않고, 먼저 Python 스캐폴딩과 계약 테스트를 만듭니다. 현재 저장소에는 앱 코드가 없으므로, 테스트 가능한 기반 없이 DB/API 구현으로 바로 가는 것은 위험합니다.

## 2. 외부 의존성

이번 단계는 Python 표준 라이브러리와 이미 설치된 pytest만 사용합니다. FastAPI와 SQLAlchemy 의존성은 실제 route와 DB model을 만들 때 추가합니다.

## 3. 계약 검증 방식

M0 OpenAPI 파일과 fixture를 production code에서 직접 읽고 검증합니다. 이후 FastAPI schema, frontend mock server, worker payload test가 같은 기준을 공유할 수 있게 하기 위함입니다.

## 4. 브랜치

구현 작업은 `feature/m1-scaffold-contract-tests` 브랜치에서 진행합니다. `main`에는 M0 문서 첫 커밋만 보존합니다.

