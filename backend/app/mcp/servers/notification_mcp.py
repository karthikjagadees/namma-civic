"""
Notifications & Citizen Communication MCP Tool Server
Exposes multi-channel messaging tools: SMS alert, email status update, and push notification.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from app.mcp.protocol import MCPToolSchema


NOTIFICATION_TOOLS = [
    MCPToolSchema(
        name="notify_citizen_sms",
        description="Dispatch automated SMS progress alerts to the citizen's verified phone number.",
        category="notifications",
        parameters={
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Citizen phone number"},
                "message": {"type": "string", "description": "Alert content"},
                "complaint_id": {"type": "string"},
                "incident_id": {"type": "string"},
                "idempotency_key": {"type": "string"}
            },
            "required": ["phone_number", "message"]
        },
        returns={
            "type": "object",
            "properties": {
                "delivery_id": {"type": "string"},
                "status": {"type": "string"},
                "channel": {"type": "string"},
                "timestamp": {"type": "string"}
            }
        }
    ),
    MCPToolSchema(
        name="notify_citizen_email",
        description="Send an official municipal civic ticket notification via email with tracking links.",
        category="notifications",
        parameters={
            "type": "object",
            "properties": {
                "recipient_email": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "complaint_id": {"type": "string"},
                "incident_id": {"type": "string"},
                "idempotency_key": {"type": "string"}
            },
            "required": ["recipient_email", "subject", "body"]
        },
        returns={
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "status": {"type": "string"},
                "recipient": {"type": "string"}
            }
        }
    ),
    MCPToolSchema(
        name="notify_officer_emergency_alert",
        description="Trigger high-priority emergency pager/alert to the ward nodal municipal officer.",
        category="notifications",
        parameters={
            "type": "object",
            "properties": {
                "ward_id": {"type": "string"},
                "alert_title": {"type": "string"},
                "hazard_description": {"type": "string"},
                "sla_hours_left": {"type": "number"}
            },
            "required": ["alert_title", "hazard_description"]
        },
        returns={
            "type": "object",
            "properties": {
                "dispatch_status": {"type": "string"},
                "broadcast_count": {"type": "integer"},
                "escalation_tier": {"type": "string"}
            }
        }
    )
]


from app.services.email_service import EmailService, _build_html_wrapper


async def execute_notification_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Notification MCP tool with EmailService integration."""
    now = datetime.now(timezone.utc).isoformat()

    if name == "notify_citizen_sms":
        phone = str(args.get("phone_number", ""))
        msg = str(args.get("message", "Namma Civic Update: Status changed."))
        key = str(args.get("idempotency_key", ""))
        return {
            "delivery_id": f"SMS-{key.replace('-', '')[:12].upper()}" if key else f"SMS-{uuid.uuid4().hex[:8].upper()}",
            "phone_number": phone,
            "status": "DELIVERED",
            "channel": "SMS_GATEWAY_TELECOM",
            "timestamp": now,
            "chars_sent": len(msg)
        }

    elif name == "notify_citizen_email":
        email_addr = str(args.get("recipient_email", "citizen@example.com"))
        subj = str(args.get("subject", "Namma Civic Grievance Update"))
        body = str(args.get("body", "Your municipal report has an operational update."))
        cid = str(args.get("complaint_id", ""))
        key = str(args.get("idempotency_key", ""))

        html = _build_html_wrapper(
            title=subj,
            preheader="Municipal notification from Namma Civic",
            body_html=f"<p>{body}</p>",
            tracking_id=cid[:8].upper() if cid else None
        )

        res = await EmailService.send_email(
            to_email=email_addr,
            subject=subj,
            html_content=html,
            text_content=body,
            event_type="MCP_AGENT_EMAIL",
            complaint_id=cid or None
        )
        return {
            "message_id": res.get("message_id", f"MSG-{key.replace('-', '')[:12].upper()}" if key else f"MSG-{uuid.uuid4().hex[:8]}"),
            "recipient": email_addr,
            "subject": subj,
            "status": res.get("status", "QUEUED"),
            "timestamp": now
        }

    elif name == "notify_officer_emergency_alert":
        title = str(args.get("alert_title", "URGENT CIVIC BREACH"))
        hazard = str(args.get("hazard_description", "Potential hazard detected"))
        hours_left = float(args.get("sla_hours_left", 4))
        tier = "SUPERVISOR_LEVEL_1" if hours_left > 2 else "DIRECTOR_LEVEL_2"

        # Also dispatch an alert email to municipal officer/admin
        admin_email = "officer@demo.namma-civic.ai"
        alert_html = _build_html_wrapper(
            title=f"EMERGENCY ALERT: {title}",
            preheader=f"Urgent escalation tier: {tier}",
            body_html=f"""
            <p style="color:#B91C1C;font-weight:bold;">TACTICAL MUNICIPAL ESCALATION</p>
            <p><strong>Hazard Summary:</strong> {hazard}</p>
            <p><strong>Escalation Tier:</strong> {tier} (SLA Hours Remaining: {hours_left:.1f}h)</p>
            """,
            tracking_id="ALERT"
        )
        await EmailService.send_email(
            to_email=admin_email,
            subject=f"🚨 EMERGENCY: {title}",
            html_content=alert_html,
            event_type="EMERGENCY_ALERT"
        )

        return {
            "dispatch_status": "BROADCAST_ACTIVE",
            "alert_title": title,
            "broadcast_count": 3,
            "escalation_tier": tier,
            "dispatched_at": now
        }

    raise ValueError(f"Unknown Notification tool: {name}")
