from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
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
    follow_up_reminders = relationship("FollowUpReminder", back_populates="company")
    system_settings = relationship("SystemSetting", back_populates="company", uselist=False)


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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    company = relationship("Company", back_populates="products")


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

    id = Column(Integer, primary_key=True)
    entity_name = Column(String(50), nullable=False, unique=True, index=True)
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
    support_email = Column(String(255), nullable=False, default="support@blackpapers.in")
    maintenance_mode = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


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
    """In-app notifications — global (user_id=NULL) or user-specific."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(20), nullable=False, default="INFO")
    is_read = Column(Boolean, nullable=False, default=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
