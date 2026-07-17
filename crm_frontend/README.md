# BlackPapers CRM — Frontend

React (Create React App) UI for BlackPapers CRM. Talks to the FastAPI backend at `http://127.0.0.1:8000` (see `src/utils/api.js`).

**Parent repo:** [../README.md](../README.md) — setup, seeds, multi-tenant roadmap.

---

## Current build status

| Level | Status | Frontend coverage |
|-------|--------|-------------------|
| **Level 1** | **Done** | Auth, roles, contacts, products, dashboards, notifications, files, admin settings |
| **Level 2** | **~85%** | Leads, pipeline, quotations, orders, invoices, notes, follow-ups, payments, reports |
| **Level 3** | **~90%** | Expenses, POs, vendor bills, inventory, warehouses, tax/ledger/P&L reports |
| **Level 4** | **~80%** | Projects, timesheets, leave, employees, attendance, recruitment, payroll, chat |
| **UI shell** | **Done** | App launcher, landing page, GST document previews |

---

## Navigation model (current)

The UI no longer uses a long horizontal nav strip. Navigation works in three layers:

1. **Landing** (`/`) — India-first marketing page + **Choose your workspace** (role logins)
2. **Role home** (`/admin-dashboard`, `/sales-dashboard`, etc.) — **Your apps** grid (Odoo-style tiles) + KPI snapshot
3. **Module pages** (`/leads`, `/invoices`, …) — Slim header: logo → **Apps** breadcrumb → page title; **Alerts** + profile + logout

Return to all modules anytime: click **BlackPapers** logo or **Apps** in the breadcrumb.

### Key UI components

| Component | Purpose |
|-----------|---------|
| `AppLauncher.jsx` | Permission-filtered app grid, grouped by category |
| `AppIcon.jsx` | Module icons for tiles |
| `config/appCatalog.js` | All module paths, permissions, landing-page tiles |
| `RoleHomePage.jsx` | Shared role dashboard layout (hero + KPIs + apps) |
| `DashboardLayout.jsx` | App shell header (no module strip) |
| `NotificationBell.jsx` | Alerts panel — expand to read, **Open** dismisses + navigates |
| `InvoiceDocument.jsx` / `QuotationDocument.jsx` | Print-ready GST layouts |

---

## Landing page (`Home.jsx`)

- India-first copy (SMEs, NGOs, consultants, service businesses)
- Module showcase grid (marketing — not logged-in)
- **Start free** → `/register-company` (new business workspace)
- **Staff login** → role portals (Admin, Sales, Accountant, etc.)
- Client portal signup is disabled; portal users are invited by admin

---

## Role dashboards

| Route | Role | Home experience |
|-------|------|-----------------|
| `/admin-dashboard` | Admin | Company KPIs + full app catalog (incl. email templates, numbering, roles) |
| `/sales-dashboard` | Sales | Sales KPIs + CRM/billing apps |
| `/accountant-dashboard` | Accountant | Finance KPIs + invoices, GST, payroll |
| `/manager-dashboard` | Manager | Team KPIs + pipeline/reports |
| `/employee-dashboard` | Employee | HR apps (attendance, leave, timesheets, projects) |
| `/user-dashboard` | User | Portal profile only |

---

## Level 1 pages

| Page | Route | Permission |
|------|-------|------------|
| Home | `/` | Public |
| Role logins | `/admin-login`, `/sales-login`, etc. | Public |
| Role dashboards | `/admin-dashboard`, `/sales-dashboard`, … | By role |
| My Profile | `/profile` | Staff / User |
| Contacts | `/contacts`, `/contacts/:id` | `contacts.view` |
| Products | `/products`, `/products/:id` | `products.view` |
| Company | `/admin/company` | `company.view` |
| Users | `/admin/users` | `users.view` |
| Activity logs | `/admin/activity-logs` | `activity.view` |
| Branding | `/admin/branding` | `settings.edit` |
| Roles matrix | `/admin/roles-matrix` | `roles.view` |
| System config | `/admin/system-config` | Admin |
| Numbering | `/admin/numbering-config` | `numbering_config.view` |
| Email templates | `/admin/email-templates` | `company.view` |
| Send alert | `/send-notification` | `notifications.send` |
| Alerts (bell) | Header | `notifications.view` |
| Documents | `/documents` | `files.view` / `files.view_own` |

---

## Level 2 pages

| Page | Route | Permission |
|------|-------|------------|
| Leads | `/leads`, `/leads/:id` | `leads.view` |
| Pipeline | `/pipeline`, `/deals/:id` | `deals.view` |
| Follow-ups | `/follow-ups` | `reminders.view` |
| Quotations | `/quotations`, preview, approval queue | `quotations.view` |
| Sales orders | `/sales-orders` | `sales_orders.view` |
| Invoices | `/invoices`, preview, review queue | `invoices.view` |
| Payments | `/payments` | `payments.view` |
| Client notes | `/client-notes` | `client_notes.view` |
| Sales reports | `/sales-reports` | `reports.view` |

### Client-facing (no login)

| Page | Route |
|------|-------|
| View quotation | `/quote/:token` |
| View sales order | `/order/:token` |
| View invoice | `/invoice/:token` |

---

## Level 3 & 4 pages (summary)

Expenses, purchase orders, vendor bills, inventory, stock movements, warehouses, tax reports, customer/vendor ledger, P&L — plus projects, timesheets, leave, employees, attendance, recruitment, payroll, approvals hub, internal chat. All reachable from the **app launcher** when the user’s role has permission.

---

## Key frontend folders

```
crm_frontend/src/
├── pages/                 # Route screens
├── components/            # AppLauncher, DashboardLayout, NotificationBell, documents…
├── config/
│   └── appCatalog.js      # Module tiles (single source for launcher + landing)
├── utils/
│   ├── api.js             # API URL, login, apiFetch
│   ├── permissions.js     # hasPermission() for routes and tiles
│   ├── roleHome.js        # Role → dashboard path mapping
│   ├── invoiceBranding.js
│   └── quotationBranding.js
├── App.js                 # Routes + ProtectedRoute
└── crm.css                # Global + landing + app-launcher styles
```

---

## How to run

**Prerequisite:** backend on port 8000 ([main README](../README.md)).

```powershell
cd crm_frontend
npm install
npm start
```

Open **http://localhost:3000**

### Production build

```powershell
npm run build
```

Serve `build/` with a static host. Update `API_URL` in `src/utils/api.js` for production.

---

## Auth & permissions

- `ProtectedRoute` checks role + permission before rendering a page.
- `AppLauncher` filters tiles with `hasPermission()` from `appCatalog.js`.
- After backend permission changes: **log out and log back in**.

---

## Testing notifications (Alerts)

1. Backend: `python seed_demo_level1.py --reset`
2. Log in as `sales@crm.com` / `sales123` (or Admin)
3. Click **Alerts** in the header
4. Tap an alert to expand → **Open** goes to the linked page and removes it from the list

---

## Sales document previews

- **Quotations:** `QuotationDocument.jsx` — 4-page formal layout, print-friendly
- **Invoices:** `InvoiceDocument.jsx` — GST service invoice layout (BlackPapers branding)
- Demo records: `seed_demo_flagship_quote.py`, `seed_demo_flagship_invoice.py`

---

## Not built yet (frontend)

- Live email/WhatsApp send from CRM (templates UI exists; needs SMTP/WhatsApp API)
- LLM-backed AI Assistant (rule-based chat ships today)
- Live Razorpay/Tally sync in marketplace
- Push / SMS delivery (in-app alerts work)

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Blank page after login | Browser console; ensure backend is running |
| Cannot reach server | Start `uvicorn main:app --reload` on port 8000 |
| Missing app tiles | `seed_permissions.py`, log out and back in |
| No alerts | `python seed_demo_level1.py --reset` |
| CORS errors | `API_URL` must match backend host/port |

Database setup and full seed order: [main README](../README.md).
