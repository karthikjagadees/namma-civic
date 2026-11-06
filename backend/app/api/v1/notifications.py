"""
Namma Civic — Notifications & Email Gateway API Router
Endpoints to check SMTP gateway health, test live email dispatch, and view outbox audit logs.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import CurrentUser, DBSession
from app.models.follow_up import IncidentNotificationPreference
from app.services.email_service import EmailService, _build_html_wrapper

router = APIRouter(prefix="/notifications", tags=["Notifications & Email"])


class SMTPStatusResponse(BaseModel):
    mode: str
    host: str
    port: int
    use_tls: bool
    from_address: str
    username_configured: bool
    total_outbox_logged: int
    status_description: str


class SendTestEmailRequest(BaseModel):
    to_email: EmailStr = Field(..., description="Target email recipient")
    subject: Optional[str] = Field("Namma Civic — SMTP Gateway Connectivity Test", max_length=150)
    message: Optional[str] = Field("This is a live test notification from your Namma Civic municipal dispatch engine.", max_length=500)


class OutboxRecord(BaseModel):
    id: str
    to_email: str
    from_email: str
    subject: str
    event_type: str
    complaint_id: Optional[str] = None
    html_preview: str
    text_preview: str
    created_at: str
    status: str
    delivery_channel: str
    error: Optional[str] = None


class NotificationPreferenceUpdate(BaseModel):
    """Citizen's channel choices for incident status updates."""

    sms_enabled: bool
    email_enabled: bool


@router.get("/status", response_model=SMTPStatusResponse)
async def get_notification_status() -> SMTPStatusResponse:
    """Check SMTP configuration, active delivery mode (LIVE_SMTP vs SIMULATED_DEV_MODE)."""
    return SMTPStatusResponse(**EmailService.get_smtp_status())


@router.post("/test-email")
async def send_test_email(payload: SendTestEmailRequest) -> Dict[str, Any]:
    """Send a live or simulated test email to verify SMTP gateway configuration."""
    body_html = f"""
    <p style="margin-top:0;">Hello,</p>
    <p>This email confirms that your <strong>Namma Civic SMTP Gateway</strong> is operational and communicating with your mail server.</p>
    
    <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-left:4px solid #3B82F6;padding:14px;border-radius:0 8px 8px 0;margin:18px 0;">
      <div style="font-size:12px;color:#64748B;font-weight:600;margin-bottom:4px;">Diagnostic Message:</div>
      <div style="font-size:14px;color:#0F172A;">{payload.message}</div>
    </div>

    <p style="font-size:13px;color:#475569;">
      You are now ready to receive real-time citizen grievance intake confirmations, officer tactical crew assignments, and resolution audits.
    </p>
    """

    html = _build_html_wrapper(
        title="SMTP Connectivity Verified",
        preheader="Test email from Namma Civic Municipal System",
        body_html=body_html,
        tracking_id="TEST",
    )

    result = await EmailService.send_email(
        to_email=payload.to_email,
        subject=payload.subject or "Namma Civic — SMTP Gateway Connectivity Test",
        html_content=html,
        text_content=payload.message,
        event_type="TEST_ALERT",
    )

    return result


@router.get("/outbox", response_model=List[OutboxRecord])
async def get_outbox_logs(
    limit: int = Query(50, ge=1, le=100, description="Max recent outbox records")
) -> List[OutboxRecord]:
    """Retrieve audit history of dispatched and simulated outbound emails."""
    logs = EmailService.get_outbox(limit=limit)
    return [OutboxRecord(**r) for r in logs]


@router.get("/preferences")
async def get_notification_preferences(current_user: CurrentUser, db: DBSession):
    """Return this user's persisted or default incident notification choices."""
    preferences = await db.get(IncidentNotificationPreference, current_user.id)
    return {
        "sms_enabled": preferences.sms_enabled if preferences else True,
        "email_enabled": preferences.email_enabled if preferences else True,
    }


@router.put("/preferences")
async def update_notification_preferences(
    payload: NotificationPreferenceUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    """Save channel opt-ins for future incident updates."""
    preferences = await db.get(IncidentNotificationPreference, current_user.id)
    if preferences is None:
        preferences = IncidentNotificationPreference(user_id=current_user.id)
        db.add(preferences)
    preferences.sms_enabled = payload.sms_enabled
    preferences.email_enabled = payload.email_enabled
    await db.flush()
    return {"sms_enabled": preferences.sms_enabled, "email_enabled": preferences.email_enabled}
