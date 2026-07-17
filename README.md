# BlackPapers CRM

India-first business operating software for SMEs, agencies, CAs, NGOs, and service teams — CRM, GST billing, follow-ups, HR, inventory, and platform modules in one workspace.

**Stack:** FastAPI · SQLAlchemy · PostgreSQL · Alembic · React (Create React App)

---

## Status (July 2026)

| Area | Status |
|------|--------|
| **Levels 1–4** | Core CRM, billing, accounting, HR — shipped |
| **Level 5** | All 14 platform modules (website, eCommerce, POS, manufacturing, AI, workflows, marketplace, etc.) |
| **Multi-tenant** | **Beta** — company self-registration, tenant isolation, onboarding wizard |
| **UI** | App launcher, role dashboards, GST documents, in-app notifications |
| **Production SaaS** | Not deployed yet (hosted URL + billing in roadmap Phase 4) |

### Multi-tenant (new)

- **`POST /register-company`** — creates Company + Admin + default settings/numbering
- **JWT `company_id`** — every API request scoped to the logged-in user's workspace
- **Frontend:** `/register-company` → `/onboarding` → Admin dashboard
- **Demo tenant #1:** existing BlackPapers seeds still work on the same database

Details: [docs/MULTI_TENANT_ROADMAP.md](docs/MULTI_TENANT_ROADMAP.md)

---

## What's included

**CRM & billing:** Leads, pipeline, quotations, sales orders, invoices, payments, client notes, follow-ups, sales reports

**Finance:** Expenses, purchase orders, vendor bills, inventory, warehouses, GST/tax reports, customer & vendor ledgers, P&L

**HR & ops:** Projects, tasks, timesheets, employees, attendance, leave, recruitment, payroll, approvals, chat, documents

**Platform (Level 5):** Website builder, eCommerce shop, POS, manufacturing, quality, maintenance, field service, subscriptions, rental, AI reports, AI assistant, workflows, API marketplace

**Admin:** Users, roles/permissions, company profile, branding, numbering, email templates, activity logs, notifications

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.10+ (3.11 recommended) |
| Node.js | 18+ LTS |
| PostgreSQL | 14+ (16 recommended) |
| Git | Latest |

---

## Project structure

```
CRM/
├── crm_backend/     # API, models, migrations, seeds
├── crm_frontend/    # React UI
├── docs/            # PRDs + multi-tenant roadmap
└── .env             # Not in Git — copy from crm_backend/.env.example
```

Large data files (`clients.json`, CSV, Excel) are **not in Git** — get them from your team lead if you need full BlackPapers seed data.

---

## Setup (first time)

### 1. Clone & database

```powershell
git clone https://github.com/rathorebharat937/CRM.git
cd CRM
```

```sql
CREATE DATABASE crm_db;
```

### 2. Backend

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

```powershell
python -m alembic upgrade head
```

**Minimum seeds (demo login):**

```powershell
python seed_permissions.py
python seed_company.py
python seed_users.py
python seed_numbering_config.py
python seed_demo_level1.py --reset
```

After `seed_permissions.py`, log out and back in if you were already logged in.

### 3. Frontend

```powershell
cd crm_frontend
npm install
```

---

## Run (daily)

**Terminal 1 — API (port 8000):**

```powershell
cd crm_backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — UI (port 3000):**

```powershell
cd crm_frontend
npm start
```

| URL | Purpose |
|-----|---------|
| http://localhost:3000 | App |
| http://127.0.0.1:8000/docs | API docs |

---

## Login & registration

### Register a new company (multi-tenant)

1. Open http://localhost:3000/register-company
2. Enter owner details + company name
3. Complete the onboarding wizard (GST, address, optional team invite)
4. Land on Admin dashboard — your data is isolated from other tenants

### Demo users (seeded workspace)

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@crm.com` | `admin123` |
| Sales | `sales@crm.com` | `sales123` |
| Accountant | `accountant@crm.com` | `accountant123` |
| Manager | `manager@crm.com` | `manager123` |
| Employee | `employee@crm.com` | `employee123` |

Staff sign in from the landing page or role login URLs (`/admin-login`, `/sales-login`, etc.). After login, use the **app grid** to open modules.

---

## API highlights

| Endpoint | Purpose |
|----------|---------|
| `POST /register-company` | New business signup |
| `POST /login` | Staff / admin login |
| `GET /users/me` | Current profile |
| `GET /admin/company` | Tenant company profile |
| `GET /dashboard/kpis` | Role dashboard metrics |
| `/leads`, `/invoices`, `/quotations`, … | Module APIs (tenant-scoped) |

Full reference: http://127.0.0.1:8000/docs

---

## Still to do

| Item | Notes |
|------|-------|
| Hosted production deploy | Frontend + API + managed PostgreSQL |
| Billing / plan limits | Razorpay/Stripe — roadmap Phase 4 |
| WhatsApp & outbound email | Templates exist; needs API credentials |
| Auto follow-up delivery | Cron + email/WhatsApp provider |
| Super-admin console | Internal tenant management |

---

