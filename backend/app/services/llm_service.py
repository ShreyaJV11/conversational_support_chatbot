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


SYSTEM_PROMPT = """
You are MPS Support Assistant.

You are an information extraction assistant.

You answer questions using ONLY the provided documentation.

Rules:

1. Use ONLY the provided context.
2. Do NOT invent information.
3. Do NOT guess
4. If multiple instructions exist, return them as a numbered list.
5. Each step must appear on a new line.
6. If commands exist, copy them EXACTLY.
7. If the answer is not present, respond EXACTLY with:
I do not have enough internal information to answer that.


Formatting Rules (IMPORTANT):

Always return the answer in MARKDOWN.

Use the following structure exactly:

SHORT_ANSWER:
A concise 4-5 sentence answer in numbered format if multiple steps are needed in separate lines.

DETAILED_ANSWER:
Provide detailed instructions formatted in markdown.

Formatting guidelines:

• Use numbered lists for steps in separate lines.
• split into multiple steps if needed.
• Use bullet points when listing items in separate lines.
• Use code blocks for commands.
• URLs must be on a separate line.
• Commands must be inside code blocks.
"""


def get_answers(
    history: str,
    context: str,
    user_query: str,
    llm_config: dict = None
):
    """
    Streams response tokens from LLM.
    """

    if not context or context.strip() == "":
        yield "I do not have enough internal information to answer that."
        return

    chat_model = create_chat_model(llm_config)

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    # ✅ Add conversation history
    if history:
        if isinstance(history, list):
            for msg in history:
                role = msg.get("role")
                content = msg.get("content")

                if role == "user":
                    messages.append(HumanMessage(content=content))

                elif role == "assistant":
                    messages.append(AIMessage(content=content))

    # ✅ Add current user query
    messages.append(
        HumanMessage(content=f"""
Use the following documentation to answer the question.

Documentation:
{context}

User Question:
{user_query}

Return the answer EXACTLY in this format:

SHORT_ANSWER:
<1-2 sentence answer>

DETAILED_ANSWER:
<full paragraph with more info>

Only return these two sections.
""")
    )

    full_response = ""

    for chunk in chat_model.stream(messages):
        token = chunk.content
        if not token:
            continue

        clean_token = token.replace('"', '')
        full_response += clean_token

        # 🚨 Mid-stream hallucination safety
        if "high confidence" in full_response.lower():
            yield "I do not have enough internal information to answer that."
            return

        yield clean_token