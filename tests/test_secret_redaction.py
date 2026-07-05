from sourcepack.judgment import redact_secrets


def test_redact_secrets_redacts_current_patterns_and_reports_metadata():
    secrets = {
        "openai_key": "sk-proj-abcdefghijklmnopqrstuvwxyz",
        "aws_access_key": "AKIAABCDEFGHIJKLMNOP",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----",
        "github_token": "ghp_abcdefghijklmnopqrstuvwxyz",
        "slack_token": "xoxb-abcdefghijklmnopqrstuvwx",
        "generic_api_key": "api_key = abcdefghijklmnop",
    }
    text = "ordinary text\n" + "\n".join(secrets.values()) + "\n"

    redacted, metadata = redact_secrets(text)

    assert "ordinary text" in redacted
    for label, secret in secrets.items():
        assert secret not in redacted
        assert f"[REDACTED:{label}]" in redacted
    labels = {item["pattern"] for item in metadata}
    assert set(secrets) <= labels
    assert all(isinstance(item["span_start"], int) and isinstance(item["span_end"], int) for item in metadata)
    assert all(item["span_start"] < item["span_end"] for item in metadata)


def test_redact_secrets_preserves_non_secret_text_without_metadata():
    text = "This ordinary paragraph mentions tokens as a concept, not a token assignment."

    redacted, metadata = redact_secrets(text)

    assert redacted == text
    assert metadata == []
