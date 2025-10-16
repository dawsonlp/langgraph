# Fluent LangGraph API

A chainable, fluent API wrapper for LangGraph that dramatically simplifies workflow definition.

## Overview

The fluent API reduces boilerplate and provides a natural, declarative way to build state graphs. Instead of explicitly naming nodes and manually connecting edges, the fluent API infers structure from the order of `.then()` calls.

## Key Features

- **Minimal API Surface**: Only two methods needed - `.then()` and `enable_if()`
- **Smart Type Inference**: Single `.then()` method handles sequential, parallel, and conditional execution
- **Zero Boilerplate**: No manual node naming or edge specification
- **Full IDE Support**: Complete autocomplete and type checking
- **Backwards Compatible**: Compiles to standard StateGraph

## Quick Start

```python
from typing_extensions import TypedDict
from langgraph.graph.fluent import FluentGraph, enable_if

# Define your state
class State(TypedDict):
    count: int
    valid: bool

# Define node functions
def increment(state: State) -> State:
    return {"count": state["count"] + 1}

def double(state: State) -> State:
    return {"count": state["count"] * 2}

def is_valid(state: State) -> bool:
    return state.get("valid", True)

# Build graph with fluent API
graph = (
    FluentGraph(State)
    .then(increment)                          # Sequential
    .then(double)                             # Sequential
    .then(enable_if(increment, is_valid))     # Conditional
    .compile()
)

# Use like any StateGraph
result = graph.invoke({"count": 0, "valid": True})
# Result: {"count": 3, "valid": True}
# Execution: 0 -> +1 -> *2 -> +1 (conditional) = 3
```

## Execution Patterns

### Sequential Execution

Chain nodes in sequence by calling `.then()` repeatedly:

```python
graph = (
    FluentGraph(State)
    .then(step1)
    .then(step2)
    .then(step3)
    .compile()
)
```

Nodes execute in order: `step1 → step2 → step3`

### Parallel Execution

Pass a list of nodes to `.then()` for parallel execution:

```python
graph = (
    FluentGraph(State)
    .then([branch_a, branch_b, branch_c])
    .compile()
)
```

All branches execute in parallel from the same input state.

**Note**: With default `LastValue` reducer, only one parallel branch's output will be kept. For merging multiple outputs, use `Annotated` state fields with custom reducers.

### Conditional Execution

Use `enable_if()` to conditionally execute nodes:

```python
graph = (
    FluentGraph(State)
    .then(check_input)
    .then(enable_if(process, should_process))
    .then(finalize)
    .compile()
)
```

If condition returns `False`, node is skipped and graph terminates (routes to END).

### Mixed Patterns

Combine sequential, parallel, and conditional execution:

```python
graph = (
    FluentGraph(State)
    .then(start)                              # Sequential
    .then([branch_a, branch_b])              # Parallel
    .then(enable_if(cleanup, needs_cleanup))  # Conditional
    .compile()
)
```

## Real-World Examples

### Email Spam Detection

```python
from typing_extensions import TypedDict
from langgraph.graph.fluent import FluentGraph, enable_if

class EmailState(TypedDict):
    content: str
    is_spam: bool
    classification: str

def analyze_content(state: EmailState) -> EmailState:
    spam_words = ["win", "free", "click", "urgent"]
    is_spam = any(word in state["content"].lower() for word in spam_words)
    return {"is_spam": is_spam}

def classify_as_spam(state: EmailState) -> EmailState:
    return {"classification": "SPAM"}

def classify_as_ham(state: EmailState) -> EmailState:
    return {"classification": "HAM"}

def is_spam(state: EmailState) -> bool:
    return state.get("is_spam", False)

def is_ham(state: EmailState) -> bool:
    return not state.get("is_spam", False)

# Build spam detection workflow
graph = (
    FluentGraph(EmailState)
    .then(analyze_content)
    .then([
        enable_if(classify_as_spam, is_spam),
        enable_if(classify_as_ham, is_ham)
    ])
    .compile()
)

# Test
result = graph.invoke({
    "content": "WIN FREE MONEY!",
    "is_spam": False,
    "classification": ""
})
# Result: {"content": "WIN FREE MONEY!", "is_spam": True, "classification": "SPAM"}
```

### Data Processing Pipeline

```python
from typing_extensions import TypedDict
from langgraph.graph.fluent import FluentGraph, enable_if

class DataState(TypedDict):
    data: list[int]
    processed: bool
    valid: bool

def load_data(state: DataState) -> DataState:
    return {"data": [1, 2, 3, 4, 5]}

def validate_data(state: DataState) -> DataState:
    valid = len(state["data"]) > 0
    return {"valid": valid}

def process_data(state: DataState) -> DataState:
    processed_data = [x * 2 for x in state["data"]]
    return {"data": processed_data, "processed": True}

def is_valid(state: DataState) -> bool:
    return state.get("valid", False)

graph = (
    FluentGraph(DataState)
    .then(load_data)
    .then(validate_data)
    .then(enable_if(process_data, is_valid))
    .compile()
)
```

## API Reference

### FluentGraph

Main wrapper class for building state graphs fluently.

**Constructor**:
```python
FluentGraph(state_schema: type[StateT])
```

**Methods**:

- `.then(node_or_nodes)`: Add node(s) with automatic edge creation
  - Single callable: Sequential execution
  - Single ConditionalNode: Conditional execution
  - List of callables/ConditionalNodes: Parallel execution
  - Returns: Self for method chaining

- `.compile(**kwargs)`: Compile to CompiledStateGraph
  - Accepts all StateGraph.compile() arguments
  - Returns: CompiledStateGraph ready for execution

### enable_if

Helper function to create conditional nodes.

**Signature**:
```python
enable_if(func: Callable, condition: Callable[[StateT], bool]) -> ConditionalNode
```

**Parameters**:
- `func`: Node function to execute conditionally
- `condition`: Predicate function that determines if node should execute

**Returns**: ConditionalNode wrapping the function and condition

### ConditionalNode

Wrapper for conditional node execution (usually created via `enable_if()`).

**Constructor**:
```python
ConditionalNode(func: Callable, condition: Callable[[StateT], bool])
```

**Properties** (read-only):
- `.func`: The wrapped node function
- `.condition`: The condition predicate function

## Comparison with Standard LangGraph

### Standard LangGraph

```python
from langgraph.graph import StateGraph, END

graph = StateGraph(State)

# Add nodes with explicit names
graph.add_node("increment", increment)
graph.add_node("double", double)
graph.add_node("conditional_increment", increment)

# Connect edges manually
graph.add_edge(START, "increment")
graph.add_edge("increment", "double")

# Add conditional edges
def should_continue(state):
    return "conditional_increment" if state.get("valid") else END

graph.add_conditional_edges("double", should_continue)
graph.add_edge("conditional_increment", END)

# Compile
compiled = graph.compile()
```

### Fluent LangGraph

```python
from langgraph.graph.fluent import FluentGraph, enable_if

graph = (
    FluentGraph(State)
    .then(increment)
    .then(double)
    .then(enable_if(increment, is_valid))
    .compile()
)
```

**Result**: ~50% reduction in lines of code, no string-based node names, natural reading order.

## Advanced Usage

### Checkpointing

Pass checkpointer to `compile()`:

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = (
    FluentGraph(State)
    .then(step1)
    .then(step2)
    .compile(checkpointer=checkpointer)
)
```

### Interrupts

Control execution flow with interrupts:

```python
graph = (
    FluentGraph(State)
    .then(step1)
    .then(step2)
    .then(step3)
    .compile(interrupt_before=["step2"])
)
```

### Lambda Conditions

Use lambda functions for inline conditions:

```python
graph = (
    FluentGraph(State)
    .then(increment)
    .then(enable_if(process, lambda s: s["count"] > 5))
    .compile()
)
```

## Best Practices

1. **Name Functions Clearly**: Function names appear in debugging/visualization
2. **Keep Nodes Pure**: Nodes should be side-effect free when possible
3. **Use Type Hints**: Enables better IDE support and error catching
4. **One Responsibility Per Node**: Keep nodes focused on single tasks
5. **Test Conditions Separately**: Unit test condition functions independently

## Limitations

- Conditional nodes that skip (condition=False) currently terminate the graph (route to END)
- Parallel nodes writing to same state key require custom reducers (use `Annotated` fields)
- No direct support for loops yet (use standard StateGraph for complex loops)

## Migration Guide

To migrate existing StateGraph code:

1. Replace `StateGraph(State)` with `FluentGraph(State)`
2. Replace `graph.add_node(name, func)` + `graph.add_edge()` with `.then(func)`
3. Replace conditional edges with `enable_if(func, condition)`
4. Chain calls with method chaining
5. Call `.compile()` at the end

## Contributing

See [CONTRIBUTING.md](../../../../CONTRIBUTING.md) for development setup and guidelines.

## License

MIT License - see [LICENSE](../../../../LICENSE)
