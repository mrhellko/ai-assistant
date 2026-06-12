INTENT_DEFINITIONS = [
    {
        "name": "unknown",
        "description": (
            "The request is not understood or is outside currently supported reminder commands."
        ),
        "details": (
            "Set reply to a concise Russian message saying that the request is not understood."
        ),
        "sort_order": 10,
    },
    {
        "name": "reminder_create",
        "description": "Create a new reminder.",
        "details": "Requires reminder_text and due_at.",
        "sort_order": 20,
    },
    {
        "name": "reminder_need_info",
        "description": "The request is about reminders, but required information is missing.",
        "details": (
            "Set clarification_question to a natural concise Russian question asking only "
            "for the missing information."
        ),
        "sort_order": 30,
    },
    {
        "name": "reminder_list",
        "description": "Show future active reminders.",
        "details": "Use this when the user asks for current, future, active reminders.",
        "sort_order": 40,
    },
    {
        "name": "reminder_history",
        "description": "Show reminder history, including sent/cancelled/pending reminders.",
        "details": "Use this when the user asks for reminder history.",
        "sort_order": 50,
    },
    {
        "name": "reminder_delete",
        "description": "The user wants to delete/cancel a reminder.",
        "details": (
            "If the exact reminder is not safely identifiable, still return reminder_delete; "
            "the backend will show future reminders with delete buttons."
        ),
        "sort_order": 60,
    },
    {
        "name": "thread_new",
        "description": "Start a new conversation thread and stop using the previous topic context.",
        "details": (
            "Use this only when the user explicitly asks to start a new dialog, "
            "new conversation, or switch to a clean topic."
        ),
        "sort_order": 70,
    },
    {
        "name": "thread_forget",
        "description": "Forget the current topic context and continue with a clean conversation.",
        "details": (
            "Use this only when the user explicitly asks to forget, reset, or discard "
            "the current topic. Do not delete historical database records."
        ),
        "sort_order": 80,
    },
    {
        "name": "web_search",
        "description": "Create a delegated task that requires internet search.",
        "details": (
            "Use when the user asks to find, compare, research, or choose something "
            "using current internet information. Set task_text to the full search "
            "objective and put structured constraints in extracted_context."
        ),
        "sort_order": 90,
    },
    {
        "name": "web_search_update",
        "description": "Update the active delegated web-search task with a user refinement.",
        "details": (
            "Use when recent_context contains an active search task and the user refines "
            "it, for example changing size, price, delivery, location, or other constraints. "
            "Set task_text to the full updated objective when possible, and put changed "
            "constraints in extracted_context."
        ),
        "sort_order": 100,
    },
]


def format_intent_definitions(definitions: list[dict]) -> str:
    lines = []
    for definition in sorted(definitions, key=lambda item: item["sort_order"]):
        lines.append(f"- {definition['name']}: {definition['description']}")
        if definition.get("details"):
            lines.append(f"  Details: {definition['details']}")
    return "\n".join(lines)
