# Cross-Tenant Constraint Plan

Date: 2026-06-26

## Current Implemented Steps

`employee_roles` has tenant composite foreign keys:

- `(organization_id, employee_id)` -> `employees(organization_id, id)`
- `(organization_id, role_id)` -> `roles(organization_id, id)`

`unavailabilities` has a tenant composite foreign key:

- `(organization_id, employee_id)` -> `employees(organization_id, id)`

`employee_user_links` has a tenant composite foreign key:

- `(organization_id, employee_id)` -> `employees(organization_id, id)`

`employee_requests` has a tenant composite foreign key:

- `(organization_id, employee_id)` -> `employees(organization_id, id)`

`assignments` has tenant composite foreign keys:

- `(organization_id, schedule_run_id)` -> `schedule_runs(organization_id, id)`
- `(organization_id, shift_slot_id)` -> `shift_slots(organization_id, id)`
- `(organization_id, role_id)` -> `roles(organization_id, id)`
- `(organization_id, employee_id)` -> `employees(organization_id, id)`

`publication_acknowledgements` and `publication_notifications` have tenant composite foreign keys:

- `(organization_id, publication_id)` -> `schedule_publications(organization_id, id)`
- `(organization_id, employee_id)` -> `employees(organization_id, id)`

Schedule-result rows have tenant composite foreign keys:

- `shift_slots`: `(organization_id, schedule_run_id)` -> `schedule_runs(organization_id, id)`
- `schedule_requirements`: `(organization_id, schedule_run_id)` -> `schedule_runs(organization_id, id)`, `(organization_id, shift_slot_id)` -> `shift_slots(organization_id, id)`, `(organization_id, role_id)` -> `roles(organization_id, id)`
- `schedule_issues`: `(organization_id, schedule_run_id)` -> `schedule_runs(organization_id, id)`, `(organization_id, shift_slot_id)` -> `shift_slots(organization_id, id)`, `(organization_id, role_id)` -> `roles(organization_id, id)`
- `relaxation_proposals`: `(organization_id, schedule_run_id)` -> `schedule_runs(organization_id, id)`, `(organization_id, affected_shift_slot_id)` -> `shift_slots(organization_id, id)`
- `solver_diagnostic_events`: `(organization_id, schedule_run_id)` -> `schedule_runs(organization_id, id)`, `(organization_id, shift_slot_id)` -> `shift_slots(organization_id, id)`, `(organization_id, role_id)` -> `roles(organization_id, id)`, `(organization_id, employee_id)` -> `employees(organization_id, id)`

Reference, compliance, and RAG rows have tenant composite foreign keys:

- `shift_requirements`: `(organization_id, shift_type_id)` -> `shift_types(organization_id, id)`, `(organization_id, role_id)` -> `roles(organization_id, id)`
- `pair_constraints`: each employee reference, including normalized employee ids, points to `employees(organization_id, id)`
- `compliance_warning_overrides`: `(organization_id, schedule_run_id)` -> `schedule_runs(organization_id, id)`
- `rag_document_chunks`: `(organization_id, document_id)` -> `rag_documents(organization_id, id)`

The parent tables also expose composite unique keys:

- `employees(organization_id, id)`
- `roles(organization_id, id)`
- `schedule_runs(organization_id, id)`
- `shift_slots(organization_id, id)`
- `schedule_publications(organization_id, id)`
- `shift_types(organization_id, id)`
- `rag_documents(organization_id, id)`

This prevents role eligibility, employee unavailability, employee-user link, employee request, persisted assignment, publication acknowledgement, publication notification, schedule-result, reference-data, compliance-run, and RAG chunk rows from mixing references from another tenant even when the referenced global ID exists.

## Expansion Order

Completed through Alembic `20260627_0027`.

Remaining candidates require additional product semantics before FK rollout:

1. Schedule-run-owned parent rows outside the latest batch:
   - `schedule_input_snapshots`
   - `override_approvals`
   - `schedule_recalculation_requests`
   - `schedule_publications`
2. Nullable or snapshot identity fields:
   - `shift_slots.shift_type_id` uses nullable `ON DELETE SET NULL`; composite handling should be designed explicitly before changing it.
   - `compliance_warning_overrides.employee_id`, `slot_id`, `week_key`, and `snapshot_hash` are warning-instance identity values and can be empty-string sentinels. Do not add employee/slot FKs until those identities are split from snapshot keys.
3. Audit-only rows:
   - `rag_query_audits` remain tenant-scoped audit records.

## Migration Rules

- Add parent `(organization_id, id)` unique constraints before child composite FKs.
- Keep existing single-column FK constraints during transition.
- Use Alembic batch mode for SQLite test compatibility.
- Add PostgreSQL staging verification for every new composite FK batch.
- Avoid `ON DELETE SET NULL` composite FKs until nullable tenant identity is designed explicitly.
- Current hardening uses `ON DELETE CASCADE`, matching existing single-column FK deletion behavior. Future hard-delete features must re-check whether cascading historical schedule artifacts is still acceptable.

## Remaining Risk

Application-level tenant checks and RLS remain necessary. Composite FKs prevent persisted cross-tenant references, but they do not replace authenticated actor checks, request-scoped tenant context, or row-level security.
