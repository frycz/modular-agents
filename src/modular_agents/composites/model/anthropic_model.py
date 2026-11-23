"""AnthropicModel: an EndpointModel that builds its own Anthropic endpoint (adapter + HTTP transport)."""

from __future__ import annotations

import os

from modular_agents.composites.model.adapter_endpoint import AdapterEndpoint
from modular_agents.composites.model.anthropic_adapter import AnthropicAdapter
from modular_agents.composites.model.endpoint_model import EndpointModel
from modular_agents.composites.model.http_transport import HttpTransport
from modular_agents.interfaces.model import Capabilities, ModelParams, ModelRef
from modular_agents.interfaces.routing import Scheduler


class AnthropicModel(EndpointModel):
    def __init__(
        self, ref: ModelRef, api_key: str | None = None, params: ModelParams | None = None,
        caps: Capabilities | None = None, scheduler: Scheduler | None = None,
        url: str = "https://api.anthropic.com/v1/messages", timeout_s: float = 600,
    ):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("no API key: pass api_key or set ANTHROPIC_API_KEY")
        transport = HttpTransport(url, headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}, timeout_s=timeout_s)
        super().__init__(AdapterEndpoint("anthropic", AnthropicAdapter(), transport), ref, params, caps, scheduler)
