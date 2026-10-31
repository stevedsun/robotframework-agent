"""Glue to the running robotframework-browser instance.

The Browser library drives Playwright in a Node sidecar over gRPC, so there
is no Python page object to borrow. Instead every page interaction goes
through the Browser library's own keywords: observation and scrolling via
`Evaluate JavaScript`, clicks/fills via `Click`/`Fill Text`, screenshots via
`Take Screenshot`. Interactive elements are tagged by observe.js with a
``data-rfa-id`` attribute, which is what the selectors here target.
"""

from __future__ import annotations

import uuid
from importlib.resources import files

from Browser.utils import ScreenshotReturnType
from robot.libraries.BuiltIn import BuiltIn

from .observation import format_observation

_OBSERVE_JS = files("RobotAgent").joinpath("observe.js").read_text(encoding="utf-8")

# Small settle delay after a mutating action before the screen is re-read.
SETTLE_SECONDS = 0.5


class BrowserEngine:
    """Observes and drives the Browser library's active page."""

    def __init__(self, library_name: str = "Browser") -> None:
        try:
            self._browser = BuiltIn().get_library_instance(library_name)
        except Exception as exc:  # noqa: BLE001 - rephrased for the test author
            raise RuntimeError(
                f"RobotAgent needs the Browser library in the same suite: "
                f"import it before RobotAgent (tried library name {library_name!r}). "
                f"Original error: {exc}"
            ) from exc

    @staticmethod
    def selector_for(node_id: str) -> str:
        safe = "".join(ch for ch in node_id if ch.isalnum() or ch in "_-")
        return f"css=[data-rfa-id='{safe}']"

    def observe(self, max_chars: int = 8000) -> str:
        raw = self._browser.evaluate_javascript(None, _OBSERVE_JS)
        if not isinstance(raw, dict):
            raise RuntimeError(f"observation script returned unexpected data: {raw!r}")
        return format_observation(raw, max_chars)

    def click(self, node_id: str) -> None:
        self._browser.click(self.selector_for(node_id))

    def type_text(self, node_id: str, text: str) -> None:
        self._browser.fill_text(self.selector_for(node_id), text)

    def press(self, key: str, node_id: str | None = None) -> None:
        self._browser.press_keys(self.selector_for(node_id) if node_id else "css=body", key)

    def scroll_to(self, node_id: str) -> None:
        self._browser.scroll_to_element(self.selector_for(node_id))

    def scroll(self, direction: str = "down", times: int = 1) -> None:
        times = max(1, min(int(times), 20))
        pixels = self._browser.get_viewport_size()["height"] * 0.8
        sign = -1 if direction.lower().startswith("up") else 1
        self._browser.evaluate_javascript(
            None,
            "(arg) => window.scrollBy(0, arg * 1)",
            arg=sign * pixels * times,
        )

    def screenshot_bytes(self) -> bytes:
        """Capture the viewport; the file also lands in the RF report."""
        result = self._browser.take_screenshot(
            filename=f"agent-screenshot-{uuid.uuid4().hex[:8]}",
            return_as=ScreenshotReturnType.bytes,
        )
        return bytes(result)
