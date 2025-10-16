# FluentGraph Composition - Implementation Checklist

**Feature**: Add FluentGraph-to-FluentGraph composition support via smart `.then()` overload
**Approach**: Option 3 from FLUENT_GRAPH_COMPOSITION_ANALYSIS.md
**Principles**: DRY, KISS, Python Best Practices
**Estimated Effort**: 4-6 hours

---

## Phase 1: Core FluentGraph Enhancements

### 1.1 Update `.then()` Method Type Signature
**File**: `libs/langgraph/langgraph/graph/fluent/graph.py`

- [ ] Add `FluentGraph[StateT]` to type union in `.then()` signature
  ```python
  def then(
      self,
      node_or_nodes: (
          Callable
          | ConditionalNode
          | "FluentGraph[StateT]"  # NEW
          | list[Callable | ConditionalNode | "FluentGraph[StateT]"]  # UPDATED
      ),
  ) -> "FluentGraph[StateT]":
  ```

- [ ] Update docstring to document FluentGraph composition
  ```python
  """Add node(s) to the graph with automatic edge creation.

  Args:
      node_or_nodes: Either:
          - A single callable (sequential execution)
          - A single ConditionalNode (conditional execution)
          - A FluentGraph instance (composition)  # NEW
          - A list of callables/ConditionalNodes/FluentGraphs (parallel)  # UPDATED
  ```

### 1.2 Add FluentGraph Detection to `.then()` Logic
**File**: `libs/langgraph/langgraph/graph/fluent/graph.py`

- [ ] Add `isinstance` check for FluentGraph **before** callable check
  ```python
  def then(self, node_or_nodes):
      if isinstance(node_or_nodes, FluentGraph):  # NEW - check first
          return self._compose_graph(node_or_nodes)
      elif isinstance(node_or_nodes, ConditionalNode):
          return self._add_parallel_nodes([node_or_nodes])
      elif callable(node_or_nodes) and not isinstance(node_or_nodes, list):
          return self._add_single_node(node_or_nodes)
      elif isinstance(node_or_nodes, list):
          return self._add_parallel_nodes(node_or_nodes)  # handles FluentGraph in list
      else:
          raise TypeError(...)
  ```

**Why check FluentGraph first?** FluentGraph instances might implement `__call__` later for other purposes. Explicit type check ensures correct handling.

---

## Phase 2: Graph Composition Implementation

### 2.1 Implement `_compose_graph()` Method
**File**: `libs/langgraph/langgraph/graph/fluent/graph.py`

**Purpose**: Merge another FluentGraph's nodes into this graph.

- [ ] Create `_compose_graph(self, other: "FluentGraph[StateT]") -> "FluentGraph[StateT]"`
- [ ] Verify state schema compatibility (same type)
- [ ] Copy all nodes from `other._graph` into `self._graph` with unique names
- [ ] Connect `self._last_nodes` to `other`'s first nodes (or START)
- [ ] Update `self._last_nodes` to `other._last_nodes`
- [ ] Increment `self._node_counter` to maintain uniqueness
- [ ] Return `self` for chaining

**Implementation Pattern** (DRY):
```python
def _compose_graph(self, other: "FluentGraph[StateT]") -> "FluentGraph[StateT]":
    """Compose another FluentGraph into this one.

    Merges the other graph's nodes and edges into this graph,
    connecting them after this graph's current last nodes.
    """
    # Get nodes from other graph in execution order
    other_nodes = list(other._graph.nodes.items())

    # Track mapping of old names to new names for edge recreation
    name_mapping = {}
    new_first_nodes = []

    for old_name, node_func in other_nodes:
        # Generate unique name in this graph
        new_name = self._generate_node_name(node_func)
        name_mapping[old_name] = new_name

        # Add node to this graph
        self._graph.add_node(new_name, node_func)

        # Track first nodes of other graph (no incoming edges from other graph)
        # These connect to our last nodes
        # ... implementation here

    # Connect our last nodes to other's first nodes
    # ... implementation here

    # Update tracking
    self._last_nodes = [name_mapping[n] for n in other._last_nodes]
    self._node_counter = max(self._node_counter, other._node_counter) + 1

    return self
```

**Key Considerations**:
- Preserve node execution order from `other` graph
- Handle START node in `other` graph (don't add it)
- Map edge connections using name mapping
- Handle conditional edges properly

### 2.2 Handle FluentGraph in Parallel Lists
**File**: `libs/langgraph/langgraph/graph/fluent/graph.py`

- [ ] Update `_add_parallel_nodes()` to detect FluentGraph instances
- [ ] Convert FluentGraph to callable via `to_callable()` (see Phase 3)
- [ ] Process as regular node

```python
def _add_parallel_nodes(self, nodes: list) -> "FluentGraph[StateT]":
    if not nodes:
        raise ValueError("Cannot add empty list of nodes")

    new_last_nodes = []

    for node in nodes:
        if isinstance(node, FluentGraph):  # NEW
            # Convert to callable and add as single node
            callable_node = node.to_callable()
            node_name = self._generate_node_name(callable_node)
            self._graph.add_node(node_name, callable_node)
            # ... connect edges ...
        elif isinstance(node, ConditionalNode):
            # ... existing logic ...
        else:
            # ... existing logic ...

    # ... rest of method ...
```

---

## Phase 3: FluentGraph to Callable Conversion

### 3.1 Implement `to_callable()` Method
**File**: `libs/langgraph/langgraph/graph/fluent/graph.py`

**Purpose**: Convert FluentGraph to a single callable that executes all its nodes.

- [ ] Create `to_callable(self) -> Callable[[StateT], StateT]`
- [ ] Compile the graph internally (without END connections)
- [ ] Return a function that invokes the compiled graph
- [ ] Handle state threading correctly

```python
def to_callable(self) -> Callable[[StateT], StateT]:
    """Convert this FluentGraph to a single callable node.

    Returns a function that executes all nodes in this graph
    and returns the final state. Useful for treating a subgraph
    as a single node in a larger graph.

    Returns:
        Callable that takes state and returns updated state
    """
    # Create a temporary compiled version
    # Connect last nodes to END for compilation
    temp_graph = StateGraph(self._state_schema)

    # Copy all nodes
    for node_name, node_func in self._graph.nodes.items():
        temp_graph.add_node(node_name, node_func)

    # Copy all edges
    for start, end in self._graph.edges:
        temp_graph.add_edge(start, end)

    # Copy conditional edges
    # ... handle conditional edges ...

    # Connect to END
    for node_name in self._last_nodes:
        temp_graph.add_edge(node_name, END)

    # Compile
    compiled = temp_graph.compile()

    # Return wrapper function
    def composite_node(state: StateT) -> StateT:
        """Execute the composed graph."""
        result = compiled.invoke(state)
        return result

    # Set useful name for debugging
    composite_node.__name__ = f"composite_{id(self)}"

    return composite_node
```

**Alternative Simpler Implementation** (KISS):
```python
def to_callable(self) -> Callable[[StateT], StateT]:
    """Convert to callable by compiling and wrapping invoke."""
    # Temporarily compile this graph
    compiled = self.compile()

    def composite_node(state: StateT) -> StateT:
        return compiled.invoke(state)

    composite_node.__name__ = f"composite_{len(self._graph.nodes)}_nodes"
    return composite_node
```

**Decision Point**: Choose simpler implementation unless there's a specific need for the complex version.

---

## Phase 4: Testing

### 4.1 Unit Tests for Composition Logic
**File**: `libs/langgraph/tests/test_fluent_composition.py` (update existing)

- [ ] Remove negative tests (they should now pass)
- [ ] Test sequential composition
  ```python
  def test_sequential_composition():
      graph1 = FluentGraph(State).then(add_one)
      graph2 = FluentGraph(State).then(multiply_two)

      app = FluentGraph(State).then(graph1).then(graph2).compile()
      result = app.invoke({"value": 5})
      assert result["value"] == 12  # (5 + 1) * 2
  ```

- [ ] Test parallel composition
  ```python
  def test_parallel_composition():
      graph1 = FluentGraph(State).then(add_one)
      graph2 = FluentGraph(State).then(multiply_two)

      app = FluentGraph(State).then([graph1, graph2]).compile()
      # Both should execute in parallel
  ```

- [ ] Test nested composition
  ```python
  def test_nested_composition():
      inner = FluentGraph(State).then(add_one).then(multiply_two)
      outer = FluentGraph(State).then(inner).then(add_one)

      app = FluentGraph(State).then(outer).compile()
  ```

- [ ] Test mixed composition (FluentGraph + functions)
  ```python
  def test_mixed_composition():
      subgraph = FluentGraph(State).then(add_one)

      app = (
          FluentGraph(State)
          .then(subgraph)
          .then(multiply_two)  # regular function
          .compile()
      )
  ```

- [ ] Test state threading through composition
  ```python
  def test_state_threading():
      # Verify state updates flow correctly through composed graphs
  ```

- [ ] Test node name uniqueness
  ```python
  def test_node_name_uniqueness_across_composition():
      # Same function used in multiple subgraphs should get unique names
  ```

### 4.2 Integration Tests
**File**: `libs/langgraph/tests/test_fluent_composition.py`

- [ ] Test realistic workflow composition
  ```python
  def test_auth_pipeline_composition():
      auth = FluentGraph(State).then(check_token).then(validate)
      process = FluentGraph(State).then(transform).then(save)

      app = FluentGraph(State).then(auth).then(process).compile()
      # Test full execution
  ```

- [ ] Test with conditionals in composed graphs
  ```python
  def test_conditional_in_composed_graph():
      subgraph = FluentGraph(State).then(enable_if(process, condition))
      app = FluentGraph(State).then(subgraph).compile()
  ```

### 4.3 Edge Cases
**File**: `libs/langgraph/tests/test_fluent_composition.py`

- [ ] Empty FluentGraph composition
- [ ] Single-node FluentGraph composition
- [ ] Deeply nested composition (5+ levels)
- [ ] Large graph composition (20+ nodes total)
- [ ] Self-composition (graph1.then(graph1)) - should work but use different node names

---

## Phase 5: Documentation

### 5.1 Update FluentGraph Docstring
**File**: `libs/langgraph/langgraph/graph/fluent/graph.py`

- [ ] Add composition example to class docstring
  ```python
  Example:
      >>> # Reusable workflow components
      >>> auth = FluentGraph(State).then(authenticate).then(authorize)
      >>> process = FluentGraph(State).then(validate).then(transform)
      >>>
      >>> # Compose them naturally
      >>> app = (
      ...     FluentGraph(State)
      ...     .then(auth)      # Compose subgraph
      ...     .then(process)   # Compose another
      ...     .then(save)      # Add function
      ...     .compile()
      ... )
  ```

### 5.2 Update README
**File**: `libs/langgraph/langgraph/graph/fluent/README.md`

- [ ] Add "Composition" section with examples
- [ ] Show reusable workflow patterns
- [ ] Document best practices for composition

### 5.3 Add Composition Examples
**File**: Create `libs/langgraph/langgraph/graph/fluent/examples/composition.py` (if examples dir exists)

- [ ] Auth + authorization pipeline example
- [ ] ETL pipeline composition example
- [ ] Conditional workflow composition example

---

## Phase 6: Code Quality

### 6.1 Type Checking
- [ ] Run `uv run mypy langgraph/graph/fluent/`
- [ ] Fix any new type errors
- [ ] Ensure generic types work correctly with composition

### 6.2 Linting
- [ ] Run `uv run ruff check langgraph/graph/fluent/`
- [ ] Run `uv run ruff format langgraph/graph/fluent/`
- [ ] Verify all checks pass

### 6.3 Test Coverage
- [ ] Run `uv run pytest tests/test_fluent*.py --cov=langgraph.graph.fluent --cov-report=term-missing`
- [ ] Ensure coverage remains >90%
- [ ] Add tests for any uncovered branches

### 6.4 Performance Check
- [ ] Benchmark composition overhead
- [ ] Ensure <5% overhead vs manual composition
- [ ] Profile `to_callable()` and `_compose_graph()` if needed

---

## Phase 7: Integration & Git

### 7.1 Run Full Test Suite
- [ ] Run `uv run pytest libs/langgraph/tests/` (all tests)
- [ ] Verify no regressions in existing functionality
- [ ] Ensure all 39+ tests pass (35 existing + 4+ new)

### 7.2 Git Workflow
- [ ] Commit with conventional commit message:
  ```
  feat(fluent): add FluentGraph composition support

  Implements Option 3 from composition analysis: Smart .then() overload.

  - Enhances .then() to accept FluentGraph instances
  - Adds _compose_graph() for graph merging
  - Adds to_callable() for subgraph conversion
  - Supports sequential, parallel, and nested composition
  - Maintains full backwards compatibility

  Enables reusable workflow components following DRY principle.
  99% test coverage maintained.
  ```

- [ ] Push to origin: `git push origin dawsonlp/fluent-langgraph-api`

---

## Success Criteria

**Must Have**:
- [ ] Can compose FluentGraphs sequentially: `graph.then(subgraph1).then(subgraph2)`
- [ ] Can compose in parallel: `graph.then([subgraph1, subgraph2])`
- [ ] Can mix FluentGraphs and functions: `graph.then(subgraph).then(func)`
- [ ] State threads correctly through composed graphs
- [ ] All tests pass (existing + new)
- [ ] Test coverage >90%
- [ ] No type errors
- [ ] No linting issues
- [ ] Fully backwards compatible

**Nice to Have**:
- [ ] Nested composition works (graph of graphs of graphs)
- [ ] Conditional composition: `enable_if(subgraph, condition)`
- [ ] Performance <5% overhead
- [ ] Comprehensive documentation with examples

---

## Implementation Notes

### DRY Principles Applied
- Single `_compose_graph()` method handles all graph merging logic
- `to_callable()` reuses existing compilation logic
- Node name generation reuses `_generate_node_name()`
- No duplication of edge creation logic

### KISS Principles Applied
- Smart `.then()` overload - no new methods to learn
- Leverage existing StateGraph compilation for `to_callable()`
- Minimal new code - enhance existing methods
- Clear separation: composition vs callable conversion

### Python Best Practices
- Type hints for all public APIs
- Docstrings with examples
- Explicit over implicit (type checks before operations)
- Single responsibility (each method has one job)
- Immutability where possible (return new state, don't modify)

---

## Estimated Timeline

| Phase | Time | Cumulative |
|-------|------|------------|
| Phase 1-2: Core Implementation | 2-3 hours | 2-3 hours |
| Phase 3: to_callable() | 30-60 min | 3-4 hours |
| Phase 4: Testing | 1-2 hours | 4-6 hours |
| Phase 5: Documentation | 30-60 min | 5-7 hours |
| Phase 6-7: Quality & Git | 30 min | 5-7 hours |

**Total: 5-7 hours** (slightly higher than initial estimate due to thorough testing)

---

## Quick Start Commands

```bash
# Navigate to package
cd /Users/ldawson/repos/langgraph-fork/libs/langgraph

# Run composition tests only
uv run pytest tests/test_fluent_composition.py -v

# Run all fluent tests
uv run pytest tests/test_fluent*.py -v

# Type check
uv run mypy langgraph/graph/fluent/

# Lint
uv run ruff check langgraph/graph/fluent/
uv run ruff format langgraph/graph/fluent/

# Coverage
uv run pytest tests/test_fluent*.py --cov=langgraph.graph.fluent --cov-report=term-missing

# Commit when ready
cd /Users/ldawson/repos/langgraph-fork
git add .
git commit -m "feat(fluent): add FluentGraph composition support"
git push origin dawsonlp/fluent-langgraph-api
```

---

**Status**: Ready to implement
**Last Updated**: 2025-10-16
**Implements**: Option 3 from FLUENT_GRAPH_COMPOSITION_ANALYSIS.md
