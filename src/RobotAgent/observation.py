"""Observation formatting: turns the JSON returned by observe.js into the
text tree the model reads, bounded by a character budget (the e2e project's
"observation byte budget" idea)."""

from __future__ import annotations

TRUNCATION_MARKER = "[observation truncated at the observation character limit]"

_MAX_INDENT_DEPTH = 8


def format_observation(raw: dict, max_chars: int = 8000) -> str:
    """Serialize one observation payload to text lines, one per node.

    Nodes look like::

        n12 button "Login"
        n13 textbox "Username" value="bob"
        n14 checkbox "Remember me" checked
        text "Welcome back"

    Interactive nodes keep the ids the page was tagged with; plain ``text``
    lines are reading context and cannot be targeted.
    """
    lines = [
        f"URL: {raw.get('url', '')}",
        f"Title: {raw.get('title', '')}",
        "",
    ]
    for item in raw.get("items", []):
        indent = "  " * min(item.get("depth", 0), _MAX_INDENT_DEPTH)
        if item.get("kind") == "text":
            lines.append(f'{indent}text "{item.get("text", "")}"')
            continue
        line = f"{indent}{item.get('id', '?')} {item.get('role', 'generic')}"
        name = item.get("name") or ""
        if name:
            line += f' "{name}"'
        value = item.get("value")
        if value is not None and value != "":
            line += f' value="{value}"'
        if item.get("checked"):
            line += " checked"
        lines.append(line)

    text = "\n".join(lines)
    if raw.get("truncated"):
        text += "\n[observation truncated: the collector stopped listing nodes at its limit]"
    if len(text) > max_chars:
        text = text[:max_chars] + "\n" + TRUNCATION_MARKER
    return text
