from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.middleware.tenant import TenantMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch the alert scheduler
    from app.services.alerts.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    # Shutdown: stop the alert scheduler
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Middleware (order matters — outermost first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api.v1.auth import router as auth_router  # noqa: E402
from app.api.v1.organizations import router as org_router  # noqa: E402
from app.api.v1.rag import router as rag_router  # noqa: E402
from app.api.v1.employees import router as employees_router  # noqa: E402
from app.api.v1.leave import router as leave_router  # noqa: E402
from app.api.v1.documents import router as documents_router  # noqa: E402
from app.api.v1.policies import router as policies_router  # noqa: E402
from app.api.v1.chat import router as chat_router  # noqa: E402
from app.api.v1.webhooks import router as webhooks_router  # noqa: E402
from app.api.v1.alerts import router as alerts_router  # noqa: E402

app.include_router(auth_router, prefix="/api/v1")
app.include_router(org_router, prefix="/api/v1")
app.include_router(rag_router, prefix="/api/v1")
app.include_router(employees_router, prefix="/api/v1")
app.include_router(leave_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(policies_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME}

