# app/services/bot_service.py

def get_bot_config(bot_id: int):
    return {
        "require_registration": True,
        "initial_message": "Please provide your name and email.",
        "domain_message": "I can only answer domain-related questions.",
        "escalation_message": "No relevant information found.",
        "memory_limit": 6,
        "retriever_config": {},
        "llm_config": {
            "repo_id": "llama-3.1-8b-instant",  # Fixed: GROQ model name
            "temperature": 0.0,
            "max_new_tokens": 2048  # Increased for better responses
        }
    }