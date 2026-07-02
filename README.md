# BlackPapers CRM

India-first business operating software for SMEs, service businesses, NGOs, consultants, and growing teams. Built for **BlackPapers** (BLACKPAPERS SARTHIES PRIVATE LIMITED) and positioned as a simpler alternative to heavy ERP — CRM + billing + GST + follow-ups first.

**Stack:** FastAPI + SQLAlchemy + PostgreSQL + Alembic (backend) · React (Create React App) frontend

**Current build:** Level 1 complete. Level 2 ~85%. Level 3 accounting/inventory done. Level 4 HR/operations largely done. **Level 5** — 11 of 14 platform modules shipped (see [docs/LEVEL_5_STATUS.md](docs/LEVEL_5_STATUS.md)). App-launcher UI and in-app notifications live. **Multi-tenant SaaS** is the approved next phase — see [docs/MULTI_TENANT_ROADMAP.md](docs/MULTI_TENANT_ROADMAP.md).

---

## Build status at a glance

| Level | Progress | Summary |
|-------|----------|---------|
| **Level 1** | **~100%** | Users, company, roles, contacts, products, dashboards, notifications, files, settings |
| **Level 2** | **~85%** | Leads → deal → quote → order → invoice → payments, reports, follow-ups |
| **Level 3** | **~90%** | Expenses, POs, vendor bills, inventory, warehouses, GST/tax, ledgers, P&L |
| **Level 4** | **~80%** | Projects, timesheets, leave, employees, attendance, recruitment, payroll, chat, approvals |
| **Level 5** | **100% MVP** | All 14 modules: website through API marketplace (Phase 1 scope) |
| **UI / UX** | **Recent** | App-launcher home, Level 5 category grid, India-first landing, GST invoice/quote layouts, alert centre |
| **Multi-tenant** | **Planned** | Roadmap written; single-company-per-DB today |

---

## Recent UI & product work

- **Landing page** (`/`) — India-first positioning, module showcase, workspace sign-in (Admin / Sales / Accountant / etc.)
- **App launcher** — Role dashboards show an Odoo-style app grid; Level 5 modules grouped under **Platform & Growth**
- **App shell** — Logo → Apps home, breadcrumb on inner pages, profile + Alerts + logout
- **GST documents** — Service invoice & quotation layouts aligned to BlackPapers PDFs
- **Notifications** — In-app alert bell, Admin “Send alert” by role, demo seeds (`seed_demo_level1.py`)
- **Admin apps** — Email templates, system config, numbering, roles matrix in the launcher catalog

---

## Level 1 — Core Foundation

| # | Module | Status |
|---|--------|--------|
| 1 | User Management | **Done** — staff accounts, profile, JWT auth, forgot/reset password |
| 2 | Company Management | **Done** — business profile, GSTIN/PAN, currency, branding |
| 3 | Role & Permission System | **Done** — permission-gated APIs and routes |
| 4 | Contact Database | **Done** — CRUD, notes, activities (~297 clients with seed) |
| 5 | Product / Service Master | **Done** — service catalogue (~134 services with seed) |
| 6 | Dashboard | **Done** — KPIs + app launcher per role |
| 7 | Activity Logs | **Done** — login/edit audit trail (Admin) |
| 8 | Notifications | **Done** — in-app centre, send-by-role, read/dismiss |
| 9 | File Upload | **Done** — `/documents`, record panels |
| 10 | System Settings | **Done** — company, branding, numbering, email templates, system config |

---

## Level 2 — Sales, CRM & Billing

| # | Module | Status | Notes |
|---|--------|--------|-------|
| 1 | Lead Management | **Done** | CSV import, list/filter, assign, convert (20k+ leads supported) |
| 2 | Sales Pipeline | **Done** | Kanban, stages, demo deals |
| 3 | Follow-up Reminders | **Partial** | Queue + overdue logic; auto email/WhatsApp not live |
| 4 | Quotation System | **Done** | Formal 4-page layout, approve, preview, client link |
| 5 | Sales Orders | **Done** | Convert from quote, milestones, client link |
| 6 | Invoice Generator | **Done** | GST layout, preview, client link, flagship demo seed |
| 7 | Payment Tracking | **Partial** | Ageing, payments page; full reconciliation TBD |
| 8 | Client Notes | **Done** | Notes + follow-up queue |
| 9 | WhatsApp / Email | **Not started** | Templates exist; needs SMTP + WhatsApp API |
| 10 | Sales Reports | **Done** | Overview, conversion, revenue, pipeline health |

### Sales flow

```
Lead → Deal → Quotation → Sales Order → Invoice → Payments
```

---

## Level 3 — Accounting, Purchase & Inventory

| # | Module | Status | Demo seed |
|---|--------|--------|-----------|
| 1 | Expense Management | **Done** | `seed_demo_level3.py` |
| 2 | Purchase Orders | **Done** | `seed_demo_level3.py` |
| 3 | Vendor Bills | **Done** | `seed_demo_level3.py` |
| 4 | Inventory | **Done** | `seed_demo_level3.py` |
| 5 | Stock In / Out | **Done** | `seed_demo_level3.py` |
| 6 | Warehouses | **Done** | `seed_demo_level3.py` |
| 7 | GST / Tax Reports | **Done** | Level 2 + 3 data |
| 8 | Customer Ledger | **Done** | Invoices + payments |
| 9 | Vendor Ledger | **Done** | Vendor bills |
| 10 | P&L Reports | **Done** | Revenue + expenses |

---

## Level 4 — Operations, HR & Projects

| # | Module | Status | Demo seed |
|---|--------|--------|-----------|
| 1 | Project Management | **Done** | `seed_demo_level4.py` |
| 2 | Task Management | **Done** | Inside projects |
| 3 | Timesheets | **Done** | `seed_demo_level4.py` |
| 4 | Employee Database | **Done** | `/employees`, profiles |
| 5 | Attendance | **Done** | Check-in/out, team view |
| 6 | Leave Management | **Done** | `seed_demo_level4.py` |
| 7 | Recruitment | **Done** | Job openings, candidates |
| 8 | Payroll | **Done** | Payslips |
| 9 | Approvals Hub | **Done** | Cross-module pending actions |
| 10 | Document Management | **Done** | `/documents` |
| 11 | Internal Chat | **Done** | Team messages |

---

## Level 5 — Platform & Growth

Full matrix: **[docs/LEVEL_5_STATUS.md](docs/LEVEL_5_STATUS.md)**

| # | Module | Status |
|---|--------|--------|
| 1 | Marketing Automation | **Done** — `/marketing` (drip, enrollments, reminders) |
| 2 | Website Builder | **Done** — `/website`, public `/s/:slug` |
| 3 | eCommerce | **Done** — `/ecommerce`, public shop |
| 4 | POS | **Done** — `/pos` |
| 5 | Manufacturing / MRP | **Done** — `/manufacturing` |
| 6 | Quality Control | **Done** — `/quality` |
| 7 | Maintenance | **Done** — `/maintenance` |
| 8 | Field Service | **Done** — `/field-service` |
| 9 | Subscription Management | **Done** — `/subscriptions` |
| 10 | Rental Management | **Done** — `/rental` |
| 11 | AI Reports | **Done** — `/ai-reports` |
| 12 | AI Assistant | **Done** — `/ai-assistant` (rule-based chat) |
| 13 | Workflow Builder | **Done** — `/workflows` |
| 14 | API & App Marketplace | **Done** — `/marketplace` (catalog, keys, webhooks) |

After pulling Level 5 code: `alembic upgrade head`, `python seed_permissions.py`, demo seeds for new modules, then **log out and log in**.

---

## Tenancy model (important)

| Today | Planned |
|-------|---------|
| **One company per database** — `Company.first()` in API | **Multi-tenant** — many companies, shared app, `company_id` isolation |
| Staff created by Admin or seeds | Self-service **Register your business** |
| Clone + local PostgreSQL per teammate | Hosted SaaS URL for manager/clients |

See **[docs/MULTI_TENANT_ROADMAP.md](docs/MULTI_TENANT_ROADMAP.md)** for phases and timeline.

---

## What’s remaining

| Area | What’s still needed |
|------|---------------------|
| **Multi-tenant** | Company registration, tenant isolation, hosted deploy (roadmap Phase 1–4) |
| WhatsApp / outbound email | SMTP + WhatsApp Business API credentials |
| Auto follow-up delivery | Email/WhatsApp provider + cron rules |
| Payment reconciliation | Full payment entry workflow, optional gateway |
| Production deploy | Live server, domain, SSL, production `.env` |

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.10+ (3.11 recommended) | Backend API |
| **Node.js** | 18+ (LTS) | Frontend |
| **PostgreSQL** | 14+ (16 recommended) | Database |
| **Git** | Latest | Clone repo |

---

## Project structure

```
CRM/
├── crm_backend/           # FastAPI API, models, migrations, seeds
├── crm_frontend/          # React UI (see crm_frontend/README.md)
├── docs/                  # PRDs + MULTI_TENANT_ROADMAP.md
├── clients.json           # NOT in Git — get from team lead
├── Lead_file.csv          # NOT in Git
└── *.xlsx                 # Employee / service master sheets — NOT in Git
```

---

## Setup guide (first time)

### 1 — Clone

```powershell
git clone https://github.com/rathorebharat937/CRM.git
cd CRM
```

### 2 — PostgreSQL

```sql
CREATE DATABASE crm_db;
```

### 3 — Backend

```powershell
cd crm_backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/crm_db
JWT_SECRET=your-random-secret-key-change-this
FRONTEND_URL=http://localhost:3000
```

### 4 — Migrations

```powershell
alembic upgrade head
```

### 5 — Seed data

**Minimum (quick demo):**

```powershell
python seed_permissions.py
python seed_company.py
python seed_users.py
python seed_demo_level1.py --reset
python seed_numbering_config.py
python seed_email_templates.py
```

**Full BlackPapers data** (place `clients.json`, CSV, Excel in repo root first):

```powershell
python seed_permissions.py
python seed_company.py
python seed_master_employees.py
python seed_clients.py
python seed_master_services.py
python seed_leads.py
```

**Level 5 platform modules** (website, POS, subscriptions, manufacturing, etc.):

```powershell
python seed_enable_level5.py
python seed_demo_level5.py
```

Or seed individually — see [docs/LEVEL_5_STATUS.md](docs/LEVEL_5_STATUS.md).

**Optional demo modules:**

```powershell
python seed_demo_deals.py --reset
python seed_demo_level2.py --reset
python seed_demo_flagship_quote.py
python seed_demo_flagship_invoice.py
python seed_demo_level3.py --reset
python seed_demo_level4.py --reset
python seed_demo_sales_accountant.py --reset
python seed_demo_level1.py --reset
```

| Script | Purpose |
|--------|---------|
| `seed_demo_level1.py --reset` | In-app notifications per role (for testing Alerts) |
| `seed_demo_flagship_quote.py` | PixelPolish sample quotation |
| `seed_demo_flagship_invoice.py` | Surendra-Charu Foundation sample invoice |

> After `seed_permissions.py`, **log out and log back in** so permissions and app tiles refresh.

### 6 — Frontend

```powershell
cd crm_frontend
npm install
```

---

## How to run (every day)

**Terminal 1 — Backend** (port 8000):

```powershell
cd crm_backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Frontend** (port 3000):

```powershell
cd crm_frontend
npm start
```

- App: **http://localhost:3000**
- API docs: **http://127.0.0.1:8000/docs**

---

## Login

### Dev test users (`seed_users.py`)

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@crm.com` | `admin123` |
| Manager | `manager@crm.com` | `manager123` |
| Employee | `employee@crm.com` | `employee123` |
| Sales | `sales@crm.com` | `sales123` |
| Accountant | `accountant@crm.com` | `accountant123` |

### Entry points

| Purpose | URL |
|---------|-----|
| Landing / workspace picker | http://localhost:3000 |
| Admin login | http://localhost:3000/admin-login |
| Sales login | http://localhost:3000/sales-login |
| Accountant login | http://localhost:3000/accountant-login |

After login you land on the **role home** with an **app grid** — open modules from there. Use **Apps** (breadcrumb or logo) to return home.

---

## For managers / new teammates

**Run locally:** Clone repo → PostgreSQL → seeds → two terminals (backend + frontend). Same steps as above.

**No install (future):** Multi-tenant hosted URL — in roadmap Phase 2–4.

**Pull latest UI:** `git pull origin main` then restart frontend/backend.

---

## API overview

| Area | Base path |
|------|-----------|
| Auth | `/login`, `/logout`, `/signup`, `/users/me` |
| Admin | `/admin/users`, `/admin/company`, `/admin/activity-logs` |
| Notifications | `/notifications`, `/notifications/send` |
| CRM & sales | `/leads`, `/deals`, `/quotations`, `/sales-orders`, `/invoices` |
| Finance | `/payments`, `/expenses`, `/tax-reports`, `/customer-ledger` |
| HR | `/employees`, `/attendance`, `/timesheets`, `/payroll`, `/recruitment` |
| Dashboard | `/dashboard/kpis` |

Full docs: **http://127.0.0.1:8000/docs**

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Database connection | Check PostgreSQL + `DATABASE_URL` in `.env` |
| Login / bcrypt | `pip install -r requirements.txt` |
| Frontend can’t reach API | Backend on port 8000; check `crm_frontend/src/utils/api.js` |
| Missing app tiles | `seed_permissions.py`, then log out and back in |
| No alerts to test | `python seed_demo_level1.py --reset` |
| Seed file not found | Data files go in **repo root**, not `crm_backend/` |

---

## What Git includes

| In Git | Not in Git |
|--------|------------|
| Source, migrations, seeds | `.env`, `clients.json`, CSV/Excel |
| `docs/MULTI_TENANT_ROADMAP.md` | `crm_backend/uploads/` (runtime files) |
| `.env.example` | `venv/`, `node_modules/` |

**Pulling does not copy database rows** — each machine runs migrations + seeds.

---

## Quick checklist for new team members

- [ ] Python, Node, PostgreSQL installed
- [ ] Repo cloned (`git pull` if already cloned)
- [ ] `crm_db` created, `.env` configured
- [ ] `alembic upgrade head`
- [ ] `seed_permissions.py` + `seed_company.py` + `seed_users.py`
- [ ] `seed_demo_level1.py --reset` (optional — test alerts)
- [ ] `npm install` in `crm_frontend`
- [ ] Backend + frontend running
- [ ] Login at http://localhost:3000 → choose workspace → use app grid

For frontend-specific notes see [crm_frontend/README.md](crm_frontend/README.md).
