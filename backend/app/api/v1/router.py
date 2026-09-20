from fastapi import APIRouter

from app.api.v1 import (
    academic, attendance, audit, auth, billing, canteen, establishment, finance, grades, guardian, library,
    networks, notifications, profile, reports, teaching, tenants, timetable, users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(networks.router)
api_router.include_router(billing.router)
api_router.include_router(users.router)
api_router.include_router(establishment.router)
api_router.include_router(profile.router)
api_router.include_router(teaching.router)
api_router.include_router(timetable.router)
api_router.include_router(academic.router)
api_router.include_router(grades.router)
api_router.include_router(attendance.router)
api_router.include_router(finance.router)
api_router.include_router(guardian.router)
api_router.include_router(notifications.router)
api_router.include_router(reports.router)
api_router.include_router(audit.router)
api_router.include_router(canteen.router)
api_router.include_router(library.router)
