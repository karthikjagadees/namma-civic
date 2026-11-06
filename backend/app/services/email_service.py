"""
Namma Civic — Email & SMTP Notification Service
Asynchronous, robust email delivery supporting Gmail, custom SMTP, and simulated dev outbox.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib
from typing import Any, Dict, List, Optional
import uuid

from app.core.config import settings

logger = logging.getLogger("namma-civic.email")

# In-memory Outbox history for auditing and Admin Dashboard inspection
_EMAIL_OUTBOX_LOG: List[Dict[str, Any]] = []
_MAX_OUTBOX_ENTRIES = 100


def _build_html_wrapper(title: str, preheader: str, body_html: str, tracking_id: Optional[str] = None) -> str:
    """Institutional, clean HTML email template matching Namma Civic aesthetic."""
    tracking_badge = (
        f'<div style="display:inline-block;padding:4px 10px;background:#EFF6FF;border:1px solid #BFDBFE;color:#1E3A8A;font-family:monospace;font-size:12px;font-weight:700;border-radius:6px;letter-spacing:0.5px;">TICKET #{tracking_id}</div>'
        if tracking_id else ''
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#F8FAFC;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1E293B;-webkit-font-smoothing:antialiased;">
  <div style="display:none;font-size:1px;color:#F8FAFC;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
    {preheader}
  </div>
  <table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#F8FAFC;padding:32px 16px;">
    <tr>
      <td align="center">
        <!-- Container Card -->
        <table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="max-width:580px;background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.03);">
          
          <!-- Header Bar -->
          <tr>
            <td style="padding:24px 32px;background:#0F172A;border-bottom:1px solid #1E293B;">
              <table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation">
                <tr>
                  <td>
                    <div style="font-size:18px;font-weight:700;color:#FFFFFF;letter-spacing:-0.3px;">
                      Namma Civic <span style="color:#38BDF8;">AI</span>
                    </div>
                    <div style="font-size:11px;color:#94A3B8;margin-top:2px;">
                      Autonomous Municipal Action Engine
                    </div>
                  </td>
                  <td align="right">
                    {tracking_badge}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding:32px;">
              <h1 style="margin:0 0 16px;font-size:20px;font-weight:700;color:#0F172A;line-height:1.3;">
                {title}
              </h1>
              <div style="font-size:14px;line-height:1.6;color:#334155;">
                {body_html}
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px;background:#F8FAFC;border-top:1px solid #E2E8F0;font-size:11px;color:#64748B;line-height:1.5;">
              <p style="margin:0 0 4px;">
                You received this notice because an issue was reported or updated on the Namma Civic Municipal Platform.
              </p>
              <p style="margin:0;">
                Municipal Operations Center • Powered by Namma Civic Multi-Agent Orchestration • Do not reply directly to this automated alert.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


class EmailService:
    """Asynchronous SMTP and notification delivery engine."""

    @classmethod
    def is_smtp_configured(cls) -> bool:
        """Check if user and password for SMTP are configured."""
        user = (settings.email_user or "").strip()
        pwd = (settings.email_password or "").strip()
        return bool(user and pwd)

    @classmethod
    def get_smtp_status(cls) -> Dict[str, Any]:
        """Return gateway status and configuration."""
        configured = cls.is_smtp_configured()
        return {
            "mode": "LIVE_SMTP" if configured else "SIMULATED_DEV_MODE",
            "host": settings.email_host,
            "port": settings.email_port,
            "use_tls": settings.email_use_tls,
            "from_address": settings.email_from or settings.email_user or "noreply@namma-civic.ai",
            "username_configured": bool((settings.email_user or "").strip()),
            "total_outbox_logged": len(_EMAIL_OUTBOX_LOG),
            "status_description": (
                "Live SMTP connected to relay host." if configured else
                "Dev Mode: Emails are logged to outbox and console without sending network packets."
            )
        }

    @classmethod
    def get_outbox(cls, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent outbound emails."""
        return _EMAIL_OUTBOX_LOG[-limit:][::-1]

    @classmethod
    async def send_email(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        event_type: str = "SYSTEM_ALERT",
        complaint_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Asynchronously send an email. If credentials are not configured,
        records it to the simulated outbox gracefully.
        """
        now = datetime.now(timezone.utc).isoformat()
        msg_id = f"MSG-{uuid.uuid4().hex[:10].upper()}"
        clean_to = to_email.strip()
        from_email = settings.email_from or settings.email_user or "noreply@namma-civic.ai"

        if not text_content:
            text_content = f"{subject}\n\nNotice from Namma Civic Municipal System."

        # Record entry for outbox
        record: Dict[str, Any] = {
            "id": msg_id,
            "to_email": clean_to,
            "from_email": from_email,
            "subject": subject,
            "event_type": event_type,
            "complaint_id": complaint_id,
            "html_preview": html_content,
            "text_preview": text_content,
            "created_at": now,
            "status": "PENDING",
            "delivery_channel": "SMTP",
            "error": None,
        }

        if not cls.is_smtp_configured():
            # Graceful dev simulation
            record["status"] = "SIMULATED"
            record["delivery_channel"] = "DEV_SIMULATOR"
            _EMAIL_OUTBOX_LOG.append(record)
            if len(_EMAIL_OUTBOX_LOG) > _MAX_OUTBOX_ENTRIES:
                _EMAIL_OUTBOX_LOG.pop(0)

            logger.info(
                f"[EmailService:SIMULATED] Outbound to={clean_to} subject='{subject}' (Event: {event_type})"
            )
            return {
                "message_id": msg_id,
                "status": "SIMULATED",
                "recipient": clean_to,
                "subject": subject,
                "note": "SMTP credentials not provided in .env — simulated successfully in Outbox.",
            }

        # Real SMTP delivery via threadpool
        def _send_sync():
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = clean_to
            msg["Date"] = email.utils.formatdate(localtime=True)
            msg["Message-ID"] = email.utils.make_msgid(domain="namma-civic.ai")

            part1 = MIMEText(text_content, "plain", "utf-8")
            part2 = MIMEText(html_content, "html", "utf-8")
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(settings.email_host, settings.email_port, timeout=12.0) as server:
                server.ehlo()
                if settings.email_use_tls:
                    server.starttls()
                    server.ehlo()
                if settings.email_user and settings.email_password:
                    server.login(settings.email_user, settings.email_password)
                server.sendmail(from_email, [clean_to], msg.as_string())

        try:
            await asyncio.to_thread(_send_sync)
            record["status"] = "SENT"
            record["delivery_channel"] = f"SMTP ({settings.email_host})"
            _EMAIL_OUTBOX_LOG.append(record)
            logger.info(f"[EmailService:SENT] Delivered to={clean_to} subject='{subject}'")
            return {
                "message_id": msg_id,
                "status": "SENT",
                "recipient": clean_to,
                "subject": subject,
            }
        except Exception as e:
            record["status"] = "FAILED"
            record["error"] = str(e)
            _EMAIL_OUTBOX_LOG.append(record)
            logger.error(f"[EmailService:ERROR] Failed delivering to {clean_to}: {e}")
            return {
                "message_id": msg_id,
                "status": "FAILED",
                "recipient": clean_to,
                "error": str(e),
            }

    # ── Lifecycle Automated Triggers ────────────────────────────────────────

    @classmethod
    async def send_complaint_confirmation(
        cls,
        complaint: Any,
        citizen_email: str,
        citizen_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch ticket intake confirmation to citizen."""
        cid = str(getattr(complaint, "id", "UNKNOWN"))
        short_id = str(getattr(complaint, "tracking_id", None) or cid[:8].upper())
        title = getattr(complaint, "title", "Civic Grievance")
        category = getattr(complaint, "category", "General")
        if hasattr(category, "value"):
            category = category.value
        priority = getattr(complaint, "priority", "Normal")
        if hasattr(priority, "value"):
            priority = priority.value
        address = getattr(complaint, "address", "Municipal Ward")

        subject = f"Grievance Acknowledged: #{short_id} — {title}"
        greeting = f"Dear {citizen_name or 'Citizen'},"

        body = f"""
        <p style="margin-top:0;">{greeting}</p>
        <p>Your civic grievance has been officially registered with the municipal administration. Our autonomous AI intake pipeline has cataloged the issue and assigned triage priority.</p>
        
        <div style="background:#F1F5F9;border-left:4px solid #0284C7;padding:14px 18px;margin:20px 0;border-radius:0 8px 8px 0;">
          <table width="100%" border="0" cellpadding="2" cellspacing="0" style="font-size:13px;">
            <tr>
              <td width="30%" style="color:#64748B;font-weight:600;">Tracking ID:</td>
              <td style="color:#0F172A;font-weight:700;font-family:monospace;">#{short_id}</td>
            </tr>
            <tr>
              <td style="color:#64748B;font-weight:600;">Category:</td>
              <td style="color:#0F172A;text-transform:capitalize;">{category.replace('_', ' ')}</td>
            </tr>
            <tr>
              <td style="color:#64748B;font-weight:600;">Priority Level:</td>
              <td style="color:#0F172A;text-transform:uppercase;font-weight:700;">{priority}</td>
            </tr>
            <tr>
              <td style="color:#64748B;font-weight:600;">Location:</td>
              <td style="color:#0F172A;">{address}</td>
            </tr>
          </table>
        </div>

        <p>You can track live progression, crew assignments, and resolution audits directly in your citizen portal.</p>
        
        <div style="margin:24px 0 10px;">
          <a href="http://localhost:5173/complaints/{cid}" style="display:inline-block;padding:10px 20px;background:#0F172A;color:#FFFFFF;text-decoration:none;border-radius:6px;font-size:13px;font-weight:600;">
            Track Grievance Status &rarr;
          </a>
        </div>
        """

        html = _build_html_wrapper(
            title="Civic Grievance Acknowledged",
            preheader=f"Grievance #{short_id} registered and triaged.",
            body_html=body,
            tracking_id=short_id,
        )

        return await cls.send_email(
            to_email=citizen_email,
            subject=subject,
            html_content=html,
            event_type="GRIEVANCE_FILED",
            complaint_id=cid,
        )

    @classmethod
    async def send_crew_dispatch_notice(
        cls,
        complaint: Any,
        citizen_email: str,
        crew_id: str,
        work_order_id: str,
        instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatch crew mobilization alert to citizen."""
        cid = str(getattr(complaint, "id", "UNKNOWN"))
        short_id = str(getattr(complaint, "tracking_id", None) or cid[:8].upper())
        title = getattr(complaint, "title", "Civic Issue")

        subject = f"Crew Dispatched: #{short_id} — Field Action In Progress"
        body = f"""
        <p style="margin-top:0;">Good news! A municipal maintenance crew has been deployed to resolve your reported issue.</p>
        
        <div style="background:#ECFDF5;border-left:4px solid #10B981;padding:14px 18px;margin:20px 0;border-radius:0 8px 8px 0;">
          <table width="100%" border="0" cellpadding="2" cellspacing="0" style="font-size:13px;">
            <tr>
              <td width="30%" style="color:#065F46;font-weight:600;">Work Order:</td>
              <td style="color:#064E3B;font-weight:700;font-family:monospace;">{work_order_id}</td>
            </tr>
            <tr>
              <td style="color:#065F46;font-weight:600;">Assigned Crew:</td>
              <td style="color:#064E3B;font-weight:700;">{crew_id}</td>
            </tr>
            <tr>
              <td style="color:#065F46;font-weight:600;">Status:</td>
              <td style="color:#047857;font-weight:700;">FIELD CREW MOBILIZED</td>
            </tr>
          </table>
        </div>

        <p style="font-size:13px;color:#475569;">
          {instructions or 'Field engineers are equipped with necessary materials to remediate the defect according to municipal specifications.'}
        </p>

        <div style="margin:24px 0 10px;">
          <a href="http://localhost:5173/complaints/{cid}" style="display:inline-block;padding:10px 20px;background:#059669;color:#FFFFFF;text-decoration:none;border-radius:6px;font-size:13px;font-weight:600;">
            View Live Work Order &rarr;
          </a>
        </div>
        """

        html = _build_html_wrapper(
            title="Field Crew Dispatched",
            preheader=f"Crew {crew_id} mobilized for ticket #{short_id}",
            body_html=body,
            tracking_id=short_id,
        )

        return await cls.send_email(
            to_email=citizen_email,
            subject=subject,
            html_content=html,
            event_type="CREW_DISPATCHED",
            complaint_id=cid,
        )

    @classmethod
    async def send_resolution_notice(
        cls,
        complaint: Any,
        citizen_email: str,
        resolution_notes: str,
        confidence_score: float = 0.95,
    ) -> Dict[str, Any]:
        """Dispatch closure and resolution notice with inspection score."""
        cid = str(getattr(complaint, "id", "UNKNOWN"))
        short_id = str(getattr(complaint, "tracking_id", None) or cid[:8].upper())
        title = getattr(complaint, "title", "Civic Issue")

        subject = f"Resolved: #{short_id} — Verification Complete"
        score_pct = int(confidence_score * 100)

        body = f"""
        <p style="margin-top:0;">Your grievance has been verified and marked as <strong>RESOLVED</strong> by municipal quality assurance.</p>
        
        <div style="background:#F0FDF4;border:1px solid #BBF7D0;padding:16px;border-radius:8px;margin:20px 0;">
          <div style="font-size:13px;font-weight:700;color:#166534;margin-bottom:6px;">
            AI Vision & Field Inspection: PASSED ({score_pct}% Confidence)
          </div>
          <p style="margin:0;font-size:13px;color:#15803D;">
            &ldquo;{resolution_notes}&rdquo;
          </p>
        </div>

        <p>Thank you for participating in proactive civic governance. Your report helped keep our community safe and accessible.</p>

        <div style="margin:24px 0 10px;">
          <a href="http://localhost:5173/complaints/{cid}" style="display:inline-block;padding:10px 20px;background:#16A34A;color:#FFFFFF;text-decoration:none;border-radius:6px;font-size:13px;font-weight:600;">
            Review Resolution Proof &rarr;
          </a>
        </div>
        """

        html = _build_html_wrapper(
            title="Issue Successfully Resolved",
            preheader=f"Ticket #{short_id} resolved and verified.",
            body_html=body,
            tracking_id=short_id,
        )

        return await cls.send_email(
            to_email=citizen_email,
            subject=subject,
            html_content=html,
            event_type="ISSUE_RESOLVED",
            complaint_id=cid,
        )

    @classmethod
    async def send_emergency_sla_alert(
        cls,
        complaint: Any,
        officer_email: str,
        sla_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Dispatch high-priority alert to municipal officer when SLA is breached or at risk."""
        cid = str(getattr(complaint, "id", "UNKNOWN"))
        short_id = str(getattr(complaint, "tracking_id", None) or cid[:8].upper())
        title = getattr(complaint, "title", "Civic Incident")
        hours_left = sla_info.get("hours_remaining", 0)

        subject = f"⚠️ SLA ALERT: #{short_id} — {hours_left:.1f}h Remaining"
        body = f"""
        <p style="margin-top:0;color:#991B1B;font-weight:700;">URGENT MUNICIPAL ESCALATION</p>
        <p>Complaint #{short_id} ({title}) has reached critical SLA threshold and requires immediate officer supervision.</p>
        
        <div style="background:#FEF2F2;border:1px solid #FECACA;border-left:4px solid #DC2626;padding:14px;border-radius:0 8px 8px 0;margin:20px 0;">
          <table width="100%" border="0" cellpadding="2" cellspacing="0" style="font-size:13px;">
            <tr>
              <td width="35%" style="color:#991B1B;font-weight:600;">SLA Status:</td>
              <td style="color:#B91C1C;font-weight:700;">{sla_info.get('sla_status', 'CRITICAL')}</td>
            </tr>
            <tr>
              <td style="color:#991B1B;font-weight:600;">Hours Remaining:</td>
              <td style="color:#B91C1C;font-weight:700;">{hours_left:.1f} Hours</td>
            </tr>
            <tr>
              <td style="color:#991B1B;font-weight:600;">Consumption:</td>
              <td style="color:#B91C1C;font-weight:700;">{sla_info.get('percent_consumed', 100)}%</td>
            </tr>
          </table>
        </div>

        <div style="margin:24px 0 10px;">
          <a href="http://localhost:5173/officer" style="display:inline-block;padding:10px 20px;background:#DC2626;color:#FFFFFF;text-decoration:none;border-radius:6px;font-size:13px;font-weight:600;">
            Open Officer Workstation &rarr;
          </a>
        </div>
        """

        html = _build_html_wrapper(
            title="Urgent SLA Escalation Alert",
            preheader=f"SLA Breach Warning for #{short_id}",
            body_html=body,
            tracking_id=short_id,
        )

        return await cls.send_email(
            to_email=officer_email,
            subject=subject,
            html_content=html,
            event_type="SLA_BREACH_ALERT",
            complaint_id=cid,
        )
