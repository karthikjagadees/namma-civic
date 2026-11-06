# Namma Civic — REST API Reference

Base URL: `http://localhost:8000/api`

Swagger UI: `http://localhost:8000/docs`

## Authentication

All protected endpoints require:

```
Authorization: Bearer <JWT_TOKEN>
```

### POST /auth/register
Register a new citizen account.

### POST /auth/login
Returns JWT access token.

### GET /auth/me
Returns current user profile.

---

## Complaints

### POST /complaints
Submit a new complaint. Triggers LangGraph pipeline asynchronously.

**Body:**
```json
{
  "title": "Large pothole",
  "description": "...",
  "latitude": 22.57,
  "longitude": 88.36,
  "address": "MG Road, Kolkata"
}
```

### GET /complaints
List complaints (role-filtered).

Query params: `status`, `priority`, `category`, `department_id`, `page`, `limit`

### GET /complaints/{id}
Get complaint details including AI analysis, agent trace, timeline.

### PATCH /complaints/{id}
Update complaint (officer/admin only).

### POST /complaints/{id}/media
Upload image/audio for a complaint.

### POST /complaints/{id}/analyze
Trigger AI re-analysis of a complaint.

---

## AI

### POST /ai/analyze
Analyze raw text + image without creating a complaint (demo/testing).

### GET /ai/analysis/{complaint_id}
Get full AI analysis result for a complaint.

---

## Tasks

### GET /tasks
List civic tasks (officer/admin).

### GET /tasks/{id}
Get task details.

### PATCH /tasks/{id}/status
Update task status (officer).

**Body:**
```json
{
  "status": "in_progress",
  "remarks": "Team dispatched"
}
```

---

## Routing

### POST /routing/{complaint_id}
Manually trigger routing decision (admin/officer).

---

## Resolution

### POST /complaints/{id}/resolution
Upload resolution evidence (before + after image).

### POST /complaints/{id}/verify-resolution
Trigger AI resolution verification.

---

## Analytics

### GET /analytics/overview
Summary statistics dashboard data.

### GET /analytics/trends
Complaint trends over time.

### GET /analytics/hotspots
Civic hotspot locations and data.

### GET /analytics/department-kpis
Department performance metrics.

---

## Admin

### GET /admin/users
List all users.

### PATCH /admin/users/{id}
Update user (activate, change role).

### GET /admin/departments
List departments.

### POST /admin/departments
Create department.

### GET /admin/audit-logs
System audit log.

### GET /admin/ai-config
Current AI provider configuration.

---

## Notifications

### GET /notifications
List user notifications.

### PATCH /notifications/{id}/read
Mark notification as read.

### POST /notifications/read-all
Mark all notifications as read.

---

## Status Codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized |
| 403 | Forbidden (RBAC) |
| 404 | Not Found |
| 422 | Unprocessable Entity |
| 429 | Rate Limited |
| 500 | Internal Server Error |
