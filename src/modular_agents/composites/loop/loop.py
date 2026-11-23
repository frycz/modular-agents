"""StandardLoop: advance a RunState one model call at a time until a stop condition."""

from __future__ import annotations

import asyncio

from modular_agents.composites.helpers import append_user
from modular_agents.interfaces.cancellation import Cancelled
from modular_agents.interfaces.events import Decision, Deny, InterceptableEvent, LoopEvent, Modify, ToolCallEvent, ToolResultEvent
from modular_agents.interfaces.loop import Loop, RunContext, RunOutcome
from modular_agents.interfaces.messages import Message, ToolCallBlock, ToolResultBlock
from modular_agents.interfaces.model import ModelResponse, Prompt
from modular_agents.interfaces.state import RunState
from modular_agents.interfaces.tools import ToolContext, ToolOutput


class StandardLoop(Loop):
    async def run(self, state: RunState, ctx: RunContext) -> RunOutcome:
        while True:
            try:
                outcome = await self.step(state, ctx)
            except Cancelled:
                outcome = RunOutcome("cancelled", self._final_message(state), state)
            if ctx.store:
                await ctx.store.save(state)
            if outcome:
                self._emit(ctx, {"type": "done", "run_id": state.id, "reason": outcome.reason})
                return outcome

    async def step(self, state: RunState, ctx: RunContext) -> RunOutcome | None:
        """One model call, plus the tool calls it asks for. Returns an outcome when the run is over."""
        if ctx.signal.is_set():
            return RunOutcome("cancelled", self._final_message(state), state)
        if any(left <= 0 for left in ctx.budget.remaining().values()):
            return RunOutcome("budget_exhausted", self._final_message(state), state)

        if ctx.inbox and (arrived := ctx.inbox.take()):
            append_user(state.messages, arrived)
        if ctx.policy and ctx.policy.needs_compaction(state, ctx.model):
            event = {"type": "compact", "run_id": state.id, "messages": len(state.messages)}
            self._emit(ctx, event)
            if not isinstance(await self._intercept(ctx, event), Deny):
                await ctx.policy.compact(state, ctx.model, ctx.budget, ctx.signal)

        prompt = Prompt(state.system, state.messages, ctx.tools.definitions() if ctx.tools else [])
        if ctx.policy:
            prompt = await ctx.policy.prepare(state, prompt, ctx.model)
        self._emit(ctx, {"type": "request", "run_id": state.id, "messages": len(prompt.messages)})
        res = await self._stream(state, prompt, ctx)
        ctx.budget.charge(res.usage)
        state.budget = ctx.budget.remaining()
        u = res.usage
        state.context_tokens = u["input_tokens"] + u.get("cache_read_tokens", 0) + u.get("cache_write_tokens", 0) + u["output_tokens"]
        state.messages.append({"role": "assistant", "content": res.content})
        self._emit(ctx, {"type": "response", "run_id": state.id, "stop_reason": res.stop_reason, "usage": res.usage})

        if res.stop_reason == "pause_turn":  # the API paused mid-turn: just call again
            return None
        if res.stop_reason == "end_turn":
            if ctx.inbox and (arrived := ctx.inbox.take()):  # something came in while the model was answering
                append_user(state.messages, arrived)
                return None
            decision = await self._intercept(ctx, {"type": "stop", "run_id": state.id})
            if isinstance(decision, Deny):  # a stop hook wants more work: its reason is the next message
                append_user(state.messages, [{"type": "text", "text": decision.reason or "Continue."}])
                return None
        if res.stop_reason != "tool_use":  # end_turn, max_tokens, refusal
            return RunOutcome(res.stop_reason, self._final_message(state), state)

        calls = [b for b in res.content if b["type"] == "tool_call"]
        tool_ctx = ToolContext(ctx.signal, ctx.budget, state.id, state, ctx.events, ctx.inbox)
        results = await self._call_tools(calls, tool_ctx, ctx)
        # All results of one turn go back in a single user message.
        state.messages.append({"role": "user", "content": results})
        return None

    async def _stream(self, state: RunState, prompt: Prompt, ctx: RunContext) -> ModelResponse:
        """Stream the response, passing deltas to the event bus for UIs."""
        res = None
        async for e in ctx.model.stream(prompt, ctx.signal):
            if e["type"] == "response_complete":
                res = e["response"]
            else:
                self._emit(ctx, {"type": "delta", "run_id": state.id, "delta": e})
        if res is None:
            raise RuntimeError(f"{ctx.model.ref}: the stream ended without a response")
        return res

    async def _call_tools(self, calls: list[ToolCallBlock], tool_ctx: ToolContext, ctx: RunContext) -> list[ToolResultBlock]:
        """Runs of concurrent tools go in parallel, every other tool runs alone, in the order the model asked."""
        results: list[ToolResultBlock] = []
        batch: list[ToolCallBlock] = []
        for call in calls:
            tool = ctx.tools.get(call["name"]) if ctx.tools else None
            if tool is None or tool.concurrent:
                batch.append(call)
                continue
            results += await asyncio.gather(*(self.call_tool(c, tool_ctx, ctx) for c in batch))
            batch = []
            results.append(await self.call_tool(call, tool_ctx, ctx))
        results += await asyncio.gather(*(self.call_tool(c, tool_ctx, ctx) for c in batch))
        return results

    async def call_tool(self, call: ToolCallBlock, tool_ctx: ToolContext, ctx: RunContext) -> ToolResultBlock:
        name = call["name"]
        event: ToolCallEvent = {"type": "tool_call", "run_id": tool_ctx.run_id, "call_id": call["id"], "name": name, "input": call["input"]}
        self._emit(ctx, event)
        tool = ctx.tools.get(name) if ctx.tools else None
        decision = await self._intercept(ctx, event)
        if tool is None:
            output = ToolOutput([{"type": "text", "text": f"unknown tool: {name}"}], True)
        elif isinstance(decision, Deny):
            output = ToolOutput([{"type": "text", "text": _denied(f"the call to {name} was denied", decision)}], True)
        else:
            tool_input = decision.value if isinstance(decision, Modify) else call["input"]
            try:
                output = await tool.execute(tool_input, tool_ctx)
            except Cancelled:  # still answer the call, so the context stays valid for the next run
                output = ToolOutput([{"type": "text", "text": "cancelled"}], True)
            except Exception as e:  # a failing tool is reported to the model, not raised
                output = ToolOutput([{"type": "text", "text": f"{type(e).__name__}: {e}"}], True)

        result: ToolResultEvent = {
            "type": "tool_result", "run_id": tool_ctx.run_id, "call_id": call["id"], "name": name,
            "is_error": output.is_error, "content": output.content,
        }
        decision = await self._intercept(ctx, result)
        if isinstance(decision, Deny):
            result.update(is_error=True, content=[{"type": "text", "text": _denied(f"the result of {name} was blocked", decision)}])
        elif isinstance(decision, Modify):
            result["content"] = decision.value
        self._emit(ctx, result)
        return {"type": "tool_result", "call_id": call["id"], "content": result["content"], "is_error": result["is_error"]}

    @staticmethod
    def _final_message(state: RunState) -> Message:
        return next((m for m in reversed(state.messages) if m["role"] == "assistant"), {"role": "assistant", "content": []})

    @staticmethod
    def _emit(ctx: RunContext, event: LoopEvent):
        if ctx.events:
            ctx.events.emit(event)

    @staticmethod
    async def _intercept(ctx: RunContext, event: InterceptableEvent) -> Decision:
        return await ctx.events.intercept(event) if ctx.events else "allow"


def _denied(text: str, decision: Deny) -> str:
    return f"{text}: {decision.reason}" if decision.reason else text
