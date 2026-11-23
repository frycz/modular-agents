"""Tests with a scripted model: every component runs for real except the API call."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import replace

import pytest

from modular_agents.composites.agent.composed_agent import ComposedAgent
from modular_agents.composites.budget.tree_budget import TreeBudget
from examples.demo_agent.events.logging_bus import LoggingEventBus
from modular_agents.composites.helpers import message_text
from modular_agents.interfaces.env import Environment
from modular_agents.interfaces.harness import Harness
from modular_agents.interfaces.model import Capabilities, Model, ModelRequest, ModelResponse
from modular_agents.interfaces.runner import CommandRunner, ExecResult
from modular_agents.interfaces.state import InitialState
from modular_agents.composites.tools.combined_toolset import CombinedToolSet
from modular_agents.interfaces.events import Deny, Modify
from modular_agents.interfaces.policy import ContextPolicy
from modular_agents.interfaces.tools import Tool, ToolContext, ToolOutput
from modular_agents.composites.loop.loop import StandardLoop
from modular_agents.composites.model.anthropic_adapter import AnthropicAdapter
from examples.demo_agent.policy.truncating_policy import TruncatingContextPolicy
from examples.demo_agent.store.json_store import JsonRunStore
from examples.demo_agent.tools.env_tools import BashTool, ReadFileTool, WriteFileTool
from examples.demo_agent.tools.shell_runner import ShellRunner
from modular_agents.composites.tools.spawn_agent import SpawnAgentTool
from modular_agents.composites.tools.static_toolset import StaticToolSet

USAGE = {"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0, "elapsed_ms": 0.0}


class ScriptedModel(Model):
    """Decides each reply from the request, like a tiny fake Claude."""

    ref = "fake"

    def __init__(self, reply):
        self.reply = reply
        self.requests = []

    async def complete(self, prompt, signal):
        req = copy.deepcopy(ModelRequest(self.ref, prompt.system, prompt.messages, prompt.tools))  # the loop changes the lists later
        self.requests.append(req)
        return self.reply(req)

    async def stream(self, prompt, signal):
        yield {"type": "response_complete", "response": await self.complete(prompt, signal)}

    def capabilities(self):
        return Capabilities()


def tool_use(*calls):
    content = [{"type": "tool_call", "id": f"t{i}", "name": n, "input": inp} for i, (n, inp) in enumerate(calls)]
    return ModelResponse(content, "tool_use", dict(USAGE))


def text(t):
    return ModelResponse([{"type": "text", "text": t}], "end_turn", dict(USAGE))


def last_results(req):
    return [b["content"][0]["text"] for b in req.messages[-1]["content"] if b["type"] == "tool_result"]


def first_text(req):
    return req.messages[0]["content"][0]["text"]


def setup(tmp_path, monkeypatch, reply, denied=frozenset(), budget=None):
    monkeypatch.chdir(tmp_path)  # JsonRunStore writes .runs/ here
    model = ScriptedModel(reply)
    events = LoggingEventBus(denied_tools=set(denied), quiet=True)
    env, policy, store = Environment("local"), TruncatingContextPolicy(), JsonRunStore()
    runner = ShellRunner()
    bash, read_file, write_file = BashTool(env, runner), ReadFileTool(env, runner), WriteFileTool(env, runner)
    sub_harness = Harness(StandardLoop(), TreeBudget({"steps": 10}), StaticToolSet([bash, read_file, write_file]), policy, events, store)
    spawn_agent = SpawnAgentTool(model, sub_harness, InitialState("You are a sub-agent."))
    tools = StaticToolSet([bash, read_file, write_file, spawn_agent])
    harness = Harness(StandardLoop(), budget or TreeBudget({"steps": 20}), tools, policy, events, store)
    return model, events, ComposedAgent(model, harness, InitialState("sys"))


def test_bash_round_trip(tmp_path, monkeypatch):
    def reply(req):
        results = last_results(req)
        return text("saw: " + results[0]) if results else tool_use(("bash", {"command": "echo hi"}))

    model, _, agent = setup(tmp_path, monkeypatch, reply)
    outcome = asyncio.run(agent.run("say hi"))
    assert outcome.reason == "end_turn"
    assert "exit code 0\nhi" in message_text(outcome.final)
    assert len(model.requests) == 2


def test_parallel_sub_agents_share_budget(tmp_path, monkeypatch):
    def reply(req):
        if req.system.startswith("You are a sub-agent"):
            return text("done: " + first_text(req))
        results = last_results(req)
        if results:
            return text(" | ".join(results))
        return tool_use(("spawn_agent", {"task": "A"}), ("spawn_agent", {"task": "B"}))

    _, events, agent = setup(tmp_path, monkeypatch, reply)
    outcome = asyncio.run(agent.run("split it"))
    assert message_text(outcome.final) == "done: A | done: B"
    assert agent.session_budget.spent["steps"] == 4  # 2 parent calls + 1 call per sub-agent
    assert sum(1 for e in events.log if e["type"] == "done") == 3
    assert len(list((tmp_path / ".runs").glob("*.json"))) == 3


def test_denied_tool_is_reported_to_model(tmp_path, monkeypatch):
    def reply(req):
        results = last_results(req)
        return text(results[0]) if results else tool_use(("bash", {"command": "rm -rf /"}))

    _, _, agent = setup(tmp_path, monkeypatch, reply, denied={"bash"})
    outcome = asyncio.run(agent.run("do it"))
    assert message_text(outcome.final) == "the call to bash was denied"


def test_budget_stops_run(tmp_path, monkeypatch):
    budget = TreeBudget({"steps": 3})
    _, _, agent = setup(tmp_path, monkeypatch, lambda req: tool_use(("bash", {"command": "true"})), budget=budget)
    outcome = asyncio.run(agent.run("loop forever"))
    assert outcome.reason == "budget_exhausted"
    assert agent.session_budget.spent["steps"] == 3
    assert budget.spent["steps"] == 0  # the harness budget is only the per-run limit
    outcome = asyncio.run(agent.run("again"))  # the next run gets a fresh budget
    assert outcome.reason == "budget_exhausted"
    assert agent.session_budget.spent["steps"] == 6


def test_cancel_stops_running_tool(tmp_path, monkeypatch):
    _, _, agent = setup(tmp_path, monkeypatch, lambda req: tool_use(("bash", {"command": "sleep 30"})))

    async def main():
        signal = asyncio.Event()
        asyncio.get_running_loop().call_later(0.2, signal.set)
        return await asyncio.wait_for(agent.run("wait", signal), 5)

    outcome = asyncio.run(main())
    assert outcome.reason == "cancelled"
    # the dangling tool call got a result, so the context can be continued
    assert outcome.state.messages[-1]["content"][0]["content"][0]["text"] == "cancelled"


def test_runs_continue_the_same_context(tmp_path, monkeypatch):
    model, _, agent = setup(tmp_path, monkeypatch, lambda req: text(f"seen {len(req.messages)}"))
    asyncio.run(agent.run("one"))
    outcome = asyncio.run(agent.run("two"))
    assert message_text(outcome.final) == "seen 3"  # one, answer, two
    assert [m["role"] for m in agent.state.messages] == ["user", "assistant", "user", "assistant"]


def test_run_store_round_trip(tmp_path, monkeypatch):
    _, _, agent = setup(tmp_path, monkeypatch, lambda req: text("ok"))
    outcome = asyncio.run(agent.run("hello"))
    loaded = asyncio.run(JsonRunStore().load(outcome.state.id))
    assert loaded.messages == outcome.state.messages
    assert loaded.budget["steps"] == 19


def test_agent_without_optional_parts():
    model = ScriptedModel(lambda req: text(f"{req.system or 'no system'}, {len(req.tools)} tools"))
    agent = ComposedAgent(model, Harness(StandardLoop(), TreeBudget({"steps": 1})))
    outcome = asyncio.run(agent.run("hi"))
    assert message_text(outcome.final) == "no system, 0 tools"


def test_env_tools_run_through_a_prefix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = Environment("box", "sh -c", "a shell")  # stands in for e.g. "ssh pi@raspi"
    runner = ShellRunner()
    write, read = WriteFileTool(env, runner), ReadFileTool(env, runner)
    assert (read.definition["name"], read.definition["description"]) == ("read_file_box", "Read a text file. Runs on: a shell.")
    path = "dir/it's a file.txt"

    async def main():
        ctx = ToolContext(asyncio.Event(), TreeBudget({}), "r")
        await write.execute({"path": path, "content": "hi there"}, ctx)
        return await read.execute({"path": path}, ctx), await read.execute({"path": "missing"}, ctx)

    found, missing = asyncio.run(main())
    assert (tmp_path / path).read_text() == "hi there"
    assert (found.content[0]["text"], found.is_error) == ("hi there", False)
    assert missing.is_error


def test_env_tools_build_commands_without_processes():
    class FakeRunner(CommandRunner):
        def __init__(self):
            self.calls = []

        async def run(self, env, command, signal, stdin=None, timeout_ms=60_000):
            self.calls.append((env.name, command, stdin))
            return ExecResult(0, "content", "")

    runner, raspi = FakeRunner(), Environment("raspi", "ssh pi@raspi")
    ctx = ToolContext(asyncio.Event(), TreeBudget({}), "r")
    asyncio.run(ReadFileTool(raspi, runner).execute({"path": "my notes.txt"}, ctx))
    asyncio.run(WriteFileTool(raspi, runner).execute({"path": "a/b.txt", "content": "hi"}, ctx))
    assert runner.calls == [("raspi", "cat -- 'my notes.txt'", None), ("raspi", "mkdir -p -- a && cat > a/b.txt", b"hi")]


def test_anthropic_adapter_round_trip():
    adapter = AnthropicAdapter()
    req = ModelRequest("m", "sys", [
        {"role": "assistant", "content": [{"type": "tool_call", "id": "a", "name": "bash", "input": {"command": "ls"}}]},
        {"role": "user", "content": [{"type": "tool_result", "call_id": "a", "content": [{"type": "text", "text": "x"}], "is_error": False}]},
    ], [], {"effort": "low"})
    wire = adapter.encode(req, Capabilities())
    assert wire["messages"][0]["content"][0]["type"] == "tool_use"
    assert wire["messages"][1]["content"][0]["tool_use_id"] == "a"
    assert wire["output_config"] == {"effort": "low"}

    async def chunks():
        for c in [
            {"type": "message_start", "message": {"usage": {"input_tokens": 3, "output_tokens": 0}}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "hi"}},
            {"type": "content_block_stop", "index": 0},
            {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "b", "name": "bash", "input": {}}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '{"command": "ls"}'}},
            {"type": "content_block_stop", "index": 1},
            {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 7}},
        ]:
            yield c

    async def collect():
        return [e async for e in adapter.decode_stream(chunks())]

    events = asyncio.run(collect())
    assert events[0] == {"type": "text_delta", "text": "hi"}
    res = events[-1]["response"]
    assert res.content[1] == {"type": "tool_call", "id": "b", "name": "bash", "input": {"command": "ls"}}
    assert (res.stop_reason, res.usage["output_tokens"]) == ("tool_use", 7)


class HookBus(LoggingEventBus):
    """Records events and answers interceptions from a dict: event type -> decision or callable."""

    def __init__(self, decisions):
        super().__init__(quiet=True)
        self.decisions = decisions

    async def intercept(self, e):
        d = self.decisions.get(e["type"], "allow")
        return d(e) if callable(d) else d


def bare_agent(reply, tools=(), events=None, policy=None, steps=10):
    model = ScriptedModel(reply)
    harness = Harness(StandardLoop(), TreeBudget({"steps": steps}), StaticToolSet(list(tools)), policy, events)
    return model, ComposedAgent(model, harness, InitialState("sys"))


class SlowTool(Tool):
    """Records when it starts and ends, to see what ran in parallel."""

    def __init__(self, name, log, concurrent):
        self.name, self.log, self.concurrent = name, log, concurrent

    @property
    def definition(self):
        return {"name": self.name, "description": "", "input_schema": {"type": "object"}}

    async def execute(self, input, ctx=None):
        self.log.append(f"start {input['i']}")
        await asyncio.sleep(0.01)
        self.log.append(f"end {input['i']}")
        return ToolOutput([{"type": "text", "text": str(input["i"])}])


def test_only_concurrent_tools_run_in_parallel():
    log = []
    tools = [SlowTool("look", log, True), SlowTool("change", log, False)]
    calls = [("look", {"i": 1}), ("look", {"i": 2}), ("change", {"i": 3}), ("look", {"i": 4})]
    _, agent = bare_agent(lambda req: text("ok") if last_results(req) else tool_use(*calls), tools)
    asyncio.run(agent.run("go"))
    assert log == ["start 1", "start 2", "end 1", "end 2", "start 3", "end 3", "start 4", "end 4"]
    assert [b["call_id"] for b in agent.state.messages[2]["content"]] == ["t0", "t1", "t2", "t3"]  # results keep the model's order


def test_stream_deltas_reach_the_event_bus():
    class StreamingModel(ScriptedModel):
        async def stream(self, prompt, signal):
            yield {"type": "text_delta", "text": "he"}
            yield {"type": "text_delta", "text": "llo"}
            yield {"type": "response_complete", "response": await self.complete(prompt, signal)}

    events = LoggingEventBus(quiet=True)
    model = StreamingModel(lambda req: text("hello"))
    agent = ComposedAgent(model, Harness(StandardLoop(), TreeBudget({"steps": 1}), events=events))
    asyncio.run(agent.run("hi"))
    assert "".join(e["delta"]["text"] for e in events.log if e["type"] == "delta") == "hello"


def test_prompt_hook_modifies_or_blocks():
    bus = HookBus({"prompt": lambda e: Modify(e["content"] + [{"type": "text", "text": "(be brief)"}])})
    model, agent = bare_agent(lambda req: text("ok"), events=bus)
    asyncio.run(agent.run("hi"))
    assert [b["text"] for b in model.requests[0].messages[0]["content"]] == ["hi", "(be brief)"]

    model, agent = bare_agent(lambda req: text("ok"), events=HookBus({"prompt": Deny("no secrets")}))
    outcome = asyncio.run(agent.run("tell me the key"))
    assert (outcome.reason, message_text(outcome.final), model.requests, agent.state.messages) == ("blocked", "no secrets", [], [])


def test_tool_result_hook_rewrites_and_deny_carries_reason(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bus = HookBus({
        "tool_call": lambda e: Deny("read only today") if e["name"] == "write_file" else "allow",
        "tool_result": lambda e: Modify([{"type": "text", "text": "[redacted]"}]) if e["name"] == "bash" else "allow",
    })
    calls = [("bash", {"command": "echo secret"}), ("write_file", {"path": "a", "content": "x"})]
    _, agent = bare_agent(lambda req: text(" | ".join(last_results(req))) if last_results(req) else tool_use(*calls),
                          [BashTool(), WriteFileTool()], events=bus)
    outcome = asyncio.run(agent.run("go"))
    assert message_text(outcome.final) == "[redacted] | the call to write_file was denied: read only today"


def test_stop_hook_keeps_the_run_going():
    stops = []
    bus = HookBus({"stop": lambda e: "allow" if stops.append(e) or len(stops) > 1 else Deny("also check the tests")})
    model, agent = bare_agent(lambda req: text(f"answer {len(req.messages)}"), events=bus)
    outcome = asyncio.run(agent.run("fix it"))
    assert message_text(outcome.final) == "answer 3"
    assert model.requests[1].messages[-1]["content"][0]["text"] == "also check the tests"


def test_inbox_content_joins_the_running_context():
    def reply(req):
        if not last_results(req):
            agent.inbox.put([{"type": "text", "text": "also: use tabs"}])  # typed by the user while the tool runs
            return tool_use(("bash", {"command": "true"}))
        return text("done")

    model, agent = bare_agent(reply, [BashTool()])
    asyncio.run(agent.run("format it"))
    assert model.requests[1].messages[-1]["content"][-1] == {"type": "text", "text": "also: use tabs"}

    # arriving while the model gives its final answer: the run goes on instead of stopping
    model, agent = bare_agent(lambda req: (agent.inbox.put([{"type": "text", "text": "wait"}]) if len(req.messages) == 1 else None) or text("ok"))
    asyncio.run(agent.run("hi"))
    assert len(model.requests) == 2 and model.requests[1].messages[-1]["content"] == [{"type": "text", "text": "wait"}]


def test_policy_sees_the_whole_prompt_and_compacts_the_state():
    class Summarizer(ContextPolicy):
        async def prepare(self, state, prompt, model):
            return replace(prompt, system=[{"type": "text", "text": prompt.system}, {"type": "text", "text": "skills: none"}], tools=[])

        def needs_compaction(self, state, model):
            return len(state.messages) > 2

        async def compact(self, state, model, budget, signal):
            state.messages[:] = [{"role": "user", "content": [{"type": "text", "text": "summary"}]}]

    bus = HookBus({})
    model, agent = bare_agent(lambda req: text("ok"), [BashTool()], events=bus, policy=Summarizer())
    asyncio.run(agent.run("one"))
    asyncio.run(agent.run("two"))
    assert model.requests[0].system == [{"type": "text", "text": "sys"}, {"type": "text", "text": "skills: none"}]
    assert model.requests[0].tools == []
    assert model.requests[1].messages == [{"role": "user", "content": [{"type": "text", "text": "summary"}]}]
    assert [e["type"] for e in bus.log].count("compact") == 1

    model, agent = bare_agent(lambda req: text("ok"), events=HookBus({"compact": Deny()}), policy=Summarizer())
    asyncio.run(agent.run("one"))
    asyncio.run(agent.run("two"))
    assert len(model.requests[1].messages) == 3


def test_resume_from_saved_state(tmp_path, monkeypatch):
    model, _, agent = setup(tmp_path, monkeypatch, lambda req: text(f"seen {len(req.messages)}"))
    first = asyncio.run(agent.run("one"))
    saved = asyncio.run(JsonRunStore().load(first.state.id))
    resumed = ComposedAgent(model, agent.harness, state=saved)
    assert message_text(asyncio.run(resumed.run("two")).final) == "seen 3"


def test_tool_name_clash_is_an_error():
    with pytest.raises(ValueError, match="bash"):
        StaticToolSet([BashTool(), BashTool()])
    with pytest.raises(ValueError, match="bash"):
        CombinedToolSet(StaticToolSet([BashTool()]), BashTool()).definitions()


def test_agent_starts_and_closes_its_parts():
    class Conn(SlowTool):
        def __init__(self):
            super().__init__("conn", [], True)

        async def start(self):
            self.log.append("start")

        async def aclose(self):
            self.log.append("close")

    conn = Conn()
    _, agent = bare_agent(lambda req: text("ok"), [conn])

    async def main():
        async with agent:
            await agent.run("hi")

    asyncio.run(main())
    assert conn.log == ["start", "close"]


def test_anthropic_adapter_ext_images_and_cache_usage():
    adapter = AnthropicAdapter()
    foreign = {"type": "thinking", "text": "hmm", "ext": {"openai": {"id": "r1"}}}
    own = {"type": "thinking", "text": "hmm", "ext": {"anthropic": {"type": "thinking", "thinking": "hmm", "signature": "s"}}}
    image = {"type": "image", "media_type": "image/png", "data": "AAA"}
    cached = {"type": "text", "text": "big", "ext": {"anthropic": {"cache_control": {"type": "ephemeral"}}}}
    search = {"name": "web_search", "description": "", "input_schema": {}, "ext": {"anthropic": {"type": "web_search_20250305", "name": "web_search"}}}
    req = ModelRequest("m", [cached], [
        {"role": "user", "content": [image]},
        {"role": "assistant", "content": [foreign, own, {"type": "text", "text": "hi"}]},
    ], [search])
    wire = adapter.encode(req, Capabilities())
    assert wire["system"] == [{"type": "text", "text": "big", "cache_control": {"type": "ephemeral"}}]
    assert wire["messages"][0]["content"] == [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAA"}}]
    assert wire["messages"][1]["content"] == [own["ext"]["anthropic"], {"type": "text", "text": "hi"}]  # the foreign block is dropped
    assert wire["tools"] == [{"type": "web_search_20250305", "name": "web_search"}]

    res = adapter.decode({
        "content": [{"type": "server_tool_use", "id": "s", "name": "web_search", "input": {}}, {"type": "text", "text": "x"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 100, "cache_creation_input_tokens": None},
    })
    assert res.content[0] == {"type": "opaque", "ext": {"anthropic": {"type": "server_tool_use", "id": "s", "name": "web_search", "input": {}}}}
    assert (res.usage["cache_read_tokens"], res.usage["cache_write_tokens"]) == (100, 0)
    assert adapter.encode(ModelRequest("m", "", [{"role": "assistant", "content": res.content}], []), Capabilities())["messages"][0]["content"][0]["type"] == "server_tool_use"
