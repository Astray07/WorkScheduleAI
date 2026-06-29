# 공개 문서 안내

이 디렉터리는 제출자와 검토자가 직접 읽어도 되는 공개 문서만 남기는 것을 원칙으로 합니다.

## 제출 문서

- `submission-report.md`: 프로젝트 목표, 구조, 주요 기능, 의사결정, 한계, 향후 개선 방향을 정리한 제출 보고서입니다.
- `../output/pdf/workscheduleai-submission-report.pdf`: 제출 보고서 PDF 변환본입니다.

## 계약 문서

- `contracts/openapi.m0.json`: API 계약 스냅샷입니다.
- `contracts/schedule-run-state-machine.md`: ScheduleRun 상태와 허용 전이를 설명합니다.
- `contracts/xlsx-import-contract.md`: CSV/TSV/XLSX 가져오기 요청과 시트 계약을 설명합니다.
- `contracts/fixtures/*.json`: 결과 화면과 계약 테스트에 쓰는 fixture입니다.

## 공개하지 않는 문서

작업 기록, 릴리스 체크리스트, 배포 런북, 실험 기록은 공개 제출물로 추적하지 않습니다. 이 구분은 제출용 저장소가 내부 운영 메모처럼 보이지 않게 하기 위한 것입니다.
