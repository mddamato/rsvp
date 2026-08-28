from rsvp import guests


def test_guest_rows_from_form_drops_blank_names():
    form = {"guest_name_1": "Bob Smith", "guest_name_2": "  ", "guest_name_3": ""}
    result = guests.guest_rows_from_form(form, 3)
    assert result == [{"name": "Bob Smith", "child": False}]


def test_guest_rows_from_form_respects_count_cutoff():
    form = {"guest_name_1": "Bob", "guest_name_2": "Sue", "guest_name_3": "Ignored"}
    result = guests.guest_rows_from_form(form, 2)
    assert result == [{"name": "Bob", "child": False}, {"name": "Sue", "child": False}]


def test_guest_rows_from_form_reads_checkbox_by_presence():
    form = {"guest_name_1": "Bob", "guest_child_1": "on", "guest_name_2": "Sue"}
    result = guests.guest_rows_from_form(form, 2)
    assert result == [{"name": "Bob", "child": True}, {"name": "Sue", "child": False}]


def test_guest_rows_from_form_truncates_long_names():
    form = {"guest_name_1": "A" * 500}
    result = guests.guest_rows_from_form(form, 1)
    assert len(result[0]["name"]) == guests.MAX_GUEST_NAME_LEN


def test_serialize_and_parse_round_trip():
    guest_list = [{"name": "Bob Smith", "child": True}, {"name": "Sue Smith", "child": False}]
    raw = guests.serialize_guests(guest_list)
    assert guests.parse_guests(raw) == guest_list


def test_parse_guests_handles_empty_and_none():
    assert guests.parse_guests(None) == []
    assert guests.parse_guests("") == []
    assert guests.parse_guests("[]") == []


def test_parse_guests_handles_malformed_input():
    assert guests.parse_guests("not json") == []
    assert guests.parse_guests('"just a string"') == []
    assert guests.parse_guests("42") == []
    assert guests.parse_guests('[{"no_name": "oops"}, "not a dict", {"name": "Bob"}]') == [
        {"name": "Bob"}
    ]
