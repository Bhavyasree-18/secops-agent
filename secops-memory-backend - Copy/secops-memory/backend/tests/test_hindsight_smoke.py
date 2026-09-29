"""
Phase 3 checkpoint: smallest possible working Hindsight test.

Flow:
    retain -> recall -> verify

This test makes a real network call to Hindsight.
"""

import time
import uuid

import pytest

from app.config import get_settings
from app.services.hindsight_client import get_hindsight_service


def _hindsight_configured() -> bool:
    s = get_settings()

    # Local Docker needs no API key.
    # Hindsight Cloud requires an API key.
    # In both cases, a base URL is required.
    return bool(s.hindsight_base_url)


@pytest.mark.skipif(
    not _hindsight_configured(),
    reason="HINDSIGHT_BASE_URL not set",
)
def test_retain_then_recall_roundtrip():

    # ---------------------------------------------------------
    # 1. Connect to Hindsight
    # ---------------------------------------------------------
    service = get_hindsight_service()

    assert service.ensure_bank(), (
        "Bank creation/connection failed"
    )

    # ---------------------------------------------------------
    # 2. Create a unique incident
    # ---------------------------------------------------------
    marker = uuid.uuid4().hex[:8]

    incident_id = f"smoke-test-{marker}"

    # ---------------------------------------------------------
    # 3. Store the incident in Hindsight
    # ---------------------------------------------------------
    retained = service.retain_incident_experience(
        incident_id=incident_id,
        summary_content=(
            f"[SMOKE-TEST-{marker}] "
            "Credential stuffing incident: 15 IP addresses "
            "attempted logins against one employee account, "
            "one succeeded. "

            "Root cause: no MFA on the account. "

            "Investigation: reviewed authentication logs and "
            "confirmed no lateral movement. "

            "Containment: disabled the account and revoked "
            "active sessions. "

            "Remediation: reset credentials and enforced MFA "
            "organization-wide. "

            "Outcome: resolved. "

            "Analyst feedback: this response sequence worked "
            "well and should be the default for future "
            "credential stuffing incidents."
        ),
        incident_type="credential_stuffing",
        outcome="resolved",
    )

    assert retained, (
        "retain_incident_experience returned False"
    )

    # ---------------------------------------------------------
    # 4. Wait for Hindsight to process the memory
    # ---------------------------------------------------------
    time.sleep(3)

    # ---------------------------------------------------------
    # 5. Recall similar incident information
    # ---------------------------------------------------------
    result = service.recall_similar_incidents(
        query=(
            "Employee account had many failed login attempts "
            "from different IP addresses and then one login "
            "succeeded. What should the security team investigate "
            "and what containment and remediation steps should "
            "they follow?"
        )
    )

    # ---------------------------------------------------------
    # 6. Verify recall worked
    # ---------------------------------------------------------
    assert result.available, (
        "Hindsight recall reported unavailable"
    )

    assert result.memories, (
        "Hindsight returned no memories"
    )

    # Combine all recalled memory text.
    joined = " ".join(
        memory.text
        for memory in result.memories
    )

    joined_lower = joined.lower()

    # ---------------------------------------------------------
    # 7. Verify meaningful information was recalled
    #
    # IMPORTANT:
    # Hindsight may extract facts from the original incident
    # instead of returning the original raw text.
    #
    # Therefore, the random smoke-test marker does NOT need
    # to appear in the recalled result.
    # ---------------------------------------------------------

    assert "credential stuffing" in joined_lower, (
        "Recalled memories did not contain the incident type. "
        f"Got: {[m.text for m in result.memories]}"
    )

    assert "mfa" in joined_lower, (
        "Recalled memories did not contain the MFA "
        "root-cause/remediation information. "
        f"Got: {[m.text for m in result.memories]}"
    )

    # ---------------------------------------------------------
    # 8. Display successful recall
    # ---------------------------------------------------------
    print(
        f"\nRecalled {len(result.memories)} memories successfully."
    )

    for i, memory in enumerate(result.memories, start=1):
        print(f"\nMemory {i}:")
        print(memory.text)