# Delivery plan

## Goal
- Finish the branch into a strong production-minded foundation for a 3x-ui Telegram seller bot with Django admin, scoped multi-admin permissions, and controlled config generation.

## What already exists
- Django project, admin, SQLite setup, API health endpoint
- Plan, panel, user service, payment receipt, and system config models
- Basic Telegram polling bot
- Basic 3x-ui client and provisioning flow
- Installer and deployment bootstrap

## What this branch is building
- Explicit admin roles and grants
- Panel-level admin scopes
- Config generation policy and daily quota controls
- Audit logging for privileged actions
- Admin receipt approval that provisions services through the policy layer
- A clearer execution path toward renew, suspend, revoke, reporting, and async job support

## Full todo list

### Platform foundation
- Keep migrations linear and valid
- Expand tests around policy enforcement and admin approval flows
- Add seed/bootstrap commands for roles and initial config
- Document architecture and rollout order in-repo

### Permissions and policy
- Add admin profile, role, grant, assignment, and panel scope models
- Enforce `configs.generate` through a service-layer policy check
- Enforce per-panel daily admin limits
- Enforce per-plan generation policy and self-service toggles
- Record quota events for each successful generation
- Record audit entries for each privileged action

### Sales and approval flow
- Let users submit receipts
- Let admins approve receipts from Django admin
- Provision services automatically on approval
- Reject receipts cleanly from Django admin
- Prevent approval actions from bypassing policy checks

### Service lifecycle
- Support renew flow in the service layer
- Support suspend and revoke flow in the service layer
- Track service status transitions explicitly
- Add admin actions for lifecycle management

### Telegram bot
- Keep customer menu simple and working
- Add clearer service status display
- Add renewal entry point
- Add `payment pending` and `receipt submitted` states
- Later: split handlers and business logic more cleanly for async-first operation

### 3x-ui integration
- Keep 3x-ui code isolated behind service adapters
- Add stronger error messages and retry strategy
- Extend adapter for lifecycle operations after create
- Add tests around provisioning edge cases

### Admin and operations
- Add role bootstrap command
- Add better list filters and search for services, audits, quotas
- Add operational visibility for who approved what
- Preserve existing restart controls

### Later but planned
- Payment gateway callbacks
- Usage sync and expiry jobs
- Reporting dashboards
- Background worker separation
- Full async bot/webhook architecture

## Execution order
1. Fix migration chain and stabilize the policy foundation.
2. Finish admin approval and provisioning flow.
3. Add tests for policy and approval behavior.
4. Add service lifecycle actions and status transitions.
5. Improve Telegram and API integration around the new service layer.
6. Continue toward async separation and background jobs.
