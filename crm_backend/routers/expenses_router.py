from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from config import STAFF_ROLES
from expense_config import (
    ALLOWED_TRANSITIONS,
    APPROVAL_THRESHOLD,
    EDITABLE_STATUSES,
    EXPENSE_CATEGORIES,
    EXPENSE_CATEGORY_LABELS,
    EXPENSE_STATUS_LABELS,
    EXPENSE_STATUSES,
    PAYMENT_MODE_LABELS,
    PAYMENT_MODES,
    PROOF_REQUIRED_THRESHOLD,
)
from models import Company, Contact, Deal, Expense, ExpenseAttachment, User
from permissions import role_has_permission
from schemas import (
    ExpenseAttachmentResponse,
    ExpenseCategoryOption,
    ExpenseCreateRequest,
    ExpenseListResponse,
    ExpensePaymentModeOption,
    ExpenseRejectRequest,
    ExpenseResponse,
    ExpenseReviewRequest,
    ExpenseStatsResponse,
    ExpenseStatusOption,
    ExpenseUpdateRequest,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads" / "expenses"
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}
MAX_FILE_SIZE = 5 * 1024 * 1024




def _float(v) -> float:
    return 0.0 if v is None else float(v)


def _validate_category(category: str) -> None:
    if category not in EXPENSE_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Category must be one of: {', '.join(EXPENSE_CATEGORIES)}")


def _validate_payment_mode(mode: str) -> None:
    if mode not in PAYMENT_MODES:
        raise HTTPException(status_code=400, detail=f"Payment mode must be one of: {', '.join(PAYMENT_MODES)}")


def _validate_status(status: str) -> None:
    if status not in EXPENSE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(EXPENSE_STATUSES)}")


def _set_status(expense: Expense, new_status: str) -> None:
    _validate_status(new_status)
    allowed = ALLOWED_TRANSITIONS.get(expense.status, set())
    if new_status not in allowed and expense.status != new_status:
        raise HTTPException(status_code=400, detail=f"Cannot transition from {expense.status} to {new_status}")
    expense.status = new_status


def _generate_expense_number(db: Session, company: Company) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"EXP-{year}-"
    last = (
        db.query(Expense)
        .filter(Expense.company_id == company.id, Expense.expense_number.like(f"{prefix}%"))
        .order_by(Expense.id.desc())
        .first()
    )
    seq = 1
    if last and last.expense_number:
        try:
            seq = int(last.expense_number.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


def _requires_proof(expense: Expense) -> bool:
    return _float(expense.amount) >= PROOF_REQUIRED_THRESHOLD


def _expense_resp(expense: Expense) -> ExpenseResponse:
    total = _float(expense.amount) + _float(expense.tax_amount)
    return ExpenseResponse(
        id=expense.id,
        expense_number=expense.expense_number,
        title=expense.title,
        category=expense.category,
        vendor_name=expense.vendor_name,
        amount=_float(expense.amount),
        tax_amount=_float(expense.tax_amount),
        total_amount=total,
        currency=expense.currency,
        expense_date=expense.expense_date,
        reimbursement_due_date=expense.reimbursement_due_date,
        payment_mode=expense.payment_mode,
        status=expense.status,
        notes=expense.notes,
        receipt_reference=expense.receipt_reference,
        rejection_reason=expense.rejection_reason,
        reviewer_comments=expense.reviewer_comments,
        cost_center=expense.cost_center,
        deal_id=expense.deal_id,
        deal_title=expense.deal.title if expense.deal else None,
        contact_id=expense.contact_id,
        contact_name=expense.contact.name if expense.contact else None,
        submitted_by_id=expense.submitted_by_id,
        submitted_by_name=expense.submitted_by.name if expense.submitted_by else None,
        reviewed_by_name=expense.reviewed_by.name if expense.reviewed_by else None,
        approved_by_name=expense.approved_by.name if expense.approved_by else None,
        paid_by_name=expense.paid_by.name if expense.paid_by else None,
        submitted_at=expense.submitted_at,
        reviewed_at=expense.reviewed_at,
        approved_at=expense.approved_at,
        paid_at=expense.paid_at,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
        attachments=[
            ExpenseAttachmentResponse(
                id=a.id,
                original_filename=a.original_filename,
                content_type=a.content_type,
                file_size=a.file_size,
                uploaded_by_name=a.uploaded_by.name if a.uploaded_by else None,
                created_at=a.created_at,
            )
            for a in expense.attachments
        ],
        has_proof=len(expense.attachments) > 0,
        requires_proof=_requires_proof(expense),
    )


def _get_expense(db: Session, expense_id: int, company_id: int) -> Expense:
    expense = (
        db.query(Expense)
        .options(
            joinedload(Expense.submitted_by),
            joinedload(Expense.reviewed_by),
            joinedload(Expense.approved_by),
            joinedload(Expense.paid_by),
            joinedload(Expense.deal),
            joinedload(Expense.contact),
            joinedload(Expense.attachments).joinedload(ExpenseAttachment.uploaded_by),
        )
        .filter(Expense.id == expense_id, Expense.company_id == company_id)
        .first()
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


def _can_edit(expense: Expense, user: User, db: Session) -> bool:
    if role_has_permission(db, user.role, "expenses.edit_all"):
        return True
    if role_has_permission(db, user.role, "expenses.edit_own") and expense.submitted_by_id == user.id:
        return expense.status in EDITABLE_STATUSES
    return False


@router.get("/statuses", response_model=list[ExpenseStatusOption])
def statuses(_: User = Depends(require_permission("expenses.view"))):
    return [ExpenseStatusOption(value=s, label=EXPENSE_STATUS_LABELS[s]) for s in EXPENSE_STATUSES]


@router.get("/categories", response_model=list[ExpenseCategoryOption])
def categories(_: User = Depends(require_permission("expenses.view"))):
    return [ExpenseCategoryOption(value=c, label=EXPENSE_CATEGORY_LABELS[c]) for c in EXPENSE_CATEGORIES]


@router.get("/payment-modes", response_model=list[ExpensePaymentModeOption])
def payment_modes(_: User = Depends(require_permission("expenses.view"))):
    return [ExpensePaymentModeOption(value=m, label=PAYMENT_MODE_LABELS[m]) for m in PAYMENT_MODES]


@router.get("/stats/summary", response_model=ExpenseStatsResponse)
def stats(user: User = Depends(require_permission("expenses.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    base = db.query(Expense).filter(Expense.company_id == company.id)
    month_expenses = base.filter(Expense.expense_date >= month_start).all()

    total_spend = sum(_float(e.amount) + _float(e.tax_amount) for e in month_expenses if e.status in {"approved", "paid", "submitted", "under_review"})
    pending = base.filter(Expense.status.in_(["submitted", "under_review"])).all()
    pending_amount = sum(_float(e.amount) + _float(e.tax_amount) for e in pending)
    approved_unpaid = base.filter(Expense.status == "approved").all()
    approved_unpaid_amount = sum(_float(e.amount) + _float(e.tax_amount) for e in approved_unpaid)
    rejected_count = base.filter(Expense.status == "rejected").count()

    cat_totals: dict[str, float] = {}
    vendor_totals: dict[str, float] = {}
    for e in month_expenses:
        if e.status in {"approved", "paid"}:
            val = _float(e.amount) + _float(e.tax_amount)
            cat_totals[e.category] = cat_totals.get(e.category, 0) + val
            vendor_totals[e.vendor_name] = vendor_totals.get(e.vendor_name, 0) + val

    top_category = max(cat_totals, key=cat_totals.get) if cat_totals else None
    top_vendor = max(vendor_totals, key=vendor_totals.get) if vendor_totals else None

    return ExpenseStatsResponse(
        total_spend_month=total_spend,
        pending_approval_amount=pending_amount,
        approved_unpaid_amount=approved_unpaid_amount,
        rejected_count=rejected_count,
        top_category=EXPENSE_CATEGORY_LABELS.get(top_category, top_category) if top_category else None,
        top_vendor=top_vendor,
        by_category=[{"name": EXPENSE_CATEGORY_LABELS.get(k, k), "value": v} for k, v in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)],
        by_vendor=[{"name": k, "value": v} for k, v in sorted(vendor_totals.items(), key=lambda x: x[1], reverse=True)[:10]],
    )


@router.get("/approval-queue", response_model=ExpenseListResponse)
def approval_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("expenses.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(Expense)
        .options(
            joinedload(Expense.submitted_by),
            joinedload(Expense.attachments).joinedload(ExpenseAttachment.uploaded_by),
            joinedload(Expense.deal),
            joinedload(Expense.contact),
        )
        .filter(Expense.company_id == company.id, Expense.status.in_(["submitted", "under_review"]))
    )
    total = query.count()
    items = query.order_by(Expense.submitted_at.asc().nullslast(), Expense.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return ExpenseListResponse(items=[_expense_resp(e) for e in items], total=total, page=page, limit=limit)


@router.get("", response_model=ExpenseListResponse)
def list_expenses(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    category: str | None = None,
    payment_mode: str | None = None,
    mine: bool = False,
    search: str | None = None,
    user: User = Depends(require_permission("expenses.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    query = (
        db.query(Expense)
        .options(
            joinedload(Expense.submitted_by),
            joinedload(Expense.attachments).joinedload(ExpenseAttachment.uploaded_by),
            joinedload(Expense.deal),
            joinedload(Expense.contact),
        )
        .filter(Expense.company_id == company.id)
    )
    if mine:
        query = query.filter(Expense.submitted_by_id == user.id)
    if status:
        _validate_status(status)
        query = query.filter(Expense.status == status)
    if category:
        query = query.filter(Expense.category == category)
    if payment_mode:
        query = query.filter(Expense.payment_mode == payment_mode)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            Expense.title.ilike(term),
            Expense.vendor_name.ilike(term),
            Expense.expense_number.ilike(term),
        ))
    total = query.count()
    items = query.order_by(Expense.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return ExpenseListResponse(items=[_expense_resp(e) for e in items], total=total, page=page, limit=limit)


@router.post("", response_model=ExpenseResponse, status_code=201)
def create_expense(
    payload: ExpenseCreateRequest,
    request: Request,
    user: User = Depends(require_permission("expenses.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    _validate_category(payload.category)
    _validate_payment_mode(payload.payment_mode)
    if payload.deal_id:
        deal = db.query(Deal).filter(Deal.id == payload.deal_id, Deal.company_id == company.id).first()
        if not deal:
            raise HTTPException(status_code=404, detail="Deal not found")
    if payload.contact_id:
        contact = db.query(Contact).filter(Contact.id == payload.contact_id, Contact.company_id == company.id).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

    expense = Expense(
        company_id=company.id,
        submitted_by_id=user.id,
        title=payload.title.strip(),
        category=payload.category,
        vendor_name=payload.vendor_name.strip(),
        amount=payload.amount,
        tax_amount=payload.tax_amount,
        currency=payload.currency,
        expense_date=payload.expense_date,
        reimbursement_due_date=payload.reimbursement_due_date,
        payment_mode=payload.payment_mode,
        notes=payload.notes,
        receipt_reference=payload.receipt_reference,
        cost_center=payload.cost_center,
        deal_id=payload.deal_id,
        contact_id=payload.contact_id,
        status="draft",
    )
    db.add(expense)
    db.commit()
    expense = _get_expense(db, expense.id, company.id)
    log_activity(db, "expense_created", user_id=user.id, email=user.email, details=expense.title, ip_address=get_client_ip(request))
    return _expense_resp(expense)


@router.get("/{expense_id}", response_model=ExpenseResponse)
def get_expense(expense_id: int, user: User = Depends(require_permission("expenses.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    return _expense_resp(_get_expense(db, expense_id, company.id))


@router.put("/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    expense_id: int,
    payload: ExpenseUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("expenses.edit_own")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    expense = _get_expense(db, expense_id, company.id)
    if not _can_edit(expense, user, db):
        raise HTTPException(status_code=403, detail="Not allowed to edit this expense")
    _validate_category(payload.category)
    _validate_payment_mode(payload.payment_mode)

    expense.title = payload.title.strip()
    expense.category = payload.category
    expense.vendor_name = payload.vendor_name.strip()
    expense.amount = payload.amount
    expense.tax_amount = payload.tax_amount
    expense.currency = payload.currency
    expense.expense_date = payload.expense_date
    expense.reimbursement_due_date = payload.reimbursement_due_date
    expense.payment_mode = payload.payment_mode
    expense.notes = payload.notes
    expense.receipt_reference = payload.receipt_reference
    expense.cost_center = payload.cost_center
    expense.deal_id = payload.deal_id
    expense.contact_id = payload.contact_id
    if expense.status == "rejected":
        expense.rejection_reason = None
        expense.reviewer_comments = None
        expense.status = "draft"
    db.commit()
    expense = _get_expense(db, expense.id, company.id)
    log_activity(db, "expense_updated", user_id=user.id, email=user.email, details=expense.title, ip_address=get_client_ip(request))
    return _expense_resp(expense)


@router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    user: User = Depends(require_permission("expenses.delete")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    expense = _get_expense(db, expense_id, company.id)
    if expense.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft expenses can be deleted")
    if not _can_edit(expense, user, db):
        raise HTTPException(status_code=403, detail="Not allowed to delete this expense")
    db.delete(expense)
    db.commit()
    return {"ok": True}


@router.post("/{expense_id}/submit", response_model=ExpenseResponse)
def submit_expense(
    expense_id: int,
    request: Request,
    user: User = Depends(require_permission("expenses.submit")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    expense = _get_expense(db, expense_id, company.id)
    if expense.submitted_by_id != user.id and not role_has_permission(db, user.role, "expenses.edit_all"):
        raise HTTPException(status_code=403, detail="Only the submitter can submit this expense")
    if expense.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Only draft or rejected expenses can be submitted")
    if _requires_proof(expense) and not expense.attachments:
        raise HTTPException(status_code=400, detail="Proof attachment is required for this expense amount")

    if not expense.expense_number:
        expense.expense_number = _generate_expense_number(db, company)
    expense.submitted_at = datetime.now(timezone.utc)
    _set_status(expense, "submitted")
    if _float(expense.amount) >= APPROVAL_THRESHOLD:
        _set_status(expense, "under_review")
    db.commit()
    expense = _get_expense(db, expense.id, company.id)
    log_activity(db, "expense_submitted", user_id=user.id, email=user.email, details=expense.expense_number, ip_address=get_client_ip(request))
    return _expense_resp(expense)


@router.post("/{expense_id}/approve", response_model=ExpenseResponse)
def approve_expense(
    expense_id: int,
    payload: ExpenseReviewRequest,
    request: Request,
    user: User = Depends(require_permission("expenses.approve")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    expense = _get_expense(db, expense_id, company.id)
    if expense.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=400, detail="Expense is not pending approval")
    expense.reviewed_by_id = user.id
    expense.approved_by_id = user.id
    expense.reviewed_at = datetime.now(timezone.utc)
    expense.approved_at = datetime.now(timezone.utc)
    expense.reviewer_comments = payload.comments
    _set_status(expense, "approved")
    db.commit()
    expense = _get_expense(db, expense.id, company.id)
    log_activity(db, "expense_approved", user_id=user.id, email=user.email, details=expense.expense_number, ip_address=get_client_ip(request))
    return _expense_resp(expense)


@router.post("/{expense_id}/reject", response_model=ExpenseResponse)
def reject_expense(
    expense_id: int,
    payload: ExpenseRejectRequest,
    request: Request,
    user: User = Depends(require_permission("expenses.reject")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    expense = _get_expense(db, expense_id, company.id)
    if expense.status not in {"submitted", "under_review"}:
        raise HTTPException(status_code=400, detail="Expense is not pending approval")
    expense.reviewed_by_id = user.id
    expense.reviewed_at = datetime.now(timezone.utc)
    expense.rejection_reason = payload.reason.strip()
    expense.reviewer_comments = payload.comments
    _set_status(expense, "rejected")
    db.commit()
    expense = _get_expense(db, expense.id, company.id)
    log_activity(db, "expense_rejected", user_id=user.id, email=user.email, details=expense.expense_number, ip_address=get_client_ip(request))
    return _expense_resp(expense)


@router.post("/{expense_id}/mark-paid", response_model=ExpenseResponse)
def mark_paid(
    expense_id: int,
    request: Request,
    user: User = Depends(require_permission("expenses.mark_paid")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    expense = _get_expense(db, expense_id, company.id)
    if expense.status != "approved":
        raise HTTPException(status_code=400, detail="Only approved expenses can be marked paid")
    expense.paid_by_id = user.id
    expense.paid_at = datetime.now(timezone.utc)
    _set_status(expense, "paid")
    db.commit()
    expense = _get_expense(db, expense.id, company.id)
    log_activity(db, "expense_marked_paid", user_id=user.id, email=user.email, details=expense.expense_number, ip_address=get_client_ip(request))
    return _expense_resp(expense)


@router.post("/{expense_id}/cancel", response_model=ExpenseResponse)
def cancel_expense(
    expense_id: int,
    request: Request,
    user: User = Depends(require_permission("expenses.edit_own")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    expense = _get_expense(db, expense_id, company.id)
    if expense.status in {"paid", "cancelled"}:
        raise HTTPException(status_code=400, detail="Expense cannot be cancelled")
    if expense.submitted_by_id != user.id and not role_has_permission(db, user.role, "expenses.edit_all"):
        raise HTTPException(status_code=403, detail="Not allowed to cancel this expense")
    _set_status(expense, "cancelled")
    db.commit()
    expense = _get_expense(db, expense.id, company.id)
    log_activity(db, "expense_cancelled", user_id=user.id, email=user.email, details=expense.expense_number or expense.title, ip_address=get_client_ip(request))
    return _expense_resp(expense)


@router.post("/{expense_id}/attachments", response_model=ExpenseAttachmentResponse)
async def upload_attachment(
    expense_id: int,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("expenses.create")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    expense = _get_expense(db, expense_id, company.id)
    if expense.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=400, detail="Cannot add proof to a non-editable expense")

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="File type must be JPG, PNG, WEBP, or PDF")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size must be under 5MB")

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "proof").suffix or ".bin"
    stored = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_ROOT / stored
    path.write_bytes(data)

    attachment = ExpenseAttachment(
        expense_id=expense.id,
        uploaded_by_id=user.id,
        original_filename=file.filename or stored,
        stored_filename=stored,
        content_type=content_type,
        file_size=len(data),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    log_activity(db, "expense_attachment_uploaded", user_id=user.id, email=user.email, details=attachment.original_filename, ip_address=get_client_ip(request))
    return ExpenseAttachmentResponse(
        id=attachment.id,
        original_filename=attachment.original_filename,
        content_type=attachment.content_type,
        file_size=attachment.file_size,
        uploaded_by_name=user.name,
        created_at=attachment.created_at,
    )


@router.get("/{expense_id}/attachments/{attachment_id}/download")
def download_attachment(
    expense_id: int,
    attachment_id: int,
    user: User = Depends(require_permission("expenses.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    expense = _get_expense(db, expense_id, company.id)
    attachment = next((a for a in expense.attachments if a.id == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = UPLOAD_ROOT / attachment.stored_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(path, filename=attachment.original_filename, media_type=attachment.content_type or "application/octet-stream")
