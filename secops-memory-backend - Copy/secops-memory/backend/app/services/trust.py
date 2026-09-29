"""Typed extraction and trust labels for attacker-controlled telemetry."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


_USERNAME = re.compile(r"[A-Za-z0-9_.@-]{1,80}\Z")
_USER_AGENT_PRODUCT = re.compile(r"([A-Za-z][A-Za-z0-9._-]{0,31})(?:/[A-Za-z0-9._-]{1,24})?")

ANALYST_CONFIRMED_TAG = "trust:analyst-confirmed"
TRUSTED_RECALL_TAGS = [ANALYST_CONFIRMED_TAG]
APP_MEMORY_TAG = "source:secops-memory"
TRUST_TIERS = (
    "raw-user-text",
    "telemetry",
    "llm-inferred",
    "analyst-confirmed",
)


@dataclass(frozen=True)
class TelemetryIndicators:
    username: str | None
    user_agent_family: str | None
    remark_length: int
    remark_fingerprint: str | None

    def as_prompt_context(self) -> str:
        """Return only validated, typed indicators; never include raw fields."""
        return "\n".join(
            (
                f"Username indicator: {self.username or 'not extracted'}",
                f"User-agent product family: {self.user_agent_family or 'not extracted'}",
                f"Untrusted remark present: {'yes' if self.remark_length else 'no'}",
                f"Untrusted remark length: {self.remark_length}",
                "Raw remark excluded from protected analysis.",
            )
        )


def extract_telemetry(
    username: str,
    user_agent: str,
    remark: str,
) -> TelemetryIndicators:
    """Extract bounded indicator types without forwarding attacker prose."""
    normalized_username = username.strip()
    if not _USERNAME.fullmatch(normalized_username):
        normalized_username = ""

    ua_match = _USER_AGENT_PRODUCT.search(user_agent[:256])
    remark_bytes = remark.encode("utf-8")

    return TelemetryIndicators(
        username=normalized_username or None,
        user_agent_family=ua_match.group(1) if ua_match else None,
        remark_length=len(remark),
        remark_fingerprint=(
            hashlib.sha256(remark_bytes).hexdigest()[:16] if remark else None
        ),
    )
