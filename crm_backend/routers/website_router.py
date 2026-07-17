"""Website Builder — authenticated and public API routes."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from activity import log_activity
from tenant_utils import get_current_company
from auth_utils import get_client_ip, get_db, require_permission
from company_branding import build_company_branding
from config import FRONTEND_URL
from lead_config import LEAD_SOURCES, normalize_phone
from models import (
    Company,
    Lead,
    Product,
    SystemSetting,
    User,
    WebsiteBlogPost,
    WebsiteForm,
    WebsiteFormSubmission,
    WebsitePage,
    WebsitePageView,
    WebsiteSettings,
)
from website_config import (
    BLOG_STATUSES,
    DEFAULT_CONTACT_FORM_FIELDS,
    FORM_RATE_LIMIT_PER_HOUR,
    PAGE_STATUSES,
    PAGE_TEMPLATES,
    PAGE_TYPE_LABELS,
    PAGE_TYPES,
    SECTION_LABELS,
    SECTION_TYPES,
    STATUS_LABELS,
    WEBSITE_LEAD_SOURCE,
    FORM_FIELD_TYPES,
    LEAD_MAP_FIELDS,
    new_preview_token,
    normalize_slug,
    sanitize_html,
    validate_slug,
)
from website_schemas import (
    PublicBlogIndexResponse,
    PublicBlogPostResponse,
    PublicCompanyBranding,
    PublicFormSubmitRequest,
    PublicFormSubmitResponse,
    PublicPageResponse,
    WebsiteBlogCreateRequest,
    WebsiteBlogListItem,
    WebsiteBlogListResponse,
    WebsiteBlogResponse,
    WebsiteBlogUpdateRequest,
    WebsiteDashboardResponse,
    WebsiteFormCreateRequest,
    WebsiteFormListItem,
    WebsiteFormListResponse,
    WebsiteFormResponse,
    WebsiteFormUpdateRequest,
    WebsiteMetaResponse,
    WebsiteOption,
    WebsitePageCreateRequest,
    WebsitePageListItem,
    WebsitePageListResponse,
    WebsitePageResponse,
    WebsitePageUpdateRequest,
    WebsiteSettingsResponse,
    WebsiteSettingsUpdateRequest,
    WebsiteSubmissionSummary,
)

router = APIRouter(prefix="/website", tags=["website"])
public_router = APIRouter(prefix="/public", tags=["public-website"])

_form_rate_limit: dict[str, list[datetime]] = defaultdict(list)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)




def _get_settings(db: Session, company: Company) -> WebsiteSettings:
    settings = db.query(WebsiteSettings).filter(WebsiteSettings.company_id == company.id).first()
    if settings:
        return settings
    base_slug = normalize_slug(company.display_name or company.legal_name or f"company-{company.id}")
    slug = base_slug or f"company-{company.id}"
    suffix = 0
    while db.query(WebsiteSettings).filter(WebsiteSettings.company_slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}" if base_slug else f"company-{company.id}-{suffix}"
    settings = WebsiteSettings(company_id=company.id, company_slug=slug)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _public_path(company_slug: str, *parts: str) -> str:
    base = f"/s/{company_slug}"
    if not parts:
        return base
    return f"{base}/{'/'.join(parts)}"


def _public_url(company_slug: str, *parts: str) -> str:
    return f"{FRONTEND_URL.rstrip('/')}{_public_path(company_slug, *parts)}"


def _view_count_7d(db: Session, *, company_id: int, page_id: int | None = None, post_id: int | None = None) -> int:
    since = _utcnow() - timedelta(days=7)
    q = db.query(func.count(WebsitePageView.id)).filter(
        WebsitePageView.company_id == company_id,
        WebsitePageView.viewed_at >= since,
    )
    if page_id is not None:
        q = q.filter(WebsitePageView.page_id == page_id)
    if post_id is not None:
        q = q.filter(WebsitePageView.post_id == post_id)
    return int(q.scalar() or 0)


def _public_branding(company: Company, settings: SystemSetting | None) -> PublicCompanyBranding:
    branding = build_company_branding(company, settings)
    return PublicCompanyBranding(
        display_name=branding.display_name,
        legal_name=branding.legal_name,
        email=branding.email,
        phone=branding.phone,
        website=branding.website,
        address_line1=branding.address_line1,
        address_line2=branding.address_line2,
        city=branding.city,
        state=branding.state,
        pincode=branding.pincode,
        country=branding.country,
        gstin=branding.gstin,
        logo_filename=branding.logo_filename,
    )


def _page_response(
    db: Session,
    page: WebsitePage,
    site: WebsiteSettings,
) -> WebsitePageResponse:
    return WebsitePageResponse(
        id=page.id,
        title=page.title,
        slug=page.slug,
        page_type=page.page_type,
        status=page.status,
        seo_title=page.seo_title,
        seo_description=page.seo_description,
        sections_json=page.sections_json or [],
        product_id=page.product_id,
        is_home=page.is_home,
        preview_token=page.preview_token,
        published_at=page.published_at,
        created_at=page.created_at,
        updated_at=page.updated_at,
        public_url=_public_url(site.company_slug, page.slug) if page.status == "published" else None,
        view_count_7d=_view_count_7d(db, company_id=page.company_id, page_id=page.id),
    )


def _form_response(form: WebsiteForm, submission_count: int = 0) -> WebsiteFormResponse:
    return WebsiteFormResponse(
        id=form.id,
        name=form.name,
        slug=form.slug,
        fields_json=form.fields_json or [],
        success_message=form.success_message,
        redirect_url=form.redirect_url,
        is_active=form.is_active,
        created_at=form.created_at,
        updated_at=form.updated_at,
    )


def _blog_response(db: Session, post: WebsiteBlogPost) -> WebsiteBlogResponse:
    author_name = post.author.name if post.author else None
    return WebsiteBlogResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        excerpt=post.excerpt,
        body_html=post.body_html or "",
        cover_image_url=post.cover_image_url,
        author_id=post.author_id,
        author_name=author_name,
        status=post.status,
        seo_title=post.seo_title,
        seo_description=post.seo_description,
        tags=post.tags or [],
        preview_token=post.preview_token,
        published_at=post.published_at,
        created_at=post.created_at,
        updated_at=post.updated_at,
        view_count_7d=_view_count_7d(db, company_id=post.company_id, post_id=post.id),
    )


def _get_page(db: Session, page_id: int, company_id: int) -> WebsitePage:
    page = (
        db.query(WebsitePage)
        .filter(WebsitePage.id == page_id, WebsitePage.company_id == company_id)
        .first()
    )
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


def _get_form(db: Session, form_id: int, company_id: int) -> WebsiteForm:
    form = (
        db.query(WebsiteForm)
        .filter(WebsiteForm.id == form_id, WebsiteForm.company_id == company_id)
        .first()
    )
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    return form


def _get_blog_post(db: Session, post_id: int, company_id: int) -> WebsiteBlogPost:
    post = (
        db.query(WebsiteBlogPost)
        .filter(WebsiteBlogPost.id == post_id, WebsiteBlogPost.company_id == company_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    return post


def _ensure_unique_slug(db: Session, model, company_id: int, slug: str, exclude_id: int | None = None) -> None:
    q = db.query(model).filter(model.company_id == company_id, model.slug == slug)
    if exclude_id:
        q = q.filter(model.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=400, detail=f"Slug '{slug}' is already in use")


def _ensure_unique_company_slug(db: Session, slug: str, exclude_id: int | None = None) -> None:
    q = db.query(WebsiteSettings).filter(WebsiteSettings.company_slug == slug)
    if exclude_id:
        q = q.filter(WebsiteSettings.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=400, detail=f"Company slug '{slug}' is already in use")


def _validate_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for section in sections:
        section_type = section.get("type")
        if section_type not in SECTION_TYPES:
            raise HTTPException(status_code=400, detail=f"Unknown section type: {section_type}")
        props = section.get("props") or {}
        if section_type == "rich_text" and props.get("body"):
            props = {**props, "body": sanitize_html(str(props["body"]))}
        cleaned.append(
            {
                "id": section.get("id") or str(uuid.uuid4()),
                "type": section_type,
                "props": props,
            }
        )
    return cleaned


def _apply_template_sections(sections: list[dict[str, Any]], company_id: int, db: Session) -> list[dict[str, Any]]:
    default_form = (
        db.query(WebsiteForm)
        .filter(WebsiteForm.company_id == company_id, WebsiteForm.is_active.is_(True))
        .order_by(WebsiteForm.id.asc())
        .first()
    )
    result = []
    for section in sections:
        props = dict(section.get("props") or {})
        if section.get("type") == "form_embed" and props.get("form_id") is None and default_form:
            props["form_id"] = default_form.id
        result.append({**section, "id": section.get("id") or str(uuid.uuid4()), "props": props})
    return result


def _log_page_view(
    db: Session,
    *,
    company_id: int,
    path: str,
    page_id: int | None = None,
    post_id: int | None = None,
    session_id: str | None = None,
) -> None:
    db.add(
        WebsitePageView(
            company_id=company_id,
            page_id=page_id,
            post_id=post_id,
            path=path,
            session_id=session_id,
        )
    )
    db.commit()


def _check_form_rate_limit(ip: str | None) -> None:
    if not ip:
        return
    now = _utcnow()
    window_start = now - timedelta(hours=1)
    hits = [t for t in _form_rate_limit[ip] if t >= window_start]
    if len(hits) >= FORM_RATE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many submissions. Please try again later.")
    hits.append(now)
    _form_rate_limit[ip] = hits


def _create_lead_from_submission(
    db: Session,
    *,
    company: Company,
    form: WebsiteForm,
    payload: dict[str, Any],
    site: WebsiteSettings,
    utm_source: str | None,
    utm_medium: str | None,
    utm_campaign: str | None,
) -> Lead:
    lead_data: dict[str, Any] = {
        "name": "Website enquiry",
        "source": WEBSITE_LEAD_SOURCE,
        "status": "open",
        "notes": "",
    }
    extra_notes: list[str] = []
    for field in form.fields_json or []:
        key = field.get("key")
        map_to = field.get("map_to")
        if not key or key == "website_trap":
            continue
        value = payload.get(key)
        if value in (None, ""):
            continue
        if map_to in ("name", "email", "phone", "organization_name", "requirement", "notes"):
            if map_to == "phone":
                lead_data[map_to] = normalize_phone(value)
            else:
                lead_data[map_to] = str(value).strip()
        elif field.get("label"):
            extra_notes.append(f"{field['label']}: {value}")

    if not lead_data.get("email") and not lead_data.get("phone"):
        raise HTTPException(status_code=400, detail="Email or phone is required")

    if extra_notes:
        lead_data["notes"] = "\n".join(filter(None, [lead_data.get("notes"), *extra_notes]))

    if utm_source or utm_medium or utm_campaign:
        utm_note = " | ".join(
            x
            for x in [
                f"utm_source={utm_source}" if utm_source else None,
                f"utm_medium={utm_medium}" if utm_medium else None,
                f"utm_campaign={utm_campaign}" if utm_campaign else None,
            ]
            if x
        )
        lead_data["notes"] = "\n".join(filter(None, [lead_data.get("notes"), f"Campaign: {utm_note}"]))

    lead_data["notes"] = "\n".join(filter(None, [lead_data.get("notes"), f"Form: {form.name}"]))

    if site.default_lead_assignee_id:
        assignee = (
            db.query(User)
            .filter(User.id == site.default_lead_assignee_id, User.company_id == company.id)
            .first()
        )
        if assignee:
            lead_data["assigned_to_id"] = assignee.id

    if WEBSITE_LEAD_SOURCE not in LEAD_SOURCES:
        lead_data["source"] = "Other"

    lead = Lead(
        company_id=company.id,
        name=lead_data.get("name") or "Website enquiry",
        email=lead_data.get("email"),
        phone=lead_data.get("phone"),
        organization_name=lead_data.get("organization_name"),
        requirement=lead_data.get("requirement"),
        notes=lead_data.get("notes"),
        source=lead_data["source"],
        status=lead_data["status"],
        assigned_to_id=lead_data.get("assigned_to_id"),
        registered_at=_utcnow(),
    )
    db.add(lead)
    db.flush()
    return lead


def _resolve_company_by_slug(db: Session, company_slug: str) -> tuple[Company, WebsiteSettings]:
    site = db.query(WebsiteSettings).filter(WebsiteSettings.company_slug == company_slug).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    company = db.query(Company).filter(Company.id == site.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Site not found")
    return company, site


@router.get("/meta", response_model=WebsiteMetaResponse)
def website_meta(user: User = Depends(require_permission("website.view")), db: Session = Depends(get_db)):
    get_current_company(db, user)
    return WebsiteMetaResponse(
        page_types=[WebsiteOption(value=k, label=v) for k, v in PAGE_TYPE_LABELS.items()],
        page_statuses=[WebsiteOption(value=k, label=v) for k, v in STATUS_LABELS.items()],
        section_types=[WebsiteOption(value=k, label=v) for k, v in SECTION_LABELS.items()],
        templates=[{"key": k, **v} for k, v in PAGE_TEMPLATES.items()],
        form_field_types=FORM_FIELD_TYPES,
        lead_map_fields=LEAD_MAP_FIELDS,
    )


@router.get("/dashboard", response_model=WebsiteDashboardResponse)
def website_dashboard(user: User = Depends(require_permission("website.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    site = _get_settings(db, company)
    since = _utcnow() - timedelta(days=7)
    published_pages = db.query(func.count(WebsitePage.id)).filter(
        WebsitePage.company_id == company.id, WebsitePage.status == "published"
    ).scalar()
    draft_pages = db.query(func.count(WebsitePage.id)).filter(
        WebsitePage.company_id == company.id, WebsitePage.status == "draft"
    ).scalar()
    blog_posts = db.query(func.count(WebsiteBlogPost.id)).filter(
        WebsiteBlogPost.company_id == company.id
    ).scalar()
    submissions_7d = db.query(func.count(WebsiteFormSubmission.id)).filter(
        WebsiteFormSubmission.company_id == company.id,
        WebsiteFormSubmission.created_at >= since,
    ).scalar()
    recent = (
        db.query(WebsiteFormSubmission, WebsiteForm)
        .join(WebsiteForm, WebsiteForm.id == WebsiteFormSubmission.form_id)
        .filter(WebsiteFormSubmission.company_id == company.id)
        .order_by(WebsiteFormSubmission.created_at.desc())
        .limit(8)
        .all()
    )
    recent_submissions = []
    for sub, form in recent:
        preview = ""
        payload = sub.payload_json or {}
        preview = str(payload.get("name") or payload.get("email") or payload.get("phone") or "Submission")
        recent_submissions.append(
            WebsiteSubmissionSummary(
                id=sub.id,
                form_name=form.name,
                lead_id=sub.lead_id,
                created_at=sub.created_at,
                preview=preview,
            )
        )
    return WebsiteDashboardResponse(
        published_pages=int(published_pages or 0),
        draft_pages=int(draft_pages or 0),
        blog_posts=int(blog_posts or 0),
        form_submissions_7d=int(submissions_7d or 0),
        company_slug=site.company_slug,
        public_url=_public_url(site.company_slug),
        recent_submissions=recent_submissions,
    )


@router.get("/settings", response_model=WebsiteSettingsResponse)
def get_website_settings(user: User = Depends(require_permission("website.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    site = _get_settings(db, company)
    return WebsiteSettingsResponse(
        company_slug=site.company_slug,
        home_page_id=site.home_page_id,
        default_lead_assignee_id=site.default_lead_assignee_id,
        public_base_path=_public_path(site.company_slug),
    )


@router.put("/settings", response_model=WebsiteSettingsResponse)
def update_website_settings(
    data: WebsiteSettingsUpdateRequest,
    user: User = Depends(require_permission("website.manage")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    site = _get_settings(db, company)
    if data.company_slug is not None:
        slug = normalize_slug(data.company_slug)
        try:
            validate_slug(slug)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _ensure_unique_company_slug(db, slug, site.id)
        site.company_slug = slug
    if data.home_page_id is not None:
        page = _get_page(db, data.home_page_id, company.id)
        site.home_page_id = page.id
        db.query(WebsitePage).filter(WebsitePage.company_id == company.id).update({"is_home": False})
        page.is_home = True
    if data.default_lead_assignee_id is not None:
        assignee = (
            db.query(User).filter(User.id == data.default_lead_assignee_id, User.company_id == company.id).first()
        )
        if not assignee:
            raise HTTPException(status_code=400, detail="Invalid default lead assignee")
        site.default_lead_assignee_id = assignee.id
    db.commit()
    db.refresh(site)
    return WebsiteSettingsResponse(
        company_slug=site.company_slug,
        home_page_id=site.home_page_id,
        default_lead_assignee_id=site.default_lead_assignee_id,
        public_base_path=_public_path(site.company_slug),
    )


@router.get("/pages", response_model=WebsitePageListResponse)
def list_pages(
    status: str | None = None,
    page_type: str | None = None,
    user: User = Depends(require_permission("website.view")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    site = _get_settings(db, company)
    q = db.query(WebsitePage).filter(WebsitePage.company_id == company.id)
    if status:
        q = q.filter(WebsitePage.status == status)
    if page_type:
        q = q.filter(WebsitePage.page_type == page_type)
    pages = q.order_by(WebsitePage.updated_at.desc()).all()
    items = [
        WebsitePageListItem(
            id=p.id,
            title=p.title,
            slug=p.slug,
            page_type=p.page_type,
            status=p.status,
            is_home=p.is_home,
            published_at=p.published_at,
            updated_at=p.updated_at,
            view_count_7d=_view_count_7d(db, company_id=company.id, page_id=p.id),
            public_url=_public_url(site.company_slug, p.slug) if p.status == "published" else None,
        )
        for p in pages
    ]
    return WebsitePageListResponse(items=items, total=len(items))


@router.post("/pages", response_model=WebsitePageResponse)
def create_page(
    data: WebsitePageCreateRequest,
    user: User = Depends(require_permission("website.manage")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    site = _get_settings(db, company)
    if data.page_type not in PAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid page type")
    slug = normalize_slug(data.slug or data.title)
    try:
        validate_slug(slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _ensure_unique_slug(db, WebsitePage, company.id, slug)
    sections = data.sections_json or []
    if data.template_key:
        template = PAGE_TEMPLATES.get(data.template_key)
        if not template:
            raise HTTPException(status_code=400, detail="Unknown template")
        sections = _apply_template_sections(template["sections"], company.id, db)
        page_type = template["page_type"]
    else:
        page_type = data.page_type
        sections = _validate_sections(sections)
    page = WebsitePage(
        company_id=company.id,
        title=data.title.strip(),
        slug=slug,
        page_type=page_type,
        status="draft",
        seo_title=data.seo_title,
        seo_description=data.seo_description,
        sections_json=sections,
        product_id=data.product_id,
        preview_token=new_preview_token(),
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    log_activity(db, "website_page_created", user_id=user.id, email=user.email, details=f"page:{page.id}")
    return _page_response(db, page, site)


@router.get("/pages/{page_id}", response_model=WebsitePageResponse)
def get_page(page_id: int, user: User = Depends(require_permission("website.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    site = _get_settings(db, company)
    page = _get_page(db, page_id, company.id)
    return _page_response(db, page, site)


@router.put("/pages/{page_id}", response_model=WebsitePageResponse)
def update_page(
    page_id: int,
    data: WebsitePageUpdateRequest,
    user: User = Depends(require_permission("website.manage")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    site = _get_settings(db, company)
    page = _get_page(db, page_id, company.id)
    if data.title is not None:
        page.title = data.title.strip()
    if data.slug is not None:
        slug = normalize_slug(data.slug)
        try:
            validate_slug(slug)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _ensure_unique_slug(db, WebsitePage, company.id, slug, page.id)
        page.slug = slug
    if data.page_type is not None:
        if data.page_type not in PAGE_TYPES:
            raise HTTPException(status_code=400, detail="Invalid page type")
        page.page_type = data.page_type
    if data.seo_title is not None:
        page.seo_title = data.seo_title
    if data.seo_description is not None:
        page.seo_description = data.seo_description
    if data.sections_json is not None:
        page.sections_json = _validate_sections(data.sections_json)
    if data.product_id is not None:
        page.product_id = data.product_id
    if data.is_home is True:
        db.query(WebsitePage).filter(WebsitePage.company_id == company.id).update({"is_home": False})
        page.is_home = True
        site.home_page_id = page.id
    elif data.is_home is False:
        page.is_home = False
        if site.home_page_id == page.id:
            site.home_page_id = None
    page.updated_by_id = user.id
    if not page.preview_token:
        page.preview_token = new_preview_token()
    db.commit()
    db.refresh(page)
    return _page_response(db, page, site)


@router.post("/pages/{page_id}/publish", response_model=WebsitePageResponse)
def publish_page(
    page_id: int,
    request: Request,
    user: User = Depends(require_permission("website.publish")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    site = _get_settings(db, company)
    page = _get_page(db, page_id, company.id)
    if not page.sections_json:
        raise HTTPException(status_code=400, detail="Add at least one section before publishing")
    page.status = "published"
    page.published_at = _utcnow()
    if not page.preview_token:
        page.preview_token = new_preview_token()
    db.commit()
    db.refresh(page)
    log_activity(
        db,
        "website_page_published",
        user_id=user.id,
        email=user.email,
        details=f"page:{page.id}",
        ip_address=get_client_ip(request),
    )
    return _page_response(db, page, site)


@router.post("/pages/{page_id}/unpublish", response_model=WebsitePageResponse)
def unpublish_page(
    page_id: int,
    request: Request,
    user: User = Depends(require_permission("website.publish")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    site = _get_settings(db, company)
    page = _get_page(db, page_id, company.id)
    page.status = "draft"
    db.commit()
    db.refresh(page)
    log_activity(
        db,
        "website_page_unpublished",
        user_id=user.id,
        email=user.email,
        details=f"page:{page.id}",
        ip_address=get_client_ip(request),
    )
    return _page_response(db, page, site)


@router.delete("/pages/{page_id}")
def delete_page(
    page_id: int,
    user: User = Depends(require_permission("website.delete")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    site = _get_settings(db, company)
    page = _get_page(db, page_id, company.id)
    if page.status == "published":
        page.status = "archived"
        db.commit()
        return {"detail": "Page archived"}
    db.delete(page)
    if site.home_page_id == page.id:
        site.home_page_id = None
    db.commit()
    return {"detail": "Page deleted"}


@router.get("/forms", response_model=WebsiteFormListResponse)
def list_forms(user: User = Depends(require_permission("website.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    forms = db.query(WebsiteForm).filter(WebsiteForm.company_id == company.id).order_by(WebsiteForm.updated_at.desc()).all()
    items = []
    for form in forms:
        count = db.query(func.count(WebsiteFormSubmission.id)).filter(WebsiteFormSubmission.form_id == form.id).scalar()
        items.append(
            WebsiteFormListItem(
                id=form.id,
                name=form.name,
                slug=form.slug,
                is_active=form.is_active,
                submission_count=int(count or 0),
                updated_at=form.updated_at,
            )
        )
    return WebsiteFormListResponse(items=items, total=len(items))


@router.post("/forms", response_model=WebsiteFormResponse)
def create_form(
    data: WebsiteFormCreateRequest,
    user: User = Depends(require_permission("website.forms")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    slug = normalize_slug(data.slug or data.name)
    try:
        validate_slug(slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _ensure_unique_slug(db, WebsiteForm, company.id, slug)
    form = WebsiteForm(
        company_id=company.id,
        name=data.name.strip(),
        slug=slug,
        fields_json=data.fields_json or DEFAULT_CONTACT_FORM_FIELDS,
        success_message=data.success_message or "Thank you! We will contact you shortly.",
        redirect_url=data.redirect_url,
        is_active=data.is_active,
    )
    db.add(form)
    db.commit()
    db.refresh(form)
    log_activity(db, "website_form_created", user_id=user.id, email=user.email, details=f"form:{form.id}")
    return _form_response(form)


@router.get("/forms/{form_id}", response_model=WebsiteFormResponse)
def get_form(form_id: int, user: User = Depends(require_permission("website.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    form = _get_form(db, form_id, company.id)
    return _form_response(form)


@router.put("/forms/{form_id}", response_model=WebsiteFormResponse)
def update_form(
    form_id: int,
    data: WebsiteFormUpdateRequest,
    user: User = Depends(require_permission("website.forms")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    form = _get_form(db, form_id, company.id)
    if data.name is not None:
        form.name = data.name.strip()
    if data.slug is not None:
        slug = normalize_slug(data.slug)
        try:
            validate_slug(slug)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _ensure_unique_slug(db, WebsiteForm, company.id, slug, form.id)
        form.slug = slug
    if data.fields_json is not None:
        form.fields_json = data.fields_json
    if data.success_message is not None:
        form.success_message = data.success_message
    if data.redirect_url is not None:
        form.redirect_url = data.redirect_url
    if data.is_active is not None:
        form.is_active = data.is_active
    db.commit()
    db.refresh(form)
    log_activity(db, "website_form_updated", user_id=user.id, email=user.email, details=f"form:{form.id}")
    return _form_response(form)


@router.get("/blog", response_model=WebsiteBlogListResponse)
def list_blog_posts(user: User = Depends(require_permission("website.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    posts = (
        db.query(WebsiteBlogPost)
        .filter(WebsiteBlogPost.company_id == company.id)
        .order_by(WebsiteBlogPost.updated_at.desc())
        .all()
    )
    items = [
        WebsiteBlogListItem(
            id=p.id,
            title=p.title,
            slug=p.slug,
            status=p.status,
            author_name=p.author.name if p.author else None,
            published_at=p.published_at,
            updated_at=p.updated_at,
            view_count_7d=_view_count_7d(db, company_id=company.id, post_id=p.id),
        )
        for p in posts
    ]
    return WebsiteBlogListResponse(items=items, total=len(items))


@router.post("/blog", response_model=WebsiteBlogResponse)
def create_blog_post(
    data: WebsiteBlogCreateRequest,
    user: User = Depends(require_permission("website.manage")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    slug = normalize_slug(data.slug or data.title)
    try:
        validate_slug(slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _ensure_unique_slug(db, WebsiteBlogPost, company.id, slug)
    post = WebsiteBlogPost(
        company_id=company.id,
        title=data.title.strip(),
        slug=slug,
        excerpt=data.excerpt,
        body_html=sanitize_html(data.body_html),
        cover_image_url=data.cover_image_url,
        author_id=user.id,
        status="draft",
        seo_title=data.seo_title,
        seo_description=data.seo_description,
        tags=data.tags or [],
        preview_token=new_preview_token(),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _blog_response(db, post)


@router.get("/blog/{post_id}", response_model=WebsiteBlogResponse)
def get_blog_post(post_id: int, user: User = Depends(require_permission("website.view")), db: Session = Depends(get_db)):
    company = get_current_company(db, user)
    post = _get_blog_post(db, post_id, company.id)
    return _blog_response(db, post)


@router.put("/blog/{post_id}", response_model=WebsiteBlogResponse)
def update_blog_post(
    post_id: int,
    data: WebsiteBlogUpdateRequest,
    user: User = Depends(require_permission("website.manage")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    post = _get_blog_post(db, post_id, company.id)
    if data.title is not None:
        post.title = data.title.strip()
    if data.slug is not None:
        slug = normalize_slug(data.slug)
        try:
            validate_slug(slug)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _ensure_unique_slug(db, WebsiteBlogPost, company.id, slug, post.id)
        post.slug = slug
    if data.excerpt is not None:
        post.excerpt = data.excerpt
    if data.body_html is not None:
        post.body_html = sanitize_html(data.body_html)
    if data.cover_image_url is not None:
        post.cover_image_url = data.cover_image_url
    if data.seo_title is not None:
        post.seo_title = data.seo_title
    if data.seo_description is not None:
        post.seo_description = data.seo_description
    if data.tags is not None:
        post.tags = data.tags
    if not post.preview_token:
        post.preview_token = new_preview_token()
    db.commit()
    db.refresh(post)
    return _blog_response(db, post)


@router.post("/blog/{post_id}/publish", response_model=WebsiteBlogResponse)
def publish_blog_post(
    post_id: int,
    request: Request,
    user: User = Depends(require_permission("website.publish")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    post = _get_blog_post(db, post_id, company.id)
    post.status = "published"
    post.published_at = _utcnow()
    db.commit()
    db.refresh(post)
    log_activity(
        db,
        "website_blog_published",
        user_id=user.id,
        email=user.email,
        details=f"post:{post.id}",
        ip_address=get_client_ip(request),
    )
    return _blog_response(db, post)


@router.post("/blog/{post_id}/unpublish", response_model=WebsiteBlogResponse)
def unpublish_blog_post(
    post_id: int,
    user: User = Depends(require_permission("website.publish")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    post = _get_blog_post(db, post_id, company.id)
    post.status = "draft"
    db.commit()
    db.refresh(post)
    return _blog_response(db, post)


@router.delete("/blog/{post_id}")
def delete_blog_post(
    post_id: int,
    user: User = Depends(require_permission("website.delete")),
    db: Session = Depends(get_db),
):
    company = get_current_company(db, user)
    post = _get_blog_post(db, post_id, company.id)
    if post.status == "published":
        post.status = "archived"
        db.commit()
        return {"detail": "Post archived"}
    db.delete(post)
    db.commit()
    return {"detail": "Post deleted"}


def _load_public_page(
    db: Session,
    company: Company,
    site: WebsiteSettings,
    page_slug: str | None,
    preview_token: str | None = None,
) -> WebsitePage:
    if page_slug:
        page = (
            db.query(WebsitePage)
            .filter(WebsitePage.company_id == company.id, WebsitePage.slug == page_slug)
            .first()
        )
    elif site.home_page_id:
        page = db.query(WebsitePage).filter(WebsitePage.id == site.home_page_id).first()
    else:
        page = (
            db.query(WebsitePage)
            .filter(WebsitePage.company_id == company.id, WebsitePage.status == "published")
            .order_by(WebsitePage.is_home.desc(), WebsitePage.published_at.desc())
            .first()
        )
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    if page.status != "published":
        if not preview_token or preview_token != page.preview_token:
            raise HTTPException(status_code=404, detail="Page not found")
    return page


def _public_products(db: Session, company_id: int, limit: int = 6) -> list[dict[str, Any]]:
    products = (
        db.query(Product)
        .filter(Product.company_id == company_id, Product.status == "active")
        .order_by(Product.name.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price": float(p.offer_price or p.total_price or 0) if (p.offer_price or p.total_price) is not None else None,
            "category": p.category,
        }
        for p in products
    ]


def _forms_for_page(db: Session, company_id: int, sections: list[dict[str, Any]]) -> list[WebsiteFormResponse]:
    form_ids = []
    for section in sections or []:
        if section.get("type") == "form_embed":
            form_id = (section.get("props") or {}).get("form_id")
            if form_id:
                form_ids.append(form_id)
    if not form_ids:
        return []
    forms = db.query(WebsiteForm).filter(WebsiteForm.company_id == company_id, WebsiteForm.id.in_(form_ids)).all()
    return [_form_response(f) for f in forms]


@public_router.get("/{company_slug}", response_model=PublicPageResponse)
def public_home(
    company_slug: str,
    preview: str | None = None,
    db: Session = Depends(get_db),
):
    company, site = _resolve_company_by_slug(db, company_slug)
    page = _load_public_page(db, company, site, None, preview)
    sys_settings = db.query(SystemSetting).filter(SystemSetting.company_id == company.id).first()
    _log_page_view(db, company_id=company.id, page_id=page.id, path=_public_path(company_slug))
    return PublicPageResponse(
        page=_page_response(db, page, site),
        company=_public_branding(company, sys_settings),
        forms=_forms_for_page(db, company.id, page.sections_json or []),
        products=_public_products(db, company.id),
    )


@public_router.get("/{company_slug}/pages/{page_slug}", response_model=PublicPageResponse)
def public_page(
    company_slug: str,
    page_slug: str,
    preview: str | None = None,
    db: Session = Depends(get_db),
):
    company, site = _resolve_company_by_slug(db, company_slug)
    page = _load_public_page(db, company, site, page_slug, preview)
    sys_settings = db.query(SystemSetting).filter(SystemSetting.company_id == company.id).first()
    _log_page_view(db, company_id=company.id, page_id=page.id, path=_public_path(company_slug, page_slug))
    return PublicPageResponse(
        page=_page_response(db, page, site),
        company=_public_branding(company, sys_settings),
        forms=_forms_for_page(db, company.id, page.sections_json or []),
        products=_public_products(db, company.id),
    )


@public_router.get("/{company_slug}/blog", response_model=PublicBlogIndexResponse)
def public_blog_index(company_slug: str, db: Session = Depends(get_db)):
    company, site = _resolve_company_by_slug(db, company_slug)
    sys_settings = db.query(SystemSetting).filter(SystemSetting.company_id == company.id).first()
    posts = (
        db.query(WebsiteBlogPost)
        .filter(WebsiteBlogPost.company_id == company.id, WebsiteBlogPost.status == "published")
        .order_by(WebsiteBlogPost.published_at.desc())
        .all()
    )
    return PublicBlogIndexResponse(
        company=_public_branding(company, sys_settings),
        posts=[
            WebsiteBlogListItem(
                id=p.id,
                title=p.title,
                slug=p.slug,
                status=p.status,
                author_name=p.author.name if p.author else None,
                published_at=p.published_at,
                updated_at=p.updated_at,
                view_count_7d=_view_count_7d(db, company_id=company.id, post_id=p.id),
            )
            for p in posts
        ],
    )


@public_router.get("/{company_slug}/blog/{post_slug}", response_model=PublicBlogPostResponse)
def public_blog_post(
    company_slug: str,
    post_slug: str,
    preview: str | None = None,
    db: Session = Depends(get_db),
):
    company, site = _resolve_company_by_slug(db, company_slug)
    post = (
        db.query(WebsiteBlogPost)
        .filter(WebsiteBlogPost.company_id == company.id, WebsiteBlogPost.slug == post_slug)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != "published":
        if not preview or preview != post.preview_token:
            raise HTTPException(status_code=404, detail="Post not found")
    sys_settings = db.query(SystemSetting).filter(SystemSetting.company_id == company.id).first()
    _log_page_view(db, company_id=company.id, post_id=post.id, path=_public_path(company_slug, "blog", post_slug))
    return PublicBlogPostResponse(post=_blog_response(db, post), company=_public_branding(company, sys_settings))


@public_router.post("/{company_slug}/forms/{form_slug}/submit", response_model=PublicFormSubmitResponse)
def public_form_submit(
    company_slug: str,
    form_slug: str,
    data: PublicFormSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if data.website_trap:
        return PublicFormSubmitResponse(success=True, message="Thank you!", lead_id=None)
    company, site = _resolve_company_by_slug(db, company_slug)
    form = (
        db.query(WebsiteForm)
        .filter(WebsiteForm.company_id == company.id, WebsiteForm.slug == form_slug)
        .first()
    )
    if not form or not form.is_active:
        raise HTTPException(status_code=403, detail="Form is not available")
    ip = get_client_ip(request)
    _check_form_rate_limit(ip)
    payload = data.fields or {}
    try:
        lead = _create_lead_from_submission(
            db,
            company=company,
            form=form,
            payload=payload,
            site=site,
            utm_source=data.utm_source,
            utm_medium=data.utm_medium,
            utm_campaign=data.utm_campaign,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    submission = WebsiteFormSubmission(
        form_id=form.id,
        company_id=company.id,
        payload_json=payload,
        lead_id=lead.id,
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
        utm_source=data.utm_source,
        utm_medium=data.utm_medium,
        utm_campaign=data.utm_campaign,
    )
    db.add(submission)
    db.commit()
    redirect = None
    if form.redirect_url:
        redirect = _public_url(site.company_slug, form.redirect_url.lstrip("/"))
    return PublicFormSubmitResponse(
        success=True,
        message=form.success_message,
        lead_id=lead.id,
        redirect_url=redirect,
    )
