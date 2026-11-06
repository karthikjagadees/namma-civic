"""
Resolution Verification API Endpoints
Enables municipal officers & crews to submit resolution proof and receive AI verification.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import RequireOfficer
from app.services.verification_service import ResolutionVerificationService

router = APIRouter(prefix="/resolution", tags=["Resolution Verification"])


class ResolutionSubmitRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=5, description="Description of the repair/resolution performed")
    resolution_image_url: Optional[str] = Field(None, description="URL or upload path of the repaired scene")


@router.post("/verify/{complaint_id}")
async def submit_and_verify_resolution(
    complaint_id: str,
    payload: ResolutionSubmitRequest,
    current_user: RequireOfficer,
    db: AsyncSession = Depends(get_db)
):
    """
    Officer/Crew submission endpoint: validates repair evidence through multimodal verification
    and marks complaint as resolved upon success.
    """
    try:
        result = await ResolutionVerificationService.verify_resolution_evidence(
            session=db,
            complaint_id=complaint_id,
            resolution_notes=payload.resolution_notes,
            resolution_image_url=payload.resolution_image_url,
            officer_id=current_user.id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Verification error: {str(e)}")
