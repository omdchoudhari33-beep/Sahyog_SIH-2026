from app.agents.pii_scrubber import scrub_pii


def test_scrub_phone_and_aadhaar():
    result = scrub_pii("Call 9876543210. Aadhaar 1234 5678 9012")
    assert "9876543210" not in result
    assert "1234 5678 9012" not in result
    assert "[PHONE]" in result
    assert "[AADHAAR]" in result
