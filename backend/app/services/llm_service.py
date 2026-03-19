import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

load_dotenv()

def create_chat_model(llm_config: dict = None):
    """
    Dynamically creates a chat model based on configuration.
    """
    llm_config = llm_config or {}

    llm = HuggingFaceEndpoint(
        repo_id=llm_config.get("repo_id", "HuggingFaceH4/zephyr-7b-beta"),
        huggingfacehub_api_token=os.getenv("HF_TOKEN"),
        task="conversational",
        temperature=llm_config.get("temperature", 0.0),
        max_new_tokens=llm_config.get("max_new_tokens", 20000),
    )

    return ChatHuggingFace(llm=llm)


#rewriting queryyy
def rewrite_query(user_query, history, llm_config=None):
    chat_model = create_chat_model(llm_config)
    history_summary = ""
    if history and isinstance(history, list):
        history_summary = "\n".join([f"{m['role']}: {m['content']}" for m in history[-3:]])

    prompt = f"""Given the chat history and the latest question, rewrite it into a 
    standalone technical search query for a documentation database.
    History: {history_summary}
    Question: {user_query}
    Search Query:"""
    
    response = chat_model.invoke([HumanMessage(content=prompt)])
    return response.content.strip()


def get_answers(history, context, user_query, llm_config=None):
    # Fix 1: Set a reasonable token limit and force temperature to 0.0.
    if llm_config is None:
        llm_config = {"max_new_tokens": 1024, "temperature": 0.0}
    else:
        llm_config["max_new_tokens"] = 1024 
        llm_config["temperature"] = 0.0 

    chat_model = create_chat_model(llm_config)

    
    optimized_system_prompt = """You are the MPS Support Assistant.
- Answer ONLY using the provided documentation.
- If the information is not present in the documentation, respond ONLY with:
  I do not have enough internal information to answer that.

- Do NOT use prior knowledge.
- Do NOT guess or infer information.
- Do NOT add external examples.
- Do NOT mention things like "not mentioned in documentation".

Return the response STRICTLY in the following format:

SHORT_ANSWER:
A short 1–2 sentence answer.

DETAILED_ANSWER:
A more detailed explanation using bullet points or numbered steps if necessary.Use code blocks for commands.

Rules:
- Always start with SHORT_ANSWER:
- Then provide DETAILED_ANSWER:
- Do not add any other sections.
- Do not use markdown headers like ###.
- Do not use HTML tags like <details>.
- Do not repeat SHORT_ANSWER at the end.
"""

    messages = [SystemMessage(content=optimized_system_prompt)]

    # Add History
    if history and isinstance(history, list):
        for msg in history:
            role = msg.get("role")
            content = msg.get("content")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    # Fix 3: Removed the conflicting formatting rules from the HumanMessage
    messages.append(
        HumanMessage(content=f"""DOCUMENTATION:
{context}

USER QUESTION:
{user_query}

INSTRUCTION: 
Apply the ### SHORT_ANSWER and <details> structure to the documentation above. Do not add any text outside this structure.""")
    )

    full_response = ""
    for chunk in chat_model.stream(messages):
        token = chunk.content
        if not token:
            continue
        
        
        banned_phrases = ["Note:", "(Code block", "[No detailed", "Detailed steps", "(Details","Incorrect answers:",
        "If the documentation does not",
        "this will not work"]
        if any(phrase in token for phrase in banned_phrases):
            break
            
        full_response += token
        yield token
def detect_ticket_intent(user_message, llm_config=None):

    chat_model = create_chat_model(llm_config)

    prompt = f"""
Determine if the user wants to create a support ticket.

User message: "{user_message}"

Reply ONLY with YES or NO.
"""

    response = chat_model.invoke([HumanMessage(content=prompt)])

    result = response.content.strip()

    return "YES" in result.upper()