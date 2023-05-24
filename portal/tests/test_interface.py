import uuid

from help_to_heat.frontdoor import interface

from . import utils


def test_answers():
    session_id = uuid.uuid4()
    page_name = "country"
    data = {"floob": "blumble", "country": "England"}
    result = interface.api.session.save_answer(session_id=session_id, page_name=page_name, data=data)
    expected = {"country": "England"}
    assert result == expected, (result, expected)

    result = interface.api.session.get_answer(session_id=session_id, page_name=page_name)
    assert result == expected, (result, expected)


def test_answer_missing():
    session_id = uuid.uuid4()
    page_name = "country"
    expected = {}
    result = interface.api.session.get_answer(session_id=session_id, page_name=page_name)
    assert result == expected, (result, expected)


def test_duplicate_answer():
    session_id = uuid.uuid4()
    page_name = "country"
    data = {"floob": "blumble", "country": "England"}
    result = interface.api.session.save_answer(session_id=session_id, page_name=page_name, data=data)
    expected = {"country": "England"}
    assert result == expected, (result, expected)

    data = {"floob": "blumble", "country": "Wales"}
    result = interface.api.session.save_answer(session_id=session_id, page_name=page_name, data=data)
    expected = {"country": "Wales"}
    assert result == expected, (result, expected)

    result = interface.api.session.get_answer(session_id=session_id, page_name=page_name)
    assert result == expected, (result, expected)


@utils.mock_os_api
def test_find_addresses():
    result = interface.api.address.find_addresses("foobar")
    assert result[0]["uprn"] == "100023336956"
