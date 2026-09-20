from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Ajoute les en-têtes de sécurité HTTP recommandés (OWASP Secure Headers).

    HSTS n'est ajouté que si la requête est déjà en HTTPS (ou derrière un proxy
    qui le signale), pour ne pas casser un environnement de dev en HTTP.

    La CSP par défaut ("default-src 'self'") est volontairement stricte pour
    toutes les réponses de l'API elle-même (données JSON, pas de script tiers
    à charger). Elle est assouplie UNIQUEMENT sur /docs, /redoc et leurs
    dépendances : ces pages HTML générées par FastAPI chargent Swagger UI
    depuis un CDN externe (cdn.jsdelivr.net) — sans cette exception, le
    navigateur charge la page mais bloque son JavaScript, ce qui donne une
    page blanche (observé en déploiement staging).
    """

    DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        if request.url.path in self.DOCS_PATHS:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                "img-src 'self' https://fastapi.tiangolo.com data:; "
                "font-src 'self' https://cdn.jsdelivr.net;"
            )
        else:
            response.headers["Content-Security-Policy"] = "default-src 'self'"

        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
