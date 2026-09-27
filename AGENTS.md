# AGENTS.md

## Project overview

This repository is the Django backend and web dashboard for **Web Automation With Excel**. It manages User Licenses, ERP Licenses, PMFBY/Fasal Rin integrations, Khata ledgers, reminders, coupons, Google Drive downloads/attachments, UPI QR generation, and optional Razorpay payment flows.

The production site is hosted on Render and the primary database is MySQL. Excel/VBA clients call selected licensing APIs, so API response fields and status codes are public contracts even when no mobile or browser frontend uses them.

## Canonical working copy

- Work from `H:\django\software_admin` unless the user explicitly selects another clone.
- The Google Drive clone can suffer filesystem hook/lock errors; do not silently switch back to it.
- Default Git branch: `master`.
- Remote: `origin`.
- Never overwrite or discard unrelated user changes. Check `git status --short` before editing and before committing.

## Main applications

- `core`: public pages, authenticated dashboard, documentation, pricing and common UI.
- `accounts`: authentication and account-facing flows.
- `licensing`: UserInfo, PACS/ERP records, activation, licensing APIs, invoices, UPI configuration, purposes, reports and VBA-facing contracts.
- `khata`: customers, transactions, transfer vouchers, WhatsApp messages, reports and private Google Drive attachments.
- `reminders`: task/reminder management.
- `coupons`: coupon creation, reservation, usage and superuser management.
- `onedownload`: Google Drive-backed public download catalogue and superuser sync.
- `templates` / app `templates` directories: shared and app-specific UI.
- `staticfiles`: generated collectstatic output; do not hand-edit it.

## Technology and runtime

- Python virtual environment: `.venv`.
- Django version is pinned in `requirements.txt`.
- Database: MySQL in normal development/production.
- Time zone: `Asia/Kolkata`, with `USE_TZ = True`.
- Static serving: WhiteNoise with manifest storage.
- Production: Render at `https://web-automation-maar.onrender.com`.
- Secrets/configuration belong in `.env` locally and Render environment variables in production.

## Non-negotiable safety rules

1. Never print, commit, copy into templates, or expose values from `.env`, service-account JSON, API keys, database passwords, Razorpay secrets, deploy hooks, or client tokens.
2. Never commit generated credentials, local databases, uploaded customer files, `.venv`, or temporary files.
3. Do not alter existing database column names, legacy table mappings, API JSON keys, URL paths, or VBA-facing behavior unless the user explicitly requests it.
4. Treat `licensing` APIs as backward-compatible contracts. Existing distributed Excel/VBA files may still call them.
5. Do not enable Razorpay merely because credentials exist. Respect `RAZORPAY_PAYMENT_LINKS_ENABLED`.
6. All mutating views require the correct authorization. Superuser-only configuration must remain inaccessible even when someone knows the URL.
7. Preserve CSRF protection for browser forms. API exemptions must be deliberate and paired with the intended API authentication/validation.
8. Never truncate/delete production data or migrations without explicit user authorization and a verified target.
9. Use Indian date/time deliberately: save timezone-aware values and display them through Django timezone/localtime utilities.
10. Do not edit `staticfiles` directly; edit source static files/templates, then run `collectstatic` when required.

## Change workflow

1. Read the relevant model, form, view, URL, template, JavaScript and existing tests before changing behavior.
2. Search usages with `rg` before renaming or removing anything.
3. Make the smallest scoped change that satisfies the request.
4. For model changes, create a migration with `makemigrations`; never manually improvise production schema changes.
5. Keep UI consistent with the existing project theme, responsive desktop/mobile layouts, AJAX/no-reload behavior and visible spinner/modal stacking.
6. Keep user-facing messages simple and client-friendly; do not expose SQL, exception traces, internal tokens or developer terminology.
7. Add or update focused tests for business rules and regressions.
8. Report exactly what changed, what was tested, whether a migration/deployment action remains, and any VBA compatibility impact.

## Required verification

Run from the repository root with the virtual environment interpreter:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test <affected_app>
git diff --check
git status --short
```

- Use targeted tests first; run broader tests when shared licensing, authentication, middleware, base templates or settings change.
- MySQL-specific legacy migrations may not be valid under SQLite. Do not claim full test success if a substituted database skipped relevant behavior.
- For production configuration changes, also use `manage.py check --deploy` with safe production environment values when practical.
- For template/JavaScript UI changes, verify the affected page at desktop and mobile widths when a local server/browser is available.

## Database and migrations

- Always inspect current migrations before adding another one.
- Apply local migrations only after confirming the active database target.
- A migration committed to Git must also run in production through the deploy/release process; do not assume a code deploy creates tables automatically.
- Data migrations must be reversible where practical, bounded, and safe against duplicate execution.
- Preserve transaction integrity for paired Khata transfer entries and activation/ledger side effects.

## API and VBA compatibility

- Before changing a licensing endpoint, search both Python callers and any tracked `.bas`/VBA reference files.
- Preserve existing endpoint URLs, request fields, response keys, HTTP statuses and default service behavior for already-distributed Excel files.
- New API fields should normally be additive.
- State explicitly whether the user must update VBA. If no VBA change is needed, say so.
- Avoid per-entry server calls when the established contract batches successful paid uploads; free-user limits and server-side counters must remain authoritative.
- Never place server secrets in VBA. Anything shipped inside Excel/EXE must be treated as discoverable by clients.

## Permissions and business rules

- Superusers retain full administration access.
- Regular users must only see and mutate records allowed by the existing ownership/activation rules.
- Configuration tables such as purposes and UPI records remain superuser-only for add/update/delete.
- Validate permissions server-side; hiding a button is not authorization.
- Preserve duplicate UTR protections and any explicit superuser warning/override flow.
- Payment, activation, Khata ledger and reversal operations must remain auditable and atomic.

## Google Drive integrations

- Khata attachments and Download catalogue use different configured folder IDs.
- Keep service-account credentials outside Git and configure them through environment variables/files available to the runtime.
- Khata attachments are private application-managed files; Download items intentionally expose Google Drive links.
- Download page reads its synced cache/catalogue; only superusers trigger Drive sync.
- A sync failure must preserve the last valid download catalogue and show a safe message.

## Git, commit and deployment

- Do not commit, push, or deploy unless the user asks.
- Before committing, inspect the diff and exclude unrelated user-owned files.
- Use a concise commit message describing the completed feature/fix.
- Push to `origin master` only when explicitly requested or clearly included in the user request.
- Deploy only after commit/push and successful relevant checks. Use the configured Render deploy hook without printing its URL or secret.
- After deployment, verify the deployment status/log and at least `/health/`; verify the changed public/API page when safe.
- Never report deployment success merely because the hook accepted the request; wait for the Render deployment result when access is available.

## Communication style

- Communicate with the user in concise Hindi/Hinglish.
- Lead with the outcome.
- Before tool work, give a short progress update.
- Ask only when a decision is genuinely required; otherwise inspect and proceed safely.
- For read-only requests, do not modify files.
- Do not claim a fix without evidence from checks/tests or clearly state what could not be verified.

