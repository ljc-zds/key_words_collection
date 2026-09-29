import re


_SENSITIVE = re.compile(r"(?i)(signature|nonce|secretkey|authorization|cookie)=([^&\s]+)")


def redact_diagnostic(text: str) -> str:
    """Remove credential-like query values before diagnostics are persisted."""
    return _SENSITIVE.sub(lambda match: f"{match.group(1)}=REDACTED", text)
