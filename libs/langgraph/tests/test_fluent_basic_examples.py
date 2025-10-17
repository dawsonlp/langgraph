"""Integration tests for basic fluent API examples."""

from typing_extensions import TypedDict

from langgraph.graph.fluent import FluentGraph


class SimpleState(TypedDict):
    """Simple test state."""

    value: int


class MessageState(TypedDict):
    """State for message processing."""

    message: str
    processed: bool


def test_linear_workflow():
    """Test basic linear workflow with 3+ sequential nodes."""

    def step1(state: SimpleState) -> SimpleState:
        """Add 10."""
        return {"value": state["value"] + 10}

    def step2(state: SimpleState) -> SimpleState:
        """Multiply by 2."""
        return {"value": state["value"] * 2}

    def step3(state: SimpleState) -> SimpleState:
        """Subtract 5."""
        return {"value": state["value"] - 5}

    # Build linear workflow
    graph = FluentGraph(SimpleState).then(step1).then(step2).then(step3).compile()

    # Execute: (0 + 10) * 2 - 5 = 15
    result = graph.invoke({"value": 0})
    assert result["value"] == 15

    # Verify execution order matters
    result = graph.invoke({"value": 5})
    # (5 + 10) * 2 - 5 = 25
    assert result["value"] == 25


def test_parallel_execution():
    """Test parallel execution with state merging."""

    def add_one(state: SimpleState) -> SimpleState:
        return {"value": state["value"] + 1}

    def multiply_ten(state: SimpleState) -> SimpleState:
        return {"value": state["value"] * 10}

    # Build parallel workflow
    graph = FluentGraph(SimpleState).then([add_one, multiply_ten]).compile()

    # Both nodes execute in parallel from same input
    # One produces 6, other produces 50
    # LastValue reducer means one wins (order undefined)
    result = graph.invoke({"value": 5})
    assert result["value"] in [6, 50]


def test_long_chain():
    """Test longer sequential chain (10+ nodes)."""

    def add_one(state: SimpleState) -> SimpleState:
        return {"value": state["value"] + 1}

    # Build a 10-node chain
    graph = FluentGraph(SimpleState)
    for _ in range(10):
        graph = graph.then(add_one)
    graph = graph.compile()

    # Each node adds 1, so 10 nodes = +10
    result = graph.invoke({"value": 0})
    assert result["value"] == 10


def test_state_threading():
    """Test that state is correctly threaded through nodes."""

    def set_message(state: MessageState) -> MessageState:
        return {"message": "Hello", "processed": False}

    def process_message(state: MessageState) -> MessageState:
        # Should receive message from previous node
        assert state["message"] == "Hello"
        return {"message": state["message"].upper(), "processed": True}

    def verify_message(state: MessageState) -> MessageState:
        # Should receive processed message
        assert state["message"] == "HELLO"
        assert state["processed"] is True
        return {"message": f"{state['message']}!"}

    graph = (
        FluentGraph(MessageState)
        .then(set_message)
        .then(process_message)
        .then(verify_message)
        .compile()
    )

    result = graph.invoke({"message": "", "processed": False})
    assert result["message"] == "HELLO!"
    assert result["processed"] is True
