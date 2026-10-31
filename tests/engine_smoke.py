"""Debug helper library: exercises the engine layer (observe/click/type)
without an LLM, so the engine path can be tested end to end."""

from RobotAgent.engine import BrowserEngine

_engine = None


def _get() -> BrowserEngine:
    global _engine
    if _engine is None:
        _engine = BrowserEngine("Browser")
    return _engine


def observe_page() -> str:
    return _get().observe()


def click_node(node_id: str) -> None:
    _get().click(node_id)


def type_into_node(node_id: str, text: str) -> None:
    _get().type_text(node_id, text)


def screenshot_size() -> int:
    return len(_get().screenshot_bytes())
