"""Fluent API wrapper for StateGraph."""

from typing import Any, Callable, Generic, TypeVar

from langgraph.constants import END, START
from langgraph.graph.fluent.nodes import ConditionalNode
from langgraph.graph.state import CompiledStateGraph, StateGraph

StateT = TypeVar("StateT")
ContextT = TypeVar("ContextT")


class FluentGraph(Generic[StateT]):
    """A fluent/chainable API wrapper for StateGraph.

    Provides a simplified, declarative way to build state graphs using method chaining.
    Instead of explicitly naming nodes and edges, the fluent API infers structure from
    the order of .then() calls.

    Args:
        state_schema: The schema class that defines the state

    Example:
        >>> from typing_extensions import TypedDict
        >>> class State(TypedDict):
        ...     value: int
        >>> def add_one(state: State) -> State:
        ...     return {"value": state["value"] + 1}
        >>> def multiply_two(state: State) -> State:
        ...     return {"value": state["value"] * 2}
        >>> graph = (FluentGraph(State)
        ...     .then(add_one)
        ...     .then(multiply_two)
        ...     .compile())
    """

    def __init__(self, state_schema: type[StateT]) -> None:
        """Initialize fluent graph with state schema.

        Args:
            state_schema: The schema class that defines the state
        """
        self._graph = StateGraph(state_schema)
        self._state_schema = state_schema
        self._last_nodes: list[str] = []
        self._node_counter = 0
        self._has_start = False

    def then(
        self, node_or_nodes: Callable | ConditionalNode | list[Callable | ConditionalNode]
    ) -> "FluentGraph[StateT]":
        """Add node(s) to the graph with automatic edge creation.

        Args:
            node_or_nodes: Either:
                - A single callable (sequential execution)
                - A single ConditionalNode (conditional execution)
                - A list of callables/ConditionalNodes (parallel execution)

        Returns:
            Self for method chaining

        Example:
            >>> # Sequential
            >>> graph.then(node1).then(node2)
            >>> # Parallel
            >>> graph.then([node1, node2])
            >>> # Conditional
            >>> from langgraph.graph.fluent import enable_if
            >>> graph.then(enable_if(node1, condition))
            >>> graph.then([enable_if(node1, condition), node2])
        """
        if isinstance(node_or_nodes, ConditionalNode):
            # Single conditional node - wrap in list for consistent handling
            return self._add_parallel_nodes([node_or_nodes])
        elif callable(node_or_nodes) and not isinstance(node_or_nodes, list):
            # Single node - sequential execution
            return self._add_single_node(node_or_nodes)
        elif isinstance(node_or_nodes, list):
            # Multiple nodes - parallel execution (may include conditionals)
            return self._add_parallel_nodes(node_or_nodes)
        else:
            raise TypeError(
                f"Expected callable or list of callables, got {type(node_or_nodes)}"
            )

    def compile(self, **kwargs: Any) -> CompiledStateGraph:
        """Compile the graph to a CompiledStateGraph.

        Connects the last node(s) to END and compiles the underlying StateGraph.
        All kwargs are passed through to StateGraph.compile().

        Args:
            **kwargs: Additional arguments passed to StateGraph.compile()
                (checkpointer, interrupt_before, interrupt_after, etc.)

        Returns:
            Compiled graph ready for execution

        Example:
            >>> graph = FluentGraph(State).then(node1).then(node2).compile()
            >>> result = graph.invoke({"value": 0})
        """
        # Connect last nodes to END
        for node_name in self._last_nodes:
            self._graph.add_edge(node_name, END)

        # Compile and return
        return self._graph.compile(**kwargs)

    def _generate_node_name(self, func: Callable) -> str:
        """Generate unique node name from function.

        Args:
            func: The function to generate a name for

        Returns:
            Unique node name
        """
        base_name = getattr(func, "__name__", func.__class__.__name__)
        self._node_counter += 1
        return f"{base_name}_{self._node_counter}"

    def _add_single_node(self, node: Callable) -> "FluentGraph[StateT]":
        """Add a single node with sequential execution.

        Args:
            node: The node function to add

        Returns:
            Self for chaining
        """
        node_name = self._generate_node_name(node)
        self._graph.add_node(node_name, node)

        # Connect from last nodes or START
        if not self._has_start:
            self._graph.add_edge(START, node_name)
            self._has_start = True
        else:
            for last_node in self._last_nodes:
                self._graph.add_edge(last_node, node_name)

        # Update last nodes
        self._last_nodes = [node_name]
        return self

    def _add_parallel_nodes(
        self, nodes: list[Callable | ConditionalNode]
    ) -> "FluentGraph[StateT]":
        """Add multiple nodes for parallel execution.

        Args:
            nodes: List of callables or ConditionalNodes

        Returns:
            Self for chaining
        """
        if not nodes:
            raise ValueError("Cannot add empty list of nodes")

        new_last_nodes = []

        for node in nodes:
            if isinstance(node, ConditionalNode):
                # Conditional node - add with conditional edge
                node_name = self._add_conditional_node(node)
            else:
                # Regular node - add normally
                node_name = self._generate_node_name(node)
                self._graph.add_node(node_name, node)

                # Connect from last nodes or START
                if not self._has_start:
                    self._graph.add_edge(START, node_name)
                    self._has_start = True
                else:
                    for last_node in self._last_nodes:
                        self._graph.add_edge(last_node, node_name)

            new_last_nodes.append(node_name)

        # Update last nodes to all parallel nodes
        self._last_nodes = new_last_nodes
        return self

    def _add_conditional_node(self, node: ConditionalNode) -> str:
        """Add a conditional node with routing logic.

        Args:
            node: The ConditionalNode to add

        Returns:
            The generated node name
        """
        node_name = self._generate_node_name(node.func)
        self._graph.add_node(node_name, node.func)

        # Create routing function with unique name to avoid conflicts
        # when multiple conditionals branch from same source
        route_func_name = f"route_to_{node_name}"

        def route_condition(state: StateT) -> str:
            """Route to node if condition is True, else skip."""
            return node_name if node.condition(state) else END

        # Set the function name for debugging/introspection
        route_condition.__name__ = route_func_name

        # Connect with conditional edge
        if not self._has_start:
            # Conditional from START
            self._graph.set_conditional_entry_point(route_condition)
            self._has_start = True
        else:
            # Conditional from last nodes
            for last_node in self._last_nodes:
                self._graph.add_conditional_edges(last_node, route_condition)

        return node_name
