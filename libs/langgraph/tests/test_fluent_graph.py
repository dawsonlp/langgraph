"""Unit tests for FluentGraph."""

import pytest
from typing_extensions import TypedDict

from langgraph.graph.fluent import FluentGraph, enable_if
from langgraph.graph.fluent.nodes import ConditionalNode


class SimpleState(TypedDict):
    """Simple test state."""

    value: int


class CounterState(TypedDict):
    """State with counter."""

    count: int
    valid: bool


def test_fluent_graph_construction():
    """Test basic FluentGraph construction."""
    graph = FluentGraph(SimpleState)
    assert graph is not None
    assert graph._state_schema is SimpleState


def test_single_node_sequential():
    """Test adding a single node creates sequential execution."""

    def add_one(state: SimpleState) -> SimpleState:
        return {"value": state["value"] + 1}

    graph = FluentGraph(SimpleState).then(add_one).compile()

    result = graph.invoke({"value": 0})
    assert result["value"] == 1


def test_multiple_nodes_sequential():
    """Test adding multiple nodes sequentially."""

    def add_one(state: SimpleState) -> SimpleState:
        return {"value": state["value"] + 1}

    def multiply_two(state: SimpleState) -> SimpleState:
        return {"value": state["value"] * 2}

    graph = FluentGraph(SimpleState).then(add_one).then(multiply_two).compile()

    result = graph.invoke({"value": 5})
    # (5 + 1) * 2 = 12
    assert result["value"] == 12


def test_parallel_nodes():
    """Test adding nodes in parallel."""

    def add_one(state: SimpleState) -> SimpleState:
        return {"value": state["value"] + 1}

    def multiply_two(state: SimpleState) -> SimpleState:
        return {"value": state["value"] * 2}

    # Parallel execution - last writer wins, but both execute
    graph = FluentGraph(SimpleState).then([add_one, multiply_two]).compile()

    result = graph.invoke({"value": 5})
    # Both nodes run in parallel from value=5
    # One produces 6, other produces 10
    # With LastValue reducer, one of them wins (order undefined in parallel)
    assert result["value"] in [6, 10]


def test_conditional_node_true():
    """Test conditional node executes when condition is True."""

    def increment(state: CounterState) -> CounterState:
        return {"count": state["count"] + 1}

    def is_valid(state: CounterState) -> bool:
        return state.get("valid", True)

    # Single conditional node
    graph = FluentGraph(CounterState).then(enable_if(increment, is_valid)).compile()

    result = graph.invoke({"count": 0, "valid": True})
    assert result["count"] == 1


def test_conditional_node_false():
    """Test conditional node skips when condition is False."""

    def increment(state: CounterState) -> CounterState:
        return {"count": state["count"] + 1}

    def is_valid(state: CounterState) -> bool:
        return state.get("valid", True)

    # Single conditional node
    graph = FluentGraph(CounterState).then(enable_if(increment, is_valid)).compile()

    result = graph.invoke({"count": 0, "valid": False})
    # Node should be skipped, count remains 0
    assert result["count"] == 0


def test_mixed_parallel_and_conditional():
    """Test mixing regular and conditional nodes in parallel."""

    def increment(state: CounterState) -> CounterState:
        return {"count": state["count"] + 1}

    def double(state: CounterState) -> CounterState:
        return {"count": state["count"] * 2}

    def is_valid(state: CounterState) -> bool:
        return state.get("valid", True)

    graph = (
        FluentGraph(CounterState)
        .then([increment, enable_if(double, is_valid)])
        .compile()
    )

    # When valid=True, both should execute
    result = graph.invoke({"count": 5, "valid": True})
    # increment: 5 + 1 = 6, double: 5 * 2 = 10
    # One of them wins
    assert result["count"] in [6, 10]


def test_method_chaining():
    """Test that methods return self for chaining."""

    def node1(state: SimpleState) -> SimpleState:
        return state

    def node2(state: SimpleState) -> SimpleState:
        return state

    graph = FluentGraph(SimpleState).then(node1).then(node2)

    assert isinstance(graph, FluentGraph)


def test_node_name_uniqueness():
    """Test that node names are unique even with same function."""

    def same_func(state: SimpleState) -> SimpleState:
        return {"value": state["value"] + 1}

    graph = FluentGraph(SimpleState).then(same_func).then(same_func).compile()

    # Both nodes should execute (value should be incremented twice)
    result = graph.invoke({"value": 0})
    assert result["value"] == 2


def test_empty_list_raises_error():
    """Test that empty list of nodes raises error."""
    graph = FluentGraph(SimpleState)

    with pytest.raises(ValueError, match="Cannot add empty list"):
        graph.then([])


def test_invalid_node_type_raises_error():
    """Test that invalid node type raises error."""
    graph = FluentGraph(SimpleState)

    with pytest.raises(TypeError):
        graph.then("not_a_function")  # type: ignore


def test_compile_without_nodes():
    """Test that compiling without nodes raises error."""
    graph = FluentGraph(SimpleState)

    # Should raise during validation
    with pytest.raises(ValueError, match="Graph must have an entrypoint"):
        graph.compile()


def test_compile_passes_kwargs():
    """Test that compile passes kwargs to StateGraph.compile()."""

    def add_one(state: SimpleState) -> SimpleState:
        return {"value": state["value"] + 1}

    # Test that we can pass debug flag
    graph = FluentGraph(SimpleState).then(add_one).compile(debug=True)

    assert graph is not None


def test_complex_workflow():
    """Test a more complex workflow with sequential and conditional patterns."""

    def start(state: CounterState) -> CounterState:
        return {"count": state["count"] + 1}

    def double(state: CounterState) -> CounterState:
        return {"count": state["count"] * 2}

    def add_bonus(state: CounterState) -> CounterState:
        return {"count": state["count"] + 10}

    def finish(state: CounterState) -> CounterState:
        return {"count": state["count"] - 1}

    def is_valid(state: CounterState) -> bool:
        return state.get("valid", True)

    # Sequential with conditional in middle
    graph = (
        FluentGraph(CounterState)
        .then(start)
        .then(double)
        .then(enable_if(add_bonus, is_valid))
        .then(finish)
        .compile()
    )

    # Start with count=0, valid=True
    # start: 0 + 1 = 1
    # double: 1 * 2 = 2
    # add_bonus (conditional, valid=True): 2 + 10 = 12
    # finish: 12 - 1 = 11
    result = graph.invoke({"count": 0, "valid": True})
    assert result["count"] == 11

    # With valid=False, bonus is skipped and graph terminates early
    # start: 0 + 1 = 1
    # double: 1 * 2 = 2
    # add_bonus skipped (routes to END, terminating graph)
    # finish node never runs
    result = graph.invoke({"count": 0, "valid": False})
    assert result["count"] == 2  # finish node didn't run


def test_conditional_node_direct_instantiation():
    """Test using ConditionalNode directly in then()."""

    def increment(state: CounterState) -> CounterState:
        return {"count": state["count"] + 1}

    def is_valid(state: CounterState) -> bool:
        return state.get("valid", True)

    # Create ConditionalNode directly
    conditional = ConditionalNode(increment, is_valid)

    graph = FluentGraph(CounterState).then([conditional]).compile()

    result = graph.invoke({"count": 0, "valid": True})
    assert result["count"] == 1
