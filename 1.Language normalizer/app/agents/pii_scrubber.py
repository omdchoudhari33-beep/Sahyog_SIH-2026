import re

PHONE_PATTERN = re.compile(r"\b\d{10}\b")
AADHAAR_PATTERN = re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")


def scrub_pii(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    text = PHONE_PATTERN.sub("[PHONE]", text)
    text = AADHAAR_PATTERN.sub("[AADHAAR]", text)

    return text