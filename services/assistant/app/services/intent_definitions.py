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
]


def format_intent_definitions(definitions: list[dict]) -> str:
    lines = []
    for definition in sorted(definitions, key=lambda item: item["sort_order"]):
        lines.append(f"- {definition['name']}: {definition['description']}")
        if definition.get("details"):
            lines.append(f"  Details: {definition['details']}")
    return "\n".join(lines)
