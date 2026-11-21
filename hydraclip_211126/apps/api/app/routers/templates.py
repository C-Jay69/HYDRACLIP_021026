"""Templates Router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import oauth2_scheme, decode_token
from app.models.user import User
from app.models.system import PromptTemplate

router = APIRouter(prefix="/templates", tags=["templates"])


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


@router.get("")
async def list_templates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List available prompt templates."""
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.is_default == True)
    )
    templates = result.scalars().all()
    
    return [
        {
            "id": t.id,
            "name": t.name,
            "category": t.category,
            "platform_target": t.platform_target,
            "format": t.format,
            "script_template": t.script_template,
            "title_template": t.title_template,
            "description_template": t.description_template,
            "hashtag_template": t.hashtag_template,
            "is_default": t.is_default,
        }
        for t in templates
    ]


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific template."""
    result = await db.execute(
        select(PromptTemplate).where(PromptTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "id": template.id,
        "name": template.name,
        "category": template.category,
        "platform_target": template.platform_target,
        "format": template.format,
        "script_template": template.script_template,
        "title_template": template.title_template,
        "description_template": template.description_template,
        "hashtag_template": template.hashtag_template,
        "is_default": template.is_default,
    }