from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    phone: str | None = Field(default=None, max_length=30)
    invite_token: str | None = Field(default=None, max_length=128)


class RegisterCompanyRequest(BaseModel):
    owner_name: str = Field(min_length=2, max_length=120)
    owner_email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    company_legal_name: str = Field(min_length=2, max_length=200)
    company_display_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)


class RegisterCompanyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    message: str
    role: str
    name: str
    email: str
    company_id: int
    company_name: str
    permissions: list[str] = []


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    message: str
    role: str
    name: str
    email: str
    company_id: int | None = None
    permissions: list[str] = []


class PermissionResponse(BaseModel):
    code: str
    name: str
    module: str

    class Config:
        from_attributes = True


class RoleMatrixResponse(BaseModel):
    roles: list[str]
    permissions: list[PermissionResponse]
    matrix: dict[str, list[str]]


class UserProfileResponse(BaseModel):
    id: int
    company_id: int | None
    employee_id: str | None
    name: str
    email: str
    phone: str | None
    role: str
    status: str
    designation: str | None
    department: str | None
    created_at: datetime | None
    updated_at: datetime | None
    last_login_at: datetime | None

    class Config:
        from_attributes = True

# Password reset schemas
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ForgotPasswordResponse(BaseModel):
    success: bool = True
    message: str = "If the account exists, a reset link has been sent."

class VerifyResetTokenResponse(BaseModel):
    valid: bool

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=128)

class ResetPasswordResponse(BaseModel):
    success: bool = True
    message: str = "Password updated successfully"

    id: int
    company_id: int | None
    employee_id: str | None
    name: str
    email: str
    phone: str | None
    role: str
    status: str
    designation: str | None
    department: str | None
    created_at: datetime | None
    updated_at: datetime | None
    last_login_at: datetime | None

    class Config:
        from_attributes = True


class CompanyResponse(BaseModel):
    id: int
    legal_name: str
    display_name: str
    email: str | None
    phone: str | None
    website: str | None
    description: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    pincode: str | None
    country: str
    gstin: str | None
    pan: str | None
    currency: str
    financial_year_start_month: int
    timezone: str
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


class CompanyCreateRequest(BaseModel):
    legal_name: str = Field(min_length=2, max_length=200)
    display_name: str = Field(min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    website: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)
    country: str = Field(default="India", max_length=100)
    gstin: str | None = Field(default=None, max_length=15)
    pan: str | None = Field(default=None, max_length=10)
    currency: str = Field(default="INR", max_length=3)
    financial_year_start_month: int = Field(default=4, ge=1, le=12)
    timezone: str = Field(default="Asia/Kolkata", max_length=50)


class CompanyUpdateRequest(BaseModel):
    legal_name: str = Field(min_length=2, max_length=200)
    display_name: str = Field(min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    website: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)
    country: str = Field(default="India", max_length=100)
    gstin: str | None = Field(default=None, max_length=15)
    pan: str | None = Field(default=None, max_length=10)
    currency: str = Field(default="INR", max_length=3)
    financial_year_start_month: int = Field(default=4, ge=1, le=12)
    timezone: str = Field(default="Asia/Kolkata", max_length=50)


class ProfileUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


class AdminCreateUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: str
    phone: str | None = Field(default=None, max_length=30)
    employee_id: str | None = Field(default=None, max_length=20)
    designation: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    status: str = "active"


class AdminUpdateUserRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    role: str | None = None
    status: str | None = None
    designation: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    employee_id: str | None = Field(default=None, max_length=20)


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


class StaffAssigneeResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str


class ContactBaseFields(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    organization_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    alt_phone: str | None = Field(default=None, max_length=30)
    contact_type: str
    status: str = "active"
    designation: str | None = Field(default=None, max_length=120)
    website: str | None = Field(default=None, max_length=255)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=10)
    country: str = Field(default="India", max_length=100)
    gstin: str | None = Field(default=None, max_length=15)
    pan: str | None = Field(default=None, max_length=10)
    assigned_to_id: int | None = None


class ContactCreateRequest(ContactBaseFields):
    pass


class ContactUpdateRequest(ContactBaseFields):
    pass


class ContactResponse(BaseModel):
    id: int
    company_id: int
    user_id: int | None
    name: str
    organization_name: str | None
    email: str | None
    phone: str | None
    alt_phone: str | None
    contact_type: str
    status: str
    designation: str | None
    website: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    pincode: str | None
    country: str
    gstin: str | None
    pan: str | None
    assigned_to_id: int | None
    assigned_to_name: str | None = None
    created_by_id: int | None
    created_by_name: str | None = None
    created_at: datetime | None
    updated_at: datetime | None


class ContactListResponse(BaseModel):
    items: list[ContactResponse]
    total: int
    page: int
    limit: int


class ContactNoteCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class ContactNoteResponse(BaseModel):
    id: int
    contact_id: int
    body: str
    author_id: int
    author_name: str | None
    created_at: datetime | None


class ContactActivityCreateRequest(BaseModel):
    activity_type: str
    subject: str | None = Field(default=None, max_length=200)
    body: str = Field(min_length=1, max_length=5000)


class ContactActivityResponse(BaseModel):
    id: int
    contact_id: int
    activity_type: str
    subject: str | None
    body: str
    author_id: int
    author_name: str | None
    created_at: datetime | None


class ProductBaseFields(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    service_code: str | None = Field(default=None, max_length=40)
    entity_type: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=120)
    sub_category: str | None = Field(default=None, max_length=120)
    unit: str = Field(default="Service", max_length=30)
    govt_charges: float | None = None
    our_fees: float | None = None
    gst_amount: float | None = None
    total_price: float | None = None
    market_price: float | None = None
    offer_price: float | None = None
    last_price: float | None = None
    gst_rate: float = Field(default=18, ge=0, le=100)
    filing_timeline: str | None = Field(default=None, max_length=80)
    completion_timeline: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=8000)
    status: str = "active"
    is_manufactured: bool = False
    is_raw_material: bool = False
    default_bom_id: int | None = None


class ProductCreateRequest(ProductBaseFields):
    pass


class ProductUpdateRequest(ProductBaseFields):
    pass


class ProductResponse(BaseModel):
    id: int
    company_id: int
    service_code: str | None
    name: str
    entity_type: str | None
    category: str | None
    sub_category: str | None
    unit: str
    govt_charges: float | None
    our_fees: float | None
    gst_amount: float | None
    total_price: float | None
    market_price: float | None
    offer_price: float | None
    last_price: float | None
    gst_rate: float
    filing_timeline: str | None
    completion_timeline: str | None
    description: str | None
    status: str
    is_manufactured: bool = False
    is_raw_material: bool = False
    default_bom_id: int | None = None
    created_at: datetime | None
    updated_at: datetime | None


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    limit: int


class ContactStatsResponse(BaseModel):
    total: int
    active: int
    inactive: int
    active_percent: float
    inactive_percent: float


class ActivityLogResponse(BaseModel):
    id: int
    user_id: int | None
    email: str | None
    action: str
    details: str | None
    ip_address: str | None
    created_at: datetime | None

    class Config:
        from_attributes = True


class ActivityLogListResponse(BaseModel):
    items: list[ActivityLogResponse]
    total: int
    page: int
    limit: int


class SystemSettingResponse(BaseModel):
    id: int
    company_id: int
    quote_prefix: str
    invoice_prefix: str
    quote_date_format: str
    invoice_date_format: str
    default_lead_source: str
    logo_filename: str | None

    class Config:
        from_attributes = True


class SystemSettingUpdateRequest(BaseModel):
    quote_prefix: str = Field(min_length=1, max_length=30)
    invoice_prefix: str = Field(min_length=1, max_length=30)
    quote_date_format: str = Field(min_length=1, max_length=20)
    invoice_date_format: str = Field(min_length=1, max_length=20)
    default_lead_source: str = Field(min_length=1, max_length=50)


class LeadBaseFields(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    organization_name: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    requirement: str | None = Field(default=None, max_length=200)
    exact_requirement: str | None = Field(default=None, max_length=5000)
    source: str = Field(default="Omnichannel", max_length=50)
    status: str = Field(default="open", max_length=30)
    notes: str | None = Field(default=None, max_length=5000)
    assigned_to_id: int | None = None
    registered_at: datetime | None = None


class LeadCreateRequest(LeadBaseFields):
    pass


class LeadUpdateRequest(LeadBaseFields):
    pass


class LeadResponse(BaseModel):
    id: int
    company_id: int
    contact_id: int | None
    name: str
    phone: str | None
    email: str | None
    organization_name: str | None
    city: str | None
    requirement: str | None
    exact_requirement: str | None
    source: str
    status: str
    csv_status: str | None
    notes: str | None
    assigned_to_id: int | None
    assigned_to_name: str | None = None
    created_by_id: int | None
    created_by_name: str | None = None
    registered_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    limit: int


class LeadStatsResponse(BaseModel):
    total: int
    open: int
    hot: int
    follow_up: int
    cold: int
    lost: int
    qualified: int
    converted: int


class LeadDuplicateMatch(BaseModel):
    id: int
    name: str
    phone: str | None
    organization_name: str | None = None


class LeadDuplicateCheckResponse(BaseModel):
    phone: str
    has_duplicates: bool
    leads: list[LeadDuplicateMatch]
    contacts: list[LeadDuplicateMatch]


class LeadConvertResponse(BaseModel):
    lead: LeadResponse
    contact_id: int
    message: str


class DealBaseFields(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    stage: str = Field(default="new", max_length=30)
    expected_value: float | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", max_length=3)
    expected_close_date: datetime | None = None
    notes: str | None = Field(default=None, max_length=5000)
    lost_reason: str | None = Field(default=None, max_length=255)
    lead_id: int | None = None
    contact_id: int | None = None
    product_id: int | None = None
    assigned_to_id: int | None = None


class DealCreateRequest(DealBaseFields):
    pass


class DealUpdateRequest(DealBaseFields):
    pass


class DealStageUpdateRequest(BaseModel):
    stage: str = Field(min_length=2, max_length=30)
    lost_reason: str | None = Field(default=None, max_length=255)


class DealResponse(BaseModel):
    id: int
    company_id: int
    title: str
    stage: str
    expected_value: float | None
    currency: str
    expected_close_date: datetime | None
    notes: str | None
    lost_reason: str | None
    closed_at: datetime | None
    lead_id: int | None
    lead_name: str | None = None
    contact_id: int | None
    contact_name: str | None = None
    product_id: int | None
    product_name: str | None = None
    assigned_to_id: int | None
    assigned_to_name: str | None = None
    created_by_id: int | None
    created_by_name: str | None = None
    created_at: datetime | None
    updated_at: datetime | None


class DealListResponse(BaseModel):
    items: list[DealResponse]
    total: int
    page: int
    limit: int


class DealStatsResponse(BaseModel):
    total: int
    new: int
    contacted: int
    meeting: int
    proposal: int
    won: int
    lost: int
    pipeline_value: float
    won_value: float


class DealPipelineColumn(BaseModel):
    stage: str
    label: str
    count: int
    total_value: float
    deals: list[DealResponse]


class DealPipelineResponse(BaseModel):
    columns: list[DealPipelineColumn]
    closed: list[DealResponse]


# --- Quotations ---


class QuotationLineItemFields(BaseModel):
    product_id: int | None = None
    sort_order: int = 0
    section: str | None = Field(default=None, max_length=100)
    item_name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    quantity: float = Field(default=1, ge=0)
    unit: str = Field(default="Service", max_length=30)
    unit_price: float = Field(default=0, ge=0)
    discount_percent: float = Field(default=0, ge=0, le=100)
    discount_amount: float = Field(default=0, ge=0)
    tax_rate: float = Field(default=18, ge=0, le=100)


class QuotationLineItemResponse(QuotationLineItemFields):
    id: int
    line_subtotal: float
    line_total: float
    product_name: str | None = None


class QuotationBaseFields(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    currency: str = Field(default="INR", max_length=3)
    quote_date: datetime | None = None
    valid_until: datetime | None = None
    deal_id: int | None = None
    lead_id: int | None = None
    contact_id: int | None = None
    assigned_to_id: int | None = None
    client_name: str | None = Field(default=None, max_length=120)
    client_email: str | None = Field(default=None, max_length=255)
    client_org: str | None = Field(default=None, max_length=200)
    attention_to: str | None = Field(default=None, max_length=120)
    billing_address: str | None = Field(default=None, max_length=5000)
    shipping_address: str | None = Field(default=None, max_length=5000)
    header_discount_amount: float = Field(default=0, ge=0)
    header_discount_percent: float = Field(default=0, ge=0, le=100)
    scope_notes: str | None = Field(default=None, max_length=5000)
    deliverables: str | None = Field(default=None, max_length=5000)
    timeline_notes: str | None = Field(default=None, max_length=5000)
    payment_terms: str | None = Field(default=None, max_length=5000)
    validity_clause: str | None = Field(default=None, max_length=5000)
    cancellation_clause: str | None = Field(default=None, max_length=5000)
    legal_footer: str | None = Field(default=None, max_length=5000)
    internal_notes: str | None = Field(default=None, max_length=5000)


class QuotationCreateRequest(QuotationBaseFields):
    line_items: list[QuotationLineItemFields] = Field(default_factory=list)


class QuotationUpdateRequest(QuotationCreateRequest):
    pass


class QuotationResponse(BaseModel):
    id: int
    company_id: int
    quote_number: str
    title: str
    status: str
    version: int
    currency: str
    quote_date: datetime | None
    valid_until: datetime | None
    deal_id: int | None
    deal_title: str | None = None
    lead_id: int | None
    lead_name: str | None = None
    contact_id: int | None
    contact_name: str | None = None
    assigned_to_id: int | None
    assigned_to_name: str | None = None
    created_by_id: int | None
    created_by_name: str | None = None
    approved_by_id: int | None
    approved_by_name: str | None = None
    parent_quote_id: int | None
    root_quote_id: int | None
    client_name: str | None
    client_email: str | None
    client_org: str | None
    attention_to: str | None
    billing_address: str | None
    shipping_address: str | None
    subtotal: float
    line_discount_total: float
    header_discount_amount: float
    header_discount_percent: float
    total_tax: float
    grand_total: float
    scope_notes: str | None
    deliverables: str | None
    timeline_notes: str | None
    payment_terms: str | None
    validity_clause: str | None
    cancellation_clause: str | None
    legal_footer: str | None
    internal_notes: str | None
    approval_comments: str | None
    requires_approval: bool
    share_token: str | None = None
    share_url: str | None = None
    sent_at: datetime | None
    viewed_at: datetime | None
    accepted_at: datetime | None
    rejected_at: datetime | None
    approved_at: datetime | None
    cancelled_at: datetime | None
    client_rejection_reason: str | None
    line_items: list[QuotationLineItemResponse] = Field(default_factory=list)
    created_at: datetime | None
    updated_at: datetime | None


class QuotationListResponse(BaseModel):
    items: list[QuotationResponse]
    total: int
    page: int
    limit: int


class QuotationStatsResponse(BaseModel):
    total: int
    draft: int
    pending_approval: int
    approved: int
    sent: int
    viewed: int
    negotiation: int
    accepted: int
    rejected: int
    expired: int
    cancelled: int
    total_value: float
    accepted_value: float
    expiring_soon: int


class QuotationDefaultsResponse(BaseModel):
    scope_notes: str
    project_overview: str
    deliverables: str
    timeline_notes: str
    payment_terms: str
    investment_commission: str
    investment_includes: str
    payment_installments: str
    bank_instructions: str
    bank_payment_intro: str
    how_to_get_started: str
    why_choose_items: str
    validity_clause: str
    legal_footer: str
    documents_checklist: str
    prepared_by_label: str
    document_subtitle: str


class QuotationStatusOption(BaseModel):
    value: str
    label: str


class QuotationApprovalRequest(BaseModel):
    comments: str | None = Field(default=None, max_length=2000)


class QuotationRejectRequest(BaseModel):
    comments: str | None = Field(default=None, max_length=2000)


class QuotationSendRequest(BaseModel):
    recipient_email: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=2000)


class QuotationClientActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)
    message: str | None = Field(default=None, max_length=2000)


class QuotationVersionSummary(BaseModel):
    id: int
    quote_number: str
    version: int
    status: str
    grand_total: float
    created_at: datetime | None
    updated_at: datetime | None


class QuotationCompanyBranding(BaseModel):
    display_name: str
    legal_name: str
    email: str | None
    phone: str | None
    website: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    pincode: str | None
    country: str
    gstin: str | None
    pan: str | None
    logo_filename: str | None
    tagline: str | None = None
    cin: str | None = None
    invoice_document_title: str | None = None
    signatory_name: str | None = None


class QuotationPublicResponse(BaseModel):
    quote: QuotationResponse
    company: QuotationCompanyBranding
    is_expired: bool
    can_accept: bool


# --- Sales Orders ---


class SalesOrderMilestoneFields(BaseModel):
    sort_order: int = 0
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: str = Field(default="pending", max_length=20)
    due_date: datetime | None = None
    owner_id: int | None = None


class SalesOrderMilestoneResponse(SalesOrderMilestoneFields):
    id: int
    completed_at: datetime | None = None
    owner_name: str | None = None


class SalesOrderLineItemFields(BaseModel):
    product_id: int | None = None
    quotation_line_item_id: int | None = None
    sort_order: int = 0
    section: str | None = Field(default=None, max_length=100)
    item_name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    quantity: float = Field(default=1, ge=0)
    unit: str = Field(default="Service", max_length=30)
    unit_price: float = Field(default=0, ge=0)
    discount_percent: float = Field(default=0, ge=0, le=100)
    discount_amount: float = Field(default=0, ge=0)
    tax_rate: float = Field(default=18, ge=0, le=100)


class SalesOrderLineItemResponse(SalesOrderLineItemFields):
    id: int
    line_subtotal: float
    line_total: float
    fulfilled_quantity: float
    fulfillment_status: str
    product_name: str | None = None


class SalesOrderBaseFields(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    order_type: str = Field(default="mixed", max_length=30)
    currency: str = Field(default="INR", max_length=3)
    order_date: datetime | None = None
    due_date: datetime | None = None
    internal_target_date: datetime | None = None
    quotation_id: int | None = None
    deal_id: int | None = None
    lead_id: int | None = None
    contact_id: int | None = None
    assigned_to_id: int | None = None
    client_name: str | None = Field(default=None, max_length=120)
    client_email: str | None = Field(default=None, max_length=255)
    client_phone: str | None = Field(default=None, max_length=30)
    client_org: str | None = Field(default=None, max_length=200)
    attention_to: str | None = Field(default=None, max_length=120)
    billing_address: str | None = Field(default=None, max_length=5000)
    delivery_address: str | None = Field(default=None, max_length=5000)
    header_discount_amount: float = Field(default=0, ge=0)
    header_discount_percent: float = Field(default=0, ge=0, le=100)
    billing_notes: str | None = Field(default=None, max_length=5000)
    payment_milestone_notes: str | None = Field(default=None, max_length=5000)
    delivery_instructions: str | None = Field(default=None, max_length=5000)
    internal_notes: str | None = Field(default=None, max_length=5000)


class SalesOrderCreateRequest(SalesOrderBaseFields):
    line_items: list[SalesOrderLineItemFields] = Field(default_factory=list)
    milestones: list[SalesOrderMilestoneFields] = Field(default_factory=list)


class SalesOrderUpdateRequest(SalesOrderCreateRequest):
    pass


class SalesOrderResponse(BaseModel):
    id: int
    company_id: int
    order_number: str
    title: str
    status: str
    version: int
    order_type: str
    source_type: str
    currency: str
    order_date: datetime | None
    confirmation_date: datetime | None
    due_date: datetime | None
    internal_target_date: datetime | None
    quotation_id: int | None
    quotation_number: str | None = None
    deal_id: int | None
    deal_title: str | None = None
    lead_id: int | None
    lead_name: str | None = None
    contact_id: int | None
    contact_name: str | None = None
    assigned_to_id: int | None
    assigned_to_name: str | None = None
    created_by_id: int | None
    created_by_name: str | None = None
    confirmed_by_id: int | None
    confirmed_by_name: str | None = None
    parent_order_id: int | None
    root_order_id: int | None
    client_name: str | None
    client_email: str | None
    client_phone: str | None
    client_org: str | None
    attention_to: str | None
    billing_address: str | None
    delivery_address: str | None
    subtotal: float
    line_discount_total: float
    header_discount_amount: float
    header_discount_percent: float
    total_tax: float
    grand_total: float
    billing_notes: str | None
    payment_milestone_notes: str | None
    delivery_instructions: str | None
    internal_notes: str | None
    hold_reason: str | None
    cancellation_reason: str | None
    completion_notes: str | None
    fulfillment_progress: int
    billing_status: str
    preparation_status: str
    share_token: str | None = None
    share_url: str | None = None
    sent_for_confirmation_at: datetime | None
    confirmed_at: datetime | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    hold_at: datetime | None
    hold_resume_date: datetime | None
    last_status_change_at: datetime | None
    line_items: list[SalesOrderLineItemResponse] = Field(default_factory=list)
    milestones: list[SalesOrderMilestoneResponse] = Field(default_factory=list)
    created_at: datetime | None
    updated_at: datetime | None


class SalesOrderListResponse(BaseModel):
    items: list[SalesOrderResponse]
    total: int
    page: int
    limit: int


class SalesOrderStatsResponse(BaseModel):
    total: int
    draft: int
    awaiting_confirmation: int
    confirmed: int
    in_preparation: int
    in_execution: int
    partially_delivered: int
    delivered: int
    in_billing: int
    on_hold: int
    completed: int
    cancelled: int
    closed: int
    total_value: float
    confirmed_value: float
    due_soon: int
    overdue: int


class SalesOrderStatusOption(BaseModel):
    value: str
    label: str


class SalesOrderReasonRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    resume_date: datetime | None = None


class SalesOrderProgressRequest(BaseModel):
    fulfillment_progress: int = Field(ge=0, le=100)
    notes: str | None = Field(default=None, max_length=2000)


class SalesOrderSendConfirmationRequest(BaseModel):
    recipient_email: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=2000)


class SalesOrderClientActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)
    message: str | None = Field(default=None, max_length=2000)


class SalesOrderVersionSummary(BaseModel):
    id: int
    order_number: str
    version: int
    status: str
    grand_total: float
    created_at: datetime | None
    updated_at: datetime | None


class SalesOrderPublicResponse(BaseModel):
    order: SalesOrderResponse
    company: QuotationCompanyBranding
    can_confirm: bool


# --- Invoices ---


class InvoiceLineItemFields(BaseModel):
    product_id: int | None = None
    sales_order_line_item_id: int | None = None
    sort_order: int = 0
    section: str | None = Field(default=None, max_length=100)
    item_name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    quantity: float = Field(default=1, ge=0)
    unit: str = Field(default="Service", max_length=30)
    unit_price: float = Field(default=0, ge=0)
    discount_percent: float = Field(default=0, ge=0, le=100)
    discount_amount: float = Field(default=0, ge=0)
    tax_rate: float = Field(default=18, ge=0, le=100)


class InvoiceLineItemResponse(InvoiceLineItemFields):
    id: int
    line_subtotal: float
    line_total: float
    product_name: str | None = None


class InvoicePaymentFields(BaseModel):
    amount: float = Field(gt=0)
    payment_date: datetime
    payment_method: str = Field(default="bank_transfer", max_length=30)
    reference: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=2000)


class InvoicePaymentResponse(InvoicePaymentFields):
    id: int
    recorded_by_id: int | None
    recorded_by_name: str | None = None
    created_at: datetime | None


class InvoiceBaseFields(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    invoice_type: str = Field(default="standard", max_length=30)
    currency: str = Field(default="INR", max_length=3)
    issue_date: datetime | None = None
    due_date: datetime | None = None
    sales_order_id: int | None = None
    quotation_id: int | None = None
    deal_id: int | None = None
    contact_id: int | None = None
    assigned_to_id: int | None = None
    client_name: str | None = Field(default=None, max_length=120)
    client_email: str | None = Field(default=None, max_length=255)
    client_phone: str | None = Field(default=None, max_length=30)
    client_org: str | None = Field(default=None, max_length=200)
    client_gstin: str | None = Field(default=None, max_length=15)
    attention_to: str | None = Field(default=None, max_length=120)
    billing_address: str | None = Field(default=None, max_length=5000)
    header_discount_amount: float = Field(default=0, ge=0)
    header_discount_percent: float = Field(default=0, ge=0, le=100)
    round_off: float = Field(default=0)
    payment_terms: str | None = Field(default=None, max_length=5000)
    bank_instructions: str | None = Field(default=None, max_length=5000)
    billing_notes: str | None = Field(default=None, max_length=5000)
    internal_notes: str | None = Field(default=None, max_length=5000)


class InvoiceCreateRequest(InvoiceBaseFields):
    line_items: list[InvoiceLineItemFields] = Field(default_factory=list)


class InvoiceUpdateRequest(InvoiceCreateRequest):
    pass


class InvoiceResponse(BaseModel):
    id: int
    company_id: int
    invoice_number: str | None
    title: str
    status: str
    version: int
    invoice_type: str
    source_type: str
    currency: str
    issue_date: datetime | None
    due_date: datetime | None
    sales_order_id: int | None
    sales_order_number: str | None = None
    quotation_id: int | None
    quotation_number: str | None = None
    deal_id: int | None
    deal_title: str | None = None
    contact_id: int | None
    contact_name: str | None = None
    assigned_to_id: int | None
    assigned_to_name: str | None = None
    assigned_to_email: str | None = None
    created_by_id: int | None
    created_by_name: str | None = None
    reviewed_by_id: int | None
    reviewed_by_name: str | None = None
    issued_by_id: int | None
    issued_by_name: str | None = None
    parent_invoice_id: int | None
    root_invoice_id: int | None
    client_name: str | None
    client_email: str | None
    client_phone: str | None
    client_org: str | None
    client_gstin: str | None
    attention_to: str | None
    billing_address: str | None
    subtotal: float
    line_discount_total: float
    header_discount_amount: float
    header_discount_percent: float
    total_tax: float
    round_off: float
    grand_total: float
    amount_paid: float
    outstanding_amount: float
    write_off_amount: float
    payment_terms: str | None
    bank_instructions: str | None
    billing_notes: str | None
    internal_notes: str | None
    review_comments: str | None
    cancellation_reason: str | None
    adjustment_reason: str | None
    requires_review: bool
    share_token: str | None = None
    share_url: str | None = None
    reviewed_at: datetime | None
    approved_at: datetime | None
    issued_at: datetime | None
    sent_at: datetime | None
    viewed_at: datetime | None
    closed_at: datetime | None
    cancelled_at: datetime | None
    last_status_change_at: datetime | None
    last_payment_at: datetime | None
    line_items: list[InvoiceLineItemResponse] = Field(default_factory=list)
    payments: list[InvoicePaymentResponse] = Field(default_factory=list)
    created_at: datetime | None
    updated_at: datetime | None


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    limit: int


class InvoiceStatsResponse(BaseModel):
    total: int
    draft: int
    awaiting_review: int
    issued: int
    sent: int
    partially_paid: int
    paid: int
    overdue: int
    total_billed: float
    total_collected: float
    total_outstanding: float


class InvoiceStatusOption(BaseModel):
    value: str
    label: str


class InvoiceReviewRequest(BaseModel):
    comments: str | None = Field(default=None, max_length=2000)


class InvoiceReasonRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class InvoiceSendRequest(BaseModel):
    recipient_email: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=2000)


class InvoicePublicResponse(BaseModel):
    invoice: InvoiceResponse
    company: QuotationCompanyBranding
    is_overdue: bool


class InvoiceDefaultsResponse(BaseModel):
    payment_terms: str
    bank_instructions: str
    billing_notes: str
    document_title: str
    company_display_name: str
    tagline: str
    cin: str
    signatory_name: str
    org_type: str
    client_nature: str
    terms_label: str


# Client Notes


class ClientNoteCreateRequest(BaseModel):
    contact_id: int | None = None
    lead_id: int | None = None
    deal_id: int | None = None
    quotation_id: int | None = None
    sales_order_id: int | None = None
    invoice_id: int | None = None
    note_type: str = "call"
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    visibility_scope: str = "team"
    tags: str | None = Field(default=None, max_length=500)
    structured_data: str | None = Field(default=None, max_length=5000)
    is_pinned: bool = False
    is_sensitive: bool = False
    follow_up_required: bool = False
    follow_up_due_date: datetime | None = None
    follow_up_priority: str = "normal"
    assigned_to_id: int | None = None


class ClientNoteUpdateRequest(BaseModel):
    note_type: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=10000)
    visibility_scope: str | None = None
    tags: str | None = Field(default=None, max_length=500)
    structured_data: str | None = Field(default=None, max_length=5000)
    is_pinned: bool | None = None
    is_sensitive: bool | None = None
    is_resolved: bool | None = None
    follow_up_required: bool | None = None
    follow_up_due_date: datetime | None = None
    follow_up_priority: str | None = None
    assigned_to_id: int | None = None


class ClientNoteRevisionResponse(BaseModel):
    id: int
    editor_id: int
    editor_name: str | None = None
    note_type: str
    title: str
    body: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientNoteResponse(BaseModel):
    id: int
    contact_id: int | None = None
    contact_name: str | None = None
    lead_id: int | None = None
    deal_id: int | None = None
    deal_title: str | None = None
    quotation_id: int | None = None
    quotation_number: str | None = None
    sales_order_id: int | None = None
    sales_order_number: str | None = None
    invoice_id: int | None = None
    invoice_number: str | None = None
    author_id: int
    author_name: str | None = None
    assigned_to_id: int | None = None
    assigned_to_name: str | None = None
    last_edited_by_id: int | None = None
    last_edited_by_name: str | None = None
    note_type: str
    title: str
    body: str
    visibility_scope: str
    tags: str | None = None
    structured_data: str | None = None
    is_pinned: bool
    pin_order: int
    is_sensitive: bool
    is_resolved: bool
    follow_up_required: bool
    follow_up_due_date: datetime | None = None
    follow_up_priority: str
    follow_up_completed_at: datetime | None = None
    follow_up_overdue: bool = False
    revision_count: int
    created_at: datetime
    updated_at: datetime
    revisions: list[ClientNoteRevisionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ClientNoteListResponse(BaseModel):
    items: list[ClientNoteResponse]
    total: int
    page: int
    limit: int


class ClientNoteStatsResponse(BaseModel):
    total: int
    pinned: int
    follow_up_pending: int
    follow_up_overdue: int
    recent_7_days: int


class ClientNoteTypeOption(BaseModel):
    value: str
    label: str


# Sales Reports


class SalesReportPeriodOption(BaseModel):
    value: str
    label: str


class SalesReportKpiCard(BaseModel):
    key: str
    label: str
    value: float | int | str
    unit: str | None = None
    delta_percent: float | None = None
    delta_label: str | None = None


class SalesReportTrendPoint(BaseModel):
    label: str
    value: float


class SalesReportRankRow(BaseModel):
    id: int | str | None = None
    name: str
    count: int = 0
    value: float = 0
    rate: float | None = None
    link: str | None = None
    badge: str | None = None


class SalesReportConversionFunnel(BaseModel):
    stage: str
    label: str
    count: int
    value: float
    rate_from_previous: float | None = None


class SalesReportPendingDeal(BaseModel):
    id: int
    title: str
    stage: str
    stage_label: str
    expected_value: float
    currency: str
    owner_name: str | None
    expected_close_date: datetime | None
    updated_at: datetime | None
    days_stale: int
    is_overdue: bool
    is_stale: bool
    badge: str | None = None


class SalesReportPipelineStage(BaseModel):
    stage: str
    label: str
    count: int
    value: float
    avg_age_days: float


class SalesReportOverviewResponse(BaseModel):
    period_label: str
    date_from: datetime
    date_to: datetime
    kpis: list[SalesReportKpiCard]
    revenue_trend: list[SalesReportTrendPoint]
    top_sources: list[SalesReportRankRow]
    top_performers: list[SalesReportRankRow]
    top_pending_deals: list[SalesReportPendingDeal]


class SalesReportConversionResponse(BaseModel):
    period_label: str
    funnel: list[SalesReportConversionFunnel]
    lead_to_deal_rate: float
    deal_to_win_rate: float
    quote_to_order_rate: float
    order_to_invoice_rate: float
    by_source: list[SalesReportRankRow]
    by_owner: list[SalesReportRankRow]
    previous_lead_to_deal_rate: float | None = None
    previous_deal_to_win_rate: float | None = None


class SalesReportRevenueResponse(BaseModel):
    period_label: str
    booked_revenue: float
    collected_revenue: float
    outstanding_revenue: float
    pipeline_forecast: float
    avg_deal_size: float
    trend: list[SalesReportTrendPoint]
    by_owner: list[SalesReportRankRow]
    by_customer: list[SalesReportRankRow]
    by_source: list[SalesReportRankRow]
    previous_booked_revenue: float | None = None


class SalesReportLeadSourceResponse(BaseModel):
    period_label: str
    sources: list[SalesReportRankRow]
    conversion_chart: list[SalesReportTrendPoint]


class SalesReportExecutiveResponse(BaseModel):
    period_label: str
    executives: list[SalesReportRankRow]
    detail: list[dict]


class SalesReportPendingDealsResponse(BaseModel):
    period_label: str
    total_count: int
    total_value: float
    overdue_count: int
    stale_count: int
    aging_buckets: list[SalesReportTrendPoint]
    deals: list[SalesReportPendingDeal]


class SalesReportPipelineHealthResponse(BaseModel):
    period_label: str
    stages: list[SalesReportPipelineStage]
    total_pipeline_value: float
    concentration_top_deal_percent: float
    health_score: int
    health_label: str



class FollowUpReminderCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    reminder_type: str = Field(default="call", max_length=30)
    priority: str = Field(default="normal", max_length=20)
    due_at: datetime
    notes: str | None = Field(default=None, max_length=2000)
    lead_id: int | None = None
    deal_id: int | None = None
    contact_id: int | None = None
    assigned_to_id: int | None = None


class FollowUpReminderUpdateRequest(FollowUpReminderCreateRequest):
    status: str = Field(default="pending", max_length=20)


class FollowUpReminderResponse(BaseModel):
    id: int
    company_id: int
    lead_id: int | None
    deal_id: int | None
    contact_id: int | None
    entity_label: str | None = None
    entity_path: str | None = None
    reminder_type: str
    reminder_type_label: str
    title: str
    notes: str | None
    status: str
    priority: str
    due_at: datetime
    completed_at: datetime | None
    assigned_to_id: int | None
    assigned_to_name: str | None = None
    created_by_id: int | None
    created_by_name: str | None = None
    is_overdue: bool = False
    is_due_today: bool = False
    created_at: datetime | None
    updated_at: datetime | None


class FollowUpReminderListResponse(BaseModel):
    items: list[FollowUpReminderResponse]
    total: int
    page: int
    limit: int


class FollowUpReminderStatsResponse(BaseModel):
    total_pending: int
    due_today: int
    overdue: int
    upcoming: int
    note_follow_ups_pending: int


class UnifiedFollowUpItem(BaseModel):
    source: str
    id: int
    title: str
    subtitle: str | None = None
    entity_path: str | None = None
    reminder_type: str
    priority: str
    due_at: datetime | None
    assigned_to_name: str | None = None
    is_overdue: bool = False
    is_due_today: bool = False


class UnifiedFollowUpQueueResponse(BaseModel):
    items: list[UnifiedFollowUpItem]
    total: int


class PaymentAgingBucket(BaseModel):
    label: str
    count: int
    amount: float


class PaymentSummaryResponse(BaseModel):
    total_received: float
    total_outstanding: float
    invoice_count_outstanding: int
    invoice_count_overdue: int
    payment_count: int
    aging_buckets: list[PaymentAgingBucket]


class PaymentRecordItem(BaseModel):
    id: int
    invoice_id: int
    invoice_number: str | None
    invoice_title: str
    client_name: str | None
    client_org: str | None
    contact_id: int | None = None
    amount: float
    payment_date: datetime
    payment_method: str
    reference: str | None
    note: str | None
    recorded_by_name: str | None = None


class PaymentListResponse(BaseModel):
    items: list[PaymentRecordItem]
    total: int
    page: int
    limit: int


class InvoiceOutstandingItem(BaseModel):
    id: int
    invoice_number: str | None
    title: str
    client_name: str | None
    client_org: str | None
    contact_id: int | None = None
    status: str
    grand_total: float
    amount_paid: float
    outstanding_amount: float
    issue_date: datetime | None
    due_date: datetime | None
    is_overdue: bool
    age_days: int | None = None


class InvoiceOutstandingListResponse(BaseModel):
    items: list[InvoiceOutstandingItem]
    total: int
    page: int
    limit: int


class DashboardKpiResponse(BaseModel):
    pipeline_value: float = 0
    open_deals: int = 0
    pending_quotes: int = 0
    overdue_invoices: int = 0
    total_outstanding: float = 0
    follow_ups_due_today: int = 0
    follow_ups_overdue: int = 0
    total_leads: int = 0
    open_leads: int = 0
    open_invoices: int = 0
    total_invoices: int = 0
    revenue_collected: float = 0
    revenue_billed: float = 0
    pending_payments: float = 0
    tasks_due: int = 0
    tasks_overdue: int = 0


class NotificationResponse(BaseModel):
    id: int
    category: str
    title: str
    message: str
    link_path: str | None = None
    is_read: bool
    created_at: datetime | None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int


class NotificationSendRequest(BaseModel):
    target_role: str = Field(
        description="Staff role, User (portal accounts), or all_staff for every staff role",
        min_length=1,
        max_length=30,
    )
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="announcement", max_length=30)
    link_path: str | None = Field(default=None, max_length=255)


class NotificationSendResponse(BaseModel):
    recipient_count: int
    target_role: str
    message: str


class NotificationRolesResponse(BaseModel):
    roles: list[str]


# Expenses


class ExpenseCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=50)
    vendor_name: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    tax_amount: float = Field(default=0, ge=0)
    currency: str = Field(default="INR", max_length=3)
    expense_date: datetime
    reimbursement_due_date: datetime | None = None
    payment_mode: str = Field(min_length=1, max_length=30)
    notes: str | None = Field(default=None, max_length=5000)
    receipt_reference: str | None = Field(default=None, max_length=100)
    cost_center: str | None = Field(default=None, max_length=100)
    deal_id: int | None = None
    contact_id: int | None = None


class ExpenseUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=50)
    vendor_name: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    tax_amount: float = Field(default=0, ge=0)
    currency: str = Field(default="INR", max_length=3)
    expense_date: datetime
    reimbursement_due_date: datetime | None = None
    payment_mode: str = Field(min_length=1, max_length=30)
    notes: str | None = Field(default=None, max_length=5000)
    receipt_reference: str | None = Field(default=None, max_length=100)
    cost_center: str | None = Field(default=None, max_length=100)
    deal_id: int | None = None
    contact_id: int | None = None


class ExpenseReviewRequest(BaseModel):
    comments: str | None = Field(default=None, max_length=2000)


class ExpenseRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    comments: str | None = Field(default=None, max_length=2000)


class ExpenseAttachmentResponse(BaseModel):
    id: int
    original_filename: str
    content_type: str | None = None
    file_size: int
    uploaded_by_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExpenseResponse(BaseModel):
    id: int
    expense_number: str | None = None
    title: str
    category: str
    vendor_name: str
    amount: float
    tax_amount: float
    total_amount: float
    currency: str
    expense_date: datetime
    reimbursement_due_date: datetime | None = None
    payment_mode: str
    status: str
    notes: str | None = None
    receipt_reference: str | None = None
    rejection_reason: str | None = None
    reviewer_comments: str | None = None
    cost_center: str | None = None
    deal_id: int | None = None
    deal_title: str | None = None
    contact_id: int | None = None
    contact_name: str | None = None
    submitted_by_id: int
    submitted_by_name: str | None = None
    reviewed_by_name: str | None = None
    approved_by_name: str | None = None
    paid_by_name: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    attachments: list[ExpenseAttachmentResponse] = []
    has_proof: bool = False
    requires_proof: bool = False

    model_config = ConfigDict(from_attributes=True)


class ExpenseListResponse(BaseModel):
    items: list[ExpenseResponse]
    total: int
    page: int
    limit: int


class ExpenseStatsResponse(BaseModel):
    total_spend_month: float
    pending_approval_amount: float
    approved_unpaid_amount: float
    rejected_count: int
    top_category: str | None = None
    top_vendor: str | None = None
    by_category: list[dict]
    by_vendor: list[dict]


class ExpenseStatusOption(BaseModel):
    value: str
    label: str


class ExpenseCategoryOption(BaseModel):
    value: str
    label: str


class ExpensePaymentModeOption(BaseModel):
    value: str
    label: str


# Purchase Orders


class PurchaseOrderLineItemFields(BaseModel):
    product_id: int | None = None
    sort_order: int = 0
    description: str = Field(min_length=1, max_length=255)
    sku: str | None = Field(default=None, max_length=80)
    unit: str = Field(default="Unit", max_length=30)
    ordered_quantity: float = Field(default=1, gt=0)
    unit_price: float = Field(default=0, ge=0)
    tax_rate: float = Field(default=18, ge=0, le=100)


class PurchaseOrderLineItemResponse(PurchaseOrderLineItemFields):
    id: int
    received_quantity: float
    billed_quantity: float
    pending_receipt_quantity: float
    pending_billing_quantity: float
    line_subtotal: float
    line_total: float
    billed_amount: float
    product_name: str | None = None


class PurchaseOrderCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    vendor_name: str = Field(min_length=1, max_length=200)
    vendor_contact: str | None = Field(default=None, max_length=120)
    vendor_email: str | None = Field(default=None, max_length=255)
    vendor_phone: str | None = Field(default=None, max_length=30)
    currency: str = Field(default="INR", max_length=3)
    payment_terms: str | None = Field(default=None, max_length=40)
    po_date: datetime
    expected_delivery_date: datetime | None = None
    delivery_location: str | None = Field(default=None, max_length=5000)
    notes: str | None = Field(default=None, max_length=5000)
    internal_reference: str | None = Field(default=None, max_length=100)
    vendor_quote_reference: str | None = Field(default=None, max_length=100)
    cost_center: str | None = Field(default=None, max_length=100)
    deal_id: int | None = None
    contact_id: int | None = None
    line_items: list[PurchaseOrderLineItemFields] = Field(default_factory=list)


class PurchaseOrderUpdateRequest(PurchaseOrderCreateRequest):
    pass


class PurchaseOrderReceiptResponse(BaseModel):
    id: int
    line_item_id: int
    line_description: str | None = None
    quantity: float
    receipt_date: datetime
    grn_reference: str | None = None
    notes: str | None = None
    recorded_by_name: str | None = None
    created_at: datetime


class PurchaseOrderBillingResponse(BaseModel):
    id: int
    line_item_id: int
    line_description: str | None = None
    quantity: float
    amount: float
    bill_reference: str | None = None
    notes: str | None = None
    recorded_by_name: str | None = None
    created_at: datetime


class PurchaseOrderAttachmentResponse(BaseModel):
    id: int
    original_filename: str
    content_type: str | None = None
    file_size: int
    uploaded_by_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderResponse(BaseModel):
    id: int
    po_number: str | None = None
    title: str
    vendor_name: str
    vendor_contact: str | None = None
    vendor_email: str | None = None
    vendor_phone: str | None = None
    status: str
    currency: str
    payment_terms: str | None = None
    po_date: datetime
    expected_delivery_date: datetime | None = None
    delivery_location: str | None = None
    notes: str | None = None
    internal_reference: str | None = None
    vendor_quote_reference: str | None = None
    cost_center: str | None = None
    rejection_reason: str | None = None
    reviewer_comments: str | None = None
    subtotal: float
    total_tax: float
    grand_total: float
    received_value: float
    billed_value: float
    pending_receipt_value: float
    pending_billing_value: float
    received_percent: float
    billed_percent: float
    deal_id: int | None = None
    deal_title: str | None = None
    contact_id: int | None = None
    contact_name: str | None = None
    created_by_id: int
    created_by_name: str | None = None
    reviewed_by_name: str | None = None
    approved_by_name: str | None = None
    sent_by_name: str | None = None
    closed_by_name: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    sent_at: datetime | None = None
    closed_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    line_items: list[PurchaseOrderLineItemResponse] = Field(default_factory=list)
    receipts: list[PurchaseOrderReceiptResponse] = Field(default_factory=list)
    billings: list[PurchaseOrderBillingResponse] = Field(default_factory=list)
    attachments: list[PurchaseOrderAttachmentResponse] = Field(default_factory=list)


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderResponse]
    total: int
    page: int
    limit: int


class PurchaseOrderStatsResponse(BaseModel):
    open_po_value: float
    pending_approval_amount: float
    pending_receipt_value: float
    pending_billing_value: float
    overdue_delivery_count: int
    top_vendor: str | None = None
    by_vendor: list[dict]


class PurchaseOrderStatusOption(BaseModel):
    value: str
    label: str


class PurchaseOrderPaymentTermOption(BaseModel):
    value: str
    label: str


class PurchaseOrderReviewRequest(BaseModel):
    comments: str | None = Field(default=None, max_length=2000)


class PurchaseOrderRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    comments: str | None = Field(default=None, max_length=2000)


class PurchaseOrderRecordReceiptRequest(BaseModel):
    line_item_id: int
    quantity: float = Field(gt=0)
    receipt_date: datetime
    grn_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


class PurchaseOrderRecordBillingRequest(BaseModel):
    line_item_id: int
    quantity: float = Field(gt=0)
    amount: float = Field(gt=0)
    bill_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


# Inventory


class InventoryEnableTrackingRequest(BaseModel):
    reorder_level: float | None = Field(default=None, ge=0)
    unit_valuation: float = Field(default=0, ge=0)


class InventoryOpeningStockRequest(BaseModel):
    quantity: float = Field(gt=0)
    unit_valuation: float = Field(ge=0)
    movement_date: datetime
    reference_number: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


class InventoryRecordMovementRequest(BaseModel):
    movement_type: str = Field(min_length=1, max_length=20)
    quantity: float = Field(gt=0)
    unit_valuation: float = Field(ge=0)
    movement_date: datetime
    adjustment_direction: str | None = Field(default=None, max_length=3)
    reason: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    reference_number: str | None = Field(default=None, max_length=100)


class InventorySettingsUpdateRequest(BaseModel):
    reorder_level: float | None = Field(default=None, ge=0)
    unit_valuation: float | None = Field(default=None, ge=0)


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    product_name: str | None = None
    product_sku: str | None = None
    movement_type: str
    direction: str
    quantity: float
    unit_value: float
    total_value: float
    quantity_before: float
    quantity_after: float
    movement_date: datetime
    reference_type: str | None = None
    reference_id: int | None = None
    reference_number: str | None = None
    source_module: str
    reason: str | None = None
    notes: str | None = None
    negative_override: bool
    recorded_by_name: str | None = None
    created_at: datetime


class InventoryProductResponse(BaseModel):
    id: int
    service_code: str | None = None
    name: str
    category: str | None = None
    unit: str
    status: str
    inventory_tracked: bool
    on_hand_quantity: float
    unit_valuation: float
    stock_value: float
    reorder_level: float | None = None
    opening_recorded: bool
    inventory_status: str
    last_movement_at: datetime | None = None
    total_purchased: float = 0
    total_sold: float = 0
    total_damaged: float = 0
    net_adjustments: float = 0
    movements: list[StockMovementResponse] = Field(default_factory=list)


class InventoryListResponse(BaseModel):
    items: list[InventoryProductResponse]
    total: int
    page: int
    limit: int


class StockMovementListResponse(BaseModel):
    items: list[StockMovementResponse]
    total: int
    page: int
    limit: int


class InventoryStatsResponse(BaseModel):
    total_stock_value: float
    tracked_products: int
    low_stock_count: int
    out_of_stock_count: int
    movements_this_month: int
    top_product_name: str | None = None
    top_product_value: float = 0
    by_category: list[dict]
    recent_movements: list[StockMovementResponse]


class InventoryMovementTypeOption(BaseModel):
    value: str
    label: str


class InventoryStatusOption(BaseModel):
    value: str
    label: str


class InventoryReasonOption(BaseModel):
    value: str
    label: str


# Warehouses


class WarehouseLocationCreateRequest(BaseModel):
    location_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    location_type: str = Field(min_length=1, max_length=30)
    parent_id: int | None = None
    status: str = Field(default="active", max_length=20)
    address: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    is_default_receiving: bool = False
    is_default_dispatch: bool = False


class WarehouseLocationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    is_default_receiving: bool | None = None
    is_default_dispatch: bool | None = None


class WarehouseLocationResponse(BaseModel):
    id: int
    location_code: str
    name: str
    location_type: str
    parent_id: int | None = None
    parent_name: str | None = None
    status: str
    address: str | None = None
    notes: str | None = None
    is_default_receiving: bool
    is_default_dispatch: bool
    branch_name: str | None = None
    warehouse_name: str | None = None
    path: str | None = None
    sku_count: int = 0
    total_on_hand: float = 0
    total_stock_value: float = 0
    low_stock_count: int = 0
    child_count: int = 0
    created_at: datetime
    updated_at: datetime


class WarehouseLocationListResponse(BaseModel):
    items: list[WarehouseLocationResponse]
    total: int
    summary: dict


class WarehouseLocationDetailResponse(WarehouseLocationResponse):
    children: list[WarehouseLocationResponse] = Field(default_factory=list)
    recent_movements: list["LocationStockMovementResponse"] = Field(default_factory=list)
    stock: list["LocationStockResponse"] = Field(default_factory=list)


class LocationStockResponse(BaseModel):
    id: int
    product_id: int
    product_name: str | None = None
    product_sku: str | None = None
    product_category: str | None = None
    location_id: int
    location_name: str | None = None
    location_code: str | None = None
    location_type: str | None = None
    branch_name: str | None = None
    warehouse_name: str | None = None
    location_path: str | None = None
    on_hand_quantity: float
    available_quantity: float
    unit_valuation: float
    stock_value: float
    reorder_level: float | None = None
    stock_status: str
    last_movement_at: datetime | None = None


class LocationStockListResponse(BaseModel):
    items: list[LocationStockResponse]
    total: int
    page: int
    limit: int


class LocationStockMovementResponse(BaseModel):
    id: int
    product_id: int
    product_name: str | None = None
    product_sku: str | None = None
    location_id: int
    location_name: str | None = None
    location_path: str | None = None
    movement_type: str
    direction: str
    quantity: float
    unit_value: float
    total_value: float
    quantity_before: float
    quantity_after: float
    movement_date: datetime
    transfer_reference: str | None = None
    reference_number: str | None = None
    linked_stock_movement_id: int | None = None
    reason: str | None = None
    notes: str | None = None
    negative_override: bool
    recorded_by_name: str | None = None
    created_at: datetime


class LocationStockMovementListResponse(BaseModel):
    items: list[LocationStockMovementResponse]
    total: int
    page: int
    limit: int


class WarehouseRecordMovementRequest(BaseModel):
    product_id: int
    location_id: int
    movement_type: str = Field(min_length=1, max_length=20)
    quantity: float = Field(gt=0)
    unit_valuation: float = Field(ge=0)
    movement_date: datetime
    adjustment_direction: str | None = Field(default=None, max_length=3)
    reason: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    reference_number: str | None = Field(default=None, max_length=100)


class WarehouseTransferRequest(BaseModel):
    product_id: int
    source_location_id: int
    destination_location_id: int
    quantity: float = Field(gt=0)
    movement_date: datetime
    notes: str | None = Field(default=None, max_length=2000)
    reference_number: str | None = Field(default=None, max_length=100)


class WarehouseTransferResponse(BaseModel):
    transfer_reference: str
    transfer_out: LocationStockMovementResponse
    transfer_in: LocationStockMovementResponse


class WarehouseTransferListResponse(BaseModel):
    items: list[WarehouseTransferResponse]
    total: int
    page: int
    limit: int


class WarehouseStatsResponse(BaseModel):
    total_stock_value: float
    active_warehouses: int
    total_locations: int
    locations_with_stock: int
    low_stock_locations: int
    stock_by_branch: list[dict]
    stock_by_warehouse: list[dict]
    recent_transfers: list[WarehouseTransferResponse]
    recent_movements: list[LocationStockMovementResponse]


class WarehouseOptionResponse(BaseModel):
    value: str
    label: str

# --- System Configuration ---


class SystemConfigResponse(BaseModel):
    id: int
    company_name: str
    default_currency: str
    date_format: str
    timezone: str
    support_email: str
    maintenance_mode: bool
    default_gst_rate: float = 18
    tax_regime: str = "GST"
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


class SystemConfigUpdate(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    default_currency: str = Field(min_length=1, max_length=3)
    date_format: str = Field(min_length=1, max_length=20)
    timezone: str = Field(min_length=1, max_length=80)
    support_email: EmailStr
    maintenance_mode: bool = False
    default_gst_rate: float = Field(default=18, ge=0, le=100)
    tax_regime: str = Field(default="GST", max_length=30)


# --- Numbering Configuration ---


class NumberingConfigBaseFields(BaseModel):
    entity_name: str = Field(min_length=2, max_length=50)
    prefix: str = Field(min_length=1, max_length=20)
    starting_number: int = Field(default=1, ge=1)
    current_number: int = Field(default=0, ge=0)
    suffix: str | None = Field(default=None, max_length=20)
    is_active: bool = True


class NumberingConfigCreateRequest(NumberingConfigBaseFields):
    pass


class NumberingConfigUpdateRequest(BaseModel):
    prefix: str | None = Field(default=None, min_length=1, max_length=20)
    starting_number: int | None = Field(default=None, ge=1)
    current_number: int | None = Field(default=None, ge=0)
    suffix: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class NumberingConfigResponse(BaseModel):
    id: int
    entity_name: str
    prefix: str
    starting_number: int
    current_number: int
    suffix: str | None
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


# --- Email Templates ---


class EmailTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    subject: str = Field(min_length=2, max_length=255)
    body: str = Field(min_length=1)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


class EmailTemplateUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    subject: str = Field(min_length=2, max_length=255)
    body: str = Field(min_length=1)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True


class EmailTemplateResponse(BaseModel):
    id: int
    name: str
    subject: str
    body: str
    description: str | None
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None

    class Config:
        from_attributes = True


class UploadedFileResponse(BaseModel):
    id: int
    company_id: int | None
    original_filename: str
    stored_filename: str
    file_type: str
    file_size: int
    uploaded_by: StaffAssigneeResponse
    category: str | None = None
    category_label: str | None = None
    related_module: str | None
    related_module_label: str | None = None
    related_record_id: int | None
    created_at: datetime
    file_url: str

    class Config:
        from_attributes = True


class FileOption(BaseModel):
    value: str
    label: str


class FileMetaResponse(BaseModel):
    categories: list[FileOption]
    record_modules: list[FileOption]
    allowed_extensions: list[str]
    max_file_size_mb: int


class FileStatsResponse(BaseModel):
    total_count: int
    total_bytes: int
    by_category: list[dict]


class FileListResponse(BaseModel):
    items: list[UploadedFileResponse]
    total: int
    page: int
    limit: int


# Vendor Bills


class VendorBillLineItemFields(BaseModel):
    purchase_order_line_item_id: int | None = None
    sort_order: int = 0
    description: str = Field(min_length=1, max_length=500)
    quantity: float = Field(gt=0)
    unit: str = Field(default="Unit", max_length=30)
    unit_price: float = Field(ge=0)
    tax_rate: float = Field(default=18, ge=0)


class VendorBillLineItemResponse(BaseModel):
    id: int
    purchase_order_line_item_id: int | None = None
    sort_order: int
    description: str
    unit: str | None = None
    quantity: float
    unit_price: float
    tax_rate: float
    line_subtotal: float
    line_total: float
    po_ordered_quantity: float | None = None
    po_received_quantity: float | None = None
    po_billed_quantity: float | None = None
    po_pending_billing_quantity: float | None = None

    model_config = ConfigDict(from_attributes=True)


class VendorBillPaymentFields(BaseModel):
    amount: float = Field(gt=0)
    payment_date: datetime
    payment_method: str = Field(default="bank_transfer", max_length=30)
    reference: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=2000)


class VendorBillPaymentResponse(BaseModel):
    id: int
    amount: float
    payment_date: datetime
    payment_method: str
    reference: str | None = None
    note: str | None = None
    recorded_by_id: int
    recorded_by_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VendorBillCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    supplier_invoice_number: str | None = Field(default=None, max_length=100)
    currency: str = Field(default="INR", max_length=3)
    bill_date: datetime
    due_date: datetime | None = None
    payment_terms: str | None = Field(default=None, max_length=40)
    purchase_order_id: int | None = None
    vendor_name: str = Field(min_length=1, max_length=200)
    vendor_email: str | None = Field(default=None, max_length=255)
    vendor_phone: str | None = Field(default=None, max_length=30)
    vendor_gstin: str | None = Field(default=None, max_length=20)
    vendor_address: str | None = None
    deal_id: int | None = None
    contact_id: int | None = None
    expense_id: int | None = None
    round_off: float = Field(default=0)
    internal_notes: str | None = Field(default=None, max_length=5000)
    line_items: list[VendorBillLineItemFields] = Field(min_length=1)


class VendorBillUpdateRequest(VendorBillCreateRequest):
    pass


class VendorBillReviewRequest(BaseModel):
    comments: str | None = Field(default=None, max_length=2000)


class VendorBillRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    comments: str | None = Field(default=None, max_length=2000)


class VendorBillCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class VendorBillAttachmentResponse(BaseModel):
    id: int
    original_filename: str
    content_type: str | None = None
    file_size: int
    uploaded_by_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VendorBillResponse(BaseModel):
    id: int
    bill_number: str | None = None
    supplier_invoice_number: str | None = None
    title: str
    status: str
    currency: str
    bill_date: datetime
    due_date: datetime | None = None
    payment_terms: str | None = None
    purchase_order_id: int | None = None
    po_number: str | None = None
    vendor_name: str
    vendor_email: str | None = None
    vendor_phone: str | None = None
    vendor_gstin: str | None = None
    vendor_address: str | None = None
    deal_id: int | None = None
    deal_title: str | None = None
    contact_id: int | None = None
    contact_name: str | None = None
    expense_id: int | None = None
    subtotal: float
    total_tax: float
    round_off: float
    grand_total: float
    amount_paid: float
    outstanding_amount: float
    internal_notes: str | None = None
    approval_notes: str | None = None
    rejection_reason: str | None = None
    cancellation_reason: str | None = None
    created_by_id: int
    created_by_name: str | None = None
    reviewed_by_name: str | None = None
    approved_by_name: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    cancelled_at: datetime | None = None
    closed_at: datetime | None = None
    last_payment_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    line_items: list[VendorBillLineItemResponse] = Field(default_factory=list)
    payments: list[VendorBillPaymentResponse] = Field(default_factory=list)
    attachments: list[VendorBillAttachmentResponse] = Field(default_factory=list)
    is_overdue: bool = False

    model_config = ConfigDict(from_attributes=True)


class VendorBillListResponse(BaseModel):
    items: list[VendorBillResponse]
    total: int
    page: int
    limit: int


class VendorBillStatusOption(BaseModel):
    value: str
    label: str


class VendorBillPaymentMethodOption(BaseModel):
    value: str
    label: str


class VendorBillStatsResponse(BaseModel):
    total_outstanding: float
    overdue_amount: float
    due_this_week_amount: float
    pending_approval_count: int
    pending_approval_amount: float
    paid_this_month: float
    by_vendor: list[dict] = Field(default_factory=list)
    aging_buckets: list[dict] = Field(default_factory=list)


# Stock In / Stock Out


class StockMovementReasonOption(BaseModel):
    value: str
    label: str


class StockMovementRecordRequest(BaseModel):
    product_id: int
    quantity: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=100)
    movement_date: datetime
    reference_number: str | None = Field(default=None, max_length=100)
    reference_type: str | None = Field(default=None, max_length=30)
    reference_id: int | None = None
    source_module: str | None = Field(default="stock_movements", max_length=30)
    unit_valuation: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class StockMovementExtendedResponse(StockMovementResponse):
    movement_number: str
    reason_label: str | None = None


class StockMovementExtendedListResponse(BaseModel):
    items: list[StockMovementExtendedResponse]
    total: int
    page: int
    limit: int


class StockMovementStatsResponse(BaseModel):
    stock_in_today: float
    stock_out_today: float
    net_change_today: float
    movement_count_today: int
    top_out_product_name: str | None = None
    top_out_product_qty: float = 0
    recent_movements: list[StockMovementExtendedResponse] = Field(default_factory=list)


class TaxReportPeriodOption(BaseModel):
    key: str
    label: str


class TaxReportCompanyContext(BaseModel):
    company_name: str
    gstin: str | None = None
    gstin_configured: bool = False


class TaxReportRateRow(BaseModel):
    rate: float
    rate_label: str
    taxable_value: float
    tax_amount: float
    document_count: int


class TaxReportVendorSummaryRow(BaseModel):
    vendor_name: str
    bill_count: int
    taxable_value: float
    input_tax: float


class TaxReportDataQuality(BaseModel):
    outward_missing_gstin: int
    inward_missing_gstin: int
    excluded_outward_drafts: int
    excluded_inward_drafts: int


class TaxReportOutwardRegisterRow(BaseModel):
    id: int
    invoice_number: str | None = None
    issue_date: datetime | None = None
    customer_name: str | None = None
    customer_gstin: str | None = None
    taxable_value: float
    tax_amount: float
    grand_total: float
    status: str
    status_label: str
    invoice_type: str
    is_credit_note: bool = False
    tax_rate_summary: str
    missing_gstin: bool = False
    parent_invoice_id: int | None = None


class TaxReportInwardRegisterRow(BaseModel):
    id: int
    bill_number: str | None = None
    supplier_invoice_number: str | None = None
    bill_date: datetime
    vendor_name: str
    vendor_gstin: str | None = None
    taxable_value: float
    tax_amount: float
    grand_total: float
    status: str
    status_label: str
    purchase_order_id: int | None = None
    po_number: str | None = None
    tax_rate_summary: str
    missing_gstin: bool = False


class TaxReportOverviewResponse(BaseModel):
    period: str
    period_label: str
    date_from: datetime
    date_to: datetime
    company: TaxReportCompanyContext
    outward_taxable_value: float
    outward_tax_collected: float
    outward_document_count: int
    inward_taxable_value: float
    inward_input_tax: float
    inward_document_count: int
    missing_gstin_count: int
    data_quality: TaxReportDataQuality


class TaxReportSalesResponse(BaseModel):
    period: str
    period_label: str
    date_from: datetime
    date_to: datetime
    company: TaxReportCompanyContext
    taxable_value: float
    tax_collected: float
    gross_total: float
    document_count: int
    b2b_count: int
    b2c_count: int
    rate_breakdown: list[TaxReportRateRow] = Field(default_factory=list)
    register: list[TaxReportOutwardRegisterRow] = Field(default_factory=list)
    register_total: int = 0
    register_page: int = 1
    register_per_page: int = 50
    data_quality: TaxReportDataQuality


class TaxReportPurchaseResponse(BaseModel):
    period: str
    period_label: str
    date_from: datetime
    date_to: datetime
    company: TaxReportCompanyContext
    taxable_value: float
    input_tax: float
    gross_total: float
    document_count: int
    vendors_with_gstin: int
    rate_breakdown: list[TaxReportRateRow] = Field(default_factory=list)
    vendor_summary: list[TaxReportVendorSummaryRow] = Field(default_factory=list)
    register: list[TaxReportInwardRegisterRow] = Field(default_factory=list)
    register_total: int = 0
    register_page: int = 1
    register_per_page: int = 50
    data_quality: TaxReportDataQuality


class TaxReportSummaryResponse(BaseModel):
    period: str
    period_label: str
    date_from: datetime
    date_to: datetime
    company: TaxReportCompanyContext
    outward_taxable_value: float
    outward_tax_collected: float
    outward_document_count: int
    inward_taxable_value: float
    inward_input_tax: float
    inward_document_count: int
    informational_net_tax: float
    rate_breakdown: list[TaxReportRateRow] = Field(default_factory=list)
    data_quality: TaxReportDataQuality


class TaxReportExportLogRequest(BaseModel):
    report_type: str = Field(min_length=1, max_length=30)
    period: str = Field(min_length=1, max_length=30)
    period_label: str | None = None
    row_count: int = 0


class CustomerLedgerPeriodOption(BaseModel):
    key: str
    label: str


class CustomerLedgerIndexKpis(BaseModel):
    total_outstanding: float
    overdue_outstanding: float
    customers_with_balance: int
    collected_this_month: float
    unassigned_outstanding: float = 0


class CustomerLedgerIndexRow(BaseModel):
    contact_id: int
    name: str
    organization_name: str | None = None
    gstin: str | None = None
    email: str | None = None
    phone: str | None = None
    currency: str = "INR"
    total_billed: float
    total_collected: float
    outstanding: float
    overdue_outstanding: float
    last_activity_date: datetime | None = None
    open_invoice_count: int


class CustomerLedgerIndexResponse(BaseModel):
    kpis: CustomerLedgerIndexKpis
    items: list[CustomerLedgerIndexRow]
    total: int
    page: int
    per_page: int


class CustomerLedgerContactHeader(BaseModel):
    contact_id: int
    name: str
    organization_name: str | None = None
    gstin: str | None = None
    pan: str | None = None
    email: str | None = None
    phone: str | None = None
    contact_type: str
    billing_address: str | None = None
    currency: str = "INR"
    is_vendor: bool = False
    missing_gstin: bool = False


class CustomerLedgerEntryRow(BaseModel):
    entry_key: str
    entry_type: str
    entry_type_label: str
    effective_date: datetime
    reference: str | None = None
    description: str
    debit_amount: float
    credit_amount: float
    running_balance: float
    invoice_id: int | None = None
    payment_id: int | None = None
    status: str | None = None
    status_label: str | None = None
    is_overdue: bool = False
    excluded_from_balance: bool = False


class CustomerLedgerOpenInvoiceRow(BaseModel):
    id: int
    invoice_number: str | None = None
    title: str
    invoice_type: str
    issue_date: datetime | None = None
    due_date: datetime | None = None
    grand_total: float
    amount_paid: float
    outstanding_amount: float
    status: str
    status_label: str
    is_overdue: bool = False


class CustomerLedgerStatementSummary(BaseModel):
    opening_balance: float
    period_debits: float
    period_credits: float
    closing_balance: float
    current_outstanding: float
    overdue_outstanding: float


class CustomerLedgerStatementResponse(BaseModel):
    period: str
    period_label: str
    date_from: datetime | None = None
    date_to: datetime | None = None
    contact: CustomerLedgerContactHeader
    summary: CustomerLedgerStatementSummary
    entries: list[CustomerLedgerEntryRow]
    entries_total: int
    entries_page: int
    entries_per_page: int
    open_invoices: list[CustomerLedgerOpenInvoiceRow]
    aging_buckets: list[PaymentAgingBucket]


class CustomerLedgerContactSummaryResponse(BaseModel):
    contact_id: int
    outstanding: float
    overdue_outstanding: float
    open_invoice_count: int
    last_payment_date: datetime | None = None
    total_collected: float


class CustomerLedgerUnassignedGroup(BaseModel):
    group_key: str
    client_name: str | None = None
    client_org: str | None = None
    invoice_count: int
    total_billed: float
    outstanding: float


class CustomerLedgerUnassignedInvoiceRow(BaseModel):
    id: int
    invoice_number: str | None = None
    title: str
    client_name: str | None = None
    client_org: str | None = None
    issue_date: datetime | None = None
    due_date: datetime | None = None
    grand_total: float
    outstanding_amount: float
    status: str
    status_label: str
    is_overdue: bool = False


class CustomerLedgerUnassignedResponse(BaseModel):
    total_outstanding: float
    invoice_count: int
    groups: list[CustomerLedgerUnassignedGroup]
    invoices: list[CustomerLedgerUnassignedInvoiceRow]
    total: int
    page: int
    per_page: int


class CustomerLedgerExportLogRequest(BaseModel):
    contact_id: int
    period: str = Field(min_length=1, max_length=30)
    period_label: str | None = None
    row_count: int = 0


class VendorLedgerPeriodOption(BaseModel):
    key: str
    label: str


class VendorLedgerIndexKpis(BaseModel):
    total_outstanding: float
    overdue_outstanding: float
    vendors_with_balance: int
    paid_this_month: float
    unassigned_outstanding: float = 0


class VendorLedgerIndexRow(BaseModel):
    contact_id: int
    name: str
    organization_name: str | None = None
    gstin: str | None = None
    email: str | None = None
    phone: str | None = None
    currency: str = "INR"
    total_billed: float
    total_paid: float
    outstanding: float
    overdue_outstanding: float
    last_activity_date: datetime | None = None
    open_bill_count: int


class VendorLedgerIndexResponse(BaseModel):
    kpis: VendorLedgerIndexKpis
    items: list[VendorLedgerIndexRow]
    total: int
    page: int
    per_page: int


class VendorLedgerContactHeader(BaseModel):
    contact_id: int
    name: str
    organization_name: str | None = None
    gstin: str | None = None
    pan: str | None = None
    email: str | None = None
    phone: str | None = None
    contact_type: str
    billing_address: str | None = None
    currency: str = "INR"
    is_customer: bool = False
    missing_gstin: bool = False


class VendorLedgerEntryRow(BaseModel):
    entry_key: str
    entry_type: str
    entry_type_label: str
    effective_date: datetime
    reference: str | None = None
    description: str
    debit_amount: float
    credit_amount: float
    running_balance: float
    bill_id: int | None = None
    payment_id: int | None = None
    po_number: str | None = None
    status: str | None = None
    status_label: str | None = None
    is_overdue: bool = False


class VendorLedgerOpenBillRow(BaseModel):
    id: int
    bill_number: str | None = None
    supplier_invoice_number: str | None = None
    title: str
    bill_date: datetime
    due_date: datetime | None = None
    grand_total: float
    amount_paid: float
    outstanding_amount: float
    status: str
    status_label: str
    purchase_order_id: int | None = None
    po_number: str | None = None
    is_overdue: bool = False


class VendorLedgerStatementSummary(BaseModel):
    opening_balance: float
    period_debits: float
    period_credits: float
    closing_balance: float
    current_outstanding: float
    overdue_outstanding: float


class VendorLedgerStatementResponse(BaseModel):
    period: str
    period_label: str
    date_from: datetime | None = None
    date_to: datetime | None = None
    contact: VendorLedgerContactHeader
    summary: VendorLedgerStatementSummary
    entries: list[VendorLedgerEntryRow]
    entries_total: int
    entries_page: int
    entries_per_page: int
    open_bills: list[VendorLedgerOpenBillRow]
    aging_buckets: list[PaymentAgingBucket]


class VendorLedgerContactSummaryResponse(BaseModel):
    contact_id: int
    outstanding: float
    overdue_outstanding: float
    open_bill_count: int
    last_payment_date: datetime | None = None
    total_paid: float


class VendorLedgerUnassignedGroup(BaseModel):
    group_key: str
    vendor_name: str
    bill_count: int
    total_billed: float
    outstanding: float


class VendorLedgerUnassignedBillRow(BaseModel):
    id: int
    bill_number: str | None = None
    supplier_invoice_number: str | None = None
    title: str
    vendor_name: str
    bill_date: datetime
    due_date: datetime | None = None
    grand_total: float
    outstanding_amount: float
    status: str
    status_label: str
    is_overdue: bool = False


class VendorLedgerUnassignedResponse(BaseModel):
    total_outstanding: float
    bill_count: int
    groups: list[VendorLedgerUnassignedGroup]
    bills: list[VendorLedgerUnassignedBillRow]
    total: int
    page: int
    per_page: int


class VendorLedgerExportLogRequest(BaseModel):
    contact_id: int
    period: str = Field(min_length=1, max_length=30)
    period_label: str | None = None
    row_count: int = 0


class PLReportPeriodOption(BaseModel):
    key: str
    label: str


class PLReportCompanyContext(BaseModel):
    company_name: str
    currency: str = "INR"


class PLReportComparisonMetric(BaseModel):
    key: str
    label: str
    current: float
    previous: float
    change_amount: float
    change_pct: float | None = None


class PLReportStatementLine(BaseModel):
    key: str
    label: str
    current: float
    previous: float
    is_total: bool = False


class PLReportTrendPoint(BaseModel):
    period_label: str
    net_revenue: float
    gross_profit: float
    net_profit: float


class PLReportCategoryRow(BaseModel):
    category: str
    category_label: str
    amount: float


class PLReportDataQuality(BaseModel):
    excluded_draft_invoices: int = 0
    excluded_draft_bills: int = 0
    excluded_draft_expenses: int = 0
    deduplicated_expense_count: int = 0
    deduplicated_expense_amount: float = 0
    write_off_total: float = 0
    mixed_currency: bool = False


class PLReportSummaryResponse(BaseModel):
    period: str
    period_label: str
    date_from: datetime
    date_to: datetime
    comparison_period_label: str
    comparison_date_from: datetime
    comparison_date_to: datetime
    company: PLReportCompanyContext
    gross_sales: float
    credit_notes: float
    net_revenue: float
    purchases_costs: float
    gross_profit: float
    gross_margin_pct: float | None = None
    operating_expenses: float
    net_profit: float
    net_margin_pct: float | None = None
    previous_gross_sales: float
    previous_credit_notes: float
    previous_net_revenue: float
    previous_purchases_costs: float
    previous_gross_profit: float
    previous_operating_expenses: float
    previous_net_profit: float
    comparisons: list[PLReportComparisonMetric]
    statement: list[PLReportStatementLine]
    expense_categories: list[PLReportCategoryRow] = Field(default_factory=list)
    trend: list[PLReportTrendPoint] = Field(default_factory=list)
    data_quality: PLReportDataQuality


class PLReportRevenueRegisterRow(BaseModel):
    id: int
    invoice_number: str | None = None
    issue_date: datetime
    client_name: str | None = None
    invoice_type: str
    invoice_type_label: str
    subtotal: float
    total_tax: float
    grand_total: float
    status: str
    status_label: str
    is_credit_note: bool = False


class PLReportRevenueResponse(BaseModel):
    period: str
    period_label: str
    date_from: datetime
    date_to: datetime
    company: PLReportCompanyContext
    gross_sales: float
    credit_notes: float
    net_revenue: float
    register: list[PLReportRevenueRegisterRow] = Field(default_factory=list)
    register_total: int = 0
    register_page: int = 1
    register_per_page: int = 50
    data_quality: PLReportDataQuality


class PLReportCostRegisterRow(BaseModel):
    id: int
    bill_number: str | None = None
    supplier_invoice_number: str | None = None
    bill_date: datetime
    vendor_name: str
    subtotal: float
    total_tax: float
    grand_total: float
    status: str
    status_label: str
    purchase_order_id: int | None = None
    po_number: str | None = None
    expense_id: int | None = None
    expense_linked: bool = False


class PLReportCostsResponse(BaseModel):
    period: str
    period_label: str
    date_from: datetime
    date_to: datetime
    company: PLReportCompanyContext
    purchases_costs: float
    register: list[PLReportCostRegisterRow] = Field(default_factory=list)
    register_total: int = 0
    register_page: int = 1
    register_per_page: int = 50
    data_quality: PLReportDataQuality


class PLReportExpenseRegisterRow(BaseModel):
    id: int
    expense_number: str | None = None
    expense_date: datetime
    category: str
    category_label: str
    title: str
    vendor_name: str
    amount: float
    status: str
    status_label: str
    submitter_name: str | None = None
    included_in_pl: bool = True
    exclusion_reason: str | None = None


class PLReportExcludedExpenseRow(BaseModel):
    id: int
    expense_number: str | None = None
    expense_date: datetime
    title: str
    vendor_name: str
    amount: float
    exclusion_reason: str


class PLReportExpensesResponse(BaseModel):
    period: str
    period_label: str
    date_from: datetime
    date_to: datetime
    company: PLReportCompanyContext
    operating_expenses: float
    expense_categories: list[PLReportCategoryRow] = Field(default_factory=list)
    register: list[PLReportExpenseRegisterRow] = Field(default_factory=list)
    excluded_duplicates: list[PLReportExcludedExpenseRow] = Field(default_factory=list)
    register_total: int = 0
    register_page: int = 1
    register_per_page: int = 50
    data_quality: PLReportDataQuality


class PLReportExportLogRequest(BaseModel):
    report_type: str = Field(min_length=1, max_length=30)
    period: str = Field(min_length=1, max_length=30)
    period_label: str | None = None
    row_count: int = 0


class ProjectOption(BaseModel):
    value: str
    label: str


class ProjectMetaResponse(BaseModel):
    statuses: list[ProjectOption]
    stages: list[ProjectOption]
    task_statuses: list[ProjectOption]
    priorities: list[ProjectOption]
    project_types: list[ProjectOption]


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    project_type: str = "client"
    status: str = "draft"
    priority: str = "normal"
    contact_id: int | None = None
    deal_id: int | None = None
    sales_order_id: int | None = None
    project_manager_id: int
    start_date: datetime | None = None
    deadline: datetime | None = None
    project_number: str | None = Field(default=None, max_length=40)


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    project_type: str | None = None
    priority: str | None = None
    contact_id: int | None = None
    deal_id: int | None = None
    sales_order_id: int | None = None
    project_manager_id: int | None = None
    start_date: datetime | None = None
    deadline: datetime | None = None
    project_number: str | None = Field(default=None, max_length=40)


class ProjectStatusChangeRequest(BaseModel):
    status: str = Field(min_length=1, max_length=20)
    reason: str | None = None


class ProjectMemberAddRequest(BaseModel):
    user_id: int
    role: str = "member"


class ProjectTaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    stage_key: str = "kickoff"
    assigned_to_id: int | None = None
    status: str = "todo"
    priority: str = "normal"
    due_date: datetime | None = None
    sort_order: int = 0
    blocked_reason: str | None = None


class ProjectTaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    stage_key: str | None = None
    assigned_to_id: int | None = None
    status: str | None = None
    priority: str | None = None
    due_date: datetime | None = None
    sort_order: int | None = None
    blocked_reason: str | None = None


class ProjectExportLogRequest(BaseModel):
    project_id: int
    row_count: int = 0


class ProjectMemberResponse(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    role: str
    role_label: str
    added_at: datetime | None = None


class ProjectTaskResponse(BaseModel):
    id: int
    project_id: int
    stage_key: str
    stage_label: str
    title: str
    description: str | None = None
    assigned_to_id: int | None = None
    assigned_to_name: str | None = None
    status: str
    status_label: str
    priority: str
    priority_label: str
    due_date: datetime | None = None
    completed_at: datetime | None = None
    sort_order: int
    blocked_reason: str | None = None
    is_overdue: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectStageSummary(BaseModel):
    stage_key: str
    stage_label: str
    total_tasks: int = 0
    done_tasks: int = 0
    overdue_tasks: int = 0


class ProjectListRow(BaseModel):
    id: int
    project_number: str | None = None
    name: str
    project_type: str
    status: str
    status_label: str
    priority: str
    priority_label: str
    contact_id: int | None = None
    contact_name: str | None = None
    project_manager_id: int
    project_manager_name: str | None = None
    deadline: datetime | None = None
    progress_percent: float = 0.0
    stage_summary: str | None = None
    open_task_count: int = 0
    overdue_task_count: int = 0
    is_overdue: bool = False
    updated_at: datetime | None = None


class ProjectIndexKpis(BaseModel):
    active_projects: int = 0
    overdue_projects: int = 0
    my_open_tasks: int = 0
    completed_this_month: int = 0


class ProjectListResponse(BaseModel):
    items: list[ProjectListRow]
    total: int
    page: int
    limit: int
    kpis: ProjectIndexKpis


class ProjectDetailResponse(BaseModel):
    id: int
    project_number: str | None = None
    name: str
    description: str | None = None
    project_type: str
    project_type_label: str
    status: str
    status_label: str
    priority: str
    priority_label: str
    contact_id: int | None = None
    contact_name: str | None = None
    deal_id: int | None = None
    deal_title: str | None = None
    sales_order_id: int | None = None
    sales_order_number: str | None = None
    project_manager_id: int
    project_manager_name: str | None = None
    created_by_id: int | None = None
    start_date: datetime | None = None
    deadline: datetime | None = None
    completed_at: datetime | None = None
    progress_percent: float = 0.0
    total_tasks: int = 0
    done_tasks: int = 0
    open_task_count: int = 0
    overdue_task_count: int = 0
    blocked_task_count: int = 0
    unassigned_task_count: int = 0
    is_overdue: bool = False
    is_locked: bool = False
    stage_summaries: list[ProjectStageSummary] = Field(default_factory=list)
    tasks: list[ProjectTaskResponse] = Field(default_factory=list)
    members: list[ProjectMemberResponse] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectMyTaskRow(BaseModel):
    id: int
    title: str
    status: str
    status_label: str
    priority: str
    priority_label: str
    due_date: datetime | None = None
    is_overdue: bool = False
    stage_key: str
    stage_label: str
    project_id: int
    project_name: str
    project_number: str | None = None
    client_name: str | None = None
    project_deadline: datetime | None = None


class ProjectMyTasksResponse(BaseModel):
    items: list[ProjectMyTaskRow]
    total: int


class ProjectContactSummaryResponse(BaseModel):
    contact_id: int
    active_project_count: int = 0
    nearest_deadline: datetime | None = None
    projects: list[ProjectListRow] = Field(default_factory=list)


class LeaveOption(BaseModel):
    value: str
    label: str


class LeaveMetaResponse(BaseModel):
    leave_types: list[LeaveOption]
    statuses: list[LeaveOption]
    half_day_periods: list[LeaveOption]


class LeaveCreateRequest(BaseModel):
    leave_type: str
    start_date: datetime
    end_date: datetime
    reason: str = Field(min_length=1)
    is_half_day: bool = False
    half_day_period: str | None = None
    submit: bool = False


class LeaveUpdateRequest(BaseModel):
    leave_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    reason: str | None = Field(default=None, min_length=1)
    is_half_day: bool | None = None
    half_day_period: str | None = None


class LeaveReviewRequest(BaseModel):
    reviewer_note: str | None = None


class LeaveRejectRequest(BaseModel):
    reviewer_note: str = Field(min_length=3)


class LeaveCancelRequest(BaseModel):
    reason: str | None = None


class LeaveExportLogRequest(BaseModel):
    row_count: int = 0


class LeaveResponse(BaseModel):
    id: int
    leave_number: str | None = None
    employee_id: int
    employee_name: str | None = None
    leave_type: str
    leave_type_label: str
    start_date: datetime
    end_date: datetime
    total_days: float
    is_half_day: bool
    half_day_period: str | None = None
    half_day_period_label: str | None = None
    reason: str
    status: str
    status_label: str
    submitted_at: datetime | None = None
    reviewed_by_id: int | None = None
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None = None
    reviewer_note: str | None = None
    overlap_warning: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LeaveListResponse(BaseModel):
    items: list[LeaveResponse]
    total: int
    page: int
    limit: int


class LeaveStatsResponse(BaseModel):
    pending_count: int = 0
    approved_days_this_month: float = 0.0
    my_pending_count: int = 0
    team_on_leave_count: int = 0


# ─── Timesheets ───────────────────────────────────────────────────────────────

class TimesheetCreateRequest(BaseModel):
    project_id: int | None = None
    task_id: int | None = None
    contact_id: int | None = None
    work_date: datetime
    hours: float
    is_billable: bool = True
    description: str
    submit: bool = False


class TimesheetUpdateRequest(BaseModel):
    project_id: int | None = None
    task_id: int | None = None
    contact_id: int | None = None
    work_date: datetime | None = None
    hours: float | None = None
    is_billable: bool | None = None
    description: str | None = None


class TimesheetReviewRequest(BaseModel):
    reviewer_note: str | None = None


class TimesheetRejectRequest(BaseModel):
    reviewer_note: str


class TimesheetExportLogRequest(BaseModel):
    row_count: int = 0


class TimesheetOption(BaseModel):
    value: str
    label: str


class TimesheetMetaResponse(BaseModel):
    statuses: list[TimesheetOption]


class TimesheetResponse(BaseModel):
    id: int
    entry_number: str | None = None
    employee_id: int
    employee_name: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    project_number: str | None = None
    task_id: int | None = None
    task_title: str | None = None
    contact_id: int | None = None
    contact_name: str | None = None
    work_date: datetime
    hours: float
    is_billable: bool
    description: str
    status: str
    status_label: str
    submitted_at: datetime | None = None
    reviewed_by_id: int | None = None
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None = None
    reviewer_note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TimesheetListResponse(BaseModel):
    items: list[TimesheetResponse]
    total: int
    page: int
    limit: int


class TimesheetStatsResponse(BaseModel):
    my_pending_count: int = 0
    my_hours_this_week: float = 0.0
    my_billable_hours_this_week: float = 0.0
    pending_approval_count: int = 0
    team_hours_this_week: float = 0.0


# ─── Employees / HR ───────────────────────────────────────────────────────────

class EmployeeOption(BaseModel):
    value: str
    label: str


class EmployeeMetaResponse(BaseModel):
    employment_types: list[EmployeeOption]
    genders: list[EmployeeOption]


class EmployeeProfileResponse(BaseModel):
    id: int | None = None
    user_id: int
    employee_id: str | None = None
    name: str
    email: str
    phone: str | None = None
    role: str
    status: str
    designation: str | None = None
    department: str | None = None
    joining_date: datetime | None = None
    date_of_birth: datetime | None = None
    gender: str | None = None
    gender_label: str | None = None
    employment_type: str | None = None
    employment_type_label: str | None = None
    manager_id: int | None = None
    manager_name: str | None = None
    salary_monthly: float | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    pan: str | None = None
    bank_name: str | None = None
    bank_account_last4: str | None = None
    notes: str | None = None
    last_login_at: datetime | None = None


class EmployeeListResponse(BaseModel):
    items: list[EmployeeProfileResponse]
    total: int
    page: int
    limit: int


class EmployeeProfileUpdateRequest(BaseModel):
    joining_date: datetime | None = None
    date_of_birth: datetime | None = None
    gender: str | None = None
    employment_type: str | None = None
    manager_id: int | None = None
    salary_monthly: float | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    pan: str | None = None
    bank_name: str | None = None
    bank_account_last4: str | None = None
    notes: str | None = None
    designation: str | None = None
    department: str | None = None


# ─── Attendance ───────────────────────────────────────────────────────────────

class AttendanceMetaResponse(BaseModel):
    statuses: list[EmployeeOption]


class AttendanceResponse(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    attendance_date: datetime
    status: str
    status_label: str
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    worked_hours: float | None = None
    late_minutes: int = 0
    notes: str | None = None


class AttendanceListResponse(BaseModel):
    items: list[AttendanceResponse]
    total: int
    page: int
    limit: int


class AttendanceStatsResponse(BaseModel):
    present_today: int = 0
    absent_today: int = 0
    late_today: int = 0
    on_leave_today: int = 0
    my_status_today: str | None = None


class AttendanceTodayResponse(BaseModel):
    attendance_date: datetime
    has_record: bool = False
    status: str | None = None
    status_label: str | None = None
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    worked_hours: float | None = None
    late_minutes: int = 0
    can_check_in: bool = True
    can_check_out: bool = False


class AttendanceTeamTodayRow(BaseModel):
    user_id: int
    user_name: str
    department: str | None = None
    role: str | None = None
    status: str | None = None
    status_label: str
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    worked_hours: float | None = None
    late_minutes: int = 0


class AttendanceTeamTodayResponse(BaseModel):
    attendance_date: datetime
    items: list[AttendanceTeamTodayRow]
    total_staff: int = 0
    checked_in_count: int = 0
    checked_out_count: int = 0


class AttendanceRecordRequest(BaseModel):
    user_id: int
    attendance_date: datetime
    status: str
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    notes: str | None = None


class AttendanceCheckInRequest(BaseModel):
    notes: str | None = None


# ─── Recruitment ──────────────────────────────────────────────────────────────

class RecruitmentMetaResponse(BaseModel):
    job_statuses: list[EmployeeOption]
    applicant_statuses: list[EmployeeOption]


class JobApplicantResponse(BaseModel):
    id: int
    job_opening_id: int
    name: str
    email: str
    phone: str | None = None
    status: str
    status_label: str
    interview_round: int
    experience_years: float | None = None
    current_company: str | None = None
    resume_summary: str | None = None
    interviewer_note: str | None = None
    applied_at: datetime | None = None


class JobOpeningResponse(BaseModel):
    id: int
    job_code: str | None = None
    title: str
    department: str | None = None
    description: str | None = None
    status: str
    status_label: str
    openings_count: int
    salary_min: float | None = None
    salary_max: float | None = None
    posted_at: datetime | None = None
    applicant_count: int = 0
    notes: str | None = None


class JobOpeningDetailResponse(JobOpeningResponse):
    applicants: list[JobApplicantResponse] = []


class JobOpeningListResponse(BaseModel):
    items: list[JobOpeningResponse]
    total: int
    page: int
    limit: int


class JobOpeningCreateRequest(BaseModel):
    title: str
    department: str | None = None
    description: str | None = None
    status: str = "open"
    openings_count: int = 1
    salary_min: float | None = None
    salary_max: float | None = None
    notes: str | None = None


class JobOpeningUpdateRequest(BaseModel):
    title: str | None = None
    department: str | None = None
    description: str | None = None
    status: str | None = None
    openings_count: int | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    notes: str | None = None


class JobApplicantCreateRequest(BaseModel):
    name: str
    email: str
    phone: str | None = None
    experience_years: float | None = None
    current_company: str | None = None
    resume_summary: str | None = None


class JobApplicantUpdateRequest(BaseModel):
    status: str | None = None
    interview_round: int | None = None
    interviewer_note: str | None = None
    resume_summary: str | None = None


# ─── Payroll ──────────────────────────────────────────────────────────────────

class PayrollMetaResponse(BaseModel):
    statuses: list[EmployeeOption]


class PayslipResponse(BaseModel):
    id: int
    payslip_number: str | None = None
    employee_id: int
    employee_name: str | None = None
    period_month: int
    period_year: int
    period_label: str
    basic_salary: float
    hra: float
    allowances: float
    gross_salary: float
    pf_deduction: float
    tds_deduction: float
    other_deductions: float
    reimbursements: float
    net_salary: float
    status: str
    status_label: str
    payment_date: datetime | None = None
    notes: str | None = None


class PayslipListResponse(BaseModel):
    items: list[PayslipResponse]
    total: int
    page: int
    limit: int


class PayrollStatsResponse(BaseModel):
    generated_this_month: int = 0
    paid_this_month: int = 0
    total_net_this_month: float = 0.0
    my_latest_net: float | None = None


class PayslipGenerateRequest(BaseModel):
    employee_id: int
    period_month: int
    period_year: int
    reimbursements: float = 0.0
    other_deductions: float = 0.0
    notes: str | None = None


# ─── Approvals hub ────────────────────────────────────────────────────────────

class ApprovalQueueItem(BaseModel):
    module: str
    label: str
    count: int
    path: str


class ApprovalsSummaryResponse(BaseModel):
    total_pending: int
    queues: list[ApprovalQueueItem]


# ─── Chat ─────────────────────────────────────────────────────────────────────

class ChatMetaResponse(BaseModel):
    channels: list[EmployeeOption]


class ChatMessageResponse(BaseModel):
    id: int
    sender_id: int
    sender_name: str | None = None
    channel: str
    channel_label: str
    recipient_id: int | None = None
    recipient_name: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    body: str
    created_at: datetime | None = None


class ChatMessageListResponse(BaseModel):
    items: list[ChatMessageResponse]
    total: int


class ChatMessageCreateRequest(BaseModel):
    channel: str = "general"
    body: str
    recipient_id: int | None = None
    project_id: int | None = None
