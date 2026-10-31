"""RobotAgent: LLM agent keywords for Robot Framework.

Lets a test state a goal or an expectation in natural language and hands the
driving to a model, in the spirit of tester-army/e2e:

| ``AGENT ACT``      | use the standard user account to log in |
| ``AGENT ASSERT``   | the product list shows six items |

The library observes the Browser library's active page (an indented tree of
interactive elements with stable ids) and acts through the Browser library's
own keywords, so it composes with an existing Playwright-based suite.

The model is resolved at import time from the ``model`` argument or the
``AGENT_MODEL`` environment variable and called through LiteLLM, so any
provider LiteLLM supports works (``gpt-4o``, ``anthropic/claude-sonnet-4-5``,
``deepseek/deepseek-chat``, ...); provider credentials come from the usual
environment variables such as ``OPENAI_API_KEY`` or ``ANTHROPIC_API_KEY``.
"""

from __future__ import annotations

import os

from robot.api import logger
from robot.api.deco import keyword, library
from robot.utils import timestr_to_secs

from .agent_loop import run_act, run_assert
from .engine import BrowserEngine


@library(scope="GLOBAL", doc_format="ROBOT")
class RobotAgent:
    """LLM-driven testing keywords backed by the Browser library.

    Arguments:
      - ``model``: LiteLLM model name. Defaults to the ``AGENT_MODEL``
        environment variable.
      - ``browser_library``: name the Browser library was imported as.
      - ``max_steps``: default action budget of one ``AGENT ACT`` call.
      - ``timeout``: default wall-clock budget of one ``AGENT ACT`` call,
        in Robot Framework time format (``2 minutes``, ``90s``, ...).
      - ``max_observation_chars``: character budget of the screen text sent
        to the model.
    """

    ROBOT_LIBRARY_DOC_FORMAT = "ROBOT"

    def __init__(
        self,
        model: str | None = None,
        browser_library: str = "Browser",
        max_steps: int = 10,
        timeout: str = "2 minutes",
        max_observation_chars: int = 8000,
    ) -> None:
        self._model = model or os.environ.get("AGENT_MODEL")
        self._browser_library = browser_library
        self._max_steps = int(max_steps)
        self._timeout_s = timestr_to_secs(timeout)
        self._max_observation_chars = int(max_observation_chars)
        self._engine: BrowserEngine | None = None

    @property
    def engine(self) -> BrowserEngine:
        if self._engine is None:
            self._engine = BrowserEngine(self._browser_library)
        return self._engine

    def _require_model(self) -> str:
        if not self._model:
            raise RuntimeError(
                "No model configured: pass one on import "
                "(Library  RobotAgent  model=gpt-4o) or set AGENT_MODEL."
            )
        return self._model

    @keyword("AGENT ACT")
    def agent_act(
        self,
        instruction: str,
        max_steps: int | None = None,
        timeout: str | None = None,
    ) -> str:
        """Drive the application until ``instruction`` is achieved.

        The model sees the current screen as a tree of interactive elements
        and acts through click/type/scroll tools until it concludes the step
        passed or failed. A failed or blocked conclusion fails the test with
        the model's reason.

        Returns the model's summary of what it did.
        """
        model = self._require_model()
        steps = int(max_steps) if max_steps is not None else self._max_steps
        timeout_s = timestr_to_secs(timeout) if timeout else self._timeout_s
        logger.info(f'AGENT ACT "{instruction}" (model={model}, max_steps={steps})')
        return run_act(
            self.engine,
            model,
            instruction,
            max_steps=steps,
            timeout_s=timeout_s,
            max_observation_chars=self._max_observation_chars,
        )

    @keyword("AGENT ASSERT")
    def agent_assert(self, instruction: str, screenshot: bool = True) -> str:
        """Judge whether ``instruction`` holds on the current screen.

        One model call judges the observation (plus a viewport screenshot,
        unless ``screenshot=False``) and answers holds / fails / inconclusive.
        Only ``holds`` passes; anything else fails the test with the model's
        explanation.

        Returns the explanation when the assertion holds.
        """
        model = self._require_model()
        logger.info(f'AGENT ASSERT "{instruction}" (model={model})')
        return run_assert(
            self.engine,
            model,
            instruction,
            screenshot=bool(screenshot),
            max_observation_chars=self._max_observation_chars,
        )
