"""Projects Router."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import oauth2_scheme, decode_token
from app.models.user import User
from app.models.project import Project, ProjectAsset, ProjectFormat, ProjectAspectRatio, ProjectStatus
from app.services.storage_service import upload_file, delete_file

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    title: str
    topic: str
    niche: str = "general"
    platform_targets: List[str] = ["youtube"]
    format: ProjectFormat = ProjectFormat.SHORT
    aspect_ratio: ProjectAspectRatio = ProjectAspectRatio.RATIO_9_16
    tone: str = "educational"
    language: str = "en"


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None
    niche: Optional[str] = None
    platform_targets: Optional[List[str]] = None
    format: Optional[ProjectFormat] = None
    aspect_ratio: Optional[ProjectAspectRatio] = None
    tone: Optional[str] = None
    language: Optional[str] = None
    status: Optional[ProjectStatus] = None


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    title: str
    topic: str
    niche: str
    platform_targets: List[str]
    format: str
    aspect_ratio: str
    tone: str
    language: str
    status: str
    created_at: str
    updated_at: str


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current user from token."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's projects."""
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user.id)
        .order_by(desc(Project.created_at))
    )
    projects = result.scalars().all()
    
    return [
        ProjectResponse(
            id=p.id,
            user_id=p.user_id,
            title=p.title,
            topic=p.topic,
            niche=p.niche,
            platform_targets=eval(p.platform_targets) if isinstance(p.platform_targets, str) else p.platform_targets,
            format=p.format.value,
            aspect_ratio=p.aspect_ratio.value,
            tone=p.tone,
            language=p.language,
            status=p.status.value,
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat(),
        )
        for p in projects
    ]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    import json
    import secrets
    
    new_project = Project(
        id=secrets.token_urlsafe(16),
        user_id=user.id,
        title=project.title,
        topic=project.topic,
        niche=project.niche,
        platform_targets=json.dumps(project.platform_targets),
        format=project.format,
        aspect_ratio=project.aspect_ratio,
        tone=project.tone,
        language=project.language,
        status=ProjectStatus.DRAFT,
    )
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    
    return ProjectResponse(
        id=new_project.id,
        user_id=new_project.user_id,
        title=new_project.title,
        topic=new_project.topic,
        niche=new_project.niche,
        platform_targets=project.platform_targets,
        format=new_project.format.value,
        aspect_ratio=new_project.aspect_ratio.value,
        tone=new_project.tone,
        language=new_project.language,
        status=new_project.status.value,
        created_at=new_project.created_at.isoformat(),
        updated_at=new_project.updated_at.isoformat(),
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a project by ID."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        title=project.title,
        topic=project.topic,
        niche=project.niche,
        platform_targets=eval(project.platform_targets) if isinstance(project.platform_targets, str) else project.platform_targets,
        format=project.format.value,
        aspect_ratio=project.aspect_ratio.value,
        tone=project.tone,
        language=project.language,
        status=project.status.value,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    update: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    import json
    if update.title is not None:
        project.title = update.title
    if update.topic is not None:
        project.topic = update.topic
    if update.niche is not None:
        project.niche = update.niche
    if update.platform_targets is not None:
        project.platform_targets = json.dumps(update.platform_targets)
    if update.format is not None:
        project.format = update.format
    if update.aspect_ratio is not None:
        project.aspect_ratio = update.aspect_ratio
    if update.tone is not None:
        project.tone = update.tone
    if update.language is not None:
        project.language = update.language
    if update.status is not None:
        project.status = update.status
    
    await db.commit()
    await db.refresh(project)
    
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        title=project.title,
        topic=project.topic,
        niche=project.niche,
        platform_targets=eval(project.platform_targets) if isinstance(project.platform_targets, str) else project.platform_targets,
        format=project.format.value,
        aspect_ratio=project.aspect_ratio.value,
        tone=project.tone,
        language=project.language,
        status=project.status.value,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    await db.delete(project)
    await db.commit()
    
    return {"success": True, "message": "Project deleted"}


@router.post("/{project_id}/assets")
async def upload_asset(
    project_id: str,
    file: UploadFile = File(...),
    asset_type: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload an asset for a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Upload to storage
    storage_key = await upload_file(file, f"projects/{project_id}")
    
    # Create asset record
    import secrets
    asset = ProjectAsset(
        id=secrets.token_urlsafe(16),
        project_id=project_id,
        asset_type=asset_type,
        storage_key=storage_key,
        original_filename=file.filename or "unknown",
    )
    db.add(asset)
    await db.commit()
    
    return {"success": True, "asset_id": asset.id, "storage_key": storage_key}