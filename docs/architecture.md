# Current foundation

This branch keeps the useful parts already present in `main`:

- Django project bootstrap and admin
- basic 3x-ui panel, plan, and service models
- simple provisioning service and Telegram polling bot
- payment receipt intake flow

It adds the missing control layer needed for the planned system:

- admin profiles, roles, grants, and panel scopes
- generation policy per plan and optional panel
- daily quota ledger for config generation
- audit log for privileged actions
- provisioning policy enforcement before creating a service
- migration coverage for models that existed in Python code but were not yet represented in the verified initial migration
