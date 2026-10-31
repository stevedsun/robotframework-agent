"""The acting loop and the one-shot judgment, the heart of the two keywords.

``run_act`` is a small port of e2e's tool-loop chassis (tool-loop.ts): the
model works through tool calls, every mutating action's result carries the
fresh screen, budgets and a deadline guard the loop, and a spent budget
triggers a wind-down in which only the verdict tool is offered. ``run_assert``
is the judgment path (prompts.ts JUDGMENT_REQUEST): one call, a strict JSON
verdict, one repair round on a malformed answer.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
from robot.api import logger

from .engine import SETTLE_SECONDS, BrowserEngine
from .prompts import (
    ACT_SYSTEM,
    ACT_TOOL_CALLS_ONLY,
    ACT_VERDICT_RULES,
    ASSERT_REPAIR,
    ASSERT_SYSTEM,
    build_act_prompt,
    build_assert_prompt,
)
from .tools import DONE_ONLY_SCHEMAS, TOOL_SCHEMAS, execute_tool, is_mutating

litellm.suppress_debug_info = True

# Extra turns with only the verdict tool once the budget or clock runs out.
WIND_DOWN_TURNS = 2


class AgentStepError(AssertionError):
    """A product verdict: the application did not do what the step required."""


def _b64_png(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _message_dict(msg: Any) -> dict[str, Any]:
    """Convert a LiteLLM response message back into request format."""
    out: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
    calls = getattr(msg, "tool_calls", None) or []
    if calls:
        out["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments or "{}",
                },
            }
            for call in calls
        ]
    return out


def _looks_like_forced_choice_unsupported(exc: Exception) -> bool:
    text = str(exc).lower()
    return "tool_choice" in text or "tool choice" in text


class _AgentLoop:
    """One acting step: message history, budgets, and the completion calls."""

    def __init__(
        self,
        engine: BrowserEngine,
        model: str,
        max_steps: int,
        timeout_s: float,
        max_observation_chars: int,
    ) -> None:
        self.engine = engine
        self.model = model
        self.max_steps = max_steps
        self.deadline = time.monotonic() + timeout_s
        self.max_observation_chars = max_observation_chars
        self.tool_choice: Any = "required"
        self.steps = 0

    def remaining_ms(self) -> int:
        return max(0, int((self.deadline - time.monotonic()) * 1000))

    def budget_spent(self) -> bool:
        return self.steps >= self.max_steps or self.remaining_ms() <= 0

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        """One model call. A provider that rejects a forced tool choice gets
        ``auto`` for the rest of the step, so the refusal costs one round trip."""
        while True:
            try:
                response = litellm.completion(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice=self.tool_choice,
                    timeout=max(10.0, min(120.0, self.remaining_ms() / 1000)),
                )
                break
            except Exception as exc:  # noqa: BLE001 - provider errors reach the test verbatim
                if self.tool_choice == "required" and _looks_like_forced_choice_unsupported(exc):
                    logger.info("Model rejected forced tool choice; falling back to auto.")
                    self.tool_choice = "auto"
                    continue
                raise RuntimeError(f"LLM call failed for model {self.model!r}: {exc}") from exc
        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.debug(f"agent model usage: {usage}")
        return response.choices[0].message

    def run(self, instruction: str) -> str:
        screen = self.engine.observe(self.max_observation_chars)
        system = f"{ACT_SYSTEM}\n\n{ACT_VERDICT_RULES}\n\n{ACT_TOOL_CALLS_ONLY}"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": build_act_prompt(instruction, screen)},
        ]
        while not self.budget_spent():
            verdict = self.turn(messages, TOOL_SCHEMAS)
            if verdict is not None:
                return verdict
            self.steps += 1
        return self.wind_down(messages)

    def turn(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str | None:
        """One model turn plus the tool calls it asked for. Returns the
        passing summary if the model concluded, else None."""
        msg = self.complete(messages, tools)
        messages.append(_message_dict(msg))
        calls = getattr(msg, "tool_calls", None) or []
        if not calls:
            messages.append({"role": "user", "content": ACT_TOOL_CALLS_ONLY})
            return None
        for call in calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if name == "done":
                return self.settle(args)
            result = self.dispatch(name, args)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            pending = getattr(self, "_pending_image", None)
            if pending is not None:
                self._pending_image = None
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Current viewport screenshot:"},
                            {"type": "image_url", "image_url": {"url": _b64_png(pending)}},
                        ],
                    }
                )
        return None

    def dispatch(self, name: str, args: dict[str, Any]) -> str:
        """Run one tool; failures become text so the model can recover."""
        if name == "screenshot":
            try:
                png = self.engine.screenshot_bytes()
            except Exception as exc:  # noqa: BLE001
                return f"screenshot failed: {exc}"
            # The image rides as a user message right after the tool ack.
            self._pending_image = png
            return "Screenshot taken; it is attached after this result."
        try:
            text = execute_tool(self.engine, name, args)
        except Exception as exc:  # noqa: BLE001 - e.g. a stale id after navigation
            return f"Tool {name} failed: {exc}"
        if is_mutating(name):
            time.sleep(SETTLE_SECONDS)
            screen = self.engine.observe(self.max_observation_chars)
            return f"{text}\n\nCurrent screen:\n{screen}"
        return text

    def settle(self, args: dict[str, Any]) -> str:
        status = str(args.get("status", "")).lower()
        summary = str(args.get("summary", ""))[:2000]
        if status == "passed":
            logger.info(f"AGENT ACT passed: {summary}")
            return summary
        if status not in {"failed", "blocked"}:
            raise AgentStepError(f"AGENT ACT failed: done called with invalid status {status!r}")
        code = args.get("error_code")
        detail = f" [{code}]" if status == "blocked" and code else ""
        raise AgentStepError(f"AGENT ACT {status}{detail}: {summary}")

    def wind_down(self, messages: list[dict[str, Any]]) -> str:
        """Budget is spent: give the model a few turns with only the verdict
        tool, so a slow step still concludes with its own summary."""
        messages.append(
            {
                "role": "user",
                "content": "The step budget is spent. Call done now with your honest verdict.",
            }
        )
        for _ in range(WIND_DOWN_TURNS):
            verdict = self.turn(messages, DONE_ONLY_SCHEMAS)
            if verdict is not None:
                return verdict
        raise AgentStepError(
            f"AGENT ACT failed: exceeded its budget ({self.max_steps} steps) without reaching the goal"
        )


def run_act(
    engine: BrowserEngine,
    model: str,
    instruction: str,
    max_steps: int,
    timeout_s: float,
    max_observation_chars: int,
) -> str:
    loop = _AgentLoop(engine, model, max_steps, timeout_s, max_observation_chars)
    return loop.run(instruction)


def _parse_verdict(text: str) -> tuple[str, str] | None:
    """Extract {explanation, verdict} from a model answer, tolerating prose
    around the JSON object."""
    start = text.find("{")
    while start != -1:
        end = text.rfind("}")
        if end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            next_brace = text.find("{", start + 1)
            start = next_brace
            continue
        verdict = str(data.get("verdict", "")).lower()
        if verdict in {"holds", "fails", "inconclusive"}:
            return verdict, str(data.get("explanation", ""))[:2000]
        return None
    return None


def run_assert(
    engine: BrowserEngine,
    model: str,
    instruction: str,
    screenshot: bool,
    max_observation_chars: int,
) -> str:
    screen = engine.observe(max_observation_chars)
    content: list[dict[str, Any]] = [
        {"type": "text", "text": build_assert_prompt(instruction, screen)}
    ]
    if screenshot:
        png = engine.screenshot_bytes()
        content.append(
            {"type": "image_url", "image_url": {"url": _b64_png(png)}}
        )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": ASSERT_SYSTEM},
        {"role": "user", "content": content},
    ]
    for attempt in range(2):
        try:
            response = litellm.completion(model=model, messages=messages, timeout=120.0)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"LLM call failed for model {model!r}: {exc}") from exc
        text = response.choices[0].message.content or ""
        parsed = _parse_verdict(text)
        if parsed is not None:
            verdict, explanation = parsed
            if verdict == "holds":
                logger.info(f"AGENT ASSERT holds: {explanation}")
                return explanation
            raise AgentStepError(f"AGENT ASSERT {verdict}: {explanation}")
        if attempt == 0:
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": ASSERT_REPAIR})
    raise AgentStepError("AGENT ASSERT failed: the model did not return a valid verdict")
