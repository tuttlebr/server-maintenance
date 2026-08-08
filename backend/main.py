from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.auth import create_access_token, verify_admin
from backend.config import settings
from backend.database import SessionLocal, init_db
from backend.routers import chat, drivers, hosts, jobs, maintenance, networking, users
from backend.schemas import LoginRequest, TokenResponse
from backend.services.ansible_runner import PlaybookRequestError
from backend.services.inventory_writer import regenerate_inventory
from backend.services.job_log_indexer import start_reconcile as start_job_log_reconcile
from backend.services.login_throttle import (
    clear_account_failures,
    login_is_blocked,
    record_login_failure,
)
from backend.services.secret_store import encrypt_existing_host_secrets
from backend.services.ssh_enrollment import initialize_known_hosts

STATIC_DIR = Path(__file__).parent / "static"
class SPAMiddleware(BaseHTTPMiddleware):
    """Serve index.html for non-API GET requests that don't match a static file."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only intercept 404s for GET requests to non-API paths
        if (
            response.status_code == 404
            and request.method == "GET"
            and not request.url.path.startswith("/api")
        ):
            index = STATIC_DIR / "index.html"
            if index.exists():
                return FileResponse(index)

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "scans").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "logs").mkdir(parents=True, exist_ok=True)
    initialize_known_hosts()

    init_db()
    encrypt_existing_host_secrets()
    db = SessionLocal()
    try:
        regenerate_inventory(db)
    finally:
        db.close()
    # Reconcile in the background so startup stays available if Milvus or the
    # embedding endpoint is temporarily unavailable.
    start_job_log_reconcile()
    yield


app = FastAPI(
    title="Fleet Manager",
    version="1.0.0",
    lifespan=lifespan,
)

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

if STATIC_DIR.exists():
    app.add_middleware(SPAMiddleware)

# API routes
app.include_router(hosts.router)
app.include_router(users.router)
app.include_router(jobs.router)
app.include_router(drivers.router)
app.include_router(networking.router)
app.include_router(maintenance.router)
app.include_router(chat.router)


@app.exception_handler(PlaybookRequestError)
async def playbook_request_error_handler(request: Request, exc: PlaybookRequestError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request):
    client_address = request.client.host if request.client else "unknown"
    if login_is_blocked(client_address, payload.username):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many failed login attempts. Try again later."},
        )
    if not verify_admin(payload.username, payload.password):
        record_login_failure(client_address, payload.username)
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid username or password"},
        )
    clear_account_failures(payload.username)
    token = create_access_token(payload.username)
    return TokenResponse(access_token=token)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# Serve frontend static files — only mount /assets, not root
# The SPAMiddleware handles serving index.html for non-API 404s
if STATIC_DIR.exists() and (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/favicon.ico")
async def favicon():
    fav = STATIC_DIR / "favicon.ico"
    if fav.exists():
        return FileResponse(fav)
    return Response(status_code=204)


@app.get("/")
async def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"detail": "Frontend not built"}, status_code=503)
