"""Unit tests for fluent API extensions."""

import pytest

from langgraph.graph.fluent.extensions import enable_if
from langgraph.graph.fluent.nodes import ConditionalNode


def test_enable_if_creates_conditional_node():
    """Test that enable_if creates a ConditionalNode."""

    def my_func(state):
        return {"value": state["value"] + 1}

    def my_condition(state):
        return state["value"] > 0

    result = enable_if(my_func, my_condition)

    assert isinstance(result, ConditionalNode)
    assert result.func is my_func
    assert result.condition is my_condition


def test_enable_if_with_lambdas():
    """Test enable_if with lambda functions."""

    def func(state):
        return {"value": state["value"] * 2}

    def condition(state):
        return state["value"] < 10

    result = enable_if(func, condition)

    assert isinstance(result, ConditionalNode)
    assert callable(result.func)
    assert callable(result.condition)


def test_enable_if_invalid_func():
    """Test that enable_if validates function parameter."""
    with pytest.raises(TypeError, match="func must be callable"):
        enable_if("not_a_function", lambda x: True)  # type: ignore


def test_enable_if_invalid_condition():
    """Test that enable_if validates condition parameter."""
    with pytest.raises(TypeError, match="condition must be callable"):
        enable_if(lambda x: x, "not_a_function")  # type: ignore


def test_enable_if_preserves_function_identity():
    """Test that enable_if preserves original function reference."""

    def original_func(state):
        return state

    def check_condition(state):
        return True

    conditional = enable_if(original_func, check_condition)

    # Should be able to retrieve original function
    assert conditional.func is original_func
    assert conditional.condition is check_condition
