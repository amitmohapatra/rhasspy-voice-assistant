"""
Utility helpers for cleaning assistant responses.
"""
import re


def filter_unwanted_phrases(text: str) -> str:
    """Remove unwanted phrases and filler from responses."""
    if not text:
        return text

    unwanted_phrases = [
        r'thanks?\s+for\s+watching',
        r'thank\s+you\s+for\s+watching',
        r'thanks?\s+for\s+listening',
        r'thank\s+you\s+for\s+listening',
        r'see\s+you\s+next\s+time',
        r'until\s+next\s+time',
        r'that\'?s\s+all\s+for\s+now',
        r'that\'?s\s+it\s+for\s+now',
        r'goodbye\s+for\s+now',
        r'see\s+you\s+later',
    ]

    filtered_text = text
    for phrase in unwanted_phrases:
        pattern = re.compile(phrase, re.IGNORECASE)
        filtered_text = pattern.sub('', filtered_text)

    filtered_text = re.sub(r'\s+', ' ', filtered_text).strip()

    if not filtered_text or len(filtered_text) < 3:
        return "How can I help you further?"

    return filtered_text


