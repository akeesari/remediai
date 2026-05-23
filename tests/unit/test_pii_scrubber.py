import pytest

from packages.integrations.pii_scrubber import scrub


@pytest.mark.parametrize(
    "input_text, expected_fragment, absent_fragment",
    [
        # Email
        (
            "Error: user john.doe@example.com not found",
            "[EMAIL]",
            "john.doe@example.com",
        ),
        # IPv4
        (
            "Connection refused from 192.168.1.100",
            "[IP]",
            "192.168.1.100",
        ),
        # IPv6
        (
            "Host 2001:0db8:85a3:0000:0000:8a2e:0370:7334 unreachable",
            "[IP]",
            "2001:0db8",
        ),
        # Azure subscription ID in resource path
        (
            "Resource /subscriptions/12345678-1234-1234-1234-123456789abc/resourceGroups/rg",
            "[SUBSCRIPTION_ID]",
            "12345678-1234-1234-1234-123456789abc",
        ),
        # SAS token
        (
            "https://storage.blob.core.windows.net/container?sig=abc123XYZ%2Ftoken%3D",
            "[SAS_TOKEN]",
            "abc123XYZ",
        ),
        # Freestanding UUID (user ID)
        (
            "User 550e8400-e29b-41d4-a716-446655440000 triggered the error",
            "[UUID]",
            "550e8400-e29b-41d4-a716-446655440000",
        ),
    ],
)
def test_scrub_replaces_pii(
    input_text: str, expected_fragment: str, absent_fragment: str
) -> None:
    result = scrub(input_text)
    assert expected_fragment in result
    assert absent_fragment not in result


def test_scrub_is_idempotent_on_clean_text() -> None:
    text = "NullReferenceException: Object reference not set to an instance of an object."
    assert scrub(text) == text


def test_scrub_multiple_patterns_in_one_string() -> None:
    text = "User admin@corp.com from 10.0.0.1 hit an error"
    result = scrub(text)
    assert "[EMAIL]" in result
    assert "[IP]" in result
    assert "admin@corp.com" not in result
    assert "10.0.0.1" not in result


def test_scrub_empty_string() -> None:
    assert scrub("") == ""
