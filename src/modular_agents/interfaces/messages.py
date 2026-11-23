"""Messages: the conversation format shared by the context, the loop, tools and the model layer.

Every block may carry ext: provider data keyed by protocol name, e.g. {"anthropic": {"cache_control": ...}}. An adapter
sends its own key's data and ignores the others, so a context can move to another provider without leaking wire formats.
"""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

type Ext = dict[str, dict]  # protocol name -> that protocol's data


class TextBlock(TypedDict):
    type: Literal["text"]
    text: str
    ext: NotRequired[Ext]


class ImageBlock(TypedDict):
    type: Literal["image"]
    media_type: str  # "image/png", "image/jpeg", ...
    data: str  # base64
    ext: NotRequired[Ext]


class DocumentBlock(TypedDict):
    type: Literal["document"]
    media_type: str  # "application/pdf", "text/plain", ...
    data: str  # base64
    ext: NotRequired[Ext]


class ToolCallBlock(TypedDict):
    type: Literal["tool_call"]
    id: str
    name: str
    input: Any
    ext: NotRequired[Ext]


class ToolResultBlock(TypedDict):
    type: Literal["tool_result"]
    call_id: str
    content: list[ContentBlock]
    is_error: bool
    ext: NotRequired[Ext]


class ThinkingBlock(TypedDict):
    type: Literal["thinking"]
    text: str
    ext: NotRequired[Ext]  # the original wire block under its protocol, returned unchanged; other protocols drop it


class OpaqueBlock(TypedDict):
    """Provider-only content with no common form, e.g. a server-side web search and its results. Kept for the protocol
    that produced it, dropped by the others."""

    type: Literal["opaque"]
    ext: Ext


type ContentBlock = TextBlock | ImageBlock | DocumentBlock | ToolCallBlock | ToolResultBlock | ThinkingBlock | OpaqueBlock


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: list[ContentBlock]
