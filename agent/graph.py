from langgraph.graph import END, START, StateGraph

from agent.nodes.generate import BuildContextFunction, FormatHistoryFunction, GenerateFunction, make_generate_node
from agent.nodes.classify_intent import classify_intent
from agent.nodes.resolve_context import resolve_context
from agent.nodes.retrieve import RetrieveFunction, RewriteFunction, make_retrieve_node
from agent.nodes.select_history import select_history
from agent.state import AgentState


def prepare_agent_context(
    current_user_message: str,
    conversation_history: list[dict],
    language: str = "zh-Hant",
) -> AgentState:
    """Run the cheap context nodes before guard/cache/fast-answer decisions."""
    state: AgentState = {
        "current_user_message": current_user_message,
        "conversation_history": conversation_history,
        "language": "en" if language == "en" else "zh-Hant",
        "retrieval_filter": None,
        "metadata": {},
    }
    state.update(resolve_context(state))
    state.update(classify_intent(state))
    state.update(select_history(state))
    return state


def build_agent_graph(
    *,
    retrieve_fn: RetrieveFunction,
    rewrite_fn: RewriteFunction,
    build_context_fn: BuildContextFunction,
    format_history_fn: FormatHistoryFunction,
    generate_fn: GenerateFunction,
):
    """Build the minimal topic-isolated RAG graph using existing project functions."""
    builder = StateGraph(AgentState)
    builder.add_node("resolve_context", resolve_context)
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("select_history", select_history)
    builder.add_node("retrieve", make_retrieve_node(retrieve_fn, rewrite_fn))
    builder.add_node(
        "generate",
        make_generate_node(build_context_fn, format_history_fn, generate_fn),
    )
    builder.add_edge(START, "resolve_context")
    builder.add_edge("resolve_context", "classify_intent")
    builder.add_edge("classify_intent", "select_history")
    builder.add_edge("select_history", "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)
    return builder.compile()
