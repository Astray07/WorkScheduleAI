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

The parent tables also expose composite unique keys:

- `employees(organization_id, id)`
- `roles(organization_id, id)`

This prevents role eligibility, employee unavailability, and employee-user link rows from mixing employee or role references from another tenant even when the referenced global ID exists.

## Expansion Order

1. Employee-owned rows:
   - `employee_requests`
   - `publication_acknowledgements`
   - `publication_notifications`
2. Schedule-run-owned rows:
   - `shift_slots`
   - `schedule_requirements`
   - `assignments`
   - `schedule_issues`
   - `relaxation_proposals`
   - `solver_diagnostic_events`
3. Reference-data rows:
   - `shift_requirements` -> `shift_types` and `roles`
   - `pair_constraints` -> both employees
   - compliance warning overrides -> schedule runs and optional employee/slot identity
4. RAG rows:
   - `rag_document_chunks` -> `rag_documents`
   - `rag_query_audits` remain tenant-scoped audit records.

## Migration Rules

- Add parent `(organization_id, id)` unique constraints before child composite FKs.
- Keep existing single-column FK constraints during transition.
- Use Alembic batch mode for SQLite test compatibility.
- Add PostgreSQL staging verification for every new composite FK batch.
- Avoid `ON DELETE SET NULL` composite FKs until nullable tenant identity is designed explicitly.

## Remaining Risk

Application-level tenant checks and RLS remain necessary. Composite FKs prevent persisted cross-tenant references, but they do not replace authenticated actor checks, request-scoped tenant context, or row-level security.
