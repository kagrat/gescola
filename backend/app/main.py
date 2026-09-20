import logging
import sys

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.limiter import limiter
from app.middleware.security_headers import SecurityHeadersMiddleware

settings = get_settings()

# Un secret par défaut ne doit JAMAIS être utilisé en production : on refuse
# de démarrer plutôt que de tourner silencieusement avec une clé faible connue.
if settings.ENVIRONMENT == "production" and settings.JWT_SECRET_KEY.startswith("CHANGE_ME"):
    sys.exit("JWT_SECRET_KEY doit être défini via une variable d'environnement en production.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gescola")

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Réponse structurée mais sans fuite de détails internes (pas de trace,
    # pas de chemin de fichier) — uniquement les erreurs de champs.
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Ne jamais renvoyer la stack trace au client — uniquement la logger côté serveur.
    logger.exception("Erreur non gérée sur %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Une erreur interne est survenue."})


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
