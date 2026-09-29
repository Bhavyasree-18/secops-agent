"""Rule-based incident severity + category classification (fast, deterministic, no LLM call)."""
from __future__ import annotations

RULES: list[tuple[str, str, list[str]]] = [
    # (category, severity, keywords) - first match wins, ordered by seriousness
    ("Ransomware", "Critical", ["ransomware", "encrypted files", "ransom note", "files encrypted"]),
    ("Data Breach", "Critical", ["data breach", "exfiltrat", "data leak", "leaked data", "database dump", "apt", "customer data exposed"]),
    ("Privilege Escalation", "High", ["privilege escalation", "escalated privileges", "admin rights", "root access", "sudo abuse"]),
    ("Credential Attack", "High", ["credential stuffing", "brute force", "compromised credential", "stolen credential", "password spray", "account takeover", "failed login"]),
    ("Malware", "High", ["malware", "trojan", "c2 ", "command and control", "backdoor", "cryptominer", "botnet"]),
    ("Phishing", "Medium", ["phishing", "spear", "malicious email", "suspicious email", "fake login page"]),
    ("Suspicious Login", "Medium", ["suspicious login", "impossible travel", "unusual login", "new device login"]),
    ("Policy Violation", "Low", ["policy violation", "unauthorized software", "shadow it", "usb"]),
    ("Misconfiguration", "Low", ["misconfig", "open bucket", "public bucket", "exposed port", "default password"]),
]

SEVERITY_ORDER = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


def classify(title: str, description: str) -> dict:
    text = f"{title} {description}".lower()
    hits = [(cat, sev) for cat, sev, kws in RULES if any(k in text for k in kws)]
    if not hits:
        return {"category": "Other", "severity": "Medium"}
    category, severity = max(hits, key=lambda h: SEVERITY_ORDER[h[1]])
    # A successful compromise bumps severity one level.
    if any(k in text for k in ["succeeded", "successful login", "one login attempt succeeded", "compromised"]) and severity in ("Medium", "High"):
        severity = "High" if severity == "Medium" else "Critical"
    return {"category": category, "severity": severity}
