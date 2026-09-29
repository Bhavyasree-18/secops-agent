"""Realistic demo incidents used to pre-seed Hindsight (synthetic data)."""

SEED_INCIDENTS = [
    {
        "id": "SEED-001", "title": "Credential stuffing against VPN portal",
        "description": "Thousands of failed VPN logins from rotating residential IPs over 40 minutes; 2 accounts logged in successfully. Neither account had MFA.",
        "analyst_actions": "Blocked offending ASN ranges at WAF, forced password reset and session revocation for the 2 accounts, enforced MFA on the VPN group.",
        "outcome": "Resolved", "analyst_feedback": "Check for MFA gaps FIRST. Successful login after mass failures means the account is compromised until proven otherwise. Rate-limit per username, not just per IP.",
        "minutes": 95, "days_ago": 21,
    },
    {
        "id": "SEED-002", "title": "Phishing email with fake Microsoft 365 login page",
        "description": "12 employees received an email with a link to a credential-harvesting page. 3 clicked, 1 entered credentials.",
        "analyst_actions": "Purged the email from all mailboxes, blocked the domain at proxy, reset the affected user's password, reviewed inbox rules for forwarding.",
        "outcome": "Resolved", "analyst_feedback": "Always check for malicious inbox forwarding rules after a credential phish. Search mail logs for other recipients before closing.",
        "minutes": 70, "days_ago": 17,
    },
    {
        "id": "SEED-003", "title": "Ransomware note found on file server",
        "description": "Files on FS-02 renamed with .locked extension and ransom note dropped in every share. EDR alert fired on unsigned binary launched from a user's Downloads folder.",
        "analyst_actions": "Isolated host via EDR, disabled the user's account, restored shares from previous night's snapshot, hunted for the same hash across the fleet.",
        "outcome": "Resolved", "analyst_feedback": "Isolate first, investigate second. Snapshots saved us - verify backup integrity weekly. Check lateral movement via SMB before restoring.",
        "minutes": 240, "days_ago": 12,
    },
    {
        "id": "SEED-004", "title": "Privilege escalation on Linux build server",
        "description": "Auditd showed a CI service account running sudo to edit /etc/sudoers and add itself to the wheel group.",
        "analyst_actions": "Rotated CI secrets, reverted sudoers from config management, rebuilt the runner from a clean image, audited pipeline definitions for injected steps.",
        "outcome": "Resolved", "analyst_feedback": "Root cause was a malicious pull request modifying the pipeline. Add branch protections and require review for CI config changes.",
        "minutes": 180, "days_ago": 8,
    },
    {
        "id": "SEED-005", "title": "Suspicious impossible-travel login for finance user",
        "description": "Finance manager logged in from Hyderabad and from Frankfurt 6 minutes apart. Second session accessed the payments export.",
        "analyst_actions": "Revoked all sessions, reset credentials, confirmed with user that Frankfurt login was not theirs, reviewed the payments export access logs.",
        "outcome": "Resolved", "analyst_feedback": "Impossible travel plus access to sensitive exports = treat as account takeover, not a VPN false positive. Ask the user directly out-of-band.",
        "minutes": 55, "days_ago": 4,
    },
    {
        "id": "SEED-006", "title": "Public S3 bucket exposing internal reports",
        "description": "A cloud posture scan flagged an S3 bucket with public-read ACL containing internal quarterly reports. No access from unknown IPs seen yet.",
        "analyst_actions": "Removed public ACL, enabled account-level Block Public Access, reviewed CloudTrail and access logs for external reads.",
        "outcome": "Resolved", "analyst_feedback": "Enable Block Public Access org-wide. Always check access logs to determine whether the exposure was actually exploited.",
        "minutes": 40, "days_ago": 2,
    },
]
