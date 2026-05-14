# app/services/bot_service.py

def get_bot_config(bot_id: int):
    return {
        "require_registration": True,
        "initial_message": "Welcome to HighWirePress Support! 👋\n\nTo get started, please provide your name and email address (format: Name, email@example.com)",
        "domain_message": "I can only answer domain-related questions.",
        "escalation_message": "I don't have enough information to answer that question accurately. Would you like me to create a support ticket so our team can help you?",
        "memory_limit": 6,
        "retriever_config": {},
        "llm_config": {
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_new_tokens": 2048
        }
    }