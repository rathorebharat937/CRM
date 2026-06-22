from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from activity import log_activity
from auth_utils import get_client_ip, get_db, require_permission
from services.notification_service import create_notification
from models import Company, Product
from models import User
from schemas import ProductCreateRequest, ProductListResponse, ProductResponse, ProductUpdateRequest

router = APIRouter(prefix="/products", tags=["products"])

PRODUCT_STATUSES = {"active", "inactive"}


def _get_company(db: Session) -> Company:
    company = db.query(Company).first()
    if not company:
        raise HTTPException(
            status_code=400,
            detail="Company must be configured before managing products",
        )
    return company


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _product_response(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        company_id=product.company_id,
        service_code=product.service_code,
        name=product.name,
        entity_type=product.entity_type,
        category=product.category,
        sub_category=product.sub_category,
        unit=product.unit,
        govt_charges=_to_float(product.govt_charges),
        our_fees=_to_float(product.our_fees),
        gst_amount=_to_float(product.gst_amount),
        total_price=_to_float(product.total_price),
        market_price=_to_float(product.market_price),
        offer_price=_to_float(product.offer_price),
        last_price=_to_float(product.last_price),
        gst_rate=_to_float(product.gst_rate) or 18,
        filing_timeline=product.filing_timeline,
        completion_timeline=product.completion_timeline,
        description=product.description,
        status=product.status,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def _get_product(db: Session, product_id: int, company_id: int) -> Product:
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.company_id == company_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/categories")
def list_categories(
    _: User = Depends(require_permission("products.view")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    rows = (
        db.query(Product.category)
        .filter(Product.company_id == company.id, Product.category.isnot(None))
        .distinct()
        .order_by(Product.category)
        .all()
    )
    return [r[0] for r in rows if r[0]]


@router.get("", response_model=ProductListResponse)
def list_products(
    search: str | None = None,
    category: str | None = None,
    entity_type: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(require_permission("products.view")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    query = db.query(Product).filter(Product.company_id == company.id)

    if status:
        query = query.filter(Product.status == status)
    if category:
        query = query.filter(Product.category == category)
    if entity_type:
        query = query.filter(Product.entity_type == entity_type)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(term),
                Product.service_code.ilike(term),
                Product.category.ilike(term),
            )
        )

    total = query.count()
    products = (
        query.order_by(Product.category, Product.name)
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return ProductListResponse(
        items=[_product_response(p) for p in products],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    _: User = Depends(require_permission("products.view")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    return _product_response(_get_product(db, product_id, company.id))


@router.post("", response_model=ProductResponse)
def create_product(
    data: ProductCreateRequest,
    request: Request,
    user: User = Depends(require_permission("products.create")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    if data.status not in PRODUCT_STATUSES:
        raise HTTPException(status_code=400, detail="Status must be active or inactive")

    if data.service_code:
        existing = (
            db.query(Product)
            .filter(
                Product.company_id == company.id,
                Product.service_code == data.service_code,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Service code already exists")

    product = Product(company_id=company.id, **data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)

    log_activity(
        db,
        "product_created",
        user_id=user.id,
        email=user.email,
        details=f"Created product {product.name}",
        ip_address=get_client_ip(request),
    )

    create_notification(db, "Product Created", f"A new service {product.name} was added.", "SUCCESS")

    return _product_response(product)


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    data: ProductUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("products.edit")),
    db: Session = Depends(get_db),
):
    company = _get_company(db)
    product = _get_product(db, product_id, company.id)

    if data.status not in PRODUCT_STATUSES:
        raise HTTPException(status_code=400, detail="Status must be active or inactive")

    if data.service_code and data.service_code != product.service_code:
        existing = (
            db.query(Product)
            .filter(
                Product.company_id == company.id,
                Product.service_code == data.service_code,
                Product.id != product.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Service code already exists")

    for key, value in data.model_dump().items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)

    log_activity(
        db,
        "product_updated",
        user_id=user.id,
        email=user.email,
        details=f"Updated product {product.name}",
        ip_address=get_client_ip(request),
    )

    return _product_response(product)
