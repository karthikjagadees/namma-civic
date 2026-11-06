# Namma Civic — Database Design

## Default: SQLite (Development)

Zero-configuration local development. SQLite with `aiosqlite` async driver.

```env
DATABASE_URL=sqlite:///./namma-civic.db
DATABASE_MODE=sqlite
```

## Production: PostgreSQL + PostGIS

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/namma-civic
DATABASE_MODE=postgresql
```

Enable PostGIS:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

## Abstraction Layer

The `app/core/database.py` module auto-detects the driver:

```python
if settings.is_sqlite:
    engine = create_async_engine("sqlite+aiosqlite:///...")
else:
    engine = create_async_engine("postgresql+psycopg://...")
```

The `GeoService` abstraction in `app/gis/` provides:

- `SQLiteGeoService` — Python-based distance calculations
- `PostGISGeoService` — native PostGIS spatial queries

## Entity Relationship Overview

```
User ──────────── Role (many-to-many)
User ──────────── Complaint (citizen_id)
User ──────────── Officer
Department ─────── Officer (many)
Department ─────── Complaint (department_id)

Complaint ──────── ComplaintMedia (many)
Complaint ──────── ComplaintLocation (one)
Complaint ──────── AIAnalysis (one)
Complaint ──────── DuplicateMatch (many)
Complaint ──────── PriorityScore (one)
Complaint ──────── RoutingDecision (one)
Complaint ──────── CivicTask (one)
Complaint ──────── Notification (many)
Complaint ──────── Feedback (one)

CivicTask ──────── TaskStatusHistory (many)
CivicTask ──────── SLAConfiguration
CivicTask ──────── Escalation (many)
CivicTask ──────── ResolutionEvidence (one)

CivicHotspot ───── (aggregated from Complaints)
AuditLog ──────── (all state-changing operations)
```

## Key Models (added in Phase 2)

### User
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| email | String | Unique |
| hashed_password | String | bcrypt |
| full_name | String | |
| role | Enum | citizen/officer/admin |
| is_active | Boolean | |
| created_at | DateTime | |

### Complaint
| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| citizen_id | UUID | FK User |
| title | String | |
| description | Text | |
| category | Enum | pothole/garbage/... |
| status | Enum | pending/analyzing/... |
| latitude | Float | |
| longitude | Float | |
| address | String | |
| priority | Enum | low/medium/high/critical |
| severity | Integer | 1-10 |
| department_id | UUID | FK Department |
| assigned_officer_id | UUID | FK User |
| created_at | DateTime | |
| updated_at | DateTime | |

### Spatial Support

**SQLite mode:** latitude + longitude stored as Float columns.
Distance calculated in Python using Haversine formula.

**PostGIS mode:** Additional `location` column of type `GEOMETRY(Point, 4326)`.
Spatial queries use `ST_DWithin`, `ST_Distance`, `ST_Cluster`.

## Migrations

```bash
# Create a new migration
cd backend
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```
