"""Fluent API for LangGraph.

This module provides a simplified, chainable interface for building state graphs.
Instead of explicitly managing node names and edges, the fluent API infers graph
structure from the order and type of operations.

Example:
    >>> from typing_extensions import TypedDict
    >>> from langgraph.graph.fluent import FluentGraph, enable_if
    >>>
    >>> class State(TypedDict):
    ...     value: int
    ...     valid: bool
    >>>
    >>> def increment(state: State) -> State:
    ...     return {"value": state["value"] + 1}
    >>>
    >>> def double(state: State) -> State:
    ...     return {"value": state["value"] * 2}
    >>>
    >>> def is_valid(state: State) -> bool:
    ...     return state.get("valid", True)
    >>>
    >>> # Build graph with fluent API
    >>> graph = (FluentGraph(State)
    ...     .then(increment)
    ...     .then([double, enable_if(increment, is_valid)])
    ...     .compile())
"""

from langgraph.graph.fluent.extensions import enable_if
from langgraph.graph.fluent.graph import FluentGraph
from langgraph.graph.fluent.nodes import ConditionalNode

__all__ = [
    "FluentGraph",
    "ConditionalNode",
    "enable_if",
]
