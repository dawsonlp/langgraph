"""Conditional node wrapper for fluent API."""

from typing import Callable, Generic, TypeVar

StateT = TypeVar("StateT")


class ConditionalNode(Generic[StateT]):
    """Wraps a node function with an execution condition.

    A ConditionalNode represents a node that only executes when its condition
    evaluates to True. This allows for declarative conditional routing in workflows.

    Args:
        func: The node function to execute
        condition: A function that takes state and returns bool

    Example:
        >>> def process_data(state):
        ...     return {"processed": True}
        >>> def is_valid(state):
        ...     return state.get("valid", False)
        >>> conditional_node = ConditionalNode(process_data, is_valid)
    """

    def __init__(
        self, func: Callable[[StateT], StateT], condition: Callable[[StateT], bool]
    ) -> None:
        """Initialize conditional node with function and condition."""
        if not callable(func):
            raise TypeError(f"func must be callable, got {type(func).__name__}")
        if not callable(condition):
            raise TypeError(
                f"condition must be callable, got {type(condition).__name__}"
            )

        self._func = func
        self._condition = condition

    @property
    def func(self) -> Callable[[StateT], StateT]:
        """The wrapped node function."""
        return self._func

    @property
    def condition(self) -> Callable[[StateT], bool]:
        """The condition function that determines execution."""
        return self._condition

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        func_name = getattr(self._func, "__name__", str(self._func))
        cond_name = getattr(self._condition, "__name__", str(self._condition))
        return f"ConditionalNode(func={func_name}, condition={cond_name})"
