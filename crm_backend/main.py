from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.admin_router import router as admin_router
from routers.auth_router import router as auth_router
from routers.company_router import router as company_router
from routers.contacts_router import router as contacts_router
from routers.products_router import router as products_router
from routers.leads_router import router as leads_router
from routers.deals_router import router as deals_router
from routers.quotations_router import public_router as quotations_public_router
from routers.quotations_router import router as quotations_router
from routers.sales_orders_router import public_router as sales_orders_public_router
from routers.sales_orders_router import router as sales_orders_router
from routers.invoices_router import public_router as invoices_public_router
from routers.invoices_router import router as invoices_router
from routers.client_notes_router import router as client_notes_router
from routers.sales_reports_router import router as sales_reports_router
from routers.reminders_router import router as reminders_router
from routers.payments_router import router as payments_router
from routers.dashboard_router import router as dashboard_router
from routers.settings_router import router as settings_router
from routers.numbering_config_router import router as numbering_config_router
from routers.system_config_router import router as system_config_router
from routers.email_templates_router import router as email_templates_router
from routers.notifications_router import router as notifications_router

app = FastAPI(title="CRM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(company_router)
app.include_router(contacts_router)
app.include_router(products_router)
app.include_router(leads_router)
app.include_router(deals_router)
app.include_router(quotations_router)
app.include_router(quotations_public_router)
app.include_router(sales_orders_router)
app.include_router(sales_orders_public_router)
app.include_router(invoices_router)
app.include_router(invoices_public_router)
app.include_router(client_notes_router)
app.include_router(sales_reports_router)
app.include_router(reminders_router)
app.include_router(payments_router)
app.include_router(dashboard_router)
app.include_router(settings_router)
app.include_router(numbering_config_router)
app.include_router(system_config_router)
app.include_router(email_templates_router)
app.include_router(notifications_router)
