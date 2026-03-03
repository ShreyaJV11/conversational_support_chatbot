import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

llm = HuggingFaceEndpoint(
    repo_id="HuggingFaceH4/zephyr-7b-beta",
    huggingfacehub_api_token=os.getenv("HF_TOKEN"),
    task="conversational",
    temperature=0.0,  # even stricter
    max_new_tokens=200
)

chat_model = ChatHuggingFace(llm=llm)


SYSTEM_PROMPT = """
You are MPS Support Assistant.

You are an information extraction assistant.

STRICT RULES:
1. Answer ONLY using the provided context.
2. Return the exact sentence from context that answers the question.
3. Do NOT summarize.
4. Do NOT rephrase.
5. Do NOT add explanations.
6. Do NOT add confidence scores.
7.Do NOT include 'Question:' or 'Answer:' labels.\n"
8.If multiple sentences apply, format as numbered list.\n
9.Do not add assumptions.
- Do NOT say 'Based on the context'.
- Do NOT explain your reasoning.
- DO NOT guess.
Do not speculate.
Do not mention ambiguity unless explicitly in context.
Keep answers concise and professional.
10. If answer is not clearly present, respond EXACTLY with:
I do not have enough internal information to answer that.
"""


def get_answers(history: str, context: str, user_query: str) -> str:
    # 🚨 Safety check before calling LLM
    if not context or context.strip() == "":
        return "I do not have enough internal information to answer that."

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Context:\n{context}\n\n"
            f"Question: {user_query}\n\n"
            "Extract the exact answer sentence from the context."
        ))
    ]

    full_response = ""
    
    # 2. Use the stream method
    # Note: changed chat_model_stream to chat_model.stream
    for chunk in chat_model.stream(messages):
        token = chunk.content
        if not token:
            continue
            
        clean_token = token.replace('"', '')
        full_response += clean_token

        # 3. Mid-stream safety check for "High Confidence" hallucination
        if "high confidence" in full_response.lower():
            # Stop the current stream and send the fallback message
            yield "I do not have enough internal information to answer that."
            return 

        yield clean_token