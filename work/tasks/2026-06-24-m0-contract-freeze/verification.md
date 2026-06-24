# Verification

## 수행한 검증

### 작업 하네스 파일 존재 확인

명령:

```powershell
Test-Path 'work\tasks\2026-06-24-m0-contract-freeze\brief.md'
Test-Path 'work\tasks\2026-06-24-m0-contract-freeze\plan.md'
Test-Path 'work\tasks\2026-06-24-m0-contract-freeze\decisions.md'
Test-Path 'work\tasks\2026-06-24-m0-contract-freeze\verification.md'
Test-Path 'work\tasks\2026-06-24-m0-contract-freeze\handoff.md'
```

결과: 다섯 항목 모두 `True`입니다.

### OpenAPI JSON 파싱

명령:

```powershell
@'
import json
from pathlib import Path
path = Path('docs/contracts/openapi.m0.json')
json.loads(path.read_text(encoding='utf-8'))
print(f'parsed {path}')
'@ | python -
```

결과: `parsed docs\contracts\openapi.m0.json`

### fixture JSON 파싱

명령:

```powershell
@'
import json
from pathlib import Path
for path in sorted(Path('docs/contracts/fixtures').glob('*.json')):
    json.loads(path.read_text(encoding='utf-8'))
    print(f'parsed {path}')
'@ | python -
```

결과:

```text
parsed docs\contracts\fixtures\p0-result-after-recalculation.json
parsed docs\contracts\fixtures\p0-result-before-relaxation.json
parsed docs\contracts\fixtures\p0-schedule-run-running.json
```

### 상태 머신 핵심 용어 확인

명령:

```powershell
rg -n "queued|running|succeeded|infeasible|failed|canceled|current_attempt_no|recalculation_count|SchedulePublication" docs\contracts\schedule-run-state-machine.md
```

결과: 상태 6개, `current_attempt_no`, `recalculation_count`, `SchedulePublication` 관련 설명이 모두 검색되었습니다.

### DB 계획 핵심 invariant 확인

명령:

```powershell
rg -n "employees\(organization_id, employee_code\)|pair_constraints|schedule_publications|RLS|FORCE ROW LEVEL SECURITY" docs\contracts\m0-db-migration-plan.md
```

결과: employee unique, pair constraint 정규화, publication overlap, RLS, `FORCE ROW LEVEL SECURITY` 항목이 모두 검색되었습니다.

### P0 path/schema 일관성 확인

명령:

```powershell
@'
import json
from pathlib import Path
api = json.loads(Path('docs/contracts/openapi.m0.json').read_text(encoding='utf-8'))
required_paths = [
    '/organizations',
    '/organizations/{organization_id}/employees/bulk-paste',
    '/organizations/{organization_id}/unavailabilities',
    '/organizations/{organization_id}/pair-constraints',
    '/organizations/{organization_id}/schedule-runs',
    '/organizations/{organization_id}/schedule-runs/{schedule_run_id}',
    '/organizations/{organization_id}/schedule-runs/{schedule_run_id}/result',
    '/organizations/{organization_id}/schedule-runs/{schedule_run_id}/manual-edits/validate',
    '/organizations/{organization_id}/schedule-runs/{schedule_run_id}/relaxation-proposals/{proposal_id}/approve',
    '/organizations/{organization_id}/schedule-runs/{schedule_run_id}/recalculate',
    '/organizations/{organization_id}/schedule-runs/{schedule_run_id}/publications',
    '/organizations/{organization_id}/schedule-publications/{publication_id}/excel'
]
missing_paths = [p for p in required_paths if p not in api['paths']]
required_schemas = [
    'ScheduleRunStatus', 'SolutionQuality', 'SolverStatus', 'Severity', 'IssueType',
    'ReasonCode', 'RelaxationProposalType', 'RelaxationProposalStatus', 'AssignmentSource',
    'WarningState', 'PublicationStatus', 'ScheduleRunResponse', 'ScheduleRunResultResponse',
    'ScheduleIssue', 'RelaxationProposal', 'SchedulePublication'
]
missing_schemas = [s for s in required_schemas if s not in api['components']['schemas']]
print(f'paths={len(api["paths"])} schemas={len(api["components"]["schemas"])}')
print(f'missing_paths={missing_paths}')
print(f'missing_schemas={missing_schemas}')
if missing_paths or missing_schemas:
    raise SystemExit(1)
'@ | python -
```

결과:

```text
paths=13 schemas=46
missing_paths=[]
missing_schemas=[]
```

## 결과

- M0 계약 고정 문서와 fixture를 작성했습니다.
- OpenAPI JSON과 fixture JSON은 파싱 검증을 통과했습니다.
- P0 vertical slice에 필요한 API path와 핵심 schema가 OpenAPI에 포함되어 있음을 확인했습니다.
- 상태 머신과 DB migration 계획에 핵심 용어와 invariant가 포함되어 있음을 확인했습니다.

## 남은 위험

- OpenAPI 검증은 JSON 파싱과 핵심 path/schema 존재 확인 수준입니다. 정식 OpenAPI semantic validation은 앱 의존성 또는 별도 validator 도입 후 수행해야 합니다.
- fixture가 OpenAPI schema를 엄격히 validate하는 검증은 아직 없습니다. M1 스캐폴딩에서 schema 기반 contract test로 옮겨야 합니다.
- 실제 DB constraint 구현 가능성은 PostgreSQL/Alembic 스캐폴딩 후 migration 테스트로 검증해야 합니다.
- `btree_gist` extension 사용 가능 여부는 실제 Railway PostgreSQL 환경에서 확인해야 합니다.
