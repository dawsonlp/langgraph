"""Integration tests for conditional routing in fluent API."""

from typing_extensions import TypedDict

from langgraph.graph.fluent import FluentGraph, enable_if


class EmailState(TypedDict):
    """State for email classification."""

    content: str
    is_spam: bool
    classification: str


class ProcessingState(TypedDict):
    """State for conditional processing."""

    value: int
    should_process: bool
    processed: bool


def test_conditional_routing_true_path():
    """Test conditional node executes when condition is True."""

    def check_value(state: ProcessingState) -> ProcessingState:
        return {"value": state["value"] + 1}

    def process_if_high(state: ProcessingState) -> ProcessingState:
        return {"value": state["value"] * 10, "processed": True}

    def is_high(state: ProcessingState) -> bool:
        return state["value"] > 5

    graph = (
        FluentGraph(ProcessingState)
        .then(check_value)
        .then(enable_if(process_if_high, is_high))
        .compile()
    )

    # value starts at 10, check_value makes it 11, condition is True
    result = graph.invoke({"value": 10, "should_process": True, "processed": False})
    assert result["value"] == 110
    assert result["processed"] is True


def test_conditional_routing_false_path():
    """Test conditional node skips when condition is False."""

    def check_value(state: ProcessingState) -> ProcessingState:
        return {"value": state["value"] + 1, "processed": False}

    def process_if_high(state: ProcessingState) -> ProcessingState:
        return {"value": state["value"] * 10, "processed": True}

    def is_high(state: ProcessingState) -> bool:
        return state["value"] > 5

    graph = (
        FluentGraph(ProcessingState)
        .then(check_value)
        .then(enable_if(process_if_high, is_high))
        .compile()
    )

    # value starts at 2, check_value makes it 3, condition is False
    result = graph.invoke({"value": 2, "should_process": True, "processed": False})
    # Conditional node skipped (routes to END), graph terminates
    assert result["value"] == 3
    assert result["processed"] is False


def test_email_spam_detection_workflow():
    """Test email spam detection workflow from requirements."""

    def analyze_content(state: EmailState) -> EmailState:
        """Analyze email content for spam indicators."""
        spam_words = ["win", "free", "click", "urgent"]
        is_spam = any(word in state["content"].lower() for word in spam_words)
        return {"is_spam": is_spam}

    def classify_as_spam(state: EmailState) -> EmailState:
        """Classify email as spam."""
        return {"classification": "SPAM"}

    def classify_as_ham(state: EmailState) -> EmailState:
        """Classify email as legitimate."""
        return {"classification": "HAM"}

    def is_spam(state: EmailState) -> bool:
        """Check if email is spam."""
        return state.get("is_spam", False)

    def is_ham(state: EmailState) -> bool:
        """Check if email is legitimate."""
        return not state.get("is_spam", False)

    # Build spam detection workflow
    graph = (
        FluentGraph(EmailState)
        .then(analyze_content)
        .then(
            [enable_if(classify_as_spam, is_spam), enable_if(classify_as_ham, is_ham)]
        )
        .compile()
    )

    # Test spam email
    spam_result = graph.invoke(
        {
            "content": "WIN FREE MONEY! Click now!",
            "is_spam": False,
            "classification": "",
        }
    )
    assert spam_result["is_spam"] is True
    assert spam_result["classification"] == "SPAM"

    # Test legitimate email
    ham_result = graph.invoke(
        {
            "content": "Meeting at 3pm today",
            "is_spam": False,
            "classification": "",
        }
    )
    assert ham_result["is_spam"] is False
    assert ham_result["classification"] == "HAM"


def test_multiple_conditionals_in_sequence():
    """Test multiple conditional nodes in sequence."""

    def increment(state: ProcessingState) -> ProcessingState:
        return {"value": state["value"] + 1}

    def double_if_even(state: ProcessingState) -> ProcessingState:
        return {"value": state["value"] * 2}

    def triple_if_positive(state: ProcessingState) -> ProcessingState:
        return {"value": state["value"] * 3}

    def is_even(state: ProcessingState) -> bool:
        return state["value"] % 2 == 0

    def is_positive(state: ProcessingState) -> bool:
        return state["value"] > 0

    graph = (
        FluentGraph(ProcessingState)
        .then(increment)
        .then(enable_if(double_if_even, is_even))
        .then(enable_if(triple_if_positive, is_positive))
        .compile()
    )

    # Start with 3: increment to 4 (even), double to 8, triple to 24
    result = graph.invoke({"value": 3, "should_process": True, "processed": False})
    assert result["value"] == 24


def test_conditional_with_lambda():
    """Test conditional node with lambda condition."""

    def process(state: ProcessingState) -> ProcessingState:
        return {"value": state["value"] * 2, "processed": True}

    # Use lambda for condition
    graph = (
        FluentGraph(ProcessingState)
        .then(enable_if(process, lambda s: s["value"] > 5))
        .compile()
    )

    # Condition True
    result = graph.invoke({"value": 10, "should_process": True, "processed": False})
    assert result["value"] == 20
    assert result["processed"] is True

    # Condition False
    result = graph.invoke({"value": 3, "should_process": True, "processed": False})
    assert result["value"] == 3
    assert result["processed"] is False
