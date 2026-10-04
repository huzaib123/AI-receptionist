"""
AI Receptionist & Operations Orchestrator — FastAPI entry‑point.

Run with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
import time
import os

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.ml import NoShowRequest, NoShowResponse
from app.agent.agent import run_agent
from app.db.session import get_db, engine, Base
from app.db import crud
from app.ml.no_show_model import predict_no_show_prob
from app.core.security import admin_key_is_strong, check_rate_limit, verify_admin_key
from app.core.business_profile import get_business_profile

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── FastAPI app ────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Receptionist",
    version="0.2.0",
    description="Conversational AI receptionist for service businesses — now with database storage and admin endpoints.",
    docs_url="/docs" if settings.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_API_DOCS else None,
)

# The widget runs on client websites, so any origin may call the API. No
# cookies are used, so credentials stay off and that can't be abused.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-API-Key"],
)

# Bigger bodies than any real chat message are refused before being read.
MAX_BODY_BYTES = 16 * 1024


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > MAX_BODY_BYTES):
        return JSONResponse({"detail": "Request too large."}, status_code=413)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if response.headers.get("content-type", "").startswith("application/json"):
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    return response


if not admin_key_is_strong(settings.ADMIN_API_KEY):
    logger.warning("ADMIN_API_KEY is missing or weak, so the admin endpoints are disabled.")

# ── Metrics Registry ────────────────────────────────────────────────────────
class Metrics:
    total_chat_requests = 0
    tool_error_count = 0
    model_call_latency_total = 0.0
    model_call_count = 0

    @classmethod
    def get_average_latency(cls) -> float:
        if cls.model_call_count == 0:
            return 0.0
        return cls.model_call_latency_total / cls.model_call_count

# Auto-create tables on startup (convenience for local dev/testing)
Base.metadata.create_all(bind=engine)


# ── Routes ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/api/profile")
def public_profile():
    """Public business details used by the website and the chat widget."""
    p = get_business_profile()
    return {
        "name": p.name,
        "industry": p.industry,
        "tagline": p.tagline,
        "address": p.address,
        "phone": p.phone,
        "email": p.email,
        "hours": p.hours,
        "brand_color": p.brand_color,
        "languages": p.languages,
        "currency": p.currency,
        "services": [s.model_dump() for s in p.services],
        "whatsapp_link": p.whatsapp_link(),
    }


WIDGET_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "widget", "widget.js")


@app.get("/widget.js", include_in_schema=False)
def widget_js():
    """Embeddable chat widget: <script src="https://HOST/widget.js" defer></script>"""
    return FileResponse(WIDGET_JS, media_type="application/javascript")


@app.get("/admin/bookings/today", dependencies=[Depends(verify_admin_key)])
def get_admin_bookings_today(db: Session = Depends(get_db)):
    """
    List all bookings scheduled for today. Requires Admin API Key.
    """
    try:
        bookings = crud.get_bookings_today(db)
        res = []
        for b in bookings:
            res.append({
                "id": b.id,
                "service": b.service,
                "datetime": b.datetime.isoformat(),
                "status": b.status,
                "source": b.source,
                "calendar_event_id": b.calendar_event_id,
                "event_link": b.event_link,
                "notes": b.notes,
                "created_at": b.created_at.isoformat(),
                "customer": {
                    "id": b.customer.id,
                    "name": b.customer.name,
                    "phone": b.customer.phone,
                    "email": b.customer.email,
                }
            })
        return res
    except Exception as exc:
        logger.exception("Failed to retrieve today's bookings")
        raise HTTPException(status_code=500, detail="Internal error.") from exc


@app.get("/admin/stats", dependencies=[Depends(verify_admin_key)])
def get_admin_stats(db: Session = Depends(get_db)):
    """
    Get aggregate counts and breakdown for bookings, plus system observability metrics.
    Requires Admin API Key.
    """
    try:
        stats = crud.get_aggregate_stats(db)
        stats.update({
            "total_chat_requests": Metrics.total_chat_requests,
            "tool_error_count": Metrics.tool_error_count,
            "avg_model_call_latency_ms": round(Metrics.get_average_latency(), 2)
        })
        return stats
    except Exception as exc:
        logger.exception("Failed to compute booking statistics")
        raise HTTPException(status_code=500, detail="Internal error.") from exc


@app.post("/ml/no_show", response_model=NoShowResponse, dependencies=[Depends(check_rate_limit)])
def get_no_show_prediction(payload: NoShowRequest):
    """
    Predict no-show risk probability for a booking slot based on customer history and scheduled slot parameters.
    """
    try:
        prob = predict_no_show_prob(
            age=payload.age,
            days_until_appointment=payload.days_until_appointment,
            past_no_shows=payload.past_no_shows,
            appointment_hour=payload.appointment_hour,
            day_of_week=payload.day_of_week,
        )
        risk = "high" if prob > 0.3 else "medium" if prob > 0.15 else "low"
        return NoShowResponse(no_show_probability=prob, risk_level=risk)
    except Exception as exc:
        logger.exception("No-show prediction endpoint failed")
        raise HTTPException(status_code=500, detail="Internal error.") from exc


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(check_rate_limit)])
async def chat(payload: ChatRequest):
    """
    Chat with the AI receptionist agent.
    The agent can call tools (calendar, FAQ, CRM, no‑show prediction) as
    needed to fulfil the customer's request.
    """
    start = time.perf_counter()
    Metrics.total_chat_requests += 1

    logger.info("← /chat  message_len=%d session_id=%s", len(payload.message), payload.session_id)

    try:
        result = await run_agent(payload.message, session_id=payload.session_id)
    except Exception as exc:
        Metrics.tool_error_count += 1
        logger.exception("Agent call failed")
        # Provider error text can name models, keys' projects or limits;
        # it stays in the server log and the visitor gets a plain message.
        raise HTTPException(
            status_code=502,
            detail="The receptionist is temporarily unavailable. Please try again shortly.",
        ) from exc

    elapsed_ms = (time.perf_counter() - start) * 1000
    Metrics.model_call_latency_total += elapsed_ms
    Metrics.model_call_count += 1

    logger.info(
        "→ /chat  reply_len=%d  tools=%s  elapsed=%.0fms",
        len(result["reply"]),
        result["tools_called"],
        elapsed_ms,
    )

    return ChatResponse(
        reply=result["reply"],
        tools_called=result["tools_called"],
        usage=result["usage"],
    )

# ── Serve Static Frontend ───────────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="static")

    @app.get("/{fallback_path:path}")
    async def fallback(fallback_path: str):
        # Do not catch API paths so that regular 404 works for invalid endpoints
        if (fallback_path.startswith("chat") or
                fallback_path.startswith("admin") or
                fallback_path.startswith("ml") or
                fallback_path.startswith("health") or
                fallback_path.startswith("api")):
            raise HTTPException(status_code=404, detail="Not Found")
        
        index_file = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Index file not found")




