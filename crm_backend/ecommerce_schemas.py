"""eCommerce API schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class StoreSettingsResponse(BaseModel):
    is_enabled: bool
    store_name: str | None
    currency: str
    guest_checkout_allowed: bool
    flat_shipping_rate: Decimal
    free_shipping_above: Decimal | None
    default_payment_method: str
    order_number_prefix: str
    auto_create_sales_order: bool
    auto_create_invoice: bool
    inventory_reserve_on_checkout: bool
    return_window_days: int
    bank_details: str | None
    public_shop_url: str | None = None


class StoreSettingsUpdateRequest(BaseModel):
    is_enabled: bool | None = None
    store_name: str | None = Field(default=None, max_length=120)
    guest_checkout_allowed: bool | None = None
    flat_shipping_rate: Decimal | None = None
    free_shipping_above: Decimal | None = None
    default_payment_method: str | None = None
    order_number_prefix: str | None = Field(default=None, max_length=10)
    auto_create_sales_order: bool | None = None
    auto_create_invoice: bool | None = None
    inventory_reserve_on_checkout: bool | None = None
    return_window_days: int | None = None
    bank_details: str | None = None


class StoreDashboardResponse(BaseModel):
    orders_today: int
    revenue_7d: float
    pending_shipment: int
    open_returns: int
    unpaid_orders: int
    public_shop_url: str | None
    recent_orders: list["StoreOrderListItem"]


class StoreProductPublic(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None
    price: float | None
    compare_at_price: float | None
    category: str | None
    image_url: str | None
    gst_rate: float
    in_stock: bool


class StoreCatalogResponse(BaseModel):
    items: list[StoreProductPublic]
    total: int
    categories: list[str]


class StoreCartItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    product_slug: str
    quantity: float
    unit_price: float
    gst_rate: float
    line_total: float
    image_url: str | None


class StoreCartResponse(BaseModel):
    id: int
    items: list[StoreCartItemResponse]
    item_count: int
    subtotal: float
    session_id: str | None = None


class StoreCartAddRequest(BaseModel):
    product_id: int
    quantity: float = 1


class StoreCartUpdateRequest(BaseModel):
    quantity: float


class StoreAddressInput(BaseModel):
    line1: str
    line2: str | None = None
    city: str
    state: str
    pincode: str


class StoreCheckoutRequest(BaseModel):
    guest_name: str | None = None
    guest_email: str | None = None
    guest_phone: str | None = None
    gstin: str | None = None
    shipping_address: StoreAddressInput
    billing_address: StoreAddressInput | None = None
    shipping_method: str = "digital"
    payment_method: str = "bank_transfer"
    payment_terms: str = "due_on_receipt"
    customer_note: str | None = None


class StoreCheckoutResponse(BaseModel):
    order_number: str
    order_id: int
    grand_total: float
    payment_method: str
    message: str


class StoreCustomerRegisterRequest(BaseModel):
    name: str
    email: str
    phone: str | None = None
    password: str


class StoreCustomerLoginRequest(BaseModel):
    email: str
    password: str


class StoreCustomerTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: "StoreCustomerProfile"


class StoreCustomerProfile(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None
    gstin: str | None


class StoreOrderListItem(BaseModel):
    id: int
    order_number: str
    customer_name: str
    item_count: int
    grand_total: float
    status: str
    payment_status: str
    placed_at: datetime | None


class StoreOrderListResponse(BaseModel):
    items: list[StoreOrderListItem]
    total: int


class StoreOrderItemResponse(BaseModel):
    id: int
    product_id: int | None
    product_name_snapshot: str
    quantity: float
    unit_price: float
    gst_rate: float
    line_total: float


class StoreOrderResponse(BaseModel):
    id: int
    order_number: str
    status: str
    payment_status: str
    subtotal: float
    tax_total: float
    shipping_total: float
    grand_total: float
    currency: str
    guest_name: str | None
    guest_email: str | None
    guest_phone: str | None
    shipping_address_json: dict[str, Any] | None
    billing_address_json: dict[str, Any] | None
    shipping_method: str
    payment_method: str
    tracking_number: str | None
    customer_note: str | None
    contact_id: int | None
    sales_order_id: int | None
    placed_at: datetime | None
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    items: list[StoreOrderItemResponse]


class StoreOrderStatusUpdateRequest(BaseModel):
    status: str
    tracking_number: str | None = None


class StorePaymentRecordRequest(BaseModel):
    amount: float | None = None
    method: str | None = None
    note: str | None = None


class StoreCatalogItemResponse(BaseModel):
    id: int
    name: str
    service_code: str | None
    category: str | None
    sell_online: bool
    online_slug: str | None
    online_description: str | None
    online_image_url: str | None
    compare_at_price: float | None
    price: float | None
    public_url: str | None = None


class StoreCatalogUpdateRequest(BaseModel):
    sell_online: bool | None = None
    online_slug: str | None = None
    online_description: str | None = None
    online_image_url: str | None = None
    compare_at_price: float | None = None


class StoreReturnListItem(BaseModel):
    id: int
    return_number: str
    order_number: str
    status: str
    reason: str
    refund_amount: float | None
    requested_at: datetime


class StoreReturnListResponse(BaseModel):
    items: list[StoreReturnListItem]
    total: int


class StoreReturnRequest(BaseModel):
    reason: str
    items: list[dict[str, Any]]


class StoreReturnUpdateRequest(BaseModel):
    status: str
    refund_amount: float | None = None


class StoreShopInfoResponse(BaseModel):
    is_enabled: bool
    store_name: str | None
    checkout_mode: str = "services"
    payment_methods: list[dict[str, str]]
    payment_terms: list[dict[str, str]]
    shipping_methods: list[dict[str, str]]
    bank_details: str | None = None
    default_payment_method: str = "bank_transfer"
    default_payment_terms: str = "due_on_receipt"
