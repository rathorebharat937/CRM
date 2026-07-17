"""eCommerce — staff and public store API."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from jose import JWTError, jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, hash_password, require_permission, verify_password
from config import FRONTEND_URL, JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET
from ecommerce_config import (
    MAX_CART_QTY,
    ORDER_STATUSES,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    RETURN_STATUSES,
    SHIPPING_METHODS,
    CART_EXPIRY_DAYS,
    DEFAULT_SERVICE_PAYMENT_METHOD,
    DEFAULT_SERVICE_PAYMENT_TERMS,
    DEFAULT_SERVICE_SHIPPING_METHOD,
    SERVICE_PAYMENT_METHOD_LABELS,
    SERVICE_PAYMENT_METHODS,
    SERVICE_SHIPPING_METHOD_LABELS,
    SERVICE_SHIPPING_METHODS,
    STORE_CHECKOUT_MODE,
    STORE_PAYMENT_TERM_LABELS,
    STORE_PAYMENT_TERMS,
    product_display_image_url,
    product_online_slug,
    product_unit_price,
    normalize_slug,
)
from ecommerce_schemas import (
    StoreAddressInput,
    StoreCartAddRequest,
    StoreCartItemResponse,
    StoreCartResponse,
    StoreCartUpdateRequest,
    StoreCatalogItemResponse,
    StoreCatalogResponse,
    StoreCatalogUpdateRequest,
    StoreCheckoutRequest,
    StoreCheckoutResponse,
    StoreCustomerLoginRequest,
    StoreCustomerProfile,
    StoreCustomerRegisterRequest,
    StoreCustomerTokenResponse,
    StoreDashboardResponse,
    StoreOrderListItem,
    StoreOrderListResponse,
    StoreOrderResponse,
    StoreOrderItemResponse,
    StoreOrderStatusUpdateRequest,
    StorePaymentRecordRequest,
    StoreProductPublic,
    StoreReturnListItem,
    StoreReturnListResponse,
    StoreReturnRequest,
    StoreReturnUpdateRequest,
    StoreShopInfoResponse,
    StoreSettingsResponse,
    StoreSettingsUpdateRequest,
)
from lead_config import normalize_phone
from models import (
    Company,
    Contact,
    Product,
    SalesOrder,
    SalesOrderLineItem,
    StoreCart,
    StoreCartItem,
    StoreCustomer,
    StoreOrder,
    StoreOrderItem,
    StorePayment,
    StoreReturn,
    StoreSettings,
    User,
    WebsiteSettings,
    ActivityLog,
)

router = APIRouter(prefix="/ecommerce", tags=["ecommerce"])
public_router = APIRouter(prefix="/public", tags=["public-ecommerce"])
store_security = HTTPBearer(auto_error=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)




def _resolve_company_by_slug(db: Session, company_slug: str) -> tuple[Company, WebsiteSettings]:
    site = db.query(WebsiteSettings).filter(WebsiteSettings.company_slug == company_slug).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    company = db.query(Company).filter(Company.id == site.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Site not found")
    return company, site


def _shop_url(company_slug: str, *parts: str) -> str:
    path = f"/s/{company_slug}/shop"
    if parts:
        path += "/" + "/".join(parts)
    return f"{FRONTEND_URL.rstrip('/')}{path}"


def _get_store_settings(db: Session, company: Company) -> StoreSettings:
    settings = db.query(StoreSettings).filter(StoreSettings.company_id == company.id).first()
    if settings:
        return settings
    settings = StoreSettings(company_id=company.id, store_name=company.display_name, is_enabled=True, default_payment_method=DEFAULT_SERVICE_PAYMENT_METHOD)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _require_store_enabled(settings: StoreSettings) -> None:
    if not settings.is_enabled:
        raise HTTPException(status_code=404, detail="Store is not available")


def _settings_response(settings: StoreSettings, company_slug: str | None = None) -> StoreSettingsResponse:
    return StoreSettingsResponse(
        is_enabled=settings.is_enabled,
        store_name=settings.store_name,
        currency=settings.currency,
        guest_checkout_allowed=settings.guest_checkout_allowed,
        flat_shipping_rate=settings.flat_shipping_rate,
        free_shipping_above=settings.free_shipping_above,
        default_payment_method=settings.default_payment_method,
        order_number_prefix=settings.order_number_prefix,
        auto_create_sales_order=settings.auto_create_sales_order,
        auto_create_invoice=settings.auto_create_invoice,
        inventory_reserve_on_checkout=settings.inventory_reserve_on_checkout,
        return_window_days=settings.return_window_days,
        bank_details=settings.bank_details,
        public_shop_url=_shop_url(company_slug) if company_slug else None,
    )


def _create_store_token(customer: StoreCustomer) -> str:
    expire = _utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": str(customer.id),
        "type": "store_customer",
        "company_id": customer.company_id,
        "email": customer.email,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _optional_store_customer(
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> StoreCustomer | None:
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "store_customer":
        return None
    customer = db.query(StoreCustomer).filter(StoreCustomer.id == int(payload["sub"])).first()
    if not customer or not customer.is_active:
        return None
    return customer


def _get_store_customer(
    credentials: HTTPAuthorizationCredentials | None = Depends(store_security),
    db: Session = Depends(get_db),
) -> StoreCustomer:
    customer = _optional_store_customer(credentials, db)
    if not customer:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return customer


def _load_cart(db: Session, cart_id: int) -> StoreCart:
    cart = (
        db.query(StoreCart)
        .options(joinedload(StoreCart.items).joinedload(StoreCartItem.product))
        .filter(StoreCart.id == cart_id)
        .first()
    )
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


def optional_store_customer_dep(
    credentials: HTTPAuthorizationCredentials | None = Depends(store_security),
    db: Session = Depends(get_db),
) -> StoreCustomer | None:
    return _optional_store_customer(credentials, db)


def _get_online_product(db: Session, company_id: int, product_id: int) -> Product:
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.company_id == company_id, Product.sell_online.is_(True), Product.status == "active")
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not available")
    return product


def _product_in_stock(product: Product) -> bool:
    if product.inventory_tracked and float(product.on_hand_quantity or 0) <= 0:
        return False
    return True


def _product_public(product: Product) -> StoreProductPublic:
    return StoreProductPublic(
        id=product.id,
        name=product.name,
        slug=product_online_slug(product),
        description=product.online_description or product.description,
        price=product_unit_price(product),
        compare_at_price=float(product.compare_at_price) if product.compare_at_price is not None else None,
        category=product.category,
        image_url=product_display_image_url(product),
        gst_rate=float(product.gst_rate or 18),
        in_stock=_product_in_stock(product),
    )


def _get_or_create_cart(
    db: Session,
    company_id: int,
    session_id: str | None,
    customer_id: int | None = None,
) -> StoreCart:
    cart = None
    if customer_id:
        cart = db.query(StoreCart).filter(StoreCart.company_id == company_id, StoreCart.customer_id == customer_id).first()
    if not cart and session_id:
        cart = db.query(StoreCart).filter(StoreCart.company_id == company_id, StoreCart.session_id == session_id).first()
    if not cart:
        cart = StoreCart(
            company_id=company_id,
            session_id=session_id or secrets.token_urlsafe(16),
            customer_id=customer_id,
            expires_at=_utcnow() + timedelta(days=CART_EXPIRY_DAYS),
        )
        db.add(cart)
        db.flush()
    cart.expires_at = _utcnow() + timedelta(days=CART_EXPIRY_DAYS)
    return cart


def _cart_response(cart: StoreCart) -> StoreCartResponse:
    items = []
    subtotal = 0.0
    for item in cart.items:
        line = float(item.quantity) * float(item.unit_price_snapshot)
        subtotal += line
        product = item.product
        items.append(
            StoreCartItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=product.name if product else "Product",
                product_slug=product_online_slug(product) if product else "",
                quantity=float(item.quantity),
                unit_price=float(item.unit_price_snapshot),
                gst_rate=float(item.gst_rate_snapshot),
                line_total=line,
                image_url=product_display_image_url(product) if product else None,
            )
        )
    return StoreCartResponse(
        id=cart.id,
        items=items,
        item_count=len(items),
        subtotal=subtotal,
        session_id=cart.session_id,
    )


def _compute_shipping(settings: StoreSettings, subtotal: Decimal, shipping_method: str | None = None) -> Decimal:
    if shipping_method in ("digital", "pickup"):
        return Decimal("0")
    if settings.free_shipping_above is not None and subtotal >= settings.free_shipping_above:
        return Decimal("0")
    if settings.flat_shipping_rate is not None:
        return Decimal(str(settings.flat_shipping_rate))
    return Decimal("0")


def _compute_order_totals(
    cart: StoreCart,
    settings: StoreSettings,
    shipping_method: str | None = None,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for item in cart.items:
        line_sub = Decimal(str(item.quantity)) * Decimal(str(item.unit_price_snapshot))
        line_tax = line_sub * Decimal(str(item.gst_rate_snapshot)) / Decimal("100")
        subtotal += line_sub
        tax_total += line_tax
    shipping = _compute_shipping(settings, subtotal, shipping_method)
    grand = subtotal + tax_total + shipping
    return subtotal, tax_total, shipping, grand


def _shop_checkout_options(settings: StoreSettings) -> dict[str, Any]:
    return {
        "checkout_mode": STORE_CHECKOUT_MODE,
        "payment_methods": [
            {"value": key, "label": SERVICE_PAYMENT_METHOD_LABELS[key]}
            for key in SERVICE_PAYMENT_METHODS
        ],
        "payment_terms": [
            {"value": key, "label": STORE_PAYMENT_TERM_LABELS[key]}
            for key in STORE_PAYMENT_TERMS
        ],
        "shipping_methods": [
            {"value": key, "label": SERVICE_SHIPPING_METHOD_LABELS[key]}
            for key in SERVICE_SHIPPING_METHODS
        ],
        "bank_details": settings.bank_details,
        "default_payment_method": settings.default_payment_method or DEFAULT_SERVICE_PAYMENT_METHOD,
        "default_payment_terms": DEFAULT_SERVICE_PAYMENT_TERMS,
    }


def _checkout_order_note(payment_terms: str | None, customer_note: str | None) -> str | None:
    parts: list[str] = []
    if payment_terms and payment_terms in STORE_PAYMENT_TERM_LABELS:
        parts.append(f"Payment terms: {STORE_PAYMENT_TERM_LABELS[payment_terms]}")
    if customer_note and customer_note.strip():
        parts.append(customer_note.strip())
    return "\n".join(parts) if parts else None


def _checkout_confirmation_message(payment_method: str, payment_terms: str | None) -> str:
    terms = STORE_PAYMENT_TERM_LABELS.get(payment_terms or "", "")
    if payment_method == "online":
        return "Service order received. Complete online payment to start work. Our team will confirm shortly."
    if payment_method == "bank_transfer":
        base = "Service order received. Pay via bank transfer / UPI as per your selected payment terms."
        if terms:
            return f"{base} ({terms}) Our team will confirm payment and begin service delivery."
        return f"{base} Our team will confirm payment and begin service delivery."
    if payment_method == "cod":
        return "Order confirmed. Our team will contact you with payment instructions."
    return "Order placed successfully."


def _generate_store_order_number(db: Session, company_id: int, prefix: str) -> str:
    year = _utcnow().year
    base = f"{prefix}-{year}-"
    last = (
        db.query(StoreOrder)
        .filter(StoreOrder.company_id == company_id, StoreOrder.order_number.like(f"{base}%"))
        .order_by(StoreOrder.id.desc())
        .first()
    )
    seq = 1
    if last and last.order_number:
        try:
            seq = int(last.order_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{base}{seq:04d}"


def _generate_return_number(db: Session, company_id: int) -> str:
    year = _utcnow().year
    base = f"RET-{year}-"
    last = (
        db.query(StoreReturn)
        .filter(StoreReturn.company_id == company_id, StoreReturn.return_number.like(f"{base}%"))
        .order_by(StoreReturn.id.desc())
        .first()
    )
    seq = 1
    if last and last.return_number:
        try:
            seq = int(last.return_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{base}{seq:04d}"


def _address_dict(addr: StoreAddressInput) -> dict[str, Any]:
    return addr.model_dump()


def _format_address(addr: dict[str, Any] | None) -> str:
    if not addr:
        return ""
    return ", ".join(x for x in [addr.get("line1"), addr.get("line2"), addr.get("city"), addr.get("state"), addr.get("pincode")] if x)


def _upsert_contact(
    db: Session,
    company: Company,
    *,
    name: str,
    email: str | None,
    phone: str | None,
    gstin: str | None = None,
    address: dict[str, Any] | None = None,
) -> Contact:
    contact = None
    if email:
        contact = db.query(Contact).filter(Contact.company_id == company.id, Contact.email == email.lower()).first()
    if not contact and phone:
        contact = db.query(Contact).filter(Contact.company_id == company.id, Contact.phone == normalize_phone(phone)).first()
    if contact:
        contact.name = name or contact.name
        if phone:
            contact.phone = normalize_phone(phone)
        if gstin:
            contact.gstin = gstin
        if address:
            contact.address_line1 = address.get("line1")
            contact.address_line2 = address.get("line2")
            contact.city = address.get("city")
            contact.state = address.get("state")
            contact.pincode = address.get("pincode")
        return contact
    contact = Contact(
        company_id=company.id,
        name=name,
        email=email.lower() if email else None,
        phone=normalize_phone(phone) if phone else None,
        gstin=gstin,
        contact_type="Customer",
        status="active",
        address_line1=address.get("line1") if address else None,
        address_line2=address.get("line2") if address else None,
        city=address.get("city") if address else None,
        state=address.get("state") if address else None,
        pincode=address.get("pincode") if address else None,
    )
    db.add(contact)
    db.flush()
    return contact


def _create_sales_order_from_store(
    db: Session,
    company: Company,
    store_order: StoreOrder,
    contact: Contact,
) -> SalesOrder:
    order_number = f"SO-WEB-{store_order.id}"
    existing = db.query(SalesOrder).filter(SalesOrder.company_id == company.id, SalesOrder.order_number == order_number).first()
    if existing:
        return existing
    order = SalesOrder(
        company_id=company.id,
        contact_id=contact.id,
        order_number=order_number,
        title=f"Online order {store_order.order_number}",
        status="confirmed",
        source_type="website",
        currency=store_order.currency,
        order_date=store_order.placed_at or _utcnow(),
        confirmation_date=_utcnow(),
        client_name=store_order.guest_name or contact.name,
        client_email=store_order.guest_email or contact.email,
        client_phone=store_order.guest_phone or contact.phone,
        client_org=contact.organization_name,
        billing_address=_format_address(store_order.billing_address_json),
        delivery_address=_format_address(store_order.shipping_address_json),
        subtotal=store_order.subtotal,
        total_tax=store_order.tax_total,
        grand_total=store_order.grand_total,
        delivery_instructions=store_order.customer_note,
    )
    db.add(order)
    db.flush()
    for idx, item in enumerate(store_order.items):
        db.add(
            SalesOrderLineItem(
                sales_order_id=order.id,
                product_id=item.product_id,
                sort_order=idx,
                item_name=item.product_name_snapshot,
                quantity=item.quantity,
                unit_price=item.unit_price,
                tax_rate=item.gst_rate,
                line_subtotal=item.line_total,
                line_total=item.line_total,
            )
        )
    return order


def _order_list_item(order: StoreOrder) -> StoreOrderListItem:
    name = order.guest_name or (order.customer.name if order.customer else "Guest")
    return StoreOrderListItem(
        id=order.id,
        order_number=order.order_number,
        customer_name=name,
        item_count=len(order.items),
        grand_total=float(order.grand_total),
        status=order.status,
        payment_status=order.payment_status,
        placed_at=order.placed_at,
    )


def _order_response(order: StoreOrder) -> StoreOrderResponse:
    return StoreOrderResponse(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        payment_status=order.payment_status,
        subtotal=float(order.subtotal),
        tax_total=float(order.tax_total),
        shipping_total=float(order.shipping_total),
        grand_total=float(order.grand_total),
        currency=order.currency,
        guest_name=order.guest_name,
        guest_email=order.guest_email,
        guest_phone=order.guest_phone,
        shipping_address_json=order.shipping_address_json,
        billing_address_json=order.billing_address_json,
        shipping_method=order.shipping_method,
        payment_method=order.payment_method,
        tracking_number=order.tracking_number,
        customer_note=order.customer_note,
        contact_id=order.contact_id,
        sales_order_id=order.sales_order_id,
        placed_at=order.placed_at,
        paid_at=order.paid_at,
        shipped_at=order.shipped_at,
        delivered_at=order.delivered_at,
        items=[
            StoreOrderItemResponse(
                id=i.id,
                product_id=i.product_id,
                product_name_snapshot=i.product_name_snapshot,
                quantity=float(i.quantity),
                unit_price=float(i.unit_price),
                gst_rate=float(i.gst_rate),
                line_total=float(i.line_total),
            )
            for i in order.items
        ],
    )


def _get_store_order(db: Session, order_id: int, company_id: int) -> StoreOrder:
    order = (
        db.query(StoreOrder)
        .options(joinedload(StoreOrder.items), joinedload(StoreOrder.customer))
        .filter(StoreOrder.id == order_id, StoreOrder.company_id == company_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


# --- Staff routes ---

@router.get("/dashboard", response_model=StoreDashboardResponse)
def ecommerce_dashboard(user: User = Depends(require_permission("ecommerce.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    settings = _get_store_settings(db, company)
    site = db.query(WebsiteSettings).filter(WebsiteSettings.company_id == company.id).first()
    today = _utcnow().date()
    since = _utcnow() - timedelta(days=7)
    orders_today = db.query(func.count(StoreOrder.id)).filter(
        StoreOrder.company_id == company.id, func.date(StoreOrder.placed_at) == today
    ).scalar()
    revenue_7d = db.query(func.coalesce(func.sum(StoreOrder.grand_total), 0)).filter(
        StoreOrder.company_id == company.id, StoreOrder.placed_at >= since, StoreOrder.payment_status == "paid"
    ).scalar()
    pending_shipment = db.query(func.count(StoreOrder.id)).filter(
        StoreOrder.company_id == company.id, StoreOrder.status.in_(["paid", "processing"])
    ).scalar()
    open_returns = db.query(func.count(StoreReturn.id)).filter(
        StoreReturn.company_id == company.id, StoreReturn.status.in_(["requested", "approved", "received"])
    ).scalar()
    unpaid_orders = db.query(func.count(StoreOrder.id)).filter(
        StoreOrder.company_id == company.id, StoreOrder.payment_status == "unpaid", StoreOrder.status != "cancelled"
    ).scalar()
    recent = (
        db.query(StoreOrder)
        .options(joinedload(StoreOrder.items), joinedload(StoreOrder.customer))
        .filter(StoreOrder.company_id == company.id)
        .order_by(StoreOrder.placed_at.desc())
        .limit(8)
        .all()
    )
    return StoreDashboardResponse(
        orders_today=int(orders_today or 0),
        revenue_7d=float(revenue_7d or 0),
        pending_shipment=int(pending_shipment or 0),
        open_returns=int(open_returns or 0),
        unpaid_orders=int(unpaid_orders or 0),
        public_shop_url=_shop_url(site.company_slug) if site and settings.is_enabled else None,
        recent_orders=[_order_list_item(o) for o in recent],
    )


@router.get("/settings", response_model=StoreSettingsResponse)
def get_store_settings(user: User = Depends(require_permission("ecommerce.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    settings = _get_store_settings(db, company)
    site = db.query(WebsiteSettings).filter(WebsiteSettings.company_id == company.id).first()
    return _settings_response(settings, site.company_slug if site else None)


@router.put("/settings", response_model=StoreSettingsResponse)
def update_store_settings(
    data: StoreSettingsUpdateRequest,
    user: User = Depends(require_permission("ecommerce.manage_settings")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    settings = _get_store_settings(db, company)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    site = db.query(WebsiteSettings).filter(WebsiteSettings.company_id == company.id).first()
    log_activity(db, "ecommerce_settings_updated", user_id=user.id, email=user.email)
    return _settings_response(settings, site.company_slug if site else None)


@router.get("/catalog", response_model=list[StoreCatalogItemResponse])
def list_catalog(user: User = Depends(require_permission("ecommerce.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    site = db.query(WebsiteSettings).filter(WebsiteSettings.company_id == company.id).first()
    products = db.query(Product).filter(Product.company_id == company.id).order_by(Product.name.asc()).all()
    return [
        StoreCatalogItemResponse(
            id=p.id,
            name=p.name,
            service_code=p.service_code,
            category=p.category,
            sell_online=p.sell_online,
            online_slug=p.online_slug or product_online_slug(p),
            online_description=p.online_description,
            online_image_url=p.online_image_url,
            compare_at_price=float(p.compare_at_price) if p.compare_at_price is not None else None,
            price=product_unit_price(p),
            public_url=_shop_url(site.company_slug, product_online_slug(p)) if site and p.sell_online else None,
        )
        for p in products
    ]


@router.put("/catalog/{product_id}", response_model=StoreCatalogItemResponse)
def update_catalog_product(
    product_id: int,
    data: StoreCatalogUpdateRequest,
    user: User = Depends(require_permission("ecommerce.manage_catalog")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    site = db.query(WebsiteSettings).filter(WebsiteSettings.company_id == company.id).first()
    product = db.query(Product).filter(Product.id == product_id, Product.company_id == company.id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    payload = data.model_dump(exclude_unset=True)
    if "online_slug" in payload and payload["online_slug"]:
        payload["online_slug"] = normalize_slug(payload["online_slug"])
    for field, value in payload.items():
        setattr(product, field, value)
    if product.sell_online and not product.online_slug:
        product.online_slug = product_online_slug(product)
    db.commit()
    db.refresh(product)
    return StoreCatalogItemResponse(
        id=product.id,
        name=product.name,
        service_code=product.service_code,
        category=product.category,
        sell_online=product.sell_online,
        online_slug=product.online_slug,
        online_description=product.online_description,
        online_image_url=product.online_image_url,
        compare_at_price=float(product.compare_at_price) if product.compare_at_price is not None else None,
        price=product_unit_price(product),
        public_url=_shop_url(site.company_slug, product.online_slug) if site and product.sell_online else None,
    )


@router.get("/orders", response_model=StoreOrderListResponse)
def list_orders(
    status: str | None = None,
    payment_status: str | None = None,
    user: User = Depends(require_permission("ecommerce.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    q = db.query(StoreOrder).options(joinedload(StoreOrder.items), joinedload(StoreOrder.customer)).filter(StoreOrder.company_id == company.id)
    if status:
        q = q.filter(StoreOrder.status == status)
    if payment_status:
        q = q.filter(StoreOrder.payment_status == payment_status)
    orders = q.order_by(StoreOrder.placed_at.desc()).all()
    return StoreOrderListResponse(items=[_order_list_item(o) for o in orders], total=len(orders))


@router.get("/orders/{order_id}", response_model=StoreOrderResponse)
def get_order(order_id: int, user: User = Depends(require_permission("ecommerce.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    return _order_response(_get_store_order(db, order_id, company.id))


@router.put("/orders/{order_id}/status", response_model=StoreOrderResponse)
def update_order_status(
    order_id: int,
    data: StoreOrderStatusUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("ecommerce.manage_orders")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    order = _get_store_order(db, order_id, company.id)
    if data.status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    if data.status == "shipped" and order.status not in ("paid", "processing"):
        raise HTTPException(status_code=400, detail="Order cannot be shipped in current status")
    order.status = data.status
    if data.tracking_number is not None:
        order.tracking_number = data.tracking_number
    now = _utcnow()
    if data.status == "processing":
        pass
    elif data.status == "shipped":
        order.shipped_at = now
    elif data.status == "delivered":
        order.delivered_at = now
        if order.payment_method == "cod" and order.payment_status == "unpaid":
            order.payment_status = "paid"
            order.paid_at = now
    elif data.status == "cancelled":
        order.payment_status = "unpaid" if order.payment_status == "unpaid" else order.payment_status
    db.commit()
    log_activity(db, "store_order_status_updated", user_id=user.id, email=user.email, details=f"order:{order.id}:{data.status}", ip_address=get_client_ip(request))
    return _order_response(_get_store_order(db, order_id, company.id))


@router.post("/orders/{order_id}/payment", response_model=StoreOrderResponse)
def record_order_payment(
    order_id: int,
    data: StorePaymentRecordRequest,
    request: Request,
    user: User = Depends(require_permission("ecommerce.record_payment")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    order = _get_store_order(db, order_id, company.id)
    amount = Decimal(str(data.amount if data.amount is not None else order.grand_total))
    method = data.method or order.payment_method
    db.add(StorePayment(order_id=order.id, amount=amount, method=method, status="completed", recorded_by_id=user.id))
    order.payment_status = "paid"
    order.paid_at = _utcnow()
    if order.status == "pending_payment":
        order.status = "paid"
    db.commit()
    log_activity(db, "store_payment_recorded", user_id=user.id, email=user.email, details=f"order:{order.id}", ip_address=get_client_ip(request))
    return _order_response(_get_store_order(db, order_id, company.id))


@router.get("/returns", response_model=StoreReturnListResponse)
def list_returns(user: User = Depends(require_permission("ecommerce.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    rows = (
        db.query(StoreReturn, StoreOrder)
        .join(StoreOrder, StoreOrder.id == StoreReturn.order_id)
        .filter(StoreReturn.company_id == company.id)
        .order_by(StoreReturn.requested_at.desc())
        .all()
    )
    items = [
        StoreReturnListItem(
            id=ret.id,
            return_number=ret.return_number,
            order_number=order.order_number,
            status=ret.status,
            reason=ret.reason,
            refund_amount=float(ret.refund_amount) if ret.refund_amount is not None else None,
            requested_at=ret.requested_at,
        )
        for ret, order in rows
    ]
    return StoreReturnListResponse(items=items, total=len(items))


@router.put("/returns/{return_id}", response_model=StoreReturnListItem)
def update_return(
    return_id: int,
    data: StoreReturnUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("ecommerce.manage_returns")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    ret = db.query(StoreReturn).filter(StoreReturn.id == return_id, StoreReturn.company_id == company.id).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")
    if data.status not in RETURN_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    ret.status = data.status
    if data.refund_amount is not None:
        ret.refund_amount = Decimal(str(data.refund_amount))
    if data.status in ("refunded", "closed", "rejected"):
        ret.resolved_at = _utcnow()
        ret.resolved_by_id = user.id
    order = db.query(StoreOrder).filter(StoreOrder.id == ret.order_id).first()
    if data.status == "refunded" and order:
        order.payment_status = "refunded"
        order.status = "returned"
    db.commit()
    log_activity(db, "store_return_updated", user_id=user.id, email=user.email, details=f"return:{ret.id}:{data.status}", ip_address=get_client_ip(request))
    return StoreReturnListItem(
        id=ret.id,
        return_number=ret.return_number,
        order_number=order.order_number if order else "",
        status=ret.status,
        reason=ret.reason,
        refund_amount=float(ret.refund_amount) if ret.refund_amount is not None else None,
        requested_at=ret.requested_at,
    )


# --- Public routes ---

@public_router.get("/{company_slug}/shop/info", response_model=StoreShopInfoResponse)
def public_shop_info(company_slug: str, db: Session = Depends(get_db)):
    company, _ = _resolve_company_by_slug(db, company_slug)
    settings = _get_store_settings(db, company)
    options = _shop_checkout_options(settings)
    return StoreShopInfoResponse(
        is_enabled=settings.is_enabled,
        store_name=settings.store_name or company.display_name,
        **options,
    )


@public_router.get("/{company_slug}/shop/products", response_model=StoreCatalogResponse)
def public_catalog(
    company_slug: str,
    q: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    company, _ = _resolve_company_by_slug(db, company_slug)
    settings = _get_store_settings(db, company)
    _require_store_enabled(settings)
    query = db.query(Product).filter(Product.company_id == company.id, Product.sell_online.is_(True), Product.status == "active")
    if category:
        query = query.filter(Product.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(Product.name.ilike(like))
    products = query.order_by(Product.name.asc()).all()
    categories = sorted({p.category for p in products if p.category})
    return StoreCatalogResponse(
        items=[_product_public(p) for p in products if _product_in_stock(p) or not p.inventory_tracked],
        total=len(products),
        categories=categories,
    )


@public_router.get("/{company_slug}/shop/products/{product_slug}", response_model=StoreProductPublic)
def public_product(company_slug: str, product_slug: str, db: Session = Depends(get_db)):
    company, _ = _resolve_company_by_slug(db, company_slug)
    settings = _get_store_settings(db, company)
    _require_store_enabled(settings)
    products = db.query(Product).filter(Product.company_id == company.id, Product.sell_online.is_(True), Product.status == "active").all()
    for p in products:
        if product_online_slug(p) == product_slug:
            return _product_public(p)
    raise HTTPException(status_code=404, detail="Product not found")


@public_router.get("/{company_slug}/cart", response_model=StoreCartResponse)
def public_get_cart(
    company_slug: str,
    x_cart_session: str | None = Header(default=None, alias="X-Cart-Session"),
    customer: StoreCustomer | None = Depends(optional_store_customer_dep),
    db: Session = Depends(get_db),
):
    company, _ = _resolve_company_by_slug(db, company_slug)
    settings = _get_store_settings(db, company)
    _require_store_enabled(settings)
    cart = _get_or_create_cart(db, company.id, x_cart_session, customer.id if customer else None)
    db.commit()
    return _cart_response(_load_cart(db, cart.id))


@public_router.post("/{company_slug}/cart/items", response_model=StoreCartResponse)
def public_add_cart_item(
    company_slug: str,
    data: StoreCartAddRequest,
    x_cart_session: str | None = Header(default=None, alias="X-Cart-Session"),
    customer: StoreCustomer | None = Depends(optional_store_customer_dep),
    db: Session = Depends(get_db),
):
    company, _ = _resolve_company_by_slug(db, company_slug)
    settings = _get_store_settings(db, company)
    _require_store_enabled(settings)
    product = _get_online_product(db, company.id, data.product_id)
    if not _product_in_stock(product):
        raise HTTPException(status_code=400, detail="Product out of stock")
    qty = min(max(float(data.quantity), 1), MAX_CART_QTY)
    cart = _get_or_create_cart(db, company.id, x_cart_session, customer.id if customer else None)
    existing = next((i for i in cart.items if i.product_id == product.id), None)
    if existing:
        existing.quantity = Decimal(str(min(float(existing.quantity) + qty, MAX_CART_QTY)))
    else:
        cart.items.append(
            StoreCartItem(
                product_id=product.id,
                quantity=Decimal(str(qty)),
                unit_price_snapshot=Decimal(str(product_unit_price(product))),
                gst_rate_snapshot=Decimal(str(product.gst_rate or 18)),
            )
        )
    db.commit()
    return _cart_response(_load_cart(db, cart.id))


@public_router.put("/{company_slug}/cart/items/{item_id}", response_model=StoreCartResponse)
def public_update_cart_item(
    company_slug: str,
    item_id: int,
    data: StoreCartUpdateRequest,
    x_cart_session: str | None = Header(default=None, alias="X-Cart-Session"),
    db: Session = Depends(get_db),
):
    company, _ = _resolve_company_by_slug(db, company_slug)
    settings = _get_store_settings(db, company)
    _require_store_enabled(settings)
    cart = _get_or_create_cart(db, company.id, x_cart_session)
    item = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    qty = min(max(float(data.quantity), 1), MAX_CART_QTY)
    item.quantity = Decimal(str(qty))
    db.commit()
    return _cart_response(_load_cart(db, cart.id))


@public_router.delete("/{company_slug}/cart/items/{item_id}", response_model=StoreCartResponse)
def public_remove_cart_item(
    company_slug: str,
    item_id: int,
    x_cart_session: str | None = Header(default=None, alias="X-Cart-Session"),
    db: Session = Depends(get_db),
):
    company, _ = _resolve_company_by_slug(db, company_slug)
    settings = _get_store_settings(db, company)
    _require_store_enabled(settings)
    cart = _get_or_create_cart(db, company.id, x_cart_session)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item:
        db.delete(item)
        db.commit()
    return _cart_response(_load_cart(db, cart.id))


@public_router.post("/{company_slug}/checkout", response_model=StoreCheckoutResponse)
def public_checkout(
    company_slug: str,
    data: StoreCheckoutRequest,
    request: Request,
    x_cart_session: str | None = Header(default=None, alias="X-Cart-Session"),
    customer: StoreCustomer | None = Depends(optional_store_customer_dep),
    db: Session = Depends(get_db),
):
    company, _ = _resolve_company_by_slug(db, company_slug)
    settings = _get_store_settings(db, company)
    _require_store_enabled(settings)
    if data.payment_method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="Invalid payment method")
    if STORE_CHECKOUT_MODE == "services" and data.payment_method not in SERVICE_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="Invalid payment method for online services")
    if data.payment_terms and data.payment_terms not in STORE_PAYMENT_TERMS:
        raise HTTPException(status_code=400, detail="Invalid payment terms")
    shipping_method = "pickup" if data.shipping_method == "digital" else data.shipping_method
    if shipping_method not in SHIPPING_METHODS:
        raise HTTPException(status_code=400, detail="Invalid shipping method")
    cart = _get_or_create_cart(db, company.id, x_cart_session, customer.id if customer else None)
    if not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    for item in cart.items:
        product = item.product or db.query(Product).filter(Product.id == item.product_id).first()
        if product and product.inventory_tracked and float(product.on_hand_quantity or 0) < float(item.quantity):
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")

    name = data.guest_name or (customer.name if customer else None)
    email = (data.guest_email or (customer.email if customer else None) or "").lower()
    phone = data.guest_phone or (customer.phone if customer else None)
    if not customer and not settings.guest_checkout_allowed:
        raise HTTPException(status_code=400, detail="Guest checkout is disabled")
    if not name or not email or not phone:
        raise HTTPException(status_code=400, detail="Name, email, and phone are required")

    billing = data.billing_address or data.shipping_address
    subtotal, tax_total, shipping_total, grand_total = _compute_order_totals(cart, settings, shipping_method)
    order_number = _generate_store_order_number(db, company.id, settings.order_number_prefix)
    initial_status = "pending_payment"
    payment_status = "unpaid"
    if data.payment_method == "cod":
        initial_status = "paid"
        payment_status = "unpaid"

    order = StoreOrder(
        company_id=company.id,
        order_number=order_number,
        customer_id=customer.id if customer else None,
        status=initial_status,
        payment_status=payment_status,
        subtotal=subtotal,
        tax_total=tax_total,
        shipping_total=shipping_total,
        grand_total=grand_total,
        currency=settings.currency,
        guest_name=name,
        guest_email=email,
        guest_phone=normalize_phone(phone),
        shipping_address_json=_address_dict(data.shipping_address),
        billing_address_json=_address_dict(billing),
        shipping_method=shipping_method,
        payment_method=data.payment_method,
        customer_note=_checkout_order_note(data.payment_terms, data.customer_note),
        placed_at=_utcnow(),
        paid_at=None,
    )
    db.add(order)
    db.flush()

    for item in cart.items:
        product = item.product or db.query(Product).filter(Product.id == item.product_id).first()
        line_total = Decimal(str(item.quantity)) * Decimal(str(item.unit_price_snapshot))
        db.add(
            StoreOrderItem(
                order_id=order.id,
                product_id=item.product_id,
                product_name_snapshot=product.name if product else "Product",
                quantity=item.quantity,
                unit_price=item.unit_price_snapshot,
                gst_rate=item.gst_rate_snapshot,
                line_total=line_total,
            )
        )
        if settings.inventory_reserve_on_checkout and product and product.inventory_tracked:
            product.on_hand_quantity = Decimal(str(max(float(product.on_hand_quantity or 0) - float(item.quantity), 0)))

    contact = _upsert_contact(db, company, name=name, email=email, phone=phone, gstin=data.gstin, address=_address_dict(data.shipping_address))
    order.contact_id = contact.id
    if customer and not customer.contact_id:
        customer.contact_id = contact.id

    if settings.auto_create_sales_order:
        sales_order = _create_sales_order_from_store(db, company, order, contact)
        order.sales_order_id = sales_order.id

    for item in list(cart.items):
        db.delete(item)
    db.add(
        ActivityLog(
            action="store_order_placed",
            details=f"order:{order.order_number}",
            ip_address=get_client_ip(request),
        )
    )
    db.commit()

    message = _checkout_confirmation_message(data.payment_method, data.payment_terms)
    return StoreCheckoutResponse(
        order_number=order.order_number,
        order_id=order.id,
        grand_total=float(order.grand_total),
        payment_method=order.payment_method,
        message=message,
    )


@public_router.post("/{company_slug}/account/register", response_model=StoreCustomerTokenResponse)
def public_register(company_slug: str, data: StoreCustomerRegisterRequest, db: Session = Depends(get_db)):
    company, _ = _resolve_company_by_slug(db, company_slug)
    settings = _get_store_settings(db, company)
    _require_store_enabled(settings)
    email = data.email.lower().strip()
    existing = db.query(StoreCustomer).filter(StoreCustomer.company_id == company.id, StoreCustomer.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    customer = StoreCustomer(
        company_id=company.id,
        email=email,
        phone=normalize_phone(data.phone) if data.phone else None,
        password_hash=hash_password(data.password),
        name=data.name.strip(),
    )
    db.add(customer)
    db.flush()
    contact = _upsert_contact(db, company, name=customer.name, email=customer.email, phone=customer.phone)
    customer.contact_id = contact.id
    db.commit()
    db.refresh(customer)
    return StoreCustomerTokenResponse(
        access_token=_create_store_token(customer),
        customer=StoreCustomerProfile(id=customer.id, name=customer.name, email=customer.email, phone=customer.phone, gstin=customer.gstin),
    )


@public_router.post("/{company_slug}/account/login", response_model=StoreCustomerTokenResponse)
def public_login(company_slug: str, data: StoreCustomerLoginRequest, db: Session = Depends(get_db)):
    company, _ = _resolve_company_by_slug(db, company_slug)
    settings = _get_store_settings(db, company)
    _require_store_enabled(settings)
    customer = db.query(StoreCustomer).filter(StoreCustomer.company_id == company.id, StoreCustomer.email == data.email.lower()).first()
    if not customer or not verify_password(data.password, customer.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return StoreCustomerTokenResponse(
        access_token=_create_store_token(customer),
        customer=StoreCustomerProfile(id=customer.id, name=customer.name, email=customer.email, phone=customer.phone, gstin=customer.gstin),
    )


@public_router.get("/{company_slug}/account/orders", response_model=StoreOrderListResponse)
def public_customer_orders(company_slug: str, customer: StoreCustomer = Depends(_get_store_customer), db: Session = Depends(get_db)):
    company, _ = _resolve_company_by_slug(db, company_slug)
    if customer.company_id != company.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    orders = (
        db.query(StoreOrder)
        .options(joinedload(StoreOrder.items))
        .filter(StoreOrder.company_id == company.id, StoreOrder.customer_id == customer.id)
        .order_by(StoreOrder.placed_at.desc())
        .all()
    )
    return StoreOrderListResponse(items=[_order_list_item(o) for o in orders], total=len(orders))


@public_router.get("/{company_slug}/account/orders/{order_number}", response_model=StoreOrderResponse)
def public_customer_order_detail(
    company_slug: str,
    order_number: str,
    customer: StoreCustomer = Depends(_get_store_customer),
    db: Session = Depends(get_db),
):
    company, _ = _resolve_company_by_slug(db, company_slug)
    order = (
        db.query(StoreOrder)
        .options(joinedload(StoreOrder.items))
        .filter(StoreOrder.company_id == company.id, StoreOrder.order_number == order_number, StoreOrder.customer_id == customer.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_response(order)


@public_router.post("/{company_slug}/account/orders/{order_number}/returns")
def public_request_return(
    company_slug: str,
    order_number: str,
    data: StoreReturnRequest,
    customer: StoreCustomer = Depends(_get_store_customer),
    db: Session = Depends(get_db),
):
    company, _ = _resolve_company_by_slug(db, company_slug)
    settings = _get_store_settings(db, company)
    order = (
        db.query(StoreOrder)
        .filter(StoreOrder.company_id == company.id, StoreOrder.order_number == order_number, StoreOrder.customer_id == customer.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "delivered":
        raise HTTPException(status_code=400, detail="Returns are only allowed for delivered orders")
    if order.delivered_at and (_utcnow() - order.delivered_at).days > settings.return_window_days:
        raise HTTPException(status_code=400, detail="Return window has expired")
    ret = StoreReturn(
        company_id=company.id,
        order_id=order.id,
        return_number=_generate_return_number(db, company.id),
        status="requested",
        reason=data.reason.strip(),
        items_json=data.items,
    )
    db.add(ret)
    db.commit()
    return {"detail": "Return requested", "return_number": ret.return_number}
