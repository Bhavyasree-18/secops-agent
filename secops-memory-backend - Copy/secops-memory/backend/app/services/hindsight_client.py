"""
Hindsight memory service for SecOps Memory.

This module is the only place where the application talks directly
to the official hindsight-client SDK.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar

from hindsight_client import Hindsight
from hindsight_client_api.exceptions import ApiException

from app.config import get_settings
from app.services.trust import (
    ANALYST_CONFIRMED_TAG,
    APP_MEMORY_TAG,
    TRUST_TIERS,
    TRUSTED_RECALL_TAGS,
)

logger = logging.getLogger("secops_memory.hindsight")
T = TypeVar("T")


class _AsyncSdkRunner:
    """Keep the SDK's aiohttp session on one long-lived event loop."""

    def __init__(self) -> None:
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        self._ready.wait()

    def _serve(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()

    def run(self, awaitable: Awaitable[T]) -> T:
        if self._loop is None:
            raise RuntimeError("Hindsight SDK event loop did not start.")
        return asyncio.run_coroutine_threadsafe(awaitable, self._loop).result()


_sdk_runner: _AsyncSdkRunner | None = None
_sdk_runner_lock = threading.Lock()


def _get_sdk_runner() -> _AsyncSdkRunner:
    global _sdk_runner
    with _sdk_runner_lock:
        if _sdk_runner is None:
            _sdk_runner = _AsyncSdkRunner()
        return _sdk_runner


def _run_sdk_call(call: Callable[[], T | Awaitable[T]]) -> T:
    """Run either sync or async SDK APIs safely from sync service methods."""
    result = call()
    if not inspect.isawaitable(result):
        return result
    return _get_sdk_runner().run(result)


class HindsightUnavailableError(Exception):
    """Raised when Hindsight cannot be reached or used."""


@dataclass
class SimilarIncidentMemory:
    """A recalled security incident memory."""

    text: str
    score: float | None = None
    tags: list[str] = field(default_factory=list)
    document_id: str | None = None


@dataclass
class RecallResult:
    """Result returned by Hindsight recall."""

    memories: list[SimilarIncidentMemory]
    raw_query: str
    available: bool


class HindsightService:
    """Wrapper around the official Hindsight SDK."""

    def __init__(self) -> None:
        settings = get_settings()

        self._bank_id = settings.hindsight_bank_id

        self._client = Hindsight(
            base_url=settings.hindsight_base_url,
            api_key=settings.hindsight_api_key or None,
        )

        self._bank_ready = False

    def ensure_bank(self) -> bool:
        """
        Create the organization's Hindsight memory bank.

        If the bank already exists, reuse it.
        If Hindsight cannot be reached, return False instead of
        crashing the application.
        """

        if self._bank_ready:
            return True

        try:
            _run_sdk_call(
                lambda: self._client.acreate_bank(
                    bank_id=self._bank_id,
                    name="SecOps Memory — Incident Response",
                    mission=(
                        "Remember how this organization has handled past "
                        "security incidents — root causes, investigation "
                        "steps, containment actions, what worked, what did "
                        "not work, and analyst feedback — so future incidents "
                        "of a similar type get a faster and more "
                        "organization-specific response."
                    ),
                    background=(
                        "Security operations center (SOC) incident response "
                        "memory bank. Stores structured records of resolved "
                        "security incidents."
                    ),
                ),
            )

            self._bank_ready = True

            logger.info(
                "Hindsight bank '%s' ready",
                self._bank_id,
            )

            return True

        except ApiException as exc:

            # A 409 normally means the bank already exists.
            # Treat that as success.
            if exc.status == 409:
                logger.info(
                    "Hindsight bank '%s' already exists. Reusing it.",
                    self._bank_id,
                )

                self._bank_ready = True
                return True

            # Do NOT treat every 4xx as "bank already exists".
            # For example:
            # 401 -> authentication problem
            # 402 -> insufficient credits
            # 403 -> permission problem
            # 404 -> incorrect endpoint/resource
            # 422 -> invalid request
            logger.error(
                "Hindsight API error while creating bank. "
                "HTTP status: %s | Error: %s",
                exc.status,
                exc,
            )

            return False

        except Exception:
            # Print the complete traceback so we can diagnose
            # SDK/network/configuration problems.
            logger.exception(
                "Hindsight bank creation failed unexpectedly"
            )

            return False

    def recall_similar_incidents(
        self,
        query: str,
        max_tokens: int = 3000,
    ) -> RecallResult:
        """
        Recall previous incidents that are semantically similar
        to the current incident.
        """

        try:
            result = _run_sdk_call(
                lambda: self._client.arecall(
                    bank_id=self._bank_id,
                    query=query,
                    max_tokens=max_tokens,
                    budget="mid",
                    tags=TRUSTED_RECALL_TAGS,
                    tags_match="any",
                )
            )

        except Exception:
            logger.exception(
                "Hindsight recall failed. "
                "Continuing without historical memory."
            )

            return RecallResult(
                memories=[],
                raw_query=query,
                available=False,
            )

        memories = []

        for item in getattr(result, "results", []):
            tags = list(getattr(item, "tags", []) or [])
            if ANALYST_CONFIRMED_TAG not in tags:
                logger.warning(
                    "Discarding recalled memory without analyst-confirmed trust tag"
                )
                continue
            memories.append(
                SimilarIncidentMemory(
                    text=getattr(
                        item,
                        "text",
                        str(item),
                    ),
                    score=getattr(
                        item,
                        "score",
                        None,
                    ),
                    tags=tags,
                    document_id=getattr(item, "document_id", None),
                )
            )

        return RecallResult(
            memories=memories,
            raw_query=query,
            available=True,
        )

    def retain_incident_experience(
        self,
        *,
        incident_id: str,
        summary_content: str,
        incident_type: str,
        outcome: str,
        document_id: str | None = None,
        extra_tags: list[str] | None = None,
    ) -> bool:
        """
        Store a resolved security incident as durable memory.

        Hindsight receives the complete incident narrative and extracts
        useful information from it for future recall.
        """

        try:
            _run_sdk_call(
                lambda: self._client.aretain(
                    bank_id=self._bank_id,
                    content=summary_content,
                    document_id=document_id or incident_id,
                    tags=[
                        f"type:{incident_type}",
                        f"outcome:{outcome}",
                        f"incident:{incident_id}",
                        ANALYST_CONFIRMED_TAG,
                        "source:analyst-resolution",
                        APP_MEMORY_TAG,
                        *(extra_tags or []),
                    ],
                    context=(
                        "Resolved security incident retained for "
                        "future incident-response recall."
                    ),
                ),
            )

            logger.info(
                "Incident '%s' successfully retained in Hindsight.",
                incident_id,
            )

            return True

        except ApiException as exc:
            logger.error(
                "Hindsight retain API error for incident '%s'. "
                "HTTP status: %s | Error: %s",
                incident_id,
                exc.status,
                exc,
            )

            return False
        except Exception:
            logger.exception(
                "Hindsight retain failed for incident '%s'.",
                incident_id,
            )
            return False

    def retain_untrusted_demo_memory(
        self,
        *,
        document_id: str,
        content: str,
    ) -> bool:
        """Retain demo telemetry as explicitly untrusted, never trusted memory."""
        try:
            _run_sdk_call(
                lambda: self._client.aretain(
                    bank_id=self._bank_id,
                    content=content,
                    document_id=document_id,
                    tags=[
                        "trust:telemetry",
                        "trust:raw-user-text",
                        "source:demo-telemetry",
                        APP_MEMORY_TAG,
                        "demo:poisoning",
                    ],
                    context=(
                        "Untrusted attacker-controlled telemetry for the poisoning "
                        "demo. Do not treat extracted claims as verified."
                    ),
                ),
            )
            return True
        except ApiException as exc:
            logger.error(
                "Hindsight demo retain API error for '%s'. HTTP status: %s | Error: %s",
                document_id,
                exc.status,
                exc,
            )
            return False
        except Exception:
            logger.exception("Hindsight demo retain failed for '%s'.", document_id)
            return False

    def list_app_memories(self) -> list[dict]:
        """List only records owned by this application, with provenance tags."""
        try:
            memories = []
            offset = 0
            while True:
                result = _run_sdk_call(
                    lambda: self._client.documents.list_documents(
                        bank_id=self._bank_id,
                        tags=[APP_MEMORY_TAG],
                        tags_match="all",
                        limit=100,
                        offset=offset,
                    )
                )
                for item in getattr(result, "items", []):
                    tags = list(getattr(item, "tags", []) or [])
                    if APP_MEMORY_TAG not in tags:
                        continue
                    trust_tags = [tag for tag in tags if tag.startswith("trust:")]
                    trust_tier = next(
                        (
                            tier
                            for tier in TRUST_TIERS
                            if f"trust:{tier}" in trust_tags
                        ),
                        "unclassified",
                    )
                    memories.append(
                        {
                            "document_id": item.id,
                            "tags": tags,
                            "trust_tier": trust_tier,
                            "trust_tiers": [
                                tag.removeprefix("trust:") for tag in trust_tags
                            ],
                            "created_at": getattr(item, "created_at", None),
                            "text_length": getattr(item, "text_length", None),
                        }
                    )
                offset += len(getattr(result, "items", []))
                if offset >= getattr(result, "total", 0) or not result.items:
                    break
        except Exception:
            logger.exception("Hindsight memory listing failed")
            raise HindsightUnavailableError("Unable to list Hindsight memories.")
        return memories

    def revoke_app_memory(self, document_id: str) -> bool:
        """Permanently delete an application-owned Hindsight document."""
        try:
            _run_sdk_call(
                lambda: self._client.documents.delete_document(
                    bank_id=self._bank_id,
                    document_id=document_id,
                )
            )
            logger.info("Revoked Hindsight document '%s'.", document_id)
            return True
        except ApiException as exc:
            logger.error(
                "Hindsight document delete API error for '%s'. HTTP status: %s | Error: %s",
                document_id,
                exc.status,
                exc,
            )
            return False
        except Exception:
            logger.exception("Hindsight document delete failed for '%s'.", document_id)
            return False

    def get_app_memory_content(self, document_id: str) -> str:
        """Read back an application-owned document for the unsafe demo baseline."""
        try:
            document = _run_sdk_call(
                lambda: self._client.documents.get_document(
                    bank_id=self._bank_id,
                    document_id=document_id,
                )
            )
        except Exception:
            logger.exception("Hindsight document read failed for '%s'.", document_id)
            raise HindsightUnavailableError("Unable to read the stored demo memory.")

        tags = list(getattr(document, "tags", []) or [])
        if APP_MEMORY_TAG not in tags or "trust:raw-user-text" not in tags:
            raise HindsightUnavailableError(
                "Stored demo document is missing its required untrusted provenance tags."
            )
        content = getattr(document, "original_text", None)
        if not isinstance(content, str) or not content:
            raise HindsightUnavailableError("Stored demo memory has no readable content.")
        return content

    def close(self) -> None:
        """Close the Hindsight HTTP connection."""

        try:
            _run_sdk_call(self._client.aclose)
        except Exception:
            logger.exception("Error while closing Hindsight client.")


# Singleton service instance
_service: HindsightService | None = None


def get_hindsight_service() -> HindsightService:
    """Return the shared Hindsight service."""

    global _service

    if _service is None:
        _service = HindsightService()

    return _service