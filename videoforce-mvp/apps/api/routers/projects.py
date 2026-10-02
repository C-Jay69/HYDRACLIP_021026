"""Project CRUD.

Every query is scoped to the authenticated user. Reads of someone else's row
return 404 rather than 403 so ids cannot be probed for existence.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select

from apps.api.core.deps import CurrentUser, DbSession, OwnedProject, PageParams
from apps.api.models import Project, Video, VideoJob
from apps.api.schemas.common import Page
from apps.api.schemas.project import (
    PROJECT_STATUSES,
    ProjectCreate,
    ProjectPublic,
    ProjectUpdate,
    ProjectWithCounts,
)
from apps.api.schemas.video import VideoPublic

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: DbSession, user: CurrentUser) -> Project:
    """Create a project owned by the caller."""
    project = Project(
        user_id=user.id,
        title=payload.title,
        topic=payload.topic,
        status="pending",
        settings_json=payload.settings_json,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=Page[ProjectWithCounts])
def list_projects(
    db: DbSession,
    user: CurrentUser,
    page: PageParams,
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by project status.",
    ),
    q: str | None = Query(default=None, max_length=200, description="Search titles."),
) -> Page[ProjectWithCounts]:
    """List the caller's projects, newest first."""
    filters = [Project.user_id == user.id]

    if status_filter:
        if status_filter not in PROJECT_STATUSES:
            # Unknown status would otherwise silently return an empty page.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"status must be one of {', '.join(PROJECT_STATUSES)}.",
            )
        filters.append(Project.status == status_filter)

    if q:
        filters.append(Project.title.ilike(f"%{q}%"))

    total = db.scalar(select(func.count()).select_from(Project).where(*filters)) or 0

    rows = (
        db.execute(
            select(Project, func.count(Video.id))
            .outerjoin(Video, Video.project_id == Project.id)
            .where(*filters)
            .group_by(Project.id)
            .order_by(Project.created_at.desc(), Project.id.desc())
            .limit(page.limit)
            .offset(page.offset)
        )
        .all()
    )

    items = [
        ProjectWithCounts(**ProjectPublic.model_validate(project).model_dump(), video_count=count)
        for project, count in rows
    ]

    return Page.build(items, total=total, limit=page.limit, offset=page.offset)


@router.get("/{project_id}", response_model=ProjectPublic)
def get_project(project: OwnedProject) -> Project:
    return project


@router.patch("/{project_id}", response_model=ProjectPublic)
def update_project(payload: ProjectUpdate, project: OwnedProject, db: DbSession) -> Project:
    """Update user-editable fields. Status is pipeline-owned and not settable."""
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_project(project: OwnedProject, db: DbSession) -> Response:
    """Delete a project and everything hanging off it.

    The models declare no ForeignKey constraints, so there is no database-level
    cascade to rely on — children are removed explicitly to avoid orphan rows.
    """
    video_ids = list(db.scalars(select(Video.id).where(Video.project_id == project.id)))

    if video_ids:
        db.execute(delete(VideoJob).where(VideoJob.video_id.in_(video_ids)))
        db.execute(delete(Video).where(Video.id.in_(video_ids)))

    db.delete(project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/videos", response_model=Page[VideoPublic])
def list_project_videos(
    project: OwnedProject,
    db: DbSession,
    page: PageParams,
) -> Page[VideoPublic]:
    """List videos belonging to one project."""
    where = Video.project_id == project.id

    total = db.scalar(select(func.count()).select_from(Video).where(where)) or 0
    videos = list(
        db.scalars(
            select(Video)
            .where(where)
            .order_by(Video.created_at.desc(), Video.id.desc())
            .limit(page.limit)
            .offset(page.offset)
        )
    )

    return Page.build(
        [VideoPublic.model_validate(v) for v in videos],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )
