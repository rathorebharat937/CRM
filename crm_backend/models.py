from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    code = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    module = Column(String(50), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True)
    role = Column(String(30), nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    legal_name = Column(String(200), nullable=False)
    display_name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(30), nullable=True)
    website = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    country = Column(String(100), nullable=False, default="India")
    gstin = Column(String(15), nullable=True)
    pan = Column(String(10), nullable=True)
    currency = Column(String(3), nullable=False, default="INR")
    financial_year_start_month = Column(Integer, nullable=False, default=4)
    timezone = Column(String(50), nullable=False, default="Asia/Kolkata")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    users = relationship("User", back_populates="company")
    contacts = relationship("Contact", back_populates="company")
    products = relationship("Product", back_populates="company")
    leads = relationship("Lead", back_populates="company")
    deals = relationship("Deal", back_populates="company")
    quotations = relationship("Quotation", back_populates="company")
    sales_orders = relationship("SalesOrder", back_populates="company")
    invoices = relationship("Invoice", back_populates="company")
    client_notes = relationship("ClientNote", back_populates="company")
    expenses = relationship("Expense", back_populates="company")
    purchase_orders = relationship("PurchaseOrder", back_populates="company")
    vendor_bills = relationship("VendorBill", back_populates="company")
    stock_movements = relationship("StockMovement", back_populates="company")
    warehouse_locations = relationship("WarehouseLocation", back_populates="company")
    location_stocks = relationship("LocationStock", back_populates="company")
    location_stock_movements = relationship("LocationStockMovement", back_populates="company")
    follow_up_reminders = relationship("FollowUpReminder", back_populates="company")
    projects = relationship("Project", back_populates="company")
    leave_requests = relationship("LeaveRequest", back_populates="company")
    timesheet_entries = relationship("TimesheetEntry", back_populates="company")
    employee_profiles = relationship("EmployeeProfile", back_populates="company")
    attendance_records = relationship("AttendanceRecord", back_populates="company")
    job_openings = relationship("JobOpening", back_populates="company")
    payslips = relationship("Payslip", back_populates="company")
    chat_messages = relationship("ChatMessage", back_populates="company")
    system_settings = relationship("SystemSetting", back_populates="company", uselist=False)
    website_settings = relationship("WebsiteSettings", back_populates="company", uselist=False)
    website_pages = relationship("WebsitePage", back_populates="company")
    website_forms = relationship("WebsiteForm", back_populates="company")
    website_blog_posts = relationship("WebsiteBlogPost", back_populates="company")
    store_settings = relationship("StoreSettings", back_populates="company", uselist=False)
    store_orders = relationship("StoreOrder", back_populates="company")
    pos_settings = relationship("PosSettings", back_populates="company", uselist=False)
    pos_registers = relationship("PosRegister", back_populates="company")
    pos_bills = relationship("PosBill", back_populates="company")
    manufacturing_settings = relationship("ManufacturingSettings", back_populates="company", uselist=False)
    work_orders = relationship("WorkOrder", back_populates="company")
    quality_settings = relationship("QualitySettings", back_populates="company", uselist=False)
    inspection_points = relationship("InspectionPoint", back_populates="company")
    maintenance_settings = relationship("MaintenanceSettings", back_populates="company", uselist=False)
    maintenance_assets = relationship("MaintenanceAsset", back_populates="company")
    maintenance_work_orders = relationship("MaintenanceWorkOrder", back_populates="company")
    field_service_settings = relationship("FieldServiceSettings", back_populates="company", uselist=False)
    field_service_orders = relationship("FieldServiceOrder", back_populates="company")
    subscription_settings = relationship("SubscriptionSettings", back_populates="company", uselist=False)
    subscription_plans = relationship("SubscriptionPlan", back_populates="company")
    customer_subscriptions = relationship("CustomerSubscription", back_populates="company")
    rental_settings = relationship("RentalSettings", back_populates="company", uselist=False)
    rental_assets = relationship("RentalAsset", back_populates="company")
    rental_contracts = relationship("RentalContract", back_populates="company")
    ai_report_settings = relationship("AiReportSettings", back_populates="company", uselist=False)
    ai_insight_runs = relationship("AiInsightRun", back_populates="company")
    workflow_settings = relationship("WorkflowSettings", back_populates="company", uselist=False)
    workflows = relationship("Workflow", back_populates="company")
    workflow_runs = relationship("WorkflowRun", back_populates="company")
    marketing_settings = relationship("MarketingSettings", back_populates="company", uselist=False)
    marketing_campaigns = relationship("MarketingCampaign", back_populates="company")
    marketing_enrollments = relationship("MarketingEnrollment", back_populates="company")
    ai_assistant_settings = relationship("AiAssistantSettings", back_populates="company", uselist=False)
    ai_assistant_sessions = relationship("AiAssistantSession", back_populates="company")
    marketplace_settings = relationship("MarketplaceSettings", back_populates="company", uselist=False)
    marketplace_integrations = relationship("MarketplaceIntegration", back_populates="company")
    marketplace_api_keys = relationship("MarketplaceApiKey", back_populates="company")
    marketplace_webhooks = relationship("MarketplaceWebhook", back_populates="company")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    quote_prefix = Column(String(30), nullable=False, default="Quote-")
    invoice_prefix = Column(String(30), nullable=False, default="Inv-")
    quote_date_format = Column(String(20), nullable=False, default="DD/MM/YYYY")
    invoice_date_format = Column(String(20), nullable=False, default="DD/MM/YYYY")
    default_lead_source = Column(String(50), nullable=False, default="Omnichannel")
    logo_filename = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="system_settings")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    name = Column(String(120), nullable=False)
    phone = Column(String(30), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    organization_name = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    requirement = Column(String(200), nullable=True)
    exact_requirement = Column(Text, nullable=True)
    source = Column(String(50), nullable=False, default="Omnichannel")
    status = Column(String(30), nullable=False, default="open")
    csv_status = Column(String(80), nullable=True)
    notes = Column(Text, nullable=True)
    registered_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="leads")
    contact = relationship("Contact", foreign_keys=[contact_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    deals = relationship("Deal", back_populates="lead")


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    title = Column(String(200), nullable=False)
    stage = Column(String(30), nullable=False, default="new", index=True)
    expected_value = Column(Numeric(14, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="INR")
    expected_close_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    lost_reason = Column(String(255), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="deals")
    lead = relationship("Lead", back_populates="deals")
    contact = relationship("Contact", foreign_keys=[contact_id])
    product = relationship("Product")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    service_code = Column(String(40), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    entity_type = Column(String(80), nullable=True)
    category = Column(String(120), nullable=True)
    sub_category = Column(String(120), nullable=True)
    unit = Column(String(30), nullable=False, default="Service")
    govt_charges = Column(Numeric(12, 2), nullable=True)
    our_fees = Column(Numeric(12, 2), nullable=True)
    gst_amount = Column(Numeric(12, 2), nullable=True)
    total_price = Column(Numeric(12, 2), nullable=True)
    market_price = Column(Numeric(12, 2), nullable=True)
    offer_price = Column(Numeric(12, 2), nullable=True)
    last_price = Column(Numeric(12, 2), nullable=True)
    gst_rate = Column(Numeric(5, 2), nullable=False, default=18)
    filing_timeline = Column(String(80), nullable=True)
    completion_timeline = Column(String(80), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active")
    inventory_tracked = Column(Boolean, nullable=False, default=False)
    on_hand_quantity = Column(Numeric(12, 2), nullable=False, default=0)
    sell_online = Column(Boolean, nullable=False, default=False)
    online_slug = Column(String(80), nullable=True, index=True)
    online_description = Column(Text, nullable=True)
    online_image_url = Column(String(500), nullable=True)
    compare_at_price = Column(Numeric(12, 2), nullable=True)
    sell_at_pos = Column(Boolean, nullable=False, default=False)
    pos_category = Column(String(80), nullable=True)
    pos_sort_order = Column(Integer, nullable=False, default=0)
    is_manufactured = Column(Boolean, nullable=False, default=False)
    is_raw_material = Column(Boolean, nullable=False, default=False)
    is_spare_part = Column(Boolean, nullable=False, default=False)
    default_bom_id = Column(Integer, ForeignKey("bom_headers.id"), nullable=True)
    default_incoming_template_id = Column(Integer, ForeignKey("quality_checklist_templates.id"), nullable=True)
    default_final_template_id = Column(Integer, ForeignKey("quality_checklist_templates.id"), nullable=True)
    requires_incoming_qc = Column(Boolean, nullable=False, default=False)
    requires_final_qc = Column(Boolean, nullable=False, default=False)
    unit_valuation = Column(Numeric(14, 2), nullable=False, default=0)
    reorder_level = Column(Numeric(12, 2), nullable=True)
    opening_recorded = Column(Boolean, nullable=False, default=False)
    last_movement_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="products")
    stock_movements = relationship(
        "StockMovement",
        back_populates="product",
        order_by="StockMovement.movement_date.desc()",
    )
    location_stocks = relationship("LocationStock", back_populates="product")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    movement_type = Column(String(20), nullable=False, index=True)
    direction = Column(String(3), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    unit_value = Column(Numeric(14, 2), nullable=False, default=0)
    total_value = Column(Numeric(14, 2), nullable=False, default=0)
    quantity_before = Column(Numeric(12, 2), nullable=False, default=0)
    quantity_after = Column(Numeric(12, 2), nullable=False, default=0)
    movement_date = Column(DateTime(timezone=True), nullable=False)
    reference_type = Column(String(30), nullable=True)
    reference_id = Column(Integer, nullable=True)
    reference_number = Column(String(100), nullable=True)
    source_module = Column(String(30), nullable=False, default="manual")
    reason = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    negative_override = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="stock_movements")
    product = relationship("Product", back_populates="stock_movements")
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])
    location_movements = relationship("LocationStockMovement", back_populates="linked_stock_movement")


class WarehouseLocation(Base):
    __tablename__ = "warehouse_locations"
    __table_args__ = (UniqueConstraint("company_id", "location_code", name="uq_warehouse_location_code"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("warehouse_locations.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    location_code = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    location_type = Column(String(30), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    is_default_receiving = Column(Boolean, nullable=False, default=False)
    is_default_dispatch = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="warehouse_locations")
    parent = relationship("WarehouseLocation", remote_side=[id], back_populates="children")
    children = relationship("WarehouseLocation", back_populates="parent", order_by="WarehouseLocation.name")
    created_by = relationship("User", foreign_keys=[created_by_id])
    location_stocks = relationship("LocationStock", back_populates="location")
    movements = relationship(
        "LocationStockMovement",
        back_populates="location",
        order_by="LocationStockMovement.movement_date.desc()",
    )


class LocationStock(Base):
    __tablename__ = "location_stocks"
    __table_args__ = (UniqueConstraint("product_id", "location_id", name="uq_location_stock_product"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("warehouse_locations.id"), nullable=False)

    on_hand_quantity = Column(Numeric(12, 2), nullable=False, default=0)
    unit_valuation = Column(Numeric(14, 2), nullable=False, default=0)
    reorder_level = Column(Numeric(12, 2), nullable=True)
    last_movement_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="location_stocks")
    product = relationship("Product", back_populates="location_stocks")
    location = relationship("WarehouseLocation", back_populates="location_stocks")


class LocationStockMovement(Base):
    __tablename__ = "location_stock_movements"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("warehouse_locations.id"), nullable=False)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    linked_stock_movement_id = Column(Integer, ForeignKey("stock_movements.id"), nullable=True)

    movement_type = Column(String(20), nullable=False, index=True)
    direction = Column(String(3), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    unit_value = Column(Numeric(14, 2), nullable=False, default=0)
    total_value = Column(Numeric(14, 2), nullable=False, default=0)
    quantity_before = Column(Numeric(12, 2), nullable=False, default=0)
    quantity_after = Column(Numeric(12, 2), nullable=False, default=0)
    movement_date = Column(DateTime(timezone=True), nullable=False)
    transfer_reference = Column(String(50), nullable=True, index=True)
    reference_number = Column(String(100), nullable=True)
    reason = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    negative_override = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="location_stock_movements")
    product = relationship("Product")
    location = relationship("WarehouseLocation", back_populates="movements")
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])
    linked_stock_movement = relationship("StockMovement", back_populates="location_movements")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    name = Column(String(120), nullable=False)
    organization_name = Column(String(200), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(30), nullable=True)
    alt_phone = Column(String(30), nullable=True)
    contact_type = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    designation = Column(String(120), nullable=True)
    website = Column(String(255), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    country = Column(String(100), nullable=False, default="India")
    gstin = Column(String(15), nullable=True)
    pan = Column(String(10), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="contacts")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    portal_user = relationship("User", foreign_keys=[user_id])
    notes = relationship("ContactNote", back_populates="contact")
    activities = relationship("ContactActivity", back_populates="contact")
    client_notes = relationship("ClientNote", back_populates="contact")


class ContactNote(Base):
    __tablename__ = "contact_notes"

    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    contact = relationship("Contact", back_populates="notes")
    author = relationship("User")


class ContactActivity(Base):
    __tablename__ = "contact_activities"

    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    activity_type = Column(String(20), nullable=False)
    subject = Column(String(200), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    contact = relationship("Contact", back_populates="activities")
    author = relationship("User")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    employee_id = Column(String(20), unique=True, nullable=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(30), nullable=True)
    password = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False)
    reset_token = Column(String, nullable=True)
    reset_token_expiry = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    designation = Column(String(120), nullable=True)
    department = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    company = relationship("Company", back_populates="users")
    activities = relationship("ActivityLog", back_populates="user")


class Quotation(Base):
    __tablename__ = "quotations"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    parent_quote_id = Column(Integer, ForeignKey("quotations.id"), nullable=True)
    root_quote_id = Column(Integer, ForeignKey("quotations.id"), nullable=True)

    quote_number = Column(String(40), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    status = Column(String(30), nullable=False, default="draft", index=True)
    version = Column(Integer, nullable=False, default=1)
    currency = Column(String(3), nullable=False, default="INR")
    quote_date = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)

    client_name = Column(String(120), nullable=True)
    client_email = Column(String(255), nullable=True)
    client_org = Column(String(200), nullable=True)
    attention_to = Column(String(120), nullable=True)
    billing_address = Column(Text, nullable=True)
    shipping_address = Column(Text, nullable=True)

    subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    line_discount_total = Column(Numeric(14, 2), nullable=False, default=0)
    header_discount_amount = Column(Numeric(14, 2), nullable=False, default=0)
    header_discount_percent = Column(Numeric(5, 2), nullable=False, default=0)
    total_tax = Column(Numeric(14, 2), nullable=False, default=0)
    grand_total = Column(Numeric(14, 2), nullable=False, default=0)

    scope_notes = Column(Text, nullable=True)
    deliverables = Column(Text, nullable=True)
    timeline_notes = Column(Text, nullable=True)
    payment_terms = Column(Text, nullable=True)
    validity_clause = Column(Text, nullable=True)
    cancellation_clause = Column(Text, nullable=True)
    legal_footer = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    approval_comments = Column(Text, nullable=True)

    requires_approval = Column(Integer, nullable=False, default=0)
    share_token = Column(String(64), nullable=True, unique=True, index=True)

    sent_at = Column(DateTime(timezone=True), nullable=True)
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    client_rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="quotations")
    deal = relationship("Deal", foreign_keys=[deal_id])
    lead = relationship("Lead", foreign_keys=[lead_id])
    contact = relationship("Contact", foreign_keys=[contact_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    parent_quote = relationship("Quotation", remote_side=[id], foreign_keys=[parent_quote_id])
    line_items = relationship(
        "QuotationLineItem",
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationLineItem.sort_order",
    )
    sales_orders = relationship("SalesOrder", back_populates="quotation")
    invoices = relationship("Invoice", back_populates="quotation")


class QuotationLineItem(Base):
    __tablename__ = "quotation_line_items"

    id = Column(Integer, primary_key=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    section = Column(String(100), nullable=True)
    item_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    quantity = Column(Numeric(12, 2), nullable=False, default=1)
    unit = Column(String(30), nullable=False, default="Service")
    unit_price = Column(Numeric(14, 2), nullable=False, default=0)
    discount_percent = Column(Numeric(5, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(14, 2), nullable=False, default=0)
    tax_rate = Column(Numeric(5, 2), nullable=False, default=18)
    line_subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    line_total = Column(Numeric(14, 2), nullable=False, default=0)

    quotation = relationship("Quotation", back_populates="line_items")
    product = relationship("Product")


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    closed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    parent_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=True)
    root_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=True)

    order_number = Column(String(40), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    status = Column(String(30), nullable=False, default="draft", index=True)
    version = Column(Integer, nullable=False, default=1)
    order_type = Column(String(30), nullable=False, default="mixed")
    source_type = Column(String(20), nullable=False, default="manual")
    currency = Column(String(3), nullable=False, default="INR")
    order_date = Column(DateTime(timezone=True), nullable=True)
    confirmation_date = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    internal_target_date = Column(DateTime(timezone=True), nullable=True)

    client_name = Column(String(120), nullable=True)
    client_email = Column(String(255), nullable=True)
    client_phone = Column(String(30), nullable=True)
    client_org = Column(String(200), nullable=True)
    attention_to = Column(String(120), nullable=True)
    billing_address = Column(Text, nullable=True)
    delivery_address = Column(Text, nullable=True)

    subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    line_discount_total = Column(Numeric(14, 2), nullable=False, default=0)
    header_discount_amount = Column(Numeric(14, 2), nullable=False, default=0)
    header_discount_percent = Column(Numeric(5, 2), nullable=False, default=0)
    total_tax = Column(Numeric(14, 2), nullable=False, default=0)
    grand_total = Column(Numeric(14, 2), nullable=False, default=0)

    billing_notes = Column(Text, nullable=True)
    payment_milestone_notes = Column(Text, nullable=True)
    delivery_instructions = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    hold_reason = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    completion_notes = Column(Text, nullable=True)

    fulfillment_progress = Column(Integer, nullable=False, default=0)
    billing_status = Column(String(30), nullable=False, default="pending")
    preparation_status = Column(String(30), nullable=False, default="not_started")
    share_token = Column(String(64), nullable=True, unique=True, index=True)

    sent_for_confirmation_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    hold_at = Column(DateTime(timezone=True), nullable=True)
    hold_resume_date = Column(DateTime(timezone=True), nullable=True)
    last_status_change_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="sales_orders")
    quotation = relationship("Quotation", back_populates="sales_orders")
    deal = relationship("Deal", foreign_keys=[deal_id])
    lead = relationship("Lead", foreign_keys=[lead_id])
    contact = relationship("Contact", foreign_keys=[contact_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    confirmed_by = relationship("User", foreign_keys=[confirmed_by_id])
    closed_by = relationship("User", foreign_keys=[closed_by_id])
    parent_order = relationship("SalesOrder", remote_side=[id], foreign_keys=[parent_order_id])
    line_items = relationship(
        "SalesOrderLineItem",
        back_populates="sales_order",
        cascade="all, delete-orphan",
        order_by="SalesOrderLineItem.sort_order",
    )
    milestones = relationship(
        "SalesOrderMilestone",
        back_populates="sales_order",
        cascade="all, delete-orphan",
        order_by="SalesOrderMilestone.sort_order",
    )
    invoices = relationship("Invoice", back_populates="sales_order")


class SalesOrderLineItem(Base):
    __tablename__ = "sales_order_line_items"

    id = Column(Integer, primary_key=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    quotation_line_item_id = Column(Integer, ForeignKey("quotation_line_items.id"), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    section = Column(String(100), nullable=True)
    item_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    quantity = Column(Numeric(12, 2), nullable=False, default=1)
    unit = Column(String(30), nullable=False, default="Service")
    unit_price = Column(Numeric(14, 2), nullable=False, default=0)
    discount_percent = Column(Numeric(5, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(14, 2), nullable=False, default=0)
    tax_rate = Column(Numeric(5, 2), nullable=False, default=18)
    line_subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    line_total = Column(Numeric(14, 2), nullable=False, default=0)
    fulfilled_quantity = Column(Numeric(12, 2), nullable=False, default=0)
    fulfillment_status = Column(String(20), nullable=False, default="pending")

    sales_order = relationship("SalesOrder", back_populates="line_items")
    product = relationship("Product")


class SalesOrderMilestone(Base):
    __tablename__ = "sales_order_milestones"

    id = Column(Integer, primary_key=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    sales_order = relationship("SalesOrder", back_populates="milestones")
    owner = relationship("User", foreign_keys=[owner_id])


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    issued_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    closed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    parent_invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    root_invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)

    invoice_number = Column(String(40), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    status = Column(String(30), nullable=False, default="draft", index=True)
    version = Column(Integer, nullable=False, default=1)
    invoice_type = Column(String(30), nullable=False, default="standard")
    source_type = Column(String(20), nullable=False, default="manual")
    currency = Column(String(3), nullable=False, default="INR")
    issue_date = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)

    client_name = Column(String(120), nullable=True)
    client_email = Column(String(255), nullable=True)
    client_phone = Column(String(30), nullable=True)
    client_org = Column(String(200), nullable=True)
    client_gstin = Column(String(15), nullable=True)
    attention_to = Column(String(120), nullable=True)
    billing_address = Column(Text, nullable=True)

    subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    line_discount_total = Column(Numeric(14, 2), nullable=False, default=0)
    header_discount_amount = Column(Numeric(14, 2), nullable=False, default=0)
    header_discount_percent = Column(Numeric(5, 2), nullable=False, default=0)
    total_tax = Column(Numeric(14, 2), nullable=False, default=0)
    round_off = Column(Numeric(14, 2), nullable=False, default=0)
    grand_total = Column(Numeric(14, 2), nullable=False, default=0)
    amount_paid = Column(Numeric(14, 2), nullable=False, default=0)
    outstanding_amount = Column(Numeric(14, 2), nullable=False, default=0)
    write_off_amount = Column(Numeric(14, 2), nullable=False, default=0)

    payment_terms = Column(Text, nullable=True)
    bank_instructions = Column(Text, nullable=True)
    billing_notes = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    review_comments = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    adjustment_reason = Column(Text, nullable=True)

    requires_review = Column(Integer, nullable=False, default=0)
    share_token = Column(String(64), nullable=True, unique=True, index=True)

    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    last_status_change_at = Column(DateTime(timezone=True), nullable=True)
    last_payment_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="invoices")
    sales_order = relationship("SalesOrder", back_populates="invoices")
    quotation = relationship("Quotation", back_populates="invoices")
    deal = relationship("Deal", foreign_keys=[deal_id])
    contact = relationship("Contact", foreign_keys=[contact_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    issued_by = relationship("User", foreign_keys=[issued_by_id])
    closed_by = relationship("User", foreign_keys=[closed_by_id])
    parent_invoice = relationship("Invoice", remote_side=[id], foreign_keys=[parent_invoice_id])
    line_items = relationship(
        "InvoiceLineItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLineItem.sort_order",
    )
    payments = relationship(
        "InvoicePayment",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoicePayment.payment_date",
    )


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    sales_order_line_item_id = Column(Integer, ForeignKey("sales_order_line_items.id"), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    section = Column(String(100), nullable=True)
    item_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    quantity = Column(Numeric(12, 2), nullable=False, default=1)
    unit = Column(String(30), nullable=False, default="Service")
    unit_price = Column(Numeric(14, 2), nullable=False, default=0)
    discount_percent = Column(Numeric(5, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(14, 2), nullable=False, default=0)
    tax_rate = Column(Numeric(5, 2), nullable=False, default=18)
    line_subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    line_total = Column(Numeric(14, 2), nullable=False, default=0)

    invoice = relationship("Invoice", back_populates="line_items")
    product = relationship("Product")


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    payment_date = Column(DateTime(timezone=True), nullable=False)
    payment_method = Column(String(30), nullable=False, default="bank_transfer")
    reference = Column(String(100), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    invoice = relationship("Invoice", back_populates="payments")
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])


class ClientNote(Base):
    __tablename__ = "client_notes"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_edited_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    note_type = Column(String(30), nullable=False, default="call")
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    visibility_scope = Column(String(20), nullable=False, default="team")
    tags = Column(String(500), nullable=True)
    structured_data = Column(Text, nullable=True)

    is_pinned = Column(Boolean, nullable=False, default=False)
    pin_order = Column(Integer, nullable=False, default=0)
    is_sensitive = Column(Boolean, nullable=False, default=False)
    is_resolved = Column(Boolean, nullable=False, default=False)
    follow_up_required = Column(Boolean, nullable=False, default=False)
    follow_up_due_date = Column(DateTime(timezone=True), nullable=True)
    follow_up_priority = Column(String(20), nullable=False, default="normal")
    follow_up_completed_at = Column(DateTime(timezone=True), nullable=True)

    is_deleted = Column(Boolean, nullable=False, default=False)
    revision_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="client_notes")
    contact = relationship("Contact", back_populates="client_notes")
    lead = relationship("Lead", foreign_keys=[lead_id])
    deal = relationship("Deal", foreign_keys=[deal_id])
    quotation = relationship("Quotation", foreign_keys=[quotation_id])
    sales_order = relationship("SalesOrder", foreign_keys=[sales_order_id])
    invoice = relationship("Invoice", foreign_keys=[invoice_id])
    author = relationship("User", foreign_keys=[author_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    last_edited_by = relationship("User", foreign_keys=[last_edited_by_id])
    revisions = relationship(
        "ClientNoteRevision",
        back_populates="client_note",
        cascade="all, delete-orphan",
        order_by="ClientNoteRevision.created_at.desc()",
    )


class ClientNoteRevision(Base):
    __tablename__ = "client_note_revisions"

    id = Column(Integer, primary_key=True)
    client_note_id = Column(Integer, ForeignKey("client_notes.id"), nullable=False)
    editor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note_type = Column(String(30), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client_note = relationship("ClientNote", back_populates="revisions")
    editor = relationship("User", foreign_keys=[editor_id])


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    submitted_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    paid_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)

    expense_number = Column(String(40), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)
    vendor_name = Column(String(200), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    tax_amount = Column(Numeric(14, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="INR")
    expense_date = Column(DateTime(timezone=True), nullable=False)
    reimbursement_due_date = Column(DateTime(timezone=True), nullable=True)
    payment_mode = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, default="draft", index=True)
    notes = Column(Text, nullable=True)
    receipt_reference = Column(String(100), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    reviewer_comments = Column(Text, nullable=True)
    cost_center = Column(String(100), nullable=True)

    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="expenses")
    submitted_by = relationship("User", foreign_keys=[submitted_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    paid_by = relationship("User", foreign_keys=[paid_by_id])
    deal = relationship("Deal", foreign_keys=[deal_id])
    contact = relationship("Contact", foreign_keys=[contact_id])
    attachments = relationship(
        "ExpenseAttachment",
        back_populates="expense",
        cascade="all, delete-orphan",
        order_by="ExpenseAttachment.created_at",
    )


class ExpenseAttachment(Base):
    __tablename__ = "expense_attachments"

    id = Column(Integer, primary_key=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    expense = relationship("Expense", back_populates="attachments")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sent_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    closed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)

    po_number = Column(String(40), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    vendor_name = Column(String(200), nullable=False)
    vendor_contact = Column(String(120), nullable=True)
    vendor_email = Column(String(255), nullable=True)
    vendor_phone = Column(String(30), nullable=True)
    status = Column(String(30), nullable=False, default="draft", index=True)
    currency = Column(String(3), nullable=False, default="INR")
    payment_terms = Column(String(40), nullable=True)
    po_date = Column(DateTime(timezone=True), nullable=False)
    expected_delivery_date = Column(DateTime(timezone=True), nullable=True)
    delivery_location = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    internal_reference = Column(String(100), nullable=True)
    vendor_quote_reference = Column(String(100), nullable=True)
    cost_center = Column(String(100), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    reviewer_comments = Column(Text, nullable=True)

    subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    total_tax = Column(Numeric(14, 2), nullable=False, default=0)
    grand_total = Column(Numeric(14, 2), nullable=False, default=0)
    received_value = Column(Numeric(14, 2), nullable=False, default=0)
    billed_value = Column(Numeric(14, 2), nullable=False, default=0)

    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="purchase_orders")
    created_by = relationship("User", foreign_keys=[created_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    sent_by = relationship("User", foreign_keys=[sent_by_id])
    closed_by = relationship("User", foreign_keys=[closed_by_id])
    deal = relationship("Deal", foreign_keys=[deal_id])
    contact = relationship("Contact", foreign_keys=[contact_id])
    line_items = relationship(
        "PurchaseOrderLineItem",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLineItem.sort_order",
    )
    receipts = relationship(
        "PurchaseOrderReceipt",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderReceipt.created_at.desc()",
    )
    billings = relationship(
        "PurchaseOrderBilling",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderBilling.created_at.desc()",
    )
    attachments = relationship(
        "PurchaseOrderAttachment",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderAttachment.created_at",
    )
    vendor_bills = relationship(
        "VendorBill",
        back_populates="purchase_order",
        order_by="VendorBill.created_at.desc()",
    )


class PurchaseOrderLineItem(Base):
    __tablename__ = "purchase_order_line_items"

    id = Column(Integer, primary_key=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    description = Column(String(255), nullable=False)
    sku = Column(String(80), nullable=True)
    unit = Column(String(30), nullable=False, default="Unit")
    ordered_quantity = Column(Numeric(12, 2), nullable=False, default=1)
    received_quantity = Column(Numeric(12, 2), nullable=False, default=0)
    billed_quantity = Column(Numeric(12, 2), nullable=False, default=0)
    unit_price = Column(Numeric(14, 2), nullable=False, default=0)
    tax_rate = Column(Numeric(5, 2), nullable=False, default=18)
    line_subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    line_total = Column(Numeric(14, 2), nullable=False, default=0)
    billed_amount = Column(Numeric(14, 2), nullable=False, default=0)

    purchase_order = relationship("PurchaseOrder", back_populates="line_items")
    product = relationship("Product")


class PurchaseOrderReceipt(Base):
    __tablename__ = "purchase_order_receipts"

    id = Column(Integer, primary_key=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    line_item_id = Column(Integer, ForeignKey("purchase_order_line_items.id"), nullable=False)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    receipt_date = Column(DateTime(timezone=True), nullable=False)
    grn_reference = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    purchase_order = relationship("PurchaseOrder", back_populates="receipts")
    line_item = relationship("PurchaseOrderLineItem")
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])


class PurchaseOrderBilling(Base):
    __tablename__ = "purchase_order_billings"

    id = Column(Integer, primary_key=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    line_item_id = Column(Integer, ForeignKey("purchase_order_line_items.id"), nullable=False)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    bill_reference = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    purchase_order = relationship("PurchaseOrder", back_populates="billings")
    line_item = relationship("PurchaseOrderLineItem")
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])


class PurchaseOrderAttachment(Base):
    __tablename__ = "purchase_order_attachments"

    id = Column(Integer, primary_key=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    purchase_order = relationship("PurchaseOrder", back_populates="attachments")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])


class VendorBill(Base):
    __tablename__ = "vendor_bills"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=True)

    bill_number = Column(String(40), nullable=True, index=True)
    supplier_invoice_number = Column(String(100), nullable=True)
    title = Column(String(200), nullable=False)
    status = Column(String(30), nullable=False, default="draft", index=True)
    currency = Column(String(3), nullable=False, default="INR")
    bill_date = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    payment_terms = Column(String(40), nullable=True)

    vendor_name = Column(String(200), nullable=False)
    vendor_email = Column(String(255), nullable=True)
    vendor_phone = Column(String(30), nullable=True)
    vendor_gstin = Column(String(20), nullable=True)
    vendor_address = Column(Text, nullable=True)

    subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    total_tax = Column(Numeric(14, 2), nullable=False, default=0)
    round_off = Column(Numeric(14, 2), nullable=False, default=0)
    grand_total = Column(Numeric(14, 2), nullable=False, default=0)
    amount_paid = Column(Numeric(14, 2), nullable=False, default=0)
    outstanding_amount = Column(Numeric(14, 2), nullable=False, default=0)

    internal_notes = Column(Text, nullable=True)
    approval_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)

    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    last_payment_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="vendor_bills")
    created_by = relationship("User", foreign_keys=[created_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    purchase_order = relationship("PurchaseOrder", back_populates="vendor_bills")
    deal = relationship("Deal", foreign_keys=[deal_id])
    contact = relationship("Contact", foreign_keys=[contact_id])
    expense = relationship("Expense", foreign_keys=[expense_id])
    line_items = relationship(
        "VendorBillLineItem",
        back_populates="vendor_bill",
        cascade="all, delete-orphan",
        order_by="VendorBillLineItem.sort_order",
    )
    payments = relationship(
        "VendorBillPayment",
        back_populates="vendor_bill",
        cascade="all, delete-orphan",
        order_by="VendorBillPayment.payment_date.desc()",
    )
    attachments = relationship(
        "VendorBillAttachment",
        back_populates="vendor_bill",
        cascade="all, delete-orphan",
        order_by="VendorBillAttachment.created_at",
    )


class VendorBillLineItem(Base):
    __tablename__ = "vendor_bill_line_items"

    id = Column(Integer, primary_key=True)
    vendor_bill_id = Column(Integer, ForeignKey("vendor_bills.id"), nullable=False)
    purchase_order_line_item_id = Column(Integer, ForeignKey("purchase_order_line_items.id"), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    description = Column(String(500), nullable=False)
    unit = Column(String(30), nullable=True, default="Unit")
    quantity = Column(Numeric(12, 2), nullable=False)
    unit_price = Column(Numeric(14, 2), nullable=False)
    tax_rate = Column(Numeric(5, 2), nullable=False, default=18)
    line_subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    line_total = Column(Numeric(14, 2), nullable=False, default=0)

    vendor_bill = relationship("VendorBill", back_populates="line_items")
    purchase_order_line_item = relationship("PurchaseOrderLineItem")


class VendorBillPayment(Base):
    __tablename__ = "vendor_bill_payments"

    id = Column(Integer, primary_key=True)
    vendor_bill_id = Column(Integer, ForeignKey("vendor_bills.id"), nullable=False)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    payment_date = Column(DateTime(timezone=True), nullable=False)
    payment_method = Column(String(30), nullable=False, default="bank_transfer")
    reference = Column(String(100), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vendor_bill = relationship("VendorBill", back_populates="payments")
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])


class VendorBillAttachment(Base):
    __tablename__ = "vendor_bill_attachments"

    id = Column(Integer, primary_key=True)
    vendor_bill_id = Column(Integer, ForeignKey("vendor_bills.id"), nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vendor_bill = relationship("VendorBill", back_populates="attachments")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])


class FollowUpReminder(Base):
    __tablename__ = "follow_up_reminders"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    reminder_type = Column(String(30), nullable=False, default="call")
    title = Column(String(200), nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    priority = Column(String(20), nullable=False, default="normal")
    due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="follow_up_reminders")
    lead = relationship("Lead", foreign_keys=[lead_id])
    deal = relationship("Deal", foreign_keys=[deal_id])
    contact = relationship("Contact", foreign_keys=[contact_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])


class NumberingConfiguration(Base):
    __tablename__ = "numbering_configurations"
    __table_args__ = (
        UniqueConstraint("company_id", "entity_name", name="uq_numbering_configurations_company_entity"),
    )

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    entity_name = Column(String(50), nullable=False, index=True)
    prefix = Column(String(20), nullable=False)
    starting_number = Column(Integer, nullable=False, default=1)
    current_number = Column(Integer, nullable=False, default=0)
    suffix = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class EmailTemplate(Base):
    """Reusable email templates for CRM notifications.

    Placeholders (e.g. {{name}}, {{reset_link}}) are stored as-is.
    Rendering is handled by the notification layer, not here.
    """

    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True, index=True)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SystemConfiguration(Base):
    """Global CRM configuration — only one row should exist (id=1)."""

    __tablename__ = "system_configurations"

    id = Column(Integer, primary_key=True)
    company_name = Column(String(200), nullable=False, default="BlackPapers")
    default_currency = Column(String(3), nullable=False, default="INR")
    date_format = Column(String(20), nullable=False, default="DD/MM/YYYY")
    timezone = Column(String(80), nullable=False, default="Asia/Kolkata")
    support_email = Column(String(255), nullable=False, default="connect@blackpapers.in")
    maintenance_mode = Column(Boolean, nullable=False, default=False)
    default_gst_rate = Column(Numeric(5, 2), nullable=False, default=18)
    tax_regime = Column(String(30), nullable=False, default="GST")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("company_id", "project_number", name="uq_projects_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    project_number = Column(String(40), nullable=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    project_type = Column(String(20), nullable=False, default="client")
    status = Column(String(20), nullable=False, default="draft")
    priority = Column(String(20), nullable=False, default="normal")
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=True)
    project_manager_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="projects")
    contact = relationship("Contact")
    deal = relationship("Deal")
    sales_order = relationship("SalesOrder")
    project_manager = relationship("User", foreign_keys=[project_manager_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),)

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False, default="member")
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    added_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    project = relationship("Project", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
    added_by = relationship("User", foreign_keys=[added_by_id])


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_key = Column(String(30), nullable=False, default="kickoff")
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), nullable=False, default="todo")
    priority = Column(String(20), nullable=False, default="normal")
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    blocked_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    project = relationship("Project", back_populates="tasks")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    __table_args__ = (UniqueConstraint("company_id", "leave_number", name="uq_leave_requests_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    leave_number = Column(String(40), nullable=True)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    leave_type = Column(String(30), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False, index=True)
    end_date = Column(DateTime(timezone=True), nullable=False)
    total_days = Column(Numeric(5, 1), nullable=False, default=1)
    is_half_day = Column(Boolean, nullable=False, default=False)
    half_day_period = Column(String(20), nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewer_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="leave_requests")
    employee = relationship("User", foreign_keys=[employee_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])


class TimesheetEntry(Base):
    __tablename__ = "timesheet_entries"
    __table_args__ = (UniqueConstraint("company_id", "entry_number", name="uq_timesheet_entries_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    entry_number = Column(String(40), nullable=True)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("project_tasks.id"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    work_date = Column(DateTime(timezone=True), nullable=False, index=True)
    hours = Column(Numeric(5, 2), nullable=False)
    is_billable = Column(Boolean, nullable=False, default=True)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft", index=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewer_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="timesheet_entries")
    employee = relationship("User", foreign_keys=[employee_id])
    project = relationship("Project")
    task = relationship("ProjectTask")
    contact = relationship("Contact")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"
    __table_args__ = (UniqueConstraint("company_id", "user_id", name="uq_employee_profiles_company_user"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    joining_date = Column(DateTime(timezone=True), nullable=True)
    date_of_birth = Column(DateTime(timezone=True), nullable=True)
    gender = Column(String(20), nullable=True)
    employment_type = Column(String(30), nullable=False, default="full_time")
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    salary_monthly = Column(Numeric(12, 2), nullable=True)
    emergency_contact_name = Column(String(120), nullable=True)
    emergency_contact_phone = Column(String(30), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(10), nullable=True)
    pan = Column(String(10), nullable=True)
    bank_name = Column(String(120), nullable=True)
    bank_account_last4 = Column(String(4), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="employee_profiles")
    user = relationship("User", foreign_keys=[user_id])
    manager = relationship("User", foreign_keys=[manager_id])


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("company_id", "user_id", "attendance_date", name="uq_attendance_company_user_date"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    attendance_date = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="present")
    check_in_at = Column(DateTime(timezone=True), nullable=True)
    check_out_at = Column(DateTime(timezone=True), nullable=True)
    worked_hours = Column(Numeric(4, 2), nullable=True)
    late_minutes = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="attendance_records")
    user = relationship("User", foreign_keys=[user_id])
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])


class JobOpening(Base):
    __tablename__ = "job_openings"
    __table_args__ = (UniqueConstraint("company_id", "job_code", name="uq_job_openings_company_code"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    job_code = Column(String(40), nullable=True)
    title = Column(String(200), nullable=False)
    department = Column(String(120), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="open", index=True)
    openings_count = Column(Integer, nullable=False, default=1)
    salary_min = Column(Numeric(12, 2), nullable=True)
    salary_max = Column(Numeric(12, 2), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="job_openings")
    created_by = relationship("User", foreign_keys=[created_by_id])
    applicants = relationship("JobApplicant", back_populates="job_opening", cascade="all, delete-orphan")


class JobApplicant(Base):
    __tablename__ = "job_applicants"

    id = Column(Integer, primary_key=True)
    job_opening_id = Column(Integer, ForeignKey("job_openings.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(30), nullable=True)
    status = Column(String(30), nullable=False, default="applied", index=True)
    interview_round = Column(Integer, nullable=False, default=0)
    experience_years = Column(Numeric(4, 1), nullable=True)
    current_company = Column(String(200), nullable=True)
    resume_summary = Column(Text, nullable=True)
    interviewer_note = Column(Text, nullable=True)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    job_opening = relationship("JobOpening", back_populates="applicants")


class Payslip(Base):
    __tablename__ = "payslips"
    __table_args__ = (UniqueConstraint("company_id", "payslip_number", name="uq_payslips_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    payslip_number = Column(String(40), nullable=True)
    period_month = Column(Integer, nullable=False)
    period_year = Column(Integer, nullable=False)
    basic_salary = Column(Numeric(12, 2), nullable=False, default=0)
    hra = Column(Numeric(12, 2), nullable=False, default=0)
    allowances = Column(Numeric(12, 2), nullable=False, default=0)
    gross_salary = Column(Numeric(12, 2), nullable=False, default=0)
    pf_deduction = Column(Numeric(12, 2), nullable=False, default=0)
    tds_deduction = Column(Numeric(12, 2), nullable=False, default=0)
    other_deductions = Column(Numeric(12, 2), nullable=False, default=0)
    reimbursements = Column(Numeric(12, 2), nullable=False, default=0)
    net_salary = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="generated", index=True)
    payment_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    generated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="payslips")
    employee = relationship("User", foreign_keys=[employee_id])
    generated_by = relationship("User", foreign_keys=[generated_by_id])


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    channel = Column(String(30), nullable=False, default="general", index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    company = relationship("Company", back_populates="chat_messages")
    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_id])
    project = relationship("Project")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    email = Column(String(255), nullable=True)
    action = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="activities")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(30), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    link_path = Column(String(255), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company")
    user = relationship("User")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), unique=True, nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    related_module = Column(String(50), nullable=True, index=True)
    related_record_id = Column(Integer, nullable=True, index=True)
    category = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company")
    uploaded_by = relationship("User")


class WebsiteSettings(Base):
    __tablename__ = "website_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True, index=True)
    company_slug = Column(String(80), nullable=False, unique=True, index=True)
    home_page_id = Column(Integer, ForeignKey("website_pages.id"), nullable=True)
    default_lead_assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="website_settings")
    home_page = relationship("WebsitePage", foreign_keys=[home_page_id])
    default_lead_assignee = relationship("User", foreign_keys=[default_lead_assignee_id])


class WebsitePage(Base):
    __tablename__ = "website_pages"
    __table_args__ = (UniqueConstraint("company_id", "slug", name="uq_website_pages_company_slug"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    slug = Column(String(80), nullable=False, index=True)
    page_type = Column(String(20), nullable=False, default="general", index=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    seo_title = Column(String(200), nullable=True)
    seo_description = Column(String(500), nullable=True)
    sections_json = Column(JSON, nullable=False, default=list)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    is_home = Column(Boolean, nullable=False, default=False)
    preview_token = Column(String(64), nullable=True, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="website_pages")
    product = relationship("Product")
    created_by = relationship("User", foreign_keys=[created_by_id])
    updated_by = relationship("User", foreign_keys=[updated_by_id])


class WebsiteForm(Base):
    __tablename__ = "website_forms"
    __table_args__ = (UniqueConstraint("company_id", "slug", name="uq_website_forms_company_slug"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    slug = Column(String(80), nullable=False, index=True)
    fields_json = Column(JSON, nullable=False, default=list)
    success_message = Column(String(500), nullable=False, default="Thank you! We will contact you shortly.")
    redirect_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="website_forms")
    submissions = relationship("WebsiteFormSubmission", back_populates="form")


class WebsiteFormSubmission(Base):
    __tablename__ = "website_form_submissions"

    id = Column(Integer, primary_key=True)
    form_id = Column(Integer, ForeignKey("website_forms.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    form = relationship("WebsiteForm", back_populates="submissions")
    lead = relationship("Lead")


class WebsiteBlogPost(Base):
    __tablename__ = "website_blog_posts"
    __table_args__ = (UniqueConstraint("company_id", "slug", name="uq_website_blog_posts_company_slug"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    slug = Column(String(80), nullable=False, index=True)
    excerpt = Column(String(500), nullable=True)
    body_html = Column(Text, nullable=False, default="")
    cover_image_url = Column(String(500), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    seo_title = Column(String(200), nullable=True)
    seo_description = Column(String(500), nullable=True)
    tags = Column(JSON, nullable=False, default=list)
    preview_token = Column(String(64), nullable=True, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="website_blog_posts")
    author = relationship("User", foreign_keys=[author_id])


class WebsitePageView(Base):
    __tablename__ = "website_page_views"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    page_id = Column(Integer, ForeignKey("website_pages.id"), nullable=True, index=True)
    post_id = Column(Integer, ForeignKey("website_blog_posts.id"), nullable=True, index=True)
    path = Column(String(255), nullable=False)
    session_id = Column(String(64), nullable=True, index=True)
    viewed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class StoreSettings(Base):
    __tablename__ = "store_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True, index=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    store_name = Column(String(120), nullable=True)
    currency = Column(String(3), nullable=False, default="INR")
    guest_checkout_allowed = Column(Boolean, nullable=False, default=True)
    flat_shipping_rate = Column(Numeric(12, 2), nullable=False, default=99)
    free_shipping_above = Column(Numeric(12, 2), nullable=True)
    default_payment_method = Column(String(30), nullable=False, default="cod")
    order_number_prefix = Column(String(10), nullable=False, default="WEB")
    auto_create_sales_order = Column(Boolean, nullable=False, default=True)
    auto_create_invoice = Column(Boolean, nullable=False, default=False)
    inventory_reserve_on_checkout = Column(Boolean, nullable=False, default=False)
    return_window_days = Column(Integer, nullable=False, default=7)
    bank_details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    company = relationship("Company", back_populates="store_settings")


class StoreCustomer(Base):
    __tablename__ = "store_customers"
    __table_args__ = (UniqueConstraint("company_id", "email", name="uq_store_customers_company_email"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(30), nullable=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(120), nullable=False)
    gstin = Column(String(15), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    contact = relationship("Contact")
    addresses = relationship("StoreCustomerAddress", back_populates="customer")
    orders = relationship("StoreOrder", back_populates="customer")


class StoreCustomerAddress(Base):
    __tablename__ = "store_customer_addresses"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("store_customers.id"), nullable=False, index=True)
    label = Column(String(40), nullable=False, default="Home")
    line1 = Column(String(255), nullable=False)
    line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    pincode = Column(String(10), nullable=False)
    is_default_shipping = Column(Boolean, nullable=False, default=False)
    is_default_billing = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("StoreCustomer", back_populates="addresses")


class StoreCart(Base):
    __tablename__ = "store_carts"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey("store_customers.id"), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship("StoreCartItem", back_populates="cart", cascade="all, delete-orphan")
    customer = relationship("StoreCustomer")


class StoreCartItem(Base):
    __tablename__ = "store_cart_items"

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("store_carts.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False, default=1)
    unit_price_snapshot = Column(Numeric(12, 2), nullable=False, default=0)
    gst_rate_snapshot = Column(Numeric(5, 2), nullable=False, default=18)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cart = relationship("StoreCart", back_populates="items")
    product = relationship("Product")


class StoreOrder(Base):
    __tablename__ = "store_orders"
    __table_args__ = (UniqueConstraint("company_id", "order_number", name="uq_store_orders_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    order_number = Column(String(40), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("store_customers.id"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="pending_payment", index=True)
    payment_status = Column(String(30), nullable=False, default="unpaid", index=True)
    subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    tax_total = Column(Numeric(14, 2), nullable=False, default=0)
    shipping_total = Column(Numeric(14, 2), nullable=False, default=0)
    grand_total = Column(Numeric(14, 2), nullable=False, default=0)
    currency = Column(String(3), nullable=False, default="INR")
    guest_email = Column(String(255), nullable=True)
    guest_phone = Column(String(30), nullable=True)
    guest_name = Column(String(120), nullable=True)
    shipping_address_json = Column(JSON, nullable=True)
    billing_address_json = Column(JSON, nullable=True)
    shipping_method = Column(String(30), nullable=False, default="standard")
    payment_method = Column(String(30), nullable=False, default="cod")
    tracking_number = Column(String(120), nullable=True)
    customer_note = Column(Text, nullable=True)
    placed_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    shipped_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    company = relationship("Company", back_populates="store_orders")
    customer = relationship("StoreCustomer", back_populates="orders")
    contact = relationship("Contact")
    items = relationship("StoreOrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("StorePayment", back_populates="order")
    returns = relationship("StoreReturn", back_populates="order")


class StoreOrderItem(Base):
    __tablename__ = "store_order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("store_orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product_name_snapshot = Column(String(255), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False, default=0)
    gst_rate = Column(Numeric(5, 2), nullable=False, default=18)
    line_total = Column(Numeric(14, 2), nullable=False, default=0)

    order = relationship("StoreOrder", back_populates="items")
    product = relationship("Product")


class StorePayment(Base):
    __tablename__ = "store_payments"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("store_orders.id"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    method = Column(String(30), nullable=False)
    gateway_reference = Column(String(120), nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("StoreOrder", back_populates="payments")


class StoreReturn(Base):
    __tablename__ = "store_returns"
    __table_args__ = (UniqueConstraint("company_id", "return_number", name="uq_store_returns_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("store_orders.id"), nullable=False, index=True)
    return_number = Column(String(40), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="requested", index=True)
    reason = Column(Text, nullable=False)
    items_json = Column(JSON, nullable=False, default=list)
    refund_amount = Column(Numeric(14, 2), nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    order = relationship("StoreOrder", back_populates="returns")


class PosSettings(Base):
    __tablename__ = "pos_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True, index=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    default_register_id = Column(Integer, ForeignKey("pos_registers.id"), nullable=True)
    bill_number_prefix = Column(String(10), nullable=False, default="POS")
    auto_create_invoice = Column(Boolean, nullable=False, default=True)
    inventory_deduct_on_sale = Column(Boolean, nullable=False, default=True)
    allow_negative_stock = Column(Boolean, nullable=False, default=False)
    receipt_header = Column(Text, nullable=True)
    receipt_footer = Column(Text, nullable=True)
    require_customer_phone = Column(Boolean, nullable=False, default=False)
    max_line_discount_pct = Column(Numeric(5, 2), nullable=False, default=0)
    return_window_days = Column(Integer, nullable=False, default=7)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    company = relationship("Company", back_populates="pos_settings")


class PosRegister(Base):
    __tablename__ = "pos_registers"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_pos_registers_company_code"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    code = Column(String(20), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    default_payment_method = Column(String(20), nullable=False, default="cash")
    opening_float_default = Column(Numeric(12, 2), nullable=False, default=2000)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="pos_registers")
    sessions = relationship("PosSession", back_populates="register")


class PosSession(Base):
    __tablename__ = "pos_sessions"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    register_id = Column(Integer, ForeignKey("pos_registers.id"), nullable=False, index=True)
    opened_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    closed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), nullable=False, default="open", index=True)
    opening_float = Column(Numeric(12, 2), nullable=False, default=0)
    closing_cash_counted = Column(Numeric(12, 2), nullable=True)
    expected_cash = Column(Numeric(12, 2), nullable=True)
    cash_variance = Column(Numeric(12, 2), nullable=True)
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    register = relationship("PosRegister", back_populates="sessions")
    opened_by = relationship("User", foreign_keys=[opened_by_id])
    closed_by = relationship("User", foreign_keys=[closed_by_id])
    carts = relationship("PosCart", back_populates="session")
    bills = relationship("PosBill", back_populates="session")


class PosCart(Base):
    __tablename__ = "pos_carts"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("pos_sessions.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    customer_name = Column(String(120), nullable=True)
    customer_phone = Column(String(30), nullable=True)
    customer_gstin = Column(String(15), nullable=True)
    held_label = Column(String(80), nullable=True)
    subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    discount_total = Column(Numeric(14, 2), nullable=False, default=0)
    tax_total = Column(Numeric(14, 2), nullable=False, default=0)
    grand_total = Column(Numeric(14, 2), nullable=False, default=0)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    session = relationship("PosSession", back_populates="carts")
    items = relationship("PosCartItem", back_populates="cart", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_id])


class PosCartItem(Base):
    __tablename__ = "pos_cart_items"

    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey("pos_carts.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(12, 2), nullable=False, default=0)
    gst_rate = Column(Numeric(5, 2), nullable=False, default=18)
    line_total = Column(Numeric(14, 2), nullable=False, default=0)

    cart = relationship("PosCart", back_populates="items")
    product = relationship("Product")


class PosBill(Base):
    __tablename__ = "pos_bills"
    __table_args__ = (UniqueConstraint("company_id", "bill_number", name="uq_pos_bills_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    bill_number = Column(String(40), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("pos_sessions.id"), nullable=False, index=True)
    register_id = Column(Integer, ForeignKey("pos_registers.id"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    status = Column(String(30), nullable=False, default="completed", index=True)
    subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    discount_total = Column(Numeric(14, 2), nullable=False, default=0)
    tax_total = Column(Numeric(14, 2), nullable=False, default=0)
    grand_total = Column(Numeric(14, 2), nullable=False, default=0)
    customer_name = Column(String(120), nullable=True)
    customer_phone = Column(String(30), nullable=True)
    customer_gstin = Column(String(15), nullable=True)
    cashier_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    voided_at = Column(DateTime(timezone=True), nullable=True)
    void_reason = Column(Text, nullable=True)
    voided_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="pos_bills")
    session = relationship("PosSession", back_populates="bills")
    register = relationship("PosRegister")
    contact = relationship("Contact")
    invoice = relationship("Invoice")
    cashier = relationship("User", foreign_keys=[cashier_id])
    voided_by = relationship("User", foreign_keys=[voided_by_id])
    items = relationship("PosBillItem", back_populates="bill", cascade="all, delete-orphan")
    payments = relationship("PosPayment", back_populates="bill", cascade="all, delete-orphan")
    returns = relationship("PosReturn", back_populates="bill")


class PosBillItem(Base):
    __tablename__ = "pos_bill_items"

    id = Column(Integer, primary_key=True)
    bill_id = Column(Integer, ForeignKey("pos_bills.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product_name_snapshot = Column(String(255), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    discount_amount = Column(Numeric(12, 2), nullable=False, default=0)
    gst_rate = Column(Numeric(5, 2), nullable=False, default=18)
    line_total = Column(Numeric(14, 2), nullable=False)

    bill = relationship("PosBill", back_populates="items")
    product = relationship("Product")


class PosPayment(Base):
    __tablename__ = "pos_payments"

    id = Column(Integer, primary_key=True)
    bill_id = Column(Integer, ForeignKey("pos_bills.id"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    method = Column(String(20), nullable=False)
    reference = Column(String(120), nullable=True)
    status = Column(String(20), nullable=False, default="completed")
    crm_payment_id = Column(Integer, nullable=True)

    bill = relationship("PosBill", back_populates="payments")


class PosReturn(Base):
    __tablename__ = "pos_returns"
    __table_args__ = (UniqueConstraint("company_id", "return_number", name="uq_pos_returns_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    bill_id = Column(Integer, ForeignKey("pos_bills.id"), nullable=False, index=True)
    return_number = Column(String(40), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="completed")
    reason = Column(Text, nullable=False)
    refund_amount = Column(Numeric(14, 2), nullable=False)
    refund_method = Column(String(20), nullable=False, default="cash")
    items_json = Column(JSON, nullable=False, default=list)
    processed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

    bill = relationship("PosBill", back_populates="returns")
    processed_by = relationship("User")


class ManufacturingSettings(Base):
    __tablename__ = "manufacturing_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    work_order_prefix = Column(String(10), nullable=False, default="WO")
    auto_reserve_materials_on_release = Column(Boolean, nullable=False, default=False)
    require_qc_before_receipt = Column(Boolean, nullable=False, default=True)
    default_scrap_pct = Column(Numeric(5, 2), nullable=False, default=0)
    allow_negative_issue = Column(Boolean, nullable=False, default=False)
    default_checklist_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="manufacturing_settings")


class BomHeader(Base):
    __tablename__ = "bom_headers"
    __table_args__ = (UniqueConstraint("company_id", "product_id", "version", name="uq_bom_headers_product_version"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    version = Column(String(20), nullable=False, default="1.0")
    status = Column(String(20), nullable=False, default="draft", index=True)
    output_qty = Column(Numeric(12, 2), nullable=False, default=1)
    output_uom = Column(String(30), nullable=False, default="Unit")
    notes = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    product = relationship("Product", foreign_keys=[product_id])
    lines = relationship("BomLine", back_populates="bom", cascade="all, delete-orphan", order_by="BomLine.sort_order")
    created_by = relationship("User", foreign_keys=[created_by_id])


class BomLine(Base):
    __tablename__ = "bom_lines"

    id = Column(Integer, primary_key=True)
    bom_id = Column(Integer, ForeignKey("bom_headers.id"), nullable=False, index=True)
    component_product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Numeric(12, 4), nullable=False)
    scrap_pct = Column(Numeric(5, 2), nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)

    bom = relationship("BomHeader", back_populates="lines")
    component_product = relationship("Product", foreign_keys=[component_product_id])


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (UniqueConstraint("company_id", "work_order_number", name="uq_work_orders_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    work_order_number = Column(String(40), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    bom_id = Column(Integer, ForeignKey("bom_headers.id"), nullable=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=True, index=True)
    sales_order_line_id = Column(Integer, ForeignKey("sales_order_line_items.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    planned_qty = Column(Numeric(12, 2), nullable=False)
    completed_qty = Column(Numeric(12, 2), nullable=False, default=0)
    scrap_qty = Column(Numeric(12, 2), nullable=False, default=0)
    planned_start = Column(Date, nullable=True)
    planned_end = Column(Date, nullable=True)
    actual_start = Column(DateTime(timezone=True), nullable=True)
    actual_end = Column(DateTime(timezone=True), nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    priority = Column(String(10), nullable=False, default="normal")
    notes = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="work_orders")
    product = relationship("Product", foreign_keys=[product_id])
    bom = relationship("BomHeader")
    sales_order = relationship("SalesOrder")
    sales_order_line = relationship("SalesOrderLineItem")
    project = relationship("Project")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    material_plans = relationship(
        "WorkOrderMaterialPlan",
        back_populates="work_order",
        cascade="all, delete-orphan",
    )
    material_issues = relationship(
        "WorkOrderMaterialIssue",
        back_populates="work_order",
        cascade="all, delete-orphan",
    )
    receipts = relationship(
        "WorkOrderReceipt",
        back_populates="work_order",
        cascade="all, delete-orphan",
    )
    quality_inspections = relationship(
        "QualityInspection",
        back_populates="work_order",
        cascade="all, delete-orphan",
    )


class WorkOrderMaterialPlan(Base):
    __tablename__ = "work_order_material_plans"

    id = Column(Integer, primary_key=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, index=True)
    component_product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    required_qty = Column(Numeric(12, 4), nullable=False)
    issued_qty = Column(Numeric(12, 4), nullable=False, default=0)
    unit = Column(String(30), nullable=False, default="Unit")

    work_order = relationship("WorkOrder", back_populates="material_plans")
    component_product = relationship("Product")


class WorkOrderMaterialIssue(Base):
    __tablename__ = "work_order_material_issues"

    id = Column(Integer, primary_key=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, index=True)
    component_product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Numeric(12, 4), nullable=False)
    stock_movement_id = Column(Integer, ForeignKey("stock_movements.id"), nullable=True)
    issued_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    issued_at = Column(DateTime(timezone=True), server_default=func.now())

    work_order = relationship("WorkOrder", back_populates="material_issues")
    component_product = relationship("Product")
    issued_by = relationship("User")
    stock_movement = relationship("StockMovement")


class WorkOrderReceipt(Base):
    __tablename__ = "work_order_receipts"

    id = Column(Integer, primary_key=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, index=True)
    quantity = Column(Numeric(12, 2), nullable=False)
    stock_movement_id = Column(Integer, ForeignKey("stock_movements.id"), nullable=True)
    received_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now())

    work_order = relationship("WorkOrder", back_populates="receipts")
    received_by = relationship("User")
    stock_movement = relationship("StockMovement")


class QualityInspection(Base):
    __tablename__ = "quality_inspections"
    __table_args__ = (UniqueConstraint("company_id", "inspection_number", name="uq_quality_inspections_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True, index=True)
    inspection_point_id = Column(Integer, ForeignKey("inspection_points.id"), nullable=True, index=True)
    template_id = Column(Integer, ForeignKey("quality_checklist_templates.id"), nullable=True)
    inspection_number = Column(String(40), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    checklist_json = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    reference_type = Column(String(30), nullable=True, index=True)
    reference_id = Column(Integer, nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    batch_ref = Column(String(80), nullable=True)
    inspected_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    inspected_at = Column(DateTime(timezone=True), nullable=True)
    waived_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    waiver_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    work_order = relationship("WorkOrder", back_populates="quality_inspections")
    inspection_point = relationship("InspectionPoint")
    template = relationship("QualityChecklistTemplate")
    product = relationship("Product", foreign_keys=[product_id])
    inspected_by = relationship("User", foreign_keys=[inspected_by_id])
    waived_by = relationship("User", foreign_keys=[waived_by_id])
    corrective_actions = relationship("CorrectiveAction", back_populates="inspection")
    alerts = relationship("QualityAlert", back_populates="inspection")


class QualitySettings(Base):
    __tablename__ = "quality_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    inspection_number_prefix = Column(String(10), nullable=False, default="QC")
    capa_number_prefix = Column(String(10), nullable=False, default="CAPA")
    default_incoming_required = Column(Boolean, nullable=False, default=False)
    block_on_fail_default = Column(Boolean, nullable=False, default=True)
    alert_repeat_fail_threshold = Column(Integer, nullable=False, default=3)
    alert_overdue_hours = Column(Integer, nullable=False, default=24)
    notify_roles_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="quality_settings")


class InspectionPoint(Base):
    __tablename__ = "inspection_points"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_inspection_points_company_code"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    code = Column(String(40), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    point_type = Column(String(20), nullable=False)
    trigger = Column(String(30), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    block_on_fail = Column(Boolean, nullable=False, default=True)
    default_template_id = Column(Integer, ForeignKey("quality_checklist_templates.id"), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    company = relationship("Company", back_populates="inspection_points")


class QualityChecklistTemplate(Base):
    __tablename__ = "quality_checklist_templates"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    inspection_point_id = Column(Integer, ForeignKey("inspection_points.id"), nullable=True, index=True)
    items_json = Column(JSON, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="draft", index=True)
    version = Column(String(20), nullable=False, default="1.0")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    product = relationship("Product", foreign_keys=[product_id])
    inspection_point = relationship("InspectionPoint", foreign_keys=[inspection_point_id])
    created_by = relationship("User")


class QualityAlert(Base):
    __tablename__ = "quality_alerts"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    alert_type = Column(String(30), nullable=False, index=True)
    severity = Column(String(10), nullable=False, default="medium")
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    inspection_id = Column(Integer, ForeignKey("quality_inspections.id"), nullable=True, index=True)
    capa_id = Column(Integer, ForeignKey("corrective_actions.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    status = Column(String(20), nullable=False, default="open", index=True)
    acknowledged_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    inspection = relationship("QualityInspection", back_populates="alerts")
    capa = relationship("CorrectiveAction", back_populates="alerts")
    product = relationship("Product")
    acknowledged_by = relationship("User")


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"
    __table_args__ = (UniqueConstraint("company_id", "capa_number", name="uq_corrective_actions_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    capa_number = Column(String(40), nullable=False, index=True)
    inspection_id = Column(Integer, ForeignKey("quality_inspections.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    action_type = Column(String(30), nullable=False, default="rework")
    status = Column(String(20), nullable=False, default="open", index=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    due_date = Column(Date, nullable=True)
    root_cause = Column(Text, nullable=True)
    corrective_steps = Column(Text, nullable=False, default="")
    verification_notes = Column(Text, nullable=True)
    closed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    inspection = relationship("QualityInspection", back_populates="corrective_actions")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    closed_by = relationship("User", foreign_keys=[closed_by_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    alerts = relationship("QualityAlert", back_populates="capa")


class MaintenanceSettings(Base):
    __tablename__ = "maintenance_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    work_order_prefix = Column(String(10), nullable=False, default="MWO")
    asset_code_prefix = Column(String(10), nullable=False, default="AST")
    default_pm_interval_days = Column(Integer, nullable=False, default=90)
    critical_downtime_alert_hours = Column(Integer, nullable=False, default=4)
    auto_deduct_spare_parts = Column(Boolean, nullable=False, default=True)
    allow_negative_spare_parts = Column(Boolean, nullable=False, default=False)
    notify_roles_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="maintenance_settings")


class MaintenanceAssetCategory(Base):
    __tablename__ = "maintenance_asset_categories"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    company = relationship("Company")
    assets = relationship("MaintenanceAsset", back_populates="category")


class MaintenanceAsset(Base):
    __tablename__ = "maintenance_assets"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    asset_code = Column(String(40), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category_id = Column(Integer, ForeignKey("maintenance_asset_categories.id"), nullable=True)
    status = Column(String(30), nullable=False, default="operational", index=True)
    criticality = Column(String(20), nullable=False, default="medium")
    location_notes = Column(String(255), nullable=True)
    manufacturer = Column(String(120), nullable=True)
    model = Column(String(120), nullable=True)
    serial_number = Column(String(80), nullable=True)
    purchase_date = Column(Date, nullable=True)
    warranty_end = Column(Date, nullable=True)
    vendor_contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    pm_interval_days = Column(Integer, nullable=True)
    last_service_date = Column(Date, nullable=True)
    next_pm_due_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="maintenance_assets")
    category = relationship("MaintenanceAssetCategory", back_populates="assets")
    vendor_contact = relationship("Contact", foreign_keys=[vendor_contact_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    work_orders = relationship("MaintenanceWorkOrder", back_populates="asset")


class MaintenanceWorkOrder(Base):
    __tablename__ = "maintenance_work_orders"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    work_order_number = Column(String(40), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("maintenance_assets.id"), nullable=False, index=True)
    type = Column(String(20), nullable=False, default="breakdown", index=True)
    priority = Column(String(20), nullable=False, default="normal")
    status = Column(String(20), nullable=False, default="open", index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    reported_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    downtime_minutes = Column(Integer, nullable=True)
    root_cause = Column(Text, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    vendor_contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="maintenance_work_orders")
    asset = relationship("MaintenanceAsset", back_populates="work_orders")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    vendor_contact = relationship("Contact", foreign_keys=[vendor_contact_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    parts = relationship("MaintenanceWoPart", back_populates="work_order")


class MaintenanceWoPart(Base):
    __tablename__ = "maintenance_wo_parts"

    id = Column(Integer, primary_key=True)
    work_order_id = Column(Integer, ForeignKey("maintenance_work_orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Numeric(14, 4), nullable=False)
    stock_movement_id = Column(Integer, ForeignKey("stock_movements.id"), nullable=True)
    issued_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=False)

    work_order = relationship("MaintenanceWorkOrder", back_populates="parts")
    product = relationship("Product")
    issued_by = relationship("User", foreign_keys=[issued_by_id])


class FieldServiceSettings(Base):
    __tablename__ = "field_service_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    order_prefix = Column(String(10), nullable=False, default="FSO")
    default_sla_hours = Column(Integer, nullable=False, default=48)
    auto_deduct_parts = Column(Boolean, nullable=False, default=True)
    allow_negative_parts = Column(Boolean, nullable=False, default=False)
    notify_roles_json = Column(JSON, nullable=False, default=list)
    service_types_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="field_service_settings")


class FieldServiceOrder(Base):
    __tablename__ = "field_service_orders"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    order_number = Column(String(40), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False, index=True)
    type = Column(String(20), nullable=False, default="repair", index=True)
    priority = Column(String(20), nullable=False, default="normal")
    status = Column(String(20), nullable=False, default="draft", index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    site_address = Column(Text, nullable=True)
    site_contact_name = Column(String(120), nullable=True)
    site_contact_phone = Column(String(30), nullable=True)
    site_notes = Column(Text, nullable=True)
    scheduled_start = Column(DateTime(timezone=True), nullable=True)
    scheduled_end = Column(DateTime(timezone=True), nullable=True)
    dispatched_at = Column(DateTime(timezone=True), nullable=True)
    arrived_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    sla_due_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="field_service_orders")
    contact = relationship("Contact", foreign_keys=[contact_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    parts = relationship("FieldServiceOrderPart", back_populates="field_service_order")


class FieldServiceOrderPart(Base):
    __tablename__ = "field_service_order_parts"

    id = Column(Integer, primary_key=True)
    field_service_order_id = Column(Integer, ForeignKey("field_service_orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Numeric(14, 4), nullable=False)
    stock_movement_id = Column(Integer, ForeignKey("stock_movements.id"), nullable=True)
    issued_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    issued_at = Column(DateTime(timezone=True), nullable=False)

    field_service_order = relationship("FieldServiceOrder", back_populates="parts")
    product = relationship("Product")
    issued_by = relationship("User", foreign_keys=[issued_by_id])


class SubscriptionSettings(Base):
    __tablename__ = "subscription_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    subscription_prefix = Column(String(10), nullable=False, default="SUB")
    default_reminder_days = Column(JSON, nullable=False, default=list)
    auto_invoice_mode = Column(String(10), nullable=False, default="draft")
    auto_invoice_on_billing_date = Column(Boolean, nullable=False, default=True)
    grace_period_days = Column(Integer, nullable=False, default=7)
    notify_roles_json = Column(JSON, nullable=False, default=list)
    allow_immediate_cancel = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="subscription_settings")


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    plan_code = Column(String(40), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    billing_interval = Column(String(20), nullable=False, default="monthly")
    interval_days = Column(Integer, nullable=True)
    price = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    gst_rate = Column(Numeric(5, 2), nullable=False, default=18)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    trial_days = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="active")
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="subscription_plans")
    product = relationship("Product")
    subscriptions = relationship("CustomerSubscription", back_populates="plan")


class CustomerSubscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    subscription_number = Column(String(40), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(14, 2), nullable=True)
    start_date = Column(Date, nullable=False)
    trial_end_date = Column(Date, nullable=True)
    current_period_start = Column(Date, nullable=True)
    current_period_end = Column(Date, nullable=True)
    next_billing_date = Column(Date, nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="customer_subscriptions")
    contact = relationship("Contact", foreign_keys=[contact_id])
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
    created_by = relationship("User", foreign_keys=[created_by_id])
    subscription_invoices = relationship("SubscriptionInvoice", back_populates="subscription")
    plan_changes = relationship("SubscriptionPlanChange", back_populates="subscription")


class SubscriptionInvoice(Base):
    __tablename__ = "subscription_invoices"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    billing_period_start = Column(Date, nullable=False)
    billing_period_end = Column(Date, nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False)

    subscription = relationship("CustomerSubscription", back_populates="subscription_invoices")
    invoice = relationship("Invoice")


class SubscriptionPlanChange(Base):
    __tablename__ = "subscription_plan_changes"

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False, index=True)
    from_plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    to_plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    effective_date = Column(Date, nullable=False)
    change_type = Column(String(20), nullable=False, default="same_tier")
    notes = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    subscription = relationship("CustomerSubscription", back_populates="plan_changes")
    from_plan = relationship("SubscriptionPlan", foreign_keys=[from_plan_id])
    to_plan = relationship("SubscriptionPlan", foreign_keys=[to_plan_id])
    created_by = relationship("User", foreign_keys=[created_by_id])


class RentalSettings(Base):
    __tablename__ = "rental_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    contract_prefix = Column(String(10), nullable=False, default="RNT")
    default_rate_basis = Column(String(10), nullable=False, default="daily")
    default_deposit_percent = Column(Numeric(5, 2), nullable=False, default=20)
    late_fee_per_day = Column(Numeric(14, 2), nullable=False, default=500)
    grace_hours_after_due = Column(Integer, nullable=False, default=24)
    auto_invoice_mode = Column(String(10), nullable=False, default="draft")
    require_deposit_before_delivery = Column(Boolean, nullable=False, default=True)
    notify_roles_json = Column(JSON, nullable=False, default=list)
    allow_overbook = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="rental_settings")


class RentalAsset(Base):
    __tablename__ = "rental_assets"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    asset_code = Column(String(40), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(30), nullable=False, default="other")
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    quantity_available = Column(Integer, nullable=False, default=1)
    rate_daily = Column(Numeric(14, 2), nullable=True)
    rate_weekly = Column(Numeric(14, 2), nullable=True)
    rate_monthly = Column(Numeric(14, 2), nullable=True)
    gst_rate = Column(Numeric(5, 2), nullable=False, default=18)
    deposit_amount = Column(Numeric(14, 2), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    location_notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="rental_assets")
    product = relationship("Product")
    contract_lines = relationship("RentalContractLine", back_populates="rental_asset")


class RentalContract(Base):
    __tablename__ = "rental_contracts"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    contract_number = Column(String(40), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    rate_basis = Column(String(10), nullable=False, default="daily")
    rental_start = Column(DateTime(timezone=True), nullable=False)
    rental_end = Column(DateTime(timezone=True), nullable=False)
    actual_return_at = Column(DateTime(timezone=True), nullable=True)
    delivery_address = Column(Text, nullable=True)
    delivery_contact_name = Column(String(120), nullable=True)
    delivery_contact_phone = Column(String(30), nullable=True)
    delivery_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    delivery_completed_at = Column(DateTime(timezone=True), nullable=True)
    return_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    return_completed_at = Column(DateTime(timezone=True), nullable=True)
    subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    deposit_required = Column(Numeric(14, 2), nullable=False, default=0)
    deposit_received = Column(Numeric(14, 2), nullable=False, default=0)
    deposit_refunded = Column(Numeric(14, 2), nullable=False, default=0)
    deposit_deducted = Column(Numeric(14, 2), nullable=False, default=0)
    late_fee_total = Column(Numeric(14, 2), nullable=False, default=0)
    damage_charge_total = Column(Numeric(14, 2), nullable=False, default=0)
    grand_total = Column(Numeric(14, 2), nullable=False, default=0)
    notes = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="rental_contracts")
    contact = relationship("Contact", foreign_keys=[contact_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    lines = relationship("RentalContractLine", back_populates="contract", cascade="all, delete-orphan")
    deposits = relationship("RentalDeposit", back_populates="contract", cascade="all, delete-orphan")
    rental_invoices = relationship("RentalInvoice", back_populates="contract")


class RentalContractLine(Base):
    __tablename__ = "rental_contract_lines"

    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey("rental_contracts.id"), nullable=False, index=True)
    rental_asset_id = Column(Integer, ForeignKey("rental_assets.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    rate_basis = Column(String(10), nullable=False, default="daily")
    unit_rate = Column(Numeric(14, 2), nullable=False)
    line_days = Column(Integer, nullable=False, default=1)
    line_subtotal = Column(Numeric(14, 2), nullable=False, default=0)
    gst_rate = Column(Numeric(5, 2), nullable=False, default=18)
    line_total = Column(Numeric(14, 2), nullable=False, default=0)
    return_condition = Column(String(20), nullable=True)
    damage_notes = Column(Text, nullable=True)
    damage_charge = Column(Numeric(14, 2), nullable=True)

    contract = relationship("RentalContract", back_populates="lines")
    rental_asset = relationship("RentalAsset", back_populates="contract_lines")


class RentalDeposit(Base):
    __tablename__ = "rental_deposits"

    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey("rental_contracts.id"), nullable=False, index=True)
    type = Column(String(20), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    payment_method = Column(String(20), nullable=False, default="cash")
    reference = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False)

    contract = relationship("RentalContract", back_populates="deposits")
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])


class RentalInvoice(Base):
    __tablename__ = "rental_invoices"

    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey("rental_contracts.id"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False, index=True)
    invoice_type = Column(String(20), nullable=False, default="rental")
    generated_at = Column(DateTime(timezone=True), nullable=False)

    contract = relationship("RentalContract", back_populates="rental_invoices")
    invoice = relationship("Invoice")


class AiReportSettings(Base):
    __tablename__ = "ai_report_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    default_period = Column(String(20), nullable=False, default="30d")
    default_domains_json = Column(JSON, nullable=False, default=list)
    include_executive_brief = Column(Boolean, nullable=False, default=True)
    anomaly_thresholds_json = Column(JSON, nullable=False, default=dict)
    notify_roles_json = Column(JSON, nullable=False, default=list)
    generation_mode = Column(String(20), nullable=False, default="template")
    llm_provider = Column(String(40), nullable=True)
    redact_pii = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="ai_report_settings")


class AiInsightRun(Base):
    __tablename__ = "ai_insight_runs"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    run_number = Column(String(40), nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    domains_json = Column(JSON, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="pending", index=True)
    executive_headline = Column(Text, nullable=True)
    executive_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    generated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    company = relationship("Company", back_populates="ai_insight_runs")
    generated_by = relationship("User", foreign_keys=[generated_by_id])
    sections = relationship("AiInsightSection", back_populates="run", cascade="all, delete-orphan")


class AiInsightSection(Base):
    __tablename__ = "ai_insight_sections"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("ai_insight_runs.id"), nullable=False, index=True)
    domain = Column(String(20), nullable=False)
    headline = Column(Text, nullable=False)
    narrative = Column(Text, nullable=False)
    bullets_json = Column(JSON, nullable=False, default=list)
    watch_items_json = Column(JSON, nullable=False, default=list)
    metrics_json = Column(JSON, nullable=False, default=dict)
    sort_order = Column(Integer, nullable=False, default=0)

    run = relationship("AiInsightRun", back_populates="sections")


class WorkflowSettings(Base):
    __tablename__ = "workflow_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    max_active_workflows = Column(Integer, nullable=False, default=50)
    default_run_as_role = Column(String(40), nullable=False, default="Admin")
    rate_limit_per_hour = Column(Integer, nullable=False, default=500)
    notify_on_failure = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="workflow_settings")


class Workflow(Base):
    __tablename__ = "workflows"
    __table_args__ = (UniqueConstraint("company_id", "workflow_code", name="uq_workflows_company_code"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    workflow_code = Column(String(40), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    module = Column(String(20), nullable=False)
    trigger_type = Column(String(60), nullable=False, index=True)
    trigger_config_json = Column(JSON, nullable=False, default=dict)
    conditions_json = Column(JSON, nullable=False, default=list)
    actions_json = Column(JSON, nullable=False, default=list)
    priority = Column(Integer, nullable=False, default=100)
    stop_on_match = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    run_count = Column(Integer, nullable=False, default=0)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="workflows")
    created_by = relationship("User", foreign_keys=[created_by_id])
    updated_by = relationship("User", foreign_keys=[updated_by_id])
    runs = relationship("WorkflowRun", back_populates="workflow", cascade="all, delete-orphan")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (UniqueConstraint("company_id", "run_number", name="uq_workflow_runs_company_number"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    run_number = Column(String(40), nullable=False, index=True)
    trigger_type = Column(String(60), nullable=False)
    record_type = Column(String(40), nullable=False)
    record_id = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="skipped", index=True)
    conditions_result_json = Column(JSON, nullable=False, default=list)
    actions_result_json = Column(JSON, nullable=False, default=list)
    error_message = Column(Text, nullable=True)
    is_dry_run = Column(Boolean, nullable=False, default=False)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    company = relationship("Company", back_populates="workflow_runs")
    workflow = relationship("Workflow", back_populates="runs")


class MarketingSettings(Base):
    __tablename__ = "marketing_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    default_owner_role = Column(String(40), nullable=False, default="Sales")
    max_active_campaigns = Column(Integer, nullable=False, default=20)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="marketing_settings")


class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"
    __table_args__ = (UniqueConstraint("company_id", "campaign_code", name="uq_marketing_campaigns_company_code"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    campaign_code = Column(String(40), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    campaign_type = Column(String(20), nullable=False, default="drip")
    status = Column(String(20), nullable=False, default="draft", index=True)
    audience_type = Column(String(20), nullable=False, default="leads")
    audience_filter_json = Column(JSON, nullable=False, default=dict)
    steps_json = Column(JSON, nullable=False, default=list)
    enrolled_count = Column(Integer, nullable=False, default=0)
    sent_count = Column(Integer, nullable=False, default=0)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="marketing_campaigns")
    created_by = relationship("User", foreign_keys=[created_by_id])
    enrollments = relationship("MarketingEnrollment", back_populates="campaign", cascade="all, delete-orphan")


class MarketingEnrollment(Base):
    __tablename__ = "marketing_enrollments"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("marketing_campaigns.id"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    current_step = Column(Integer, nullable=False, default=0)
    next_send_at = Column(DateTime(timezone=True), nullable=True, index=True)
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    company = relationship("Company", back_populates="marketing_enrollments")
    campaign = relationship("MarketingCampaign", back_populates="enrollments")
    lead = relationship("Lead")
    contact = relationship("Contact")
    send_logs = relationship("MarketingSendLog", back_populates="enrollment", cascade="all, delete-orphan")


class MarketingSendLog(Base):
    __tablename__ = "marketing_send_logs"

    id = Column(Integer, primary_key=True)
    enrollment_id = Column(Integer, ForeignKey("marketing_enrollments.id"), nullable=False, index=True)
    step_index = Column(Integer, nullable=False, default=0)
    channel = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    subject = Column(String(300), nullable=True)
    body_preview = Column(Text, nullable=True)
    linked_record_type = Column(String(40), nullable=True)
    linked_record_id = Column(Integer, nullable=True)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

    enrollment = relationship("MarketingEnrollment", back_populates="send_logs")


class AiAssistantSettings(Base):
    __tablename__ = "ai_assistant_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    allowed_actions_json = Column(JSON, nullable=False, default=list)
    retain_sessions_days = Column(Integer, nullable=False, default=90)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="ai_assistant_settings")


class AiAssistantSession(Base):
    __tablename__ = "ai_assistant_sessions"
    __table_args__ = (UniqueConstraint("company_id", "session_code", name="uq_ai_assistant_sessions_company_code"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    session_code = Column(String(40), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False, default="New chat")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="ai_assistant_sessions")
    user = relationship("User")
    messages = relationship("AiAssistantMessage", back_populates="session", cascade="all, delete-orphan")


class AiAssistantMessage(Base):
    __tablename__ = "ai_assistant_messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("ai_assistant_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    intent = Column(String(40), nullable=True)
    citations_json = Column(JSON, nullable=False, default=list)
    actions_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("AiAssistantSession", back_populates="messages")


class MarketplaceSettings(Base):
    __tablename__ = "marketplace_settings"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, unique=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    public_api_enabled = Column(Boolean, nullable=False, default=False)
    max_api_keys = Column(Integer, nullable=False, default=10)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="marketplace_settings")


class MarketplaceIntegration(Base):
    __tablename__ = "marketplace_integrations"
    __table_args__ = (UniqueConstraint("company_id", "integration_key", name="uq_marketplace_integrations_company_key"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    integration_key = Column(String(60), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    category = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="available", index=True)
    config_json = Column(JSON, nullable=False, default=dict)
    installed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="marketplace_integrations")
    webhooks = relationship("MarketplaceWebhook", back_populates="integration", cascade="all, delete-orphan")


class MarketplaceApiKey(Base):
    __tablename__ = "marketplace_api_keys"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    key_prefix = Column(String(16), nullable=False, index=True)
    key_hash = Column(String(128), nullable=False)
    scopes_json = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="marketplace_api_keys")
    created_by = relationship("User", foreign_keys=[created_by_id])


class MarketplaceWebhook(Base):
    __tablename__ = "marketplace_webhooks"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    integration_id = Column(Integer, ForeignKey("marketplace_integrations.id"), nullable=True, index=True)
    name = Column(String(120), nullable=False)
    endpoint_url = Column(String(500), nullable=False)
    events_json = Column(JSON, nullable=False, default=list)
    signing_secret = Column(String(80), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="marketplace_webhooks")
    integration = relationship("MarketplaceIntegration", back_populates="webhooks")

