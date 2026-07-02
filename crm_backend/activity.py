from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from models import ActivityLog


def _details_text(details: Any) -> str | None:
    if details is None:
        return None
    if isinstance(details, str):
        return details
    return json.dumps(details, default=str)


def log_activity(
    db: Session,
    action: str,
    *,
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    details: Any = None,
    ip_address: Optional[str] = None,
) -> None:
    db.add(
        ActivityLog(
            user_id=user_id,
            email=email,
            action=action,
            details=_details_text(details),
            ip_address=ip_address,
        )
    )
    db.commit()