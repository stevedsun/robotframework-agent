"""Tool vocabulary offered to the acting model (OpenAI/LiteLLM function
format) and the dispatch that runs each call against the engine.

Mirrors e2e's grammar tools (primitives.ts) at a fraction of the surface:
click, type_text, press, scroll, scroll_to, screenshot, and the verdict tool
``done`` — the only way a step concludes.
"""

from __future__ import annotations

from typing import Any

from .engine import BrowserEngine

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click an interactive element by its node id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Node id from the screen, e.g. n12"},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Replace the whole value of a text field (or pick a select option) identified by a node id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Node id of the field"},
                    "text": {"type": "string", "description": "The text to enter"},
                },
                "required": ["id", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press",
            "description": "Press one keyboard key such as Enter, Tab or Escape, optionally focused on a node.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key name, e.g. Enter"},
                    "id": {"type": "string", "description": "Optional node id to focus the key press on"},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll the page up or down to reveal more content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down"]},
                    "times": {"type": "integer", "default": 1, "description": "Screens to scroll, 1-20"},
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_to",
            "description": "Scroll the element with the given node id into view.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Node id from the screen"},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Attach a screenshot of the current viewport so you can see it. Use when the text tree lacks what you need.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Conclude the step. Call exactly once when the goal is achieved or certainly cannot be.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["passed", "failed", "blocked"]},
                    "summary": {"type": "string", "description": "Short reason grounded in the latest screen"},
                    "error_code": {
                        "type": "string",
                        "description": "Required when status is blocked, e.g. AUTHENTICATION_FAILED, APP_UNREACHABLE",
                    },
                },
                "required": ["status", "summary"],
            },
        },
    },
]

# Only the verdict tool, offered when the budget is spent and the model must conclude.
DONE_ONLY_SCHEMAS: list[dict[str, Any]] = [TOOL_SCHEMAS[-1]]

# Actions that change application state; after them the screen is re-read.
_MUTATING = {"click", "type_text", "press", "scroll", "scroll_to"}


def execute_tool(engine: BrowserEngine, name: str, args: dict[str, Any]) -> str:
    """Run one non-verdict tool against the engine. Raises on engine errors;
    the loop turns failures into result text for the model."""
    if name == "click":
        engine.click(str(args.get("id", "")))
        return f"clicked {args.get('id')}"
    if name == "type_text":
        engine.type_text(str(args.get("id", "")), str(args.get("text", "")))
        return f"typed into {args.get('id')}"
    if name == "press":
        node = args.get("id")
        engine.press(str(args.get("key", "")), str(node) if node else None)
        return f"pressed {args.get('key')}"
    if name == "scroll":
        engine.scroll(str(args.get("direction", "down")), int(args.get("times", 1) or 1))
        return f"scrolled {args.get('direction', 'down')}"
    if name == "scroll_to":
        engine.scroll_to(str(args.get("id", "")))
        return f"scrolled to {args.get('id')}"
    raise ValueError(f"unknown tool {name!r}")


def is_mutating(name: str) -> bool:
    return name in _MUTATING
