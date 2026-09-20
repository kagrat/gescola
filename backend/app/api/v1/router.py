from fastapi import APIRouter

from app.api.v1 import (
    academic, attendance, audit, auth, canteen, finance, grades, guardian, library, networks, notifications, reports,
    tenants, users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(networks.router)
api_router.include_router(users.router)
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
