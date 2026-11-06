"""
Namma Civic — Central API Router
Aggregates all versioned routers.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, agents, ai, analytics, auth, complaints, duplicate_reviews, gis, health, incidents, mcp, notifications, officer, resolution, sla

# Root API router — all routes mounted under /api
api_router = APIRouter(prefix="/api")

# ── v1 Routes ────────────────────────────────────────────────
api_router.include_router(health.router)
api_router.include_router(gis.router)             # Maps & Geocoding: /api/gis/*
api_router.include_router(notifications.router)   # Email & SMTP: /api/notifications/*
api_router.include_router(auth.router)          # Phase 2: /api/auth/*
api_router.include_router(complaints.router)    # Phase 3: /api/complaints/*
api_router.include_router(incidents.router)     # Phase 5: /api/incidents/*
api_router.include_router(ai.router)            # Phase 4: /api/ai/*
api_router.include_router(agents.router)        # Phase 5: /api/agents/*
api_router.include_router(mcp.router)           # Phase 6: /api/mcp/*
api_router.include_router(sla.router)           # Phase 7: /api/sla/*
api_router.include_router(resolution.router)    # Phase 8: /api/resolution/*
api_router.include_router(analytics.router)     # Phase 9: /api/analytics/*
api_router.include_router(officer.router)       # Phase 11: /api/officer/*
api_router.include_router(duplicate_reviews.router)  # Phase 6: /api/officer/duplicate-reviews/*
api_router.include_router(admin.router)         # Phase 11: /api/admin/*

# api_router.include_router(complaints.router, prefix="/complaints")
