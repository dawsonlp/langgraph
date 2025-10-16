# Fluent LangGraph API - Implementation Checklist

**Purpose**: Track implementation progress for the fluent/chainable API wrapper for LangGraph.
**Engineer**: Senior Python Engineer
**Repository**: `dawsonlp/langgraph` (fork of `langchain-ai/langgraph`)
**Branch**: `dawsonlp/fluent-langgraph-api` (to be created)
**Requirements**: See `FLUENT_LANGGRAPH_REQUIREMENTS.md`

---

## Repository Context

**Current LangGraph Structure:**
- **Main Package**: `libs/langgraph/langgraph/`
- **Core Graph Module**: `libs/langgraph/langgraph/graph/`
  - `state.py` - Contains StateGraph implementation
  - `message.py` - Message handling
  - `_node.py`, `_branch.py` - Node/branch internals
- **Tests**: `libs/langgraph/tests/`
- **Python Version**: >=3.10
- **Package Version**: 1.0.0a4
- **Tools**: uv (package manager), pytest, ruff, mypy

---

## Phase 1: Project Structure & Core Infrastructure

### 1.1 Feature Branch Setup
- [ ] Create feature branch: `dawsonlp/fluent-langgraph-api` from main
- [ ] Verify branch is up to date with upstream

### 1.2 Package Structure
- [ ] Create `libs/langgraph/langgraph/graph/fluent/` directory
- [ ] Create `__init__.py` exposing public API
- [ ] Verify imports work: `from langgraph.graph.fluent import FluentGraph`

### 1.3 Core Class: FluentGraph (`fluent/graph.py`)
- [ ] Define `FluentGraph[StateT]` class with generic state type
- [ ] Implement `__init__(self, state_schema: Type[StateT])` constructor
  - Creates internal `StateGraph` instance (from `langgraph.graph.state`)
  - Tracks last node name(s) for chaining
  - Initializes node counter for unique naming
- [ ] Implement `then(self, node_or_nodes: Callable | list[Callable]) -> FluentGraph`
  - Single callable: sequential execution from last node(s)
  - List of callables: parallel execution from last node(s)
  - Handle ConditionalNode instances in list
  - Update last node tracking
  - Return self for chaining
- [ ] Implement `compile(self, **kwargs) -> CompiledGraph`
  - Connect last node(s) to END
  - Return compiled StateGraph with all kwargs passed through
  - Preserve all StateGraph compilation options
- [ ] Add private helper: `_generate_node_name(func: Callable) -> str`
  - Use function name + counter for uniqueness
  - No string collisions across workflow
- [ ] Add private helper: `_add_single_node(node: Callable) -> FluentGraph`
- [ ] Add private helper: `_add_parallel_nodes(nodes: list) -> FluentGraph`
- [ ] Add private helper: `_add_conditional_node(node: ConditionalNode) -> FluentGraph`

**Acceptance Criteria**:
- Type hints present for all public methods
- Docstrings follow LangGraph conventions (concise, clear)
- Code handles START/END node management internally
- User never specifies node names as strings
- Integrates seamlessly with existing StateGraph

### 1.4 Conditional Nodes (`fluent/nodes.py`)
- [ ] Define `ConditionalNode` class
  - `__init__(self, func: Callable, condition: Callable[[StateT], bool])`
  - Store function and condition
  - Expose as read-only properties
- [ ] Implement `__repr__` for debugging
- [ ] Type hints for generic state type consistency

**Acceptance Criteria**:
- Immutable after construction (no setters)
- Clear error messages if condition isn't callable
- Works with FluentGraph's type inference

### 1.5 Function Extensions (`fluent/extensions.py`)
- [ ] Add `.if()` method to function objects
  - Approach: Wrapper function that returns ConditionalNode
  - Signature: `def enable_if(func: Callable, condition: Callable[[State], bool]) -> ConditionalNode`
  - Usage: `enable_if(process_data, lambda s: s.data_valid)`
- [ ] Document extension mechanism clearly
- [ ] Handle edge cases (already a ConditionalNode, non-callables, etc.)

**Note**: Python doesn't support monkey-patching built-in function objects, so we'll use a wrapper function approach instead of trying to add methods to functions.

**Acceptance Criteria**:
- Works naturally with LangGraph conventions
- Clear documentation on usage pattern
- No runtime overhead when condition not used

---

## Phase 2: StateGraph Integration

### 2.1 Node Management
- [ ] Implement logic to add nodes to internal StateGraph
- [ ] Track node dependencies (parent → child relationships)
- [ ] Generate unique node names deterministically
- [ ] Handle START node connection on first `.then()` call
- [ ] Handle END node connection in `.compile()`
- [ ] Preserve StateGraph's reducer and channel semantics

### 2.2 Edge Creation
- [ ] Implement sequential edge creation (single node in `.then()`)
  - Use `StateGraph.add_edge()` from last nodes to new node
- [ ] Implement parallel edge creation (list of nodes in `.then()`)
  - Connect from all last nodes to each new node
  - Update last nodes to be all parallel nodes
- [ ] Implement conditional edge creation
  - Use `StateGraph.add_conditional_edges()`
  - Create routing function that evaluates condition
  - Route to target node if True, skip if False

### 2.3 Routing Logic
- [ ] Create internal routing function generator for conditionals
  - Takes ConditionalNode's condition function
  - Returns StateGraph-compatible routing function
  - Maps True → target node, False → next node/END
- [ ] Handle parallel nodes with mixed conditionals
  - Some nodes have conditions, others don't
  - All execute in parallel when conditions met
- [ ] Test complex routing scenarios

**Acceptance Criteria**:
- No manual edge specification by user
- Conditional routing works correctly
- Parallel execution preserves independence
- Proper error handling for unreachable nodes
- Compatible with StateGraph's checkpoint system

---

## Phase 3: Unit Tests

### 3.1 FluentGraph Tests (`tests/test_fluent_graph.py`)
- [ ] Test construction with different state types
- [ ] Test single node addition via `.then()`
- [ ] Test parallel node addition via `.then([...])`
- [ ] Test conditional node handling
- [ ] Test node name generation uniqueness
- [ ] Test error cases (invalid arguments, empty lists, etc.)
- [ ] Test method chaining returns correct type
- [ ] Test integration with StateGraph features

### 3.2 ConditionalNode Tests (`tests/test_fluent_nodes.py`)
- [ ] Test construction with valid function and condition
- [ ] Test property access (function, condition)
- [ ] Test immutability
- [ ] Test repr output
- [ ] Test error cases (non-callable condition, etc.)

### 3.3 Extension Tests (`tests/test_fluent_extensions.py`)
- [ ] Test `enable_if()` wrapper function
- [ ] Test return type is ConditionalNode
- [ ] Test chaining (e.g., defining inline vs stored)
- [ ] Test error cases

**Testing Standards**:
- Use pytest framework (already configured)
- Follow existing LangGraph test patterns
- Use `conftest.py` fixtures where appropriate
- Fast tests (<100ms each for unit tests)
- >90% code coverage target

---

## Phase 4: Integration Tests

### 4.1 Basic Examples (`tests/test_fluent_basic_examples.py`)
- [ ] Linear workflow example (3+ sequential nodes)
  - Verify execution order
  - Verify state threading
- [ ] Parallel execution example (2+ parallel nodes)
  - Verify all nodes execute
  - Verify state merging
- [ ] Conditional routing example
  - Test both True and False branches
  - Verify correct node execution

### 4.2 Complex Workflows (`tests/test_fluent_complex_workflows.py`)
- [ ] Email spam detection workflow from requirements
  - Test spam path
  - Test ham path
  - Verify all nodes execute correctly
- [ ] Software development workflow from requirements
  - Test skip scenarios
  - Test full execution path
- [ ] Loop/retry workflow
  - Test successful first attempt
  - Test retry logic
  - Test max retries exhausted

### 4.3 StateGraph Compatibility (`tests/test_fluent_compat.py`)
- [ ] Test with checkpointing enabled
- [ ] Test with different state schemas
- [ ] Test with reducers
- [ ] Test with interrupts
- [ ] Test compilation options pass through correctly

### 4.4 Edge Cases (`tests/test_fluent_edge_cases.py`)
- [ ] Empty workflow (no nodes)
- [ ] Single node workflow
- [ ] All nodes conditional
- [ ] Deeply nested parallel/conditional combinations
- [ ] Large workflows (20+ nodes)

**Integration Test Standards**:
- Use actual StateGraph compilation
- Execute workflows end-to-end
- Verify output states match expectations
- Test with various state types
- Follow LangGraph testing patterns (see `test_pregel.py`)

---

## Phase 5: Documentation

### 5.1 Code Documentation
- [ ] Docstrings for all public classes and methods
  - Follow LangGraph's concise style
  - Include parameter types and descriptions
  - Include return value descriptions
  - Include usage examples
- [ ] Type hints for all public APIs
- [ ] Internal code comments where logic is complex

### 5.2 User Guide
- [ ] Create `docs/docs/how-tos/fluent-api.md`
  - Quick start section
  - Core concepts explanation
  - Common patterns
  - When to use fluent vs traditional API
- [ ] Include all 6 examples from requirements doc as runnable code

### 5.3 Example Gallery
- [ ] Create `examples/fluent/` directory
- [ ] Add `basic.py` - linear workflow
- [ ] Add `parallel.py` - parallel execution
- [ ] Add `conditional.py` - conditional routing
- [ ] Add `loops.py` - retry and loop patterns
- [ ] Add `spam_detection.py` - email classifier
- [ ] Add `dev_workflow.py` - software development pipeline
- [ ] Add `README.md` with descriptions and how to run

### 5.4 API Reference
- [ ] Update `docs/docs/reference/graphs.md` to include fluent API
- [ ] Document FluentGraph class
- [ ] Document ConditionalNode class
- [ ] Document enable_if() function

---

## Phase 6: Code Quality & Polish

### 6.1 Type Checking
- [ ] Run `mypy libs/langgraph/langgraph/graph/fluent/`
- [ ] Fix all type errors
- [ ] Verify generic types work correctly
- [ ] Test with strict mypy settings

### 6.2 Linting & Formatting
- [ ] Run `ruff check libs/langgraph/langgraph/graph/fluent/`
- [ ] Run `ruff format libs/langgraph/langgraph/graph/fluent/`
- [ ] Verify all linting rules pass
- [ ] Follow LangGraph code style

### 6.3 Performance
- [ ] Benchmark fluent API vs traditional API
  - Measure compilation time overhead
  - Measure runtime execution overhead
- [ ] Verify <5% overhead target met
- [ ] Profile and optimize hot paths if needed

### 6.4 Error Handling
- [ ] Review all error cases
- [ ] Ensure clear, actionable error messages
- [ ] Add error recovery suggestions where possible
- [ ] Test error paths explicitly

---

## Phase 7: Review & Release Preparation

### 7.1 Testing
- [ ] Run full test suite: `pytest libs/langgraph/tests/`
- [ ] Run with coverage: `pytest --cov=langgraph.graph.fluent --cov-report=html`
- [ ] Ensure >90% coverage
- [ ] Fix any failing tests
- [ ] Test in fresh environment

### 7.2 Code Review Preparation
- [ ] Self-review all code changes
- [ ] Check for any TODOs or FIXMEs in code
- [ ] Verify no dead/commented code remains
- [ ] Ensure consistent code style throughout

### 7.3 Documentation Review
- [ ] Spell check all documentation
- [ ] Verify all examples run successfully
- [ ] Check for broken links
- [ ] Ensure code snippets are up to date

### 7.4 Git & PR Preparation
- [ ] Commit changes with conventional commit messages
- [ ] Push feature branch to origin (dawsonlp/langgraph)
- [ ] Create PR to langchain-ai/langgraph
- [ ] Write comprehensive PR description
- [ ] Reference any related issues
- [ ] Tag for review

---

## Success Metrics (from Requirements)

Verify these goals are met before considering complete:

- [ ] **Code Reduction**: 50%+ fewer lines for typical workflows (measure 5+ examples)
- [ ] **IDE Support**: Autocomplete works for all fluent methods
- [ ] **Error Messages**: Clear, actionable error messages (user testing)
- [ ] **Performance**: <5% overhead vs native StateGraph (benchmark suite)
- [ ] **Test Coverage**: >90% code coverage (run pytest --cov)
- [ ] **Type Safety**: No mypy errors with configured settings

---

## Notes for Implementation

### DRY Principles Applied
- Single source of truth for node name generation
- Reusable helper methods for node/edge addition
- Shared error handling patterns
- Common test fixtures

### KISS Principles Applied
- Only two core operations: `.then()` and conditional wrapper
- Smart method dispatch based on argument types
- No separate methods for parallel/conditional/sequential
- Minimal public API surface

### LangGraph Integration Best Practices
- Wrap StateGraph, don't replace it
- Preserve all StateGraph functionality
- Use existing StateGraph methods internally
- Maintain compatibility with checkpointing, interrupts, etc.
- Follow LangGraph naming and style conventions

### Python Best Practices
- Type hints where they add value (public API, complex logic)
- Omit type hints rather than use `Any`
- Pure functions for node name generation, condition evaluation
- Immutable ConditionalNode design
- Clear separation of concerns (graph, nodes, extensions)

### Testing Strategy
- Unit tests: Fast, isolated, pure logic
- Integration tests: End-to-end workflows
- Compatibility tests: StateGraph features work correctly
- Separate test files by component
- Use pytest fixtures to avoid duplication

---

## Quick Reference Commands

```bash
# Navigate to package directory
cd /Users/ldawson/repos/langgraph-fork/libs/langgraph

# Run all tests
pytest tests/

# Run fluent API tests only
pytest tests/test_fluent*.py

# Run with coverage
pytest --cov=langgraph.graph.fluent --cov-report=html

# Type checking
mypy langgraph/graph/fluent/

# Linting
ruff check langgraph/graph/fluent/

# Formatting
ruff format langgraph/graph/fluent/

# Run example
cd /Users/ldawson/repos/langgraph-fork
python examples/fluent/basic.py
```

---

**Status**: Ready for implementation
**Last Updated**: 2025-10-16
**Estimated Effort**: 3-5 days for Phase 1-4, 2-3 days for Phase 5-7
