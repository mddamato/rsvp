"""Structured plus-one guest entries: name + "child 6 or under" flag,
stored as a JSON array string in invitees.plus_one_details. Shared by
the RSVP form (submit_rsvp) and self-registration
(self_register_submit) so the guest_name_N/guest_child_N field
convention and parsing logic live in exactly one place.
"""
import json

MAX_GUEST_NAME_LEN = 100


def guest_rows_from_form(form, count):
    """Extract up to `count` guest_name_N / guest_child_N pairs
    (1-indexed) from a submitted form. A row with a blank name is
    dropped -- an "Add guest" slot the visitor never filled in simply
    doesn't become a guest. Returns [{"name": str, "child": bool}, ...]."""
    result = []
    for i in range(1, count + 1):
        name = (form.get(f"guest_name_{i}") or "").strip()[:MAX_GUEST_NAME_LEN]
        if not name:
            continue
        result.append({"name": name, "child": form.get(f"guest_child_{i}") is not None})
    return result


def serialize_guests(guest_list):
    return json.dumps(guest_list)


def parse_guests(raw):
    """Parse a stored plus_one_details value back into a list of
    {"name", "child"} dicts. Defensive: any missing/malformed value
    parses to an empty list rather than raising, since template
    rendering can't tolerate an exception mid-page."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [g for g in parsed if isinstance(g, dict) and g.get("name")]
