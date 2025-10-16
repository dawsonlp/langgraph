"""Fluent API wrapper for StateGraph."""

from typing import Any, Callable, Generic, TypeVar, Union

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
        # StateGraph has bounded type requirements, but we accept any state schema
        # at runtime. Type system limitation, not a safety issue.
        self._graph = StateGraph(state_schema)  # type: ignore[type-var]
        self._state_schema = state_schema
        self._last_nodes: list[str] = []
        self._node_counter = 0
        self._has_start = False

    def then(
        self,
        node_or_nodes: Union[
            Callable,
            ConditionalNode,
            "FluentGraph[StateT]",
            list[Union[Callable, ConditionalNode, "FluentGraph[StateT]"]],
        ],
    ) -> "FluentGraph[StateT]":
        """Add node(s) to the graph with automatic edge creation.

        Args:
            node_or_nodes: Either:
                - A single callable (sequential execution)
                - A single ConditionalNode (conditional execution)
                - A FluentGraph instance (composition)
                - A list of callables/ConditionalNodes/FluentGraphs (parallel)

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
            >>> # Composition
            >>> subgraph = FluentGraph(State).then(node1).then(node2)
            >>> graph.then(subgraph)
            >>> # Mixed
            >>> graph.then([subgraph1, node1, enable_if(node2, condition)])
        """
        # Check FluentGraph first (before callable check)
        if isinstance(node_or_nodes, FluentGraph):
            return self._compose_graph(node_or_nodes)
        elif isinstance(node_or_nodes, ConditionalNode):
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
        self,
        nodes: list[Union[Callable, ConditionalNode, "FluentGraph[StateT]"]],
    ) -> "FluentGraph[StateT]":
        """Add multiple nodes for parallel execution.

        Args:
            nodes: List of callables, ConditionalNodes, or FluentGraphs

        Returns:
            Self for chaining
        """
        if not nodes:
            raise ValueError("Cannot add empty list of nodes")

        new_last_nodes = []

        for node in nodes:
            if isinstance(node, FluentGraph):
                # Convert FluentGraph to callable and add as single node
                callable_node = node.to_callable()
                node_name = self._generate_node_name(callable_node)
                self._graph.add_node(node_name, callable_node)

                # Connect from last nodes or START
                if not self._has_start:
                    self._graph.add_edge(START, node_name)
                    self._has_start = True
                else:
                    for last_node in self._last_nodes:
                        self._graph.add_edge(last_node, node_name)

                new_last_nodes.append(node_name)
            elif isinstance(node, ConditionalNode):
                # Conditional node - add with conditional edge
                node_name = self._add_conditional_node(node)
                new_last_nodes.append(node_name)
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
        self._graph.add_node(node_name, node.func)  # type: ignore[arg-type]

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

    def _compose_graph(self, other: "FluentGraph[StateT]") -> "FluentGraph[StateT]":
        """Compose another FluentGraph into this one.

        Merges the other graph's nodes and edges into this graph,
        connecting them after this graph's current last nodes.

        Args:
            other: The FluentGraph to compose into this one

        Returns:
            Self for chaining
        """
        # Handle empty graph composition - nothing to do
        if not other._graph.nodes or (len(other._graph.nodes) == 1 and START in other._graph.nodes):
            return self

        # Track mapping of old names to new names for edge recreation
        name_mapping: dict[str, str] = {}
        other_first_nodes: list[str] = []

        # Get nodes from other graph (excluding START which is implicit)
        for old_name in other._graph.nodes:
            if old_name == START:
                continue

            # Get the node spec and extract the actual runnable
            node_spec = other._graph.nodes[old_name]
            # Extract the runnable from the node spec (StateNodeSpec has .runnable attribute)
            if hasattr(node_spec, "runnable"):
                node_func = node_spec.runnable  # type: ignore[attr-defined]
            else:
                # Fallback for other node types
                node_func = node_spec  # type: ignore[assignment]

            # Generate unique name in this graph based on old name
            base_name = old_name.rsplit("_", 1)[0] if "_" in old_name else old_name
            self._node_counter += 1
            new_name = f"{base_name}_{self._node_counter}"
            name_mapping[old_name] = new_name

            # Add node to this graph (pass the runnable directly)
            self._graph.add_node(new_name, node_func)  # type: ignore[arg-type]

        # Identify first nodes of other graph (nodes that connect from START)
        for start_node, end_node in other._graph.edges:
            if start_node == START:
                if end_node in name_mapping:
                    other_first_nodes.append(name_mapping[end_node])

        # If other graph has no START edges but has nodes, use last_nodes tracking
        if not other_first_nodes and name_mapping:
            other_first_nodes = [
                name_mapping[n] for n in other._last_nodes if n in name_mapping
            ]

        # If still no first nodes, use any nodes that don't have predecessors
        if not other_first_nodes and name_mapping:
            # Find nodes without incoming edges (excluding START)
            all_targets = {
                name_mapping[end]
                for start, end in other._graph.edges
                if start != START and end in name_mapping
            }
            other_first_nodes = [
                new_name for new_name in name_mapping.values() if new_name not in all_targets
            ]

        # Connect our last nodes to other's first nodes
        if not self._has_start:
            # This graph has no nodes yet - connect START to other's first nodes
            for first_node in other_first_nodes:
                self._graph.add_edge(START, first_node)
            self._has_start = True
        else:
            # Connect our last nodes to other's first nodes
            for last_node in self._last_nodes:
                for first_node in other_first_nodes:
                    self._graph.add_edge(last_node, first_node)

        # Copy edges from other graph (excluding START edges)
        for start_node, end_node in other._graph.edges:
            if start_node == START:
                continue  # Already handled above
            if start_node in name_mapping and end_node in name_mapping:
                self._graph.add_edge(name_mapping[start_node], name_mapping[end_node])

        # Note: Conditional edges are not copied in composition
        # They would need special handling and deep StateGraph API access
        # For now, use to_callable() for graphs with conditional edges in parallel

        # Update our last nodes to other's last nodes
        self._last_nodes = [name_mapping[n] for n in other._last_nodes if n in name_mapping]

        # Ensure node counter stays unique
        self._node_counter = max(self._node_counter, other._node_counter) + 1

        return self

    def to_callable(self) -> Callable[[StateT], StateT]:
        """Convert this FluentGraph to a single callable node.

        Returns a function that executes all nodes in this graph
        and returns the final state. Useful for treating a subgraph
        as a single node in a larger graph.

        Returns:
            Callable that takes state and returns updated state

        Example:
            >>> subgraph = FluentGraph(State).then(node1).then(node2)
            >>> # Use subgraph as a callable in another graph
            >>> main_graph = FluentGraph(State).then(subgraph.to_callable())
        """
        # Compile this graph to create executable version
        compiled = self.compile()

        def composite_node(state: StateT) -> StateT:
            """Execute the composed graph."""
            # Invoke returns the final state, cast to expected type
            return compiled.invoke(state)  # type: ignore[return-value]

        # Set useful name for debugging
        composite_node.__name__ = f"composite_{len(self._graph.nodes)}_nodes"

        return composite_node
