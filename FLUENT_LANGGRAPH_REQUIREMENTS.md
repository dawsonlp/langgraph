# Fluent LangGraph API - Requirements & Design Document

## Executive Summary

Create a fluent, chainable API wrapper for LangGraph that dramatically simplifies workflow definition while maintaining full compatibility with the existing LangGraph infrastructure.

## Motivation

### Current LangGraph API Problems

**Example of current verbose approach:**
```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(MyState)
graph.add_node("step1", step1_func)
graph.add_node("step2", step2_func)
graph.add_node("step3", step3_func)
graph.add_edge(START, "step1")
graph.add_edge("step1", "step2")
graph.add_edge("step2", "step3")
graph.add_edge("step3", END)
app = graph.compile()
```

**Issues:**
1. **Excessive boilerplate** - Every node and edge must be explicitly added
2. **String-based connections** - Easy to make typos, no IDE support
3. **Imperative style** - Building graph feels like manual assembly
4. **No type safety** - Node names are just strings
5. **Verbose for simple cases** - Linear workflows require tons of code
6. **Poor readability** - Hard to visualize flow from code

### Proposed Solution

**Same workflow with fluent API:**
```python
from langgraph_fluent import FluentGraph

app = (
    FluentGraph(MyState)
    .then(step1_func)
    .then(step2_func)
    .then(step3_func)
    .compile()
)
```

## Core Design Principles

### 1. Minimal Primitives
Only two core operations:
- **`.then()`** - Sequential execution
- **`.if()`** - Conditional execution

Everything else emerges from composing these primitives.

### 2. Natural Language Flow
Code should read like you would explain it:
```python
workflow.then(fetch_data).then(process).then(save)
```

### 3. Type Inference
Leverage Python's ability to handle different argument types:
- `then(single_node)` - Execute one node
- `then([node1, node2, node3])` - Execute multiple nodes (parallel)
- `then([node1.if(cond), node2])` - Mix conditional and unconditional

### 4. Composability
Everything returns a chainable object, enabling composition and reuse.

## API Specification

### Core API

#### FluentGraph Class

```python
class FluentGraph:
    """Fluent wrapper around LangGraph StateGraph."""

    def __init__(self, state_schema: Type[TypedDict]):
        """Initialize with state schema.

        Args:
            state_schema: TypedDict defining workflow state
        """

    def then(self, node_or_nodes: Union[Callable, List[Union[Callable, ConditionalNode]]]) -> 'FluentGraph':
        """Add next step(s) in workflow.

        Args:
            node_or_nodes: Single node, or list of nodes (executed in parallel)

        Returns:
            Self for chaining

        Examples:
            .then(single_node)           # Sequential
            .then([node1, node2])        # Parallel
            .then([node1.if(cond)])      # Conditional
        """

    def compile(self, **kwargs) -> CompiledStateGraph:
        """Compile to executable LangGraph.

        Returns:
            Standard LangGraph CompiledStateGraph
        """
```

#### ConditionalNode Class

```python
class ConditionalNode:
    """Node with execution condition."""

    def __init__(self, func: Callable, condition: Callable[[State], bool]):
        """Create conditional node.

        Args:
            func: Node function to execute
            condition: Function returning True if node should execute
        """
```

#### Node Extension Method

```python
def if_extension(self, condition: Callable[[State], bool]) -> ConditionalNode:
    """Add condition to node.

    Args:
        condition: Function returning True if this node should execute

    Returns:
        ConditionalNode wrapping this function
    """

# Monkey-patch onto functions
FunctionType.if = if_extension
```

### Usage Examples

#### Example 1: Linear Workflow

```python
from langgraph_fluent import FluentGraph
from typing_extensions import TypedDict

class State(TypedDict):
    data: str
    result: str

def fetch_data(state: State) -> State:
    return {"data": "fetched"}

def process_data(state: State) -> State:
    return {"result": state["data"].upper()}

def save_result(state: State) -> State:
    print(f"Saving: {state['result']}")
    return {}

# Simple linear workflow
app = (
    FluentGraph(State)
    .then(fetch_data)
    .then(process_data)
    .then(save_result)
    .compile()
)

result = app.invoke({"data": "", "result": ""})
```

#### Example 2: Parallel Execution

```python
def check_weather(state: State) -> State:
    return {"weather": "sunny"}

def query_database(state: State) -> State:
    return {"db_result": "data"}

def call_api(state: State) -> State:
    return {"api_result": "response"}

def combine_results(state: State) -> State:
    return {"final": f"{state['weather']}, {state['db_result']}, {state['api_result']}"}

# Parallel execution
app = (
    FluentGraph(State)
    .then(get_user_input)
    .then([check_weather, query_database, call_api])  # All run in parallel
    .then(combine_results)
    .compile()
)
```

#### Example 3: Conditional Execution

```python
def is_high_priority(state: State) -> bool:
    return state.get("priority", 0) > 7

def is_medium_priority(state: State) -> bool:
    priority = state.get("priority", 0)
    return 4 <= priority <= 7

def escalate_immediately(state: State) -> State:
    return {"status": "escalated"}

def assign_to_team(state: State) -> State:
    return {"status": "assigned"}

def queue_for_later(state: State) -> State:
    return {"status": "queued"}

# Conditional routing
app = (
    FluentGraph(State)
    .then(classify_request)
    .then([
        escalate_immediately.if(is_high_priority),
        assign_to_team.if(is_medium_priority),
        queue_for_later  # Default - no condition
    ])
    .then(send_notification)
    .compile()
)
```

#### Example 4: Loops and Retries

```python
def has_more_components(state: State) -> bool:
    return state["current_index"] < len(state["components"])

def all_done(state: State) -> bool:
    return state["current_index"] >= len(state["components"])

# Loop pattern
app = (
    FluentGraph(State)
    .then(setup)
    .then(process_component)
    .then([
        process_component.if(has_more_components),  # Loop back
        finalize.if(all_done)
    ])
    .compile()
)
```

#### Example 5: Email Spam Detection

```python
class EmailState(TypedDict):
    email_id: str
    spam_score: float
    spam_x_result: str
    action: str

def high_confidence_spam(state: EmailState) -> bool:
    return state["spam_score"] > 0.8 and state["spam_x_result"] == "SPAM"

def low_confidence(state: EmailState) -> bool:
    return state["spam_score"] < 0.3

def uncertain(state: EmailState) -> bool:
    score = state["spam_score"]
    return 0.3 <= score <= 0.8

app = (
    FluentGraph(EmailState)
    .then(fetch_email)
    .then(check_spam_score)
    .then(run_spam_x)
    .then([
        mark_spam.if(high_confidence_spam),
        mark_not_spam.if(low_confidence),
        human_review.if(uncertain)
    ])
    .compile()
)
```

#### Example 6: Software Development Workflow

```python
class DevState(TypedDict):
    requirements: str
    design: str
    components: list
    current_index: int
    implementations: list

def has_more_components(state: DevState) -> bool:
    return state["current_index"] < len(state["components"])

def all_components_done(state: DevState) -> bool:
    return state["current_index"] >= len(state["components"])

app = (
    FluentGraph(DevState)
    .then(gather_requirements)
    .then(create_design)
    .then(break_into_components)
    .then(implement_component)
    .then([
        implement_component.if(has_more_components),  # Loop
        finalize.if(all_components_done)
    ])
    .compile()
)
```

## Implementation Strategy

### Phase 1: Core Infrastructure

**Files to create:**
- `libs/langgraph/langgraph_fluent/__init__.py`
- `libs/langgraph/langgraph_fluent/graph.py` - FluentGraph class
- `libs/langgraph/langgraph_fluent/nodes.py` - ConditionalNode class
- `libs/langgraph/langgraph_fluent/extensions.py` - .if() extension

**Key implementation details:**

1. **FluentGraph wraps StateGraph**
   - Maintain internal StateGraph instance
   - Track current position in workflow
   - Generate unique node names internally

2. **Smart .then() handling**
   ```python
   def then(self, node_or_nodes):
       if callable(node_or_nodes):
           # Single node - add edge from last to new
           return self._add_single_node(node_or_nodes)
       elif isinstance(node_or_nodes, list):
           # Multiple nodes - parallel execution
           return self._add_parallel_nodes(node_or_nodes)
   ```

3. **Conditional routing**
   ```python
   def _add_parallel_nodes(self, nodes):
       for node in nodes:
           if isinstance(node, ConditionalNode):
               # Add conditional edge
               self._add_conditional_node(node)
           else:
               # Add regular edge
               self._add_regular_node(node)
   ```

### Phase 2: Advanced Features

1. **Retry mechanisms**
   ```python
   def retry(self, max_attempts: int, condition: Callable) -> 'FluentGraph':
       """Retry current node if condition true."""
   ```

2. **Checkpointing support**
   ```python
   def compile(self, checkpointer=None, **kwargs):
       """Compile with optional checkpointer."""
   ```

3. **Interrupt support**
   ```python
   def interrupt_before(self, *node_funcs) -> 'FluentGraph':
       """Add interrupt before specified nodes."""
   ```

### Phase 3: Testing & Documentation

1. **Unit tests** - Test each method in isolation
2. **Integration tests** - Full workflows
3. **Examples** - Real-world use cases
4. **Documentation** - API reference, migration guide

## File Structure

```
libs/langgraph/
├── langgraph_fluent/
│   ├── __init__.py          # Public API exports
│   ├── graph.py             # FluentGraph class
│   ├── nodes.py             # ConditionalNode, node utilities
│   ├── extensions.py        # Function.if() extension
│   └── examples/
│       ├── basic.py         # Simple workflows
│       ├── conditional.py   # Conditional execution
│       ├── parallel.py      # Parallel nodes
│       └── advanced.py      # Loops, retries
├── tests/
│   └── fluent/
│       ├── test_graph.py
│       ├── test_nodes.py
│       └── test_examples.py
└── docs/
    └── fluent_api.md        # User documentation
```

## Testing Strategy

### Unit Tests

```python
def test_linear_workflow():
    """Test simple sequential workflow."""
    def step1(state): return {"count": 1}
    def step2(state): return {"count": state["count"] + 1}

    app = FluentGraph(State).then(step1).then(step2).compile()
    result = app.invoke({})
    assert result["count"] == 2

def test_parallel_execution():
    """Test parallel node execution."""
    results = []
    def node1(state):
        results.append(1)
        return {}
    def node2(state):
        results.append(2)
        return {}

    app = FluentGraph(State).then([node1, node2]).compile()
    app.invoke({})
    assert set(results) == {1, 2}

def test_conditional_execution():
    """Test conditional node execution."""
    def condition_true(state): return True
    def condition_false(state): return False

    executed = []
    def node1(state):
        executed.append(1)
        return {}
    def node2(state):
        executed.append(2)
        return {}

    app = (
        FluentGraph(State)
        .then([
            node1.if(condition_true),
            node2.if(condition_false)
        ])
        .compile()
    )
    app.invoke({})
    assert executed == [1]  # Only node1 executed
```

### Integration Tests

Test complete real-world workflows from the examples section.

## Documentation Requirements

### API Reference
- Complete docstrings for all public methods
- Type hints for all parameters and return values
- Examples for each method

### User Guide
- "Getting Started" tutorial
- Migration guide from standard LangGraph
- Common patterns and recipes
- Troubleshooting guide

### Examples
- At least 10 complete, runnable examples
- Cover common use cases (CRUD, workflows, state machines)
- Include performance comparisons

## Success Criteria

1. **Functionality**
   - ✅ All examples compile and run
   - ✅ Produces identical behavior to hand-written LangGraph
   - ✅ Passes all tests

2. **Developer Experience**
   - ✅ 50%+ reduction in lines of code for typical workflows
   - ✅ IDE autocomplete works
   - ✅ Clear error messages

3. **Performance**
   - ✅ No measurable overhead vs native LangGraph
   - ✅ Compilation time < 100ms for typical workflows

4. **Maintainability**
   - ✅ Full type hints
   - ✅ Comprehensive tests (>90% coverage)
   - ✅ Clear, maintainable code

## Contribution Guidelines

### Before Starting
1. Fork `langchain-ai/langchain` to your account
2. Clone your fork locally
3. Create feature branch: `git checkout -b fluent-langgraph-api`
4. Set up development environment

### Development Process
1. Implement in phases (Core → Advanced → Polish)
2. Write tests alongside code
3. Update documentation
4. Run full test suite
5. Manual testing with examples

### Pull Request
1. Push to your fork
2. Create PR from your fork → `langchain-ai/langchain`
3. Include:
   - Clear description of changes
   - Examples demonstrating improvements
   - Test results
   - Documentation updates

### PR Checklist
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] Examples provided
- [ ] Type hints complete
- [ ] Backwards compatible (doesn't break existing code)

## Open Questions

1. **Package location**: Should this be in `langgraph` or separate `langgraph-fluent`?
2. **Backwards compatibility**: Should old API still be accessible?
3. **Performance**: Any optimizations needed for large workflows?
4. **Error messages**: How to make errors helpful when fluent chain fails?

## Next Steps

1. **Setup**
   - Fork repository
   - Clone locally
   - Create feature branch

2. **Phase 1: Core Implementation**
   - Implement FluentGraph class
   - Implement ConditionalNode class
   - Add .if() extension
   - Write basic tests

3. **Phase 2: Validation**
   - Port all examples from this doc
   - Verify behavior matches standard LangGraph
   - Performance testing

4. **Phase 3: Documentation**
   - Write API reference
   - Create user guide
   - Add examples

5. **Phase 4: Submit PR**
   - Final testing
   - Code review prep
   - Submit pull request

## References

- LangGraph documentation: https://langchain-ai.github.io/langgraph/
- LangChain contribution guidelines: https://github.com/langchain-ai/langchain/blob/master/CONTRIBUTING.md
- Design discussion: (link to this requirements doc)
