"""Extension functions for creating conditional nodes."""

from typing import Callable, TypeVar

from langgraph.graph.fluent.nodes import ConditionalNode

StateT = TypeVar("StateT")


def enable_if(
    func: Callable[[StateT], StateT], condition: Callable[[StateT], bool]
) -> ConditionalNode[StateT]:
    """Create a conditional node from a function and condition.

    This function wraps a node function with a condition, creating a ConditionalNode
    that only executes when the condition evaluates to True.

    Args:
        func: The node function to execute conditionally
        condition: A function that takes state and returns bool

    Returns:
        ConditionalNode wrapping the function with the condition

    Example:
        >>> def process_order(state):
        ...     return {"processed": True}
        >>> def has_items(state):
        ...     return len(state.get("items", [])) > 0
        >>> conditional = enable_if(process_order, has_items)
    """
    return ConditionalNode(func, condition)
