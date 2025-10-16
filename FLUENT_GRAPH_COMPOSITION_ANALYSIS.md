# FluentGraph Composition Analysis

## Executive Summary

**Current Status**: FluentGraphs are **NOT directly composable** with the current DSL implementation.

**Workarounds Available**: Yes, but manual
**Recommended Solution**: Add explicit composition support via new `.then()` overload

---

## Current Composition Limitations

### 1. Cannot Compose FluentGraphs Directly

```python
# This FAILS - FluentGraph is not callable
graph1 = FluentGraph(State).then(add_one).then(multiply_two)
graph2 = FluentGraph(State).then(increment_count)

# TypeError: Expected callable or list of callables, got <class 'FluentGraph'>
composed = FluentGraph(State).then(graph1).then(graph2)
```

**Why it fails**:
- `.then()` expects `Callable | ConditionalNode | list[...]`
- `FluentGraph` is neither callable nor a `ConditionalNode`
- The check `elif callable(node_or_nodes)` returns False for FluentGraph instances

### 2. Cannot Compose Compiled Graphs

```python
# This also FAILS - CompiledStateGraph is not callable in the expected way
graph1 = FluentGraph(State).then(add_one).compile()
graph2 = FluentGraph(State).then(increment_count).compile()

# TypeError: Expected callable or list of callables
composed = FluentGraph(State).then(graph1).then(graph2)
```

**Why it fails**:
- `CompiledStateGraph` is a complex object with `.invoke()`, `.stream()`, etc.
- It's not a simple callable that can be added as a node
- Would need wrapper logic to handle execution

---

## Current Workarounds

### Workaround 1: Wrap in Functions (Manual Composition)

```python
def workflow1(state: State) -> State:
    """Manually compose first workflow."""
    state = add_one(state)
    state = multiply_two(state)
    return state

def workflow2(state: State) -> State:
    """Second workflow."""
    return increment_count(state)

# Now compose the wrapped workflows
app = (
    FluentGraph(State)
    .then(workflow1)
    .then(workflow2)
    .compile()
)
```

**Pros**:
- Works with current implementation
- Clear and explicit
- Type-safe

**Cons**:
- Manual composition - defeats purpose of fluent API
- Loses the builder pattern elegance
- Not DRY - have to recreate the composition manually

### Workaround 2: Inline All Nodes

```python
# Just chain all nodes directly
app = (
    FluentGraph(State)
    .then(add_one)
    .then(multiply_two)
    .then(increment_count)
    .compile()
)
```

**Pros**:
- Simple and clear
- Works perfectly

**Cons**:
- Doesn't allow reusable workflow components
- Can't build libraries of reusable graph segments
- Violates DRY if same sequence used in multiple places

---

## Proposed Solutions

### Option 1: Make FluentGraph Callable (Recommended)

**Implementation**: Add `__call__` method to FluentGraph that returns a composite function.

```python
class FluentGraph(Generic[StateT]):
    def __call__(self, state: StateT) -> StateT:
        """Execute this graph as a callable node.

        Returns a function that runs the uncompiled graph's nodes in sequence.
        This enables composition without compilation.
        """
        # Create a composite function that executes all nodes
        def composite_node(input_state: StateT) -> StateT:
            # Execute each node in order, threading state through
            current_state = input_state
            for node_name in self._get_node_execution_order():
                node_func = self._graph.nodes[node_name]
                result = node_func(current_state)
                # Merge result into current state (like StateGraph does)
                current_state = {**current_state, **result}
            return current_state

        return composite_node(state)

    def _get_node_execution_order(self) -> list[str]:
        """Get topological order of nodes for execution."""
        # Implementation would traverse the graph to determine order
        pass
```

**Usage**:
```python
# Build reusable components
auth_flow = FluentGraph(State).then(authenticate).then(authorize)
process_flow = FluentGraph(State).then(validate).then(transform)

# Compose them naturally
app = (
    FluentGraph(State)
    .then(auth_flow)      # FluentGraph is now callable!
    .then(process_flow)   # Works seamlessly
    .then(save_result)
    .compile()
)
```

**Pros**:
- Natural composition within the DSL
- Maintains fluent API elegance
- Enables reusable workflow components
- No breaking changes - additive only
- Follows DRY principles

**Cons**:
- Moderate implementation complexity (need graph traversal)
- Need to handle state merging correctly
- Must handle conditionals and parallel execution

### Option 2: Add Explicit `.compose()` Method

**Implementation**: Add a method specifically for composition.

```python
class FluentGraph(Generic[StateT]):
    def compose(self, other: "FluentGraph[StateT]") -> "FluentGraph[StateT]":
        """Compose this graph with another graph.

        Args:
            other: Another FluentGraph to append to this one

        Returns:
            A new FluentGraph containing both graphs' nodes
        """
        # Merge the other graph's nodes into this graph
        # Connect this graph's last nodes to other's first nodes
        for node_name, node_func in other._graph.nodes.items():
            # Add nodes with new unique names
            new_name = self._generate_node_name(node_func)
            self._graph.add_node(new_name, node_func)

            # Connect from our last nodes
            for last_node in self._last_nodes:
                self._graph.add_edge(last_node, new_name)

        # Update tracking
        self._last_nodes = other._last_nodes.copy()
        self._node_counter += other._node_counter

        return self
```

**Usage**:
```python
auth_flow = FluentGraph(State).then(authenticate).then(authorize)
process_flow = FluentGraph(State).then(validate).then(transform)

# Explicit composition
app = (
    FluentGraph(State)
    .compose(auth_flow)
    .compose(process_flow)
    .then(save_result)
    .compile()
)
```

**Pros**:
- Explicit and clear
- Easier to implement than __call__
- No ambiguity about intent

**Cons**:
- Different syntax from `.then()` - not as fluent
- Introduces new concept/method to learn
- Doesn't feel as natural as `.then()`

### Option 3: Smart `.then()` Overload (Best of Both)

**Implementation**: Enhance `.then()` to detect and handle FluentGraph instances.

```python
def then(
    self,
    node_or_nodes: Callable | ConditionalNode | "FluentGraph[StateT]" | list[...]
) -> "FluentGraph[StateT]":
    """Add node(s) to the graph with automatic edge creation.

    Now also accepts FluentGraph instances for composition.
    """
    if isinstance(node_or_nodes, FluentGraph):
        # Compose the other graph into this one
        return self._compose_graph(node_or_nodes)
    elif isinstance(node_or_nodes, ConditionalNode):
        return self._add_parallel_nodes([node_or_nodes])
    elif callable(node_or_nodes) and not isinstance(node_or_nodes, list):
        return self._add_single_node(node_or_nodes)
    elif isinstance(node_or_nodes, list):
        # Check for FluentGraphs in list
        processed_nodes = []
        for node in node_or_nodes:
            if isinstance(node, FluentGraph):
                # Convert FluentGraph to callable
                processed_nodes.append(node.to_callable())
            else:
                processed_nodes.append(node)
        return self._add_parallel_nodes(processed_nodes)
    else:
        raise TypeError(f"Expected callable or FluentGraph, got {type(node_or_nodes)}")

def _compose_graph(self, other: "FluentGraph[StateT]") -> "FluentGraph[StateT]":
    """Compose another FluentGraph into this one."""
    # Implementation similar to Option 2
    pass

def to_callable(self) -> Callable[[StateT], StateT]:
    """Convert this FluentGraph to a single callable node."""
    # Implementation similar to Option 1's __call__
    pass
```

**Usage**:
```python
auth_flow = FluentGraph(State).then(authenticate).then(authorize)
process_flow = FluentGraph(State).then(validate).then(transform)

# Natural composition - looks like any other .then() call
app = (
    FluentGraph(State)
    .then(auth_flow)      # Automatically handles FluentGraph
    .then(process_flow)   # Seamless!
    .then(save_result)
    .compile()
)

# Also works in parallel
app = (
    FluentGraph(State)
    .then([auth_flow, rate_limit_check])  # Mix FluentGraphs and callables
    .then(process_flow)
    .compile()
)
```

**Pros**:
- Most natural and fluent
- Consistent with existing API
- Supports both sequential and parallel composition
- No new methods to learn
- Backwards compatible

**Cons**:
- Most complex implementation
- Need to handle both graph merging and callable conversion
- Type hints become more complex

---

## Recommendation

**Implement Option 3: Smart `.then()` Overload**

### Rationale:
1. **DRY Principle**: Enables true reusability of workflow components
2. **KISS Principle**: No new concepts - just enhances existing `.then()`
3. **Natural API**: Composition feels identical to adding any other node
4. **Backwards Compatible**: Existing code continues to work
5. **Composability**: Achieves the goal of composable fluent graphs

### Implementation Priority:
1. Add `isinstance(node_or_nodes, FluentGraph)` check to `.then()`
2. Implement `_compose_graph()` for graph merging
3. Implement `to_callable()` for converting FluentGraph to single node
4. Add comprehensive tests for all composition scenarios
5. Document composition patterns and best practices

### Estimated Effort:
- **Core Implementation**: 2-3 hours
- **Testing**: 1-2 hours
- **Documentation**: 1 hour
- **Total**: 4-6 hours

---

## Testing Strategy

### Test Cases Needed:

1. **Sequential Composition**
   ```python
   graph1.then(graph2).then(graph3)
   ```

2. **Parallel Composition**
   ```python
   graph.then([subgraph1, subgraph2, func])
   ```

3. **Nested Composition**
   ```python
   outer = graph1.then(graph2)
   final = graph0.then(outer).then(graph3)
   ```

4. **Conditional Composition**
   ```python
   graph.then([subgraph1.if(condition), func])
   ```

5. **State Threading**
   - Verify state flows correctly through composed graphs
   - Test state merging behavior

6. **Node Naming**
   - Ensure unique node names across composed graphs
   - No collisions in large compositions

---

## Example Use Cases Enabled

### 1. Authentication + Authorization Pipeline
```python
auth_pipeline = (
    FluentGraph(State)
    .then(check_token)
    .then(validate_token)
    .then(load_user)
)

# Reuse in multiple workflows
api_workflow = FluentGraph(State).then(auth_pipeline).then(handle_api_request)
web_workflow = FluentGraph(State).then(auth_pipeline).then(handle_web_request)
```

### 2. Data Processing Stages
```python
ingestion = FluentGraph(State).then(fetch_data).then(parse_data)
transformation = FluentGraph(State).then(validate).then(transform).then(enrich)
persistence = FluentGraph(State).then(save_to_db).then(update_cache)

# Compose full pipeline
etl_pipeline = (
    FluentGraph(State)
    .then(ingestion)
    .then(transformation)
    .then(persistence)
    .compile()
)
```

### 3. Conditional Workflow Composition
```python
premium_features = FluentGraph(State).then(feature1).then(feature2)
basic_features = FluentGraph(State).then(feature1)

workflow = (
    FluentGraph(State)
    .then(authenticate)
    .then([
        premium_features.if(is_premium_user),
        basic_features.if(is_basic_user)
    ])
    .then(finalize)
    .compile()
)
```

---

## Conclusion

The current FluentGraph implementation is **not composable** by design, but this can be easily remedied by enhancing the `.then()` method to accept FluentGraph instances. This change would:

1. Enable true reusability of workflow components (DRY)
2. Maintain API simplicity (KISS)
3. Provide natural composition syntax
4. Support both sequential and parallel composition
5. Be fully backwards compatible

**Status**: Ready to implement
**Recommendation**: Proceed with Option 3 (Smart `.then()` Overload)
