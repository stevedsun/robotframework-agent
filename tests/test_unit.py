"""Unit tests for the pure parts: observation formatting and verdict parsing."""

from RobotAgent.agent_loop import _parse_verdict
from RobotAgent.observation import format_observation

SAMPLE = {
    "url": "https://www.saucedemo.com/",
    "title": "Swag Labs",
    "viewport": {"width": 1280, "height": 720},
    "items": [
        {"kind": "text", "depth": 1, "text": "Swag Labs"},
        {"kind": "node", "id": "n1", "role": "textbox", "depth": 2, "name": "Username"},
        {
            "kind": "node",
            "id": "n2",
            "role": "textbox",
            "depth": 2,
            "name": "Password",
            "value": "<hidden>",
        },
        {"kind": "node", "id": "n3", "role": "button", "depth": 2, "name": "Login"},
        {
            "kind": "node",
            "id": "n4",
            "role": "checkbox",
            "depth": 2,
            "name": "Remember me",
            "checked": True,
        },
    ],
    "truncated": False,
}


def test_format_observation():
    text = format_observation(SAMPLE)
    assert "URL: https://www.saucedemo.com/" in text
    assert 'n1 textbox "Username"' in text
    assert 'n2 textbox "Password" value="<hidden>"' in text
    assert 'n3 button "Login"' in text
    assert 'n4 checkbox "Remember me" checked' in text
    assert 'text "Swag Labs"' in text


def test_format_observation_respects_budget():
    text = format_observation(SAMPLE, max_chars=60)
    assert len(text) <= 60 + 60  # marker tail allowed past the cut
    assert "[observation truncated" in text


def test_parse_verdict_plain_json():
    assert _parse_verdict('{"explanation": "list is visible", "verdict": "holds"}') == (
        "holds",
        "list is visible",
    )


def test_parse_verdict_tolerates_prose():
    text = 'Sure! Here is my answer:\n{"explanation": "no list", "verdict": "fails"}\nDone.'
    assert _parse_verdict(text) == ("fails", "no list")


def test_parse_verdict_rejects_garbage():
    assert _parse_verdict("I think it holds.") is None
    assert _parse_verdict('{"answer": "yes"}') is None
