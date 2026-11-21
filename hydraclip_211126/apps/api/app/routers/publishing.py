"""Publishing Router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import oauth2_scheme, decode_token
from app.models.user import User
from app.models.schedule import Schedule, PublishedPost, ScheduleStatus
from app.models.video import Video, VideoStatus
from app.services.schedule_service import publish_now

router = APIRouter(prefix="/publishing", tags=["publishing"])


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


@router.get("", response_model=List[dict])
async def list_published(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List published posts."""
    from app.models.published_post import PublishedPost
    result = await db.execute(
        select(PublishedPost).where(PublishedPost.user_id == user.id)
        .order_by(PublishedPost.created_at.desc())
    )
    posts = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "video_id": p.video_id,
            "platform": p.platform,
            "platform_url": p.platform_url,
            "title": p.title,
            "status": p.status,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "error_message": p.error_message,
        }
        for p in posts
    ]


@router.get("/{post_id}")
async def get_published_post(
    post_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a published post."""
    from app.models.published_post import PublishedPost
    result = await db.execute(
        select(PublishedPost).where(PublishedPost.id == post_id, PublishedPost.user_id == user.id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Published post not found")
    
    return {
        "id": post.id,
        "video_id": post.video_id,
        "platform": post.platform,
        "platform_url": post.platform_url,
        "title": post.title,
        "description": post.description,
        "tags": post.tags,
        "status": post.status,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "error_message": post.error_message,
    }