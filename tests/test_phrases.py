import psycopg2.errors
import pytest
from rsvp import phrases


def test_phrase_shape():
    p = phrases.generate_phrase()
    parts = p.split("-")
    assert len(parts) == 3
    assert all(part.isalpha() and part.islower() for part in parts)


def test_wordlist_is_large():
    assert len(phrases.load_words()) > 5000


def test_collision_retry():
    calls = []

    def fake_insert(name, phrase):
        calls.append(phrase)
        if len(calls) < 3:
            raise psycopg2.errors.UniqueViolation()
        return "fake-id"

    result, phrase = phrases.insert_with_unique_phrase(fake_insert, "Alice")
    assert result == "fake-id"
    assert len(calls) == 3
    assert phrase == calls[-1]


def test_retry_gives_up():
    def always_collides(name, phrase):
        raise psycopg2.errors.UniqueViolation()

    with pytest.raises(RuntimeError):
        phrases.insert_with_unique_phrase(always_collides, "Bob")
