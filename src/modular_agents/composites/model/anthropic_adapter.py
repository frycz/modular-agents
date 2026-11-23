"""AnthropicAdapter: common representation <-> Anthropic Messages API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from modular_agents.interfaces.endpoint import ProtocolAdapter, WireChunk, WireRequest, WireResponse
from modular_agents.interfaces.messages import ContentBlock
from modular_agents.interfaces.model import Capabilities, ModelEvent, ModelRequest, ModelResponse, System, ToolDefinition, Usage

PROTOCOL = "anthropic"  # the ext key this adapter reads and writes


class AnthropicAdapter(ProtocolAdapter):
    def encode(self, req: ModelRequest, caps: Capabilities) -> WireRequest:
        if req.tools and not caps.tool_calling:
            raise ValueError(f"{req.model} does not support tool calling")
        wire = {
            "model": req.model, "max_tokens": req.params.get("max_tokens", 16000), "system": self._encode_system(req.system),
            "messages": [{"role": m["role"], "content": self._encode_blocks(m["content"])} for m in req.messages],
        }
        if req.tools:
            wire["tools"] = [self._encode_tool(t) for t in req.tools]
        if "effort" in req.params:
            wire["output_config"] = {"effort": req.params["effort"]}
        return wire

    def _encode_system(self, system: System) -> str | list[dict]:
        if isinstance(system, str):
            return system
        return [{"type": "text", "text": b["text"], **b.get("ext", {}).get(PROTOCOL, {})} for b in system]

    def _encode_tool(self, t: ToolDefinition) -> dict:
        ext = t.get("ext", {}).get(PROTOCOL, {})
        if "type" in ext:  # a server tool, e.g. web search: the API defines it, only the ext is sent
            return ext
        return {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"], **ext}

    def _encode_blocks(self, blocks: list[ContentBlock]) -> list[dict]:
        return [w for b in blocks if (w := self._encode_block(b)) is not None]

    def _encode_block(self, b: ContentBlock) -> dict | None:
        ext = b.get("ext", {}).get(PROTOCOL)
        match b["type"]:
            case "thinking" | "opaque":
                return ext  # the original wire block, signature included; None when another protocol made it, so it is dropped
            case "text":
                wire = {"type": "text", "text": b["text"]}
            case "image" | "document":
                wire = {"type": b["type"], "source": {"type": "base64", "media_type": b["media_type"], "data": b["data"]}}
            case "tool_call":
                wire = {"type": "tool_use", "id": b["id"], "name": b["name"], "input": b["input"]}
            case "tool_result":
                content = self._encode_blocks(b["content"])
                wire = {"type": "tool_result", "tool_use_id": b["call_id"], "content": content, "is_error": b["is_error"]}
        return {**wire, **(ext or {})}  # e.g. cache_control

    def decode(self, res: WireResponse) -> ModelResponse:
        content: list[ContentBlock] = []
        for b in res["content"]:
            match b["type"]:
                case "text":
                    content.append({"type": "text", "text": b["text"]})
                case "tool_use":
                    content.append({"type": "tool_call", "id": b["id"], "name": b["name"], "input": b["input"]})
                case "thinking" | "redacted_thinking":
                    content.append({"type": "thinking", "text": b.get("thinking", ""), "ext": {PROTOCOL: b}})
                case _:  # server tool calls and their results: no common form, kept for this protocol only
                    content.append({"type": "opaque", "ext": {PROTOCOL: b}})
        stop = {"stop_sequence": "end_turn", "model_context_window_exceeded": "max_tokens"}.get(res["stop_reason"], res["stop_reason"])
        u = res["usage"]
        usage: Usage = {
            "input_tokens": u["input_tokens"], "output_tokens": u["output_tokens"], "cost_usd": 0.0, "elapsed_ms": 0.0,
            "cache_read_tokens": u.get("cache_read_input_tokens") or 0, "cache_write_tokens": u.get("cache_creation_input_tokens") or 0,
        }
        return ModelResponse(content, stop, usage)

    async def decode_stream(self, chunks: AsyncIterator[WireChunk]) -> AsyncIterator[ModelEvent]:
        # Rebuild the full wire message from the events, then decode it like a normal response.
        msg = {"content": [], "stop_reason": None, "usage": {}}
        async for c in chunks:
            match c["type"]:
                case "message_start":
                    msg["usage"] = c["message"]["usage"]
                case "content_block_start":
                    b = c["content_block"]
                    msg["content"].append(b)
                    if b["type"] == "tool_use":
                        yield {"type": "tool_call_start", "id": b["id"], "name": b["name"]}
                case "content_block_delta":
                    b, d = msg["content"][c["index"]], c["delta"]
                    match d["type"]:
                        case "text_delta":
                            b["text"] += d["text"]
                            yield {"type": "text_delta", "text": d["text"]}
                        case "input_json_delta":
                            b["json"] = b.get("json", "") + d["partial_json"]
                            if b["type"] == "tool_use":
                                yield {"type": "tool_input_delta", "id": b["id"], "partial_json": d["partial_json"]}
                        case "thinking_delta":
                            b["thinking"] += d["thinking"]
                            yield {"type": "thinking_delta", "text": d["thinking"]}
                        case "signature_delta":
                            b["signature"] = d["signature"]
                case "content_block_stop":
                    b = msg["content"][c["index"]]
                    if "json" in b:
                        b["input"] = json.loads(b.pop("json") or "{}")
                case "message_delta":
                    msg["stop_reason"] = c["delta"]["stop_reason"]
                    msg["usage"].update(c["usage"])
                case "error":
                    raise RuntimeError(c["error"])
        yield {"type": "response_complete", "response": self.decode(msg)}
