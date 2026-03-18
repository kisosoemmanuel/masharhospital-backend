# main.py Update Progress Tracker

## Approved Plan Breakdown

### [x] 1. Create TODO.md with steps (Current)

### [x] 2. Refactor Imports & Config

### [x] 3. Lifespan & App Setup

- DB init added to lifespan
- OpenAPI tags and improved title/description

### [x] 4. Dependencies & Helpers

- Added require_role decorator
- Enhanced get_current_user with validation

### [ ] 5. Authentication Routes

- Universal /api/login
- Role-specific aliases

### [x] 6. Public & Core Routes
 - Root /
 - /api/health enhanced
 - Patient list/create/get with tags
 - Queue status tagged
 - Admin dashboard with RBAC

### [ ] 6. Public & Core Routes

- Root /
- /api/health
- Queue public status

### [ ] 7. Patient & Queue Protected Routes

- Full CRUD + search
- Queue register/next/waiting

### [ ] 8. Role-Specific Dashboards & Mgmt

- Admin dashboard/staff/beds/inventory/logs
- Receptionist quick-reg/dashboard

### [ ] 9. Testing & Cleanup

- Consistent responses
- Error handling
- uvicorn run block

### [ ] 10. attempt_completion

- Final result summary
- Demo commands
