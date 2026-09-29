import logging
import time
import uuid
import asyncio
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.hindsight_client import HindsightUnavailableError, get_hindsight_service
from app.services.incident_agent import get_incident_agent
from app.services import store
from app.services.seed_data import SEED_INCIDENTS
from app.services.severity import classify
from app.services.trust import extract_telemetry

logging.basicConfig(level=logging.INFO)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Make sure the Hindsight memory bank is available at startup."""
    await asyncio.to_thread(get_hindsight_service().ensure_bank)
    yield


app = FastAPI(
    title="SecOps Memory API",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in settings.cors_origins.split(",")
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Request / Response Models
# ============================================================


class IncidentRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    concise: bool = False  # "Summary Mode": 3-bullet executive summary


class MemoryDetail(BaseModel):
    text: str
    score: float | None = None
    tags: list[str] = []
    document_id: str | None = None
    trust_tier: str = "unclassified"


class IncidentResponse(BaseModel):
    incident_id: str
    title: str
    description: str
    response: str
    memories_used: list[str]
    memory_details: list[MemoryDetail] = []
    hindsight_available: bool
    severity: str
    category: str
    similar_incidents: int  # resolved incidents of same category we have handled before
    estimated_minutes: int | None = None  # avg historical time-to-resolve for this category
    memory_count: int  # total resolved incidents retained so far
    analysis_ms: int
    concise: bool = False


class ResolveRequest(BaseModel):
    title: str = Field(..., min_length=1)
    incident_description: str = Field(..., min_length=1)

    # What the AI originally recommended
    ai_response: str = Field(..., min_length=1)

    # What the analyst actually did
    analyst_actions: str = Field(..., min_length=1)

    # Final result
    outcome: str = Field(..., min_length=1)

    # Human feedback about the response
    analyst_feedback: str = Field(..., min_length=1)

    # Optional: how long the incident took to resolve (drives time estimates)
    resolution_minutes: int | None = Field(default=None, ge=0)


class ResolveResponse(BaseModel):
    incident_id: str
    stored: bool
    message: str
    memory_count: int = 0


class PoisoningDemoRequest(BaseModel):
    username: str = Field(default="", max_length=256)
    user_agent: str = Field(default="", max_length=1024)
    remark: str = Field(..., min_length=1, max_length=2000)


class PoisoningDemoResponse(BaseModel):
    document_id: str
    stored: bool
    trust_tier: str
    telemetry_indicators: dict
    baseline_response: str
    protected_response: str
    raw_remark_excluded_from_protected_prompt: bool


# ============================================================
# Health
# ============================================================


@app.get("/health")
def health() -> dict:
    hindsight_ok = (
        get_hindsight_service().ensure_bank()
    )

    return {
        "status": "ok",
        "env": settings.app_env,
        "hindsight_bank_id": settings.hindsight_bank_id,
        "hindsight_reachable": hindsight_ok,
    }


# ============================================================
# Analyze Incident
# ============================================================


@app.post(
    "/incidents/analyze",
    response_model=IncidentResponse,
)
def analyze_incident(
    request: IncidentRequest,
) -> IncidentResponse:

    try:
        agent = get_incident_agent()

        incident_text = (
            f"Incident title: {request.title}\n\n"
            f"Incident description: {request.description}"
        )

        cls = classify(request.title, request.description)

        started = time.perf_counter()
        result = agent.analyze(incident_text, concise=request.concise)
        analysis_ms = int((time.perf_counter() - started) * 1000)

        past = store.resolved_of_category(cls["category"])
        times = [
            i["resolution_minutes"]
            for i in past
            if i.get("resolution_minutes") is not None
        ]
        estimated = round(sum(times) / len(times)) if times else None

        incident_id = store.new_incident_id()
        memory_count = len(
            [
                i
                for i in store.list_incidents()
                if i.get("status") == "resolved" and not i.get("memory_revoked")
            ]
        )

        store.upsert({
            "id": incident_id,
            "title": request.title,
            "description": request.description,
            "severity": cls["severity"],
            "category": cls["category"],
            "status": "open",
            "created_at": store.now_iso(),
            "memories_recalled": len(result.memories_used),
            "similar_incidents": len(past),
            "analysis_ms": analysis_ms,
            "memory_details": [
                {
                    "document_id": memory.get("document_id"),
                    "trust_tier": memory.get("trust_tier"),
                    "tags": memory.get("tags", []),
                }
                for memory in result.memory_details
            ],
        })

        return IncidentResponse(
            incident_id=incident_id,
            title=request.title,
            description=request.description,
            response=result.response,
            memories_used=result.memories_used,
            memory_details=result.memory_details,
            hindsight_available=result.hindsight_available,
            severity=cls["severity"],
            category=cls["category"],
            similar_incidents=len(past),
            estimated_minutes=estimated,
            memory_count=memory_count,
            analysis_ms=analysis_ms,
            concise=request.concise,
        )

    except Exception as exc:
        logging.exception(
            "Incident analysis failed"
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# Resolve Incident + Store Analyst Feedback
# ============================================================


@app.post(
    "/incidents/{incident_id}/resolve",
    response_model=ResolveResponse,
)
def resolve_incident(
    incident_id: str,
    request: ResolveRequest,
) -> ResolveResponse:

    try:
        hindsight = get_hindsight_service()
        known = store.get_incident(incident_id)

        # Create a complete narrative for Hindsight.
        #
        # This is important because we want future agents to learn
        # not only what the incident was, but also:
        # - what AI recommended
        # - what the analyst actually did
        # - what the outcome was
        # - what the analyst learned
        memory_content = f"""
Resolved Security Incident

Incident ID:
{incident_id}

Incident Title:
{request.title}

Incident Description:
{request.incident_description}

AI Response:
{request.ai_response}

Actual Analyst Actions:
{request.analyst_actions}

Outcome:
{request.outcome}

Analyst Feedback:
{request.analyst_feedback}

Lesson for Future Incidents:
The analyst feedback and actual response above should be considered
when handling similar security incidents in the future.
""".strip()

        stored = hindsight.retain_incident_experience(
            incident_id=incident_id,
            summary_content=memory_content,
            incident_type="security_incident",
            outcome=request.outcome,
            extra_tags=(
                [f"category:{known['category']}", f"severity:{known['severity']}"]
                if known else None
            ),
        )

        if not stored:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Incident was received, but the experience "
                    "could not be stored in Hindsight."
                ),
            )

        cls = known or {
            **classify(request.title, request.incident_description),
            "id": incident_id,
            "title": request.title,
            "description": request.incident_description,
            "created_at": store.now_iso(),
        }
        store.upsert({
            **cls,
            "status": "resolved",
            "resolved_at": store.now_iso(),
            "outcome": request.outcome,
            "analyst_actions": request.analyst_actions,
            "analyst_feedback": request.analyst_feedback,
            "resolution_minutes": request.resolution_minutes,
        })
        memory_count = len(
            [
                i
                for i in store.list_incidents()
                if i.get("status") == "resolved" and not i.get("memory_revoked")
            ]
        )

        return ResolveResponse(
            incident_id=incident_id,
            memory_count=memory_count,
            stored=True,
            message=(
                "Incident resolution and analyst feedback "
                "were successfully stored in Hindsight."
            ),
        )

    except HTTPException:
        raise

    except Exception as exc:
        logging.exception(
            "Incident resolution failed"
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# History / Timeline / Stats / Demo seed
# ============================================================


@app.get("/incidents/history")
def incident_history() -> dict:
    """All incidents (newest first) with how much memory each used."""
    items = store.list_incidents()
    return {"count": len(items), "incidents": items}


@app.get("/memory/timeline")
def memory_timeline() -> dict:
    """How the agent's knowledge grew: cumulative retained experiences over time."""
    resolved = sorted(
        (
            i
            for i in store.list_incidents()
            if i.get("status") == "resolved" and not i.get("memory_revoked")
        ),
        key=lambda i: i.get("resolved_at") or i.get("created_at", ""),
    )
    points = [
        {
            "n": n,
            "incident_id": i["id"],
            "title": i["title"],
            "category": i.get("category"),
            "severity": i.get("severity"),
            "at": i.get("resolved_at") or i.get("created_at"),
            "lesson": (i.get("analyst_feedback") or "")[:160],
        }
        for n, i in enumerate(resolved, start=1)
    ]
    return {"memory_count": len(points), "timeline": points}


@app.get("/stats")
def stats() -> dict:
    items = store.list_incidents()
    resolved = [i for i in items if i.get("status") == "resolved"]
    active_memories = [i for i in resolved if not i.get("memory_revoked")]
    analyzed = [i for i in items if i.get("memories_recalled") is not None]

    cats = Counter(i.get("category", "Other") for i in items)
    sevs = Counter(i.get("severity", "Medium") for i in items)

    by_cat: dict[str, list[int]] = {}
    for i in resolved:
        if i.get("resolution_minutes") is not None:
            by_cat.setdefault(i.get("category", "Other"), []).append(i["resolution_minutes"])
    avg_by_cat = {c: round(sum(v) / len(v)) for c, v in by_cat.items()}

    # Learning curve: memories recalled per analyzed incident, oldest -> newest
    ordered = sorted(analyzed, key=lambda i: i.get("created_at", ""))
    learning_curve = [
        {
            "n": n,
            "title": i["title"],
            "memories_recalled": i["memories_recalled"],
            "analysis_ms": i.get("analysis_ms"),
        }
        for n, i in enumerate(ordered, start=1)
    ]
    used = [i for i in analyzed if i["memories_recalled"] > 0]

    # Resolution time trend (oldest -> newest) for the "getting faster" story
    timed = sorted(
        (i for i in resolved if i.get("resolution_minutes") is not None),
        key=lambda i: i.get("resolved_at") or "",
    )
    half = len(timed) // 2
    improvement = None
    if half >= 1:
        first = sum(i["resolution_minutes"] for i in timed[:half]) / half
        last = sum(i["resolution_minutes"] for i in timed[half:]) / (len(timed) - half)
        improvement = round((first - last) / first * 100) if first else None

    top = sorted(analyzed, key=lambda i: i["memories_recalled"], reverse=True)[:5]

    return {
        "total_incidents": len(items),
        "resolved_incidents": len(resolved),
        "memory_count": len(active_memories),
        "by_category": dict(cats.most_common()),
        "by_severity": dict(sevs),
        "avg_resolution_minutes": (
            round(sum(i["resolution_minutes"] for i in timed) / len(timed)) if timed else None
        ),
        "avg_resolution_by_category": avg_by_cat,
        "resolution_time_improvement_pct": improvement,
        "memory_utilization_rate": (
            round(len(used) / len(analyzed) * 100) if analyzed else 0
        ),
        "avg_memories_per_analysis": (
            round(sum(i["memories_recalled"] for i in analyzed) / len(analyzed), 1) if analyzed else 0
        ),
        "learning_curve": learning_curve,
        "top_recalled": [
            {"id": i["id"], "title": i["title"], "memories_recalled": i["memories_recalled"]}
            for i in top
        ],
    }


@app.post("/demo/seed")
def seed_demo() -> dict:
    """Pre-load Hindsight with realistic incidents so judges start at 'experienced'."""
    hindsight = get_hindsight_service()
    now = datetime.now(timezone.utc)
    seeded, failed = 0, []

    for seed in SEED_INCIDENTS:
        cls = classify(seed["title"], seed["description"])
        content = (
            f"Resolved Security Incident\n\nIncident ID:\n{seed['id']}\n\n"
            f"Incident Title:\n{seed['title']}\n\n"
            f"Incident Description:\n{seed['description']}\n\n"
            f"Actual Analyst Actions:\n{seed['analyst_actions']}\n\n"
            f"Outcome:\n{seed['outcome']}\n\n"
            f"Analyst Feedback:\n{seed['analyst_feedback']}"
        )
        ok = hindsight.retain_incident_experience(
            incident_id=seed["id"],
            summary_content=content,
            incident_type="security_incident",
            outcome=seed["outcome"],
            extra_tags=[f"category:{cls['category']}", f"severity:{cls['severity']}", "seed:demo"],
        )
        if not ok:
            failed.append(seed["id"])
            continue
        when = (now - timedelta(days=seed["days_ago"])).isoformat()
        store.upsert({
            "id": seed["id"],
            "title": seed["title"],
            "description": seed["description"],
            **cls,
            "status": "resolved",
            "created_at": when,
            "resolved_at": when,
            "outcome": seed["outcome"],
            "analyst_actions": seed["analyst_actions"],
            "analyst_feedback": seed["analyst_feedback"],
            "resolution_minutes": seed["minutes"],
            "memories_recalled": 0,
            "seeded": True,
        })
        seeded += 1

    return {"seeded": seeded, "failed": failed, "total_seeds": len(SEED_INCIDENTS)}


@app.post("/demo/poisoning", response_model=PoisoningDemoResponse)
def demo_poisoning(request: PoisoningDemoRequest) -> PoisoningDemoResponse:
    """Compare an unfiltered baseline with Vigil's trusted-memory gate."""
    indicators = extract_telemetry(
        request.username,
        request.user_agent,
        request.remark,
    )
    document_id = f"demo-poison-{uuid.uuid4().hex}"
    untrusted_content = (
        "Attacker-controlled telemetry from a synthetic security event.\n"
        f"Username field: {request.username}\n"
        f"User-agent field: {request.user_agent}\n"
        f"Remark field: {request.remark}"
    )
    hindsight = get_hindsight_service()
    if not hindsight.retain_untrusted_demo_memory(
        document_id=document_id,
        content=untrusted_content,
    ):
        raise HTTPException(
            status_code=503,
            detail="Could not store the untrusted demo memory in Hindsight.",
        )
    try:
        stored_untrusted_memory = hindsight.get_app_memory_content(document_id)
    except HindsightUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    incident = (
        "A suspicious successful login followed repeated failed login attempts "
        "for an account. Determine the safe next response; do not dismiss it "
        "without independent evidence."
    )
    try:
        agent = get_incident_agent()
        baseline_response = agent.analyze_unfiltered_demo(
            incident,
            stored_untrusted_memory,
        )
        protected_response = agent.analyze(
            incident,
            telemetry=indicators,
        ).response
    except Exception as exc:
        logging.exception("Poisoning demo analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return PoisoningDemoResponse(
        document_id=document_id,
        stored=True,
        trust_tier="raw-user-text",
        telemetry_indicators={
            "username": indicators.username,
            "user_agent_family": indicators.user_agent_family,
            "remark_length": indicators.remark_length,
            "remark_fingerprint": indicators.remark_fingerprint,
        },
        baseline_response=baseline_response,
        protected_response=protected_response,
        raw_remark_excluded_from_protected_prompt=True,
    )


@app.get("/memory/documents")
def memory_documents() -> dict:
    """Show memory provenance and trust tier for the blame/revoke view."""
    try:
        memories = get_hindsight_service().list_app_memories()
    except HindsightUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"memories": memories}


@app.delete("/memory/documents/{document_id}")
def revoke_memory(document_id: str) -> dict:
    """Revoke an application-owned memory and mark its incident accordingly."""
    hindsight = get_hindsight_service()
    try:
        memories = hindsight.list_app_memories()
    except HindsightUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    memory = next((m for m in memories if m["document_id"] == document_id), None)
    if memory is None:
        raise HTTPException(status_code=404, detail="Application memory not found.")

    if not hindsight.revoke_app_memory(document_id):
        raise HTTPException(status_code=503, detail="Hindsight could not revoke this memory.")

    incident_id = next(
        (tag.removeprefix("incident:") for tag in memory["tags"] if tag.startswith("incident:")),
        document_id,
    )
    store.mark_memory_revoked(incident_id)
    return {"document_id": document_id, "revoked": True}
