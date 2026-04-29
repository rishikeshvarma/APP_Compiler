# REPAIR TICKET: Cross-Layer Schema Inconsistency

**Ticket ID:** RT-2026-04-29-001
**Auditor:** Agent C (The Validator)
**Severity:** Critical (Blocks functional implementation)

---

## 1. Missing Database Support for "Hot Leads"
- **Location:** [db_schema.sql](file:///home/rishi/Desktop/stuff/AI_Internship/project/schemas/db_schema.sql#L31-L39)
- **Mismatch:** The `leads` table lacks a `priority` or `is_hot` column.
- **Dependency:** [api_endpoints.json](file:///home/rishi/Desktop/stuff/AI_Internship/project/schemas/api_endpoints.json#L12-L17) requires this to support the `/api/v1/leads/hot` endpoint.
- **Repair Instruction:** Add `is_hot BOOLEAN DEFAULT FALSE` to the `leads` table in `db_schema.sql`.

## 2. Missing Database Support for Payment Automation
- **Location:** [db_schema.sql](file:///home/rishi/Desktop/stuff/AI_Internship/project/schemas/db_schema.sql#L67)
- **Mismatch:** No table or columns exist to store payment gateway configurations.
- **Dependency:** [api_endpoints.json](file:///home/rishi/Desktop/stuff/AI_Internship/project/schemas/api_endpoints.json#L94-L105) requires storage for `gateway` (string) and `auto_invoice` (boolean) via the `/api/v1/payments/automate` endpoint.
- **Repair Instruction:** Add `gateway TEXT` and `auto_invoice BOOLEAN DEFAULT FALSE` to the `teams` table (or create a `system_settings` table). For simplicity in this DDL, let's add them to `plan_types` or a new `payment_configs` table. Let's create a new table `payment_configs`.

## 3. Missing API Endpoints for UI Actions
- **Location:** [api_endpoints.json](file:///home/rishi/Desktop/stuff/AI_Internship/project/schemas/api_endpoints.json#L106)
- **Mismatch:** No endpoints exist for updating lead status or reassigning owners.
- **Dependency:** [ui_layout.json](file:///home/rishi/Desktop/stuff/AI_Internship/project/schemas/ui_layout.json#L60) defines `update-status` and `reassign` actions in the `LeadDataTable` component.
- **Repair Instruction:** Add a new endpoint to `api_endpoints.json`:
    - `PATCH /api/v1/leads/:id`
    - Roles: `["Rep", "Manager", "Admin"]`
    - Validation: `body: { status: "string", owner_id: "uuid" }`

---

**Next Step:** Compiler agent to execute repairs based on these instructions.
