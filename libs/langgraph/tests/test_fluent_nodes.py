"""Unit tests for ConditionalNode."""

import pytest

from langgraph.graph.fluent.nodes import ConditionalNode


def test_conditional_node_construction():
    """Test basic construction of ConditionalNode."""

    def my_func(state):
        return {"value": state["value"] + 1}

    def my_condition(state):
        return state["value"] > 0

    node = ConditionalNode(my_func, my_condition)

    assert node.func is my_func
    assert node.condition is my_condition


def test_conditional_node_properties_readonly():
    """Test that ConditionalNode properties are read-only."""

    def my_func(state):
        return state

    def my_condition(state):
        return True

    node = ConditionalNode(my_func, my_condition)

    # Properties should not have setters
    with pytest.raises(AttributeError):
        node.func = lambda x: x  # type: ignore

    with pytest.raises(AttributeError):
        node.condition = lambda x: False  # type: ignore


def test_conditional_node_invalid_func():
    """Test that ConditionalNode raises error for non-callable func."""
    with pytest.raises(TypeError, match="func must be callable"):
        ConditionalNode("not_a_function", lambda x: True)  # type: ignore


def test_conditional_node_invalid_condition():
    """Test that ConditionalNode raises error for non-callable condition."""
    with pytest.raises(TypeError, match="condition must be callable"):
        ConditionalNode(lambda x: x, "not_a_function")  # type: ignore


def test_conditional_node_repr():
    """Test ConditionalNode string representation."""

    def process_data(state):
        return state

    def is_valid(state):
        return True

    node = ConditionalNode(process_data, is_valid)
    repr_str = repr(node)

    assert "ConditionalNode" in repr_str
    assert "process_data" in repr_str
    assert "is_valid" in repr_str


def test_conditional_node_with_lambda():
    """Test ConditionalNode with lambda functions."""
    func = lambda state: {"value": state["value"] * 2}
    condition = lambda state: state["value"] < 10

    node = ConditionalNode(func, condition)

    assert callable(node.func)
    assert callable(node.condition)
    assert "lambda" in repr(node).lower()
