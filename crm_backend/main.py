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
from routers.expenses_router import router as expenses_router
from routers.purchase_orders_router import router as purchase_orders_router
from routers.vendor_bills_router import router as vendor_bills_router
from routers.stock_movements_router import router as stock_movements_router
from routers.tax_reports_router import router as tax_reports_router
from routers.pl_reports_router import router as pl_reports_router
from routers.projects_router import router as projects_router
from routers.leaves_router import router as leaves_router
from routers.timesheets_router import router as timesheets_router
from routers.employees_router import router as employees_router
from routers.attendance_router import router as attendance_router
from routers.recruitment_router import router as recruitment_router
from routers.payroll_router import router as payroll_router
from routers.approvals_router import router as approvals_router
from routers.chat_router import router as chat_router
from routers.customer_ledger_router import router as customer_ledger_router
from routers.vendor_ledger_router import router as vendor_ledger_router
from routers.inventory_router import router as inventory_router
from routers.warehouses_router import router as warehouses_router
from routers.reminders_router import router as reminders_router
from routers.payments_router import router as payments_router
from routers.dashboard_router import router as dashboard_router
from routers.settings_router import router as settings_router
from routers.numbering_config_router import router as numbering_config_router
from routers.system_config_router import router as system_config_router
from routers.email_templates_router import router as email_templates_router
from routers.files_router import router as files_router
from routers.notifications_router import router as notifications_router
from routers.website_router import public_router as website_public_router
from routers.website_router import router as website_router
from routers.ecommerce_router import public_router as ecommerce_public_router
from routers.ecommerce_router import router as ecommerce_router
from routers.pos_router import router as pos_router
from routers.manufacturing_router import router as manufacturing_router
from routers.quality_router import router as quality_router
from routers.maintenance_router import router as maintenance_router
from routers.field_service_router import router as field_service_router
from routers.subscriptions_router import router as subscriptions_router
from routers.rental_router import router as rental_router
from routers.ai_reports_router import router as ai_reports_router
from routers.workflow_router import router as workflow_router
from routers.marketing_router import router as marketing_router
from routers.ai_assistant_router import router as ai_assistant_router
from routers.marketplace_router import router as marketplace_router

app = FastAPI(title="CRM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?",
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
app.include_router(expenses_router)
app.include_router(purchase_orders_router)
app.include_router(vendor_bills_router)
app.include_router(stock_movements_router)
app.include_router(tax_reports_router)
app.include_router(pl_reports_router)
app.include_router(projects_router)
app.include_router(leaves_router)
app.include_router(timesheets_router)
app.include_router(employees_router)
app.include_router(attendance_router)
app.include_router(recruitment_router)
app.include_router(payroll_router)
app.include_router(approvals_router)
app.include_router(chat_router)
app.include_router(customer_ledger_router)
app.include_router(vendor_ledger_router)
app.include_router(inventory_router)
app.include_router(warehouses_router)
app.include_router(reminders_router)
app.include_router(payments_router)
app.include_router(dashboard_router)
app.include_router(settings_router)
app.include_router(numbering_config_router)
app.include_router(system_config_router)
app.include_router(email_templates_router)
app.include_router(files_router)
app.include_router(notifications_router)
app.include_router(website_router)
app.include_router(website_public_router)
app.include_router(ecommerce_router)
app.include_router(ecommerce_public_router)
app.include_router(pos_router)
app.include_router(manufacturing_router)
app.include_router(quality_router)
app.include_router(maintenance_router)
app.include_router(field_service_router)
app.include_router(subscriptions_router)
app.include_router(rental_router)
app.include_router(ai_reports_router)
app.include_router(workflow_router)
app.include_router(marketing_router)
app.include_router(ai_assistant_router)
app.include_router(marketplace_router)
