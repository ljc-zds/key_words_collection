from product_hunt.aitdk.data.redaction import redact_diagnostic


def test_redact_diagnostic_removes_sensitive_query_values() -> None:
    text = "https://example.test/?domain=deno.com&signature=abc&nonce=def"
    redacted = redact_diagnostic(text)
    assert "signature=REDACTED" in redacted
    assert "nonce=REDACTED" in redacted
    assert "abc" not in redacted
