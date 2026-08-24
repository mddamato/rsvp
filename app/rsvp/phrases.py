"""3-word passcode generation from the EFF wordlist.

Phrases look like `apple-sky-boat`. Collisions against the unique
constraint on invitees.lookup_phrase are handled by regenerating,
capped at MAX_RETRIES attempts.
"""
import re
import secrets
from pathlib import Path

import psycopg2.errors

WORDLIST_PATH = Path(__file__).resolve().parent.parent / "wordlist" / "eff_words.txt"
MAX_RETRIES = 10

_APOSTROPHES_RE = re.compile(r"[’']")
_DASH_RE = re.compile(r"-+")

_words = None


def normalize_phrase(raw):
    """Lowercase, strip, drop apostrophes, and collapse whitespace/
    underscores into single hyphens. Used both for guest passcode
    lookups and for comparing against the configured ANONYMOUS_PHRASE,
    so both sides must normalize identically. Does not enforce word
    count or restrict to letters-only -- callers that need the strict
    3-word EFF-generated shape still apply PHRASE_RE on top."""
    text = (raw or "").strip().lower()
    text = _APOSTROPHES_RE.sub("", text)
    text = text.replace("_", "-")
    text = "-".join(text.split())
    return _DASH_RE.sub("-", text)


def load_words():
    global _words
    if _words is None:
        _words = WORDLIST_PATH.read_text().split()
        if len(_words) < 1000:
            raise RuntimeError(
                f"Wordlist at {WORDLIST_PATH} looks too small "
                f"({len(_words)} words). Refusing to generate weak phrases."
            )
    return _words


def generate_phrase():
    words = load_words()
    return "-".join(secrets.choice(words) for _ in range(3))


def insert_with_unique_phrase(insert_fn, *args):
    """Call insert_fn(*args, phrase), regenerating the phrase on a
    unique-constraint collision. insert_fn must raise
    psycopg2.errors.UniqueViolation on collision."""
    for _ in range(MAX_RETRIES):
        phrase = generate_phrase()
        try:
            return insert_fn(*args, phrase), phrase
        except psycopg2.errors.UniqueViolation:
            continue
    raise RuntimeError(
        f"Could not generate a unique phrase after {MAX_RETRIES} attempts. "
        "Check the wordlist and table state."
    )
