"""Admin panel endpoints.

Every route here goes through the ``AdminUser`` dependency, which rejects
anyone whose ``users.role`` is not ``ADMIN`` — there is no other gate, so a
missing dependency would silently expose user management to everyone.

All mutating actions are written to ``admin_audit_logs`` with the acting
admin's id, the target, and best-effort request metadata.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select

from apps.api.core.deps import AdminUser, DbSession, PageParams
from apps.api.models import (
    AdminAuditLog,
    Plan,
    Project,
    Subscription,
    SystemSetting,
    User,
    Video,
)
from apps.api.schemas.admin import (
    AdminAuditLogPublic,
    AdminSetPlanRequest,
    AdminStats,
    AdminUserPublic,
    AdminUserUpdate,
    SystemSettingPublic,
    SystemSettingUpsert,
)
from apps.api.schemas.billing import SubscriptionPublic
from apps.api.schemas.common import Page
from apps.api.services import billing as billing_service

router = APIRouter(prefix="/admin", tags=["admin"])

ACTIVE_SUB_STATUSES = billing_service.ACTIVE_SUBSCRIPTION_STATUSES


def _audit(
    db, admin: User, action: str, target_type: str,
    target_id: int | None, request: Request, **meta,
) -> None:
    db.add(
        AdminAuditLog(
            admin_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=meta or {},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )


def _user_summaries(db, rows: list[User]) -> list[AdminUserPublic]:
    """Assemble the panel rows with counts and plan names in bulk."""
    ids = [u.id for u in rows]

    project_counts: dict[int, int] = {}
    video_counts: dict[int, int] = {}
    if ids:
        project_counts = {
            uid: count
            for uid, count in db.execute(
                select(Project.user_id, func.count())
                .where(Project.user_id.in_(ids))
                .group_by(Project.user_id)
            ).all()
        }
        video_counts = {
            uid: count
            for uid, count in db.execute(
                select(Video.user_id, func.count())
                .where(Video.user_id.in_(ids))
                .group_by(Video.user_id)
            ).all()
        }

    # Active plan per user, resolved in one query.
    plan_names: dict[int, str] = {}
    if ids:
        sub_rows = db.execute(
            select(Subscription.user_id, Plan.name)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(
                Subscription.user_id.in_(ids),
                Subscription.status.in_(ACTIVE_SUB_STATUSES),
            )
        ).all()
        plan_names = {uid: name for uid, name in sub_rows}

    return [
        AdminUserPublic(
            id=u.id,
            email=u.email,
            name=u.name,
            role=u.role or "USER",
            is_active=u.is_active,
            is_verified=u.is_verified,
            stripe_customer_id=u.stripe_customer_id,
            created_at=u.created_at,
            project_count=project_counts.get(u.id, 0),
            video_count=video_counts.get(u.id, 0),
            plan_name=plan_names.get(u.id),
        )
        for u in rows
    ]


@router.get("/users", response_model=Page[AdminUserPublic])
def list_users(
    db: DbSession,
    admin: AdminUser,
    page: PageParams,
    search: str | None = Query(default=None, max_length=200),
) -> Page[AdminUserPublic]:
    """All accounts, newest first, optionally filtered by email/name."""
    filters = []
    if search:
        needle = f"%{search.strip().lower()}%"
        filters.append(
            func.lower(User.email).like(needle)
            | func.lower(func.coalesce(User.name, "")).like(needle)
        )

    total = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(User)
            .where(*filters)
            .order_by(User.id.desc())
            .limit(page.limit)
            .offset(page.offset)
        )
    )
    return Page.build(
        _user_summaries(db, rows), total=total, limit=page.limit, offset=page.offset
    )


@router.get("/users/{user_id}", response_model=AdminUserPublic)
def get_user(user_id: int, db: DbSession, admin: AdminUser) -> AdminUserPublic:
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _user_summaries(db, [row])[0]


@router.patch("/users/{user_id}", response_model=AdminUserPublic)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: DbSession,
    admin: AdminUser,
    request: Request,
) -> AdminUserPublic:
    row = db.get(User, user_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    changes: dict[str, object] = {}
    if payload.name is not None and payload.name != row.name:
        row.name = payload.name
        changes["name"] = payload.name
    if payload.role is not None and payload.role != row.role:
        # An admin must not be able to lock themselves out of the panel by
        # demoting their own account.
        if row.id == admin.id and payload.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You cannot revoke your own administrator role.",
            )
        row.role = payload.role
        changes["role"] = payload.role
    if payload.is_active is not None and payload.is_active != row.is_active:
        if row.id == admin.id and not payload.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You cannot deactivate your own account.",
            )
        row.is_active = payload.is_active
        changes["is_active"] = payload.is_active
    if payload.is_verified is not None and payload.is_verified != row.is_verified:
        row.is_verified = payload.is_verified
        changes["is_verified"] = payload.is_verified

    if changes:
        _audit(db, admin, "user.update", "user", row.id, request, changes=changes)
        db.commit()

    db.refresh(row)
    return _user_summaries(db, [row])[0]


@router.get("/stats", response_model=AdminStats)
def admin_stats(db: DbSession, admin: AdminUser) -> AdminStats:
    """Top-line platform numbers for the overview cards."""
    users = db.scalar(select(func.count()).select_from(User)) or 0
    active_users = (
        db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    )
    projects = db.scalar(select(func.count()).select_from(Project)) or 0
    videos = db.scalar(select(func.count()).select_from(Video)) or 0
    completed_videos = (
        db.scalar(select(func.count()).select_from(Video).where(Video.status == "completed"))
        or 0
    )
    failed_videos = (
        db.scalar(select(func.count()).select_from(Video).where(Video.status == "failed")) or 0
    )
    active_subscriptions = (
        db.scalar(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.status.in_(ACTIVE_SUB_STATUSES))
        )
        or 0
    )
    plan_breakdown = {
        name: count
        for name, count in db.execute(
            select(Plan.name, func.count())
            .join(Subscription, Subscription.plan_id == Plan.id)
            .where(Subscription.status.in_(ACTIVE_SUB_STATUSES))
            .group_by(Plan.name)
        ).all()
    }
    return AdminStats(
        users=users,
        active_users=active_users,
        projects=projects,
        videos=videos,
        completed_videos=completed_videos,
        failed_videos=failed_videos,
        active_subscriptions=active_subscriptions,
        plan_breakdown=plan_breakdown,
    )


@router.post("/users/{user_id}/plan", response_model=SubscriptionPublic)
def set_user_plan(
    user_id: int,
    payload: AdminSetPlanRequest,
    db: DbSession,
    admin: AdminUser,
    request: Request,
) -> SubscriptionPublic:
    """Grant or change a user's plan directly, bypassing Stripe."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    plan = db.get(Plan, payload.plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found."
        )

    subscription = billing_service.grant_manual_plan(db, user, plan)
    _audit(
        db, admin, "plan.grant", "user", user.id, request,
        plan=plan.name, subscription_id=subscription.id,
    )
    db.commit()
    body = SubscriptionPublic.model_validate(subscription)
    body.plan_name = plan.name
    return body


@router.get("/audit-logs", response_model=Page[AdminAuditLogPublic])
def list_audit_logs(
    db: DbSession, admin: AdminUser, page: PageParams
) -> Page[AdminAuditLogPublic]:
    total = db.scalar(select(func.count()).select_from(AdminAuditLog)) or 0
    rows = list(
        db.scalars(
            select(AdminAuditLog)
            .order_by(AdminAuditLog.id.desc())
            .limit(page.limit)
            .offset(page.offset)
        )
    )
    return Page.build(
        [AdminAuditLogPublic.model_validate(r) for r in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/settings", response_model=list[SystemSettingPublic])
def list_settings(db: DbSession, admin: AdminUser) -> list[SystemSettingPublic]:
    return [
        SystemSettingPublic.model_validate(row)
        for row in db.scalars(select(SystemSetting).order_by(SystemSetting.key))
    ]


@router.put("/settings/{key}", response_model=SystemSettingPublic)
def upsert_setting(
    key: str,
    payload: SystemSettingUpsert,
    db: DbSession,
    admin: AdminUser,
    request: Request,
) -> SystemSettingPublic:
    """Create or update one platform setting (spec: admin manages settings)."""
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if row is None:
        row = SystemSetting(key=key)
        db.add(row)
    row.value = payload.value
    row.value_type = payload.value_type
    row.description = payload.description
    row.updated_by = admin.id

    _audit(db, admin, "setting.upsert", "system_setting", None, request, key=key)
    db.commit()
    db.refresh(row)
    return SystemSettingPublic.model_validate(row)
