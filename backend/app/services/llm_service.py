import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpoint,ChatHuggingFace
from langchain_core.messages import SystemMessage,HumanMessage
 
load_dotenv()
llm=HuggingFaceEndpoint(
repo_id="HuggingFaceH4/zephyr-7b-beta",
huggingfacehub_api_token=os.getenv("HF_TOKEN"),
task="conversational",
temperature=0.1,
stop_sequences=["USER QUESTION:", "USER:", "\n\nHuman:"],
)
chat_model=ChatHuggingFace(llm=llm)
#main function that generates answers
def get_answers(history:str,context:str,user_query:str,)->str:
    formatted_prompt = (
        f"Use the following pieces of context to answer the question.\n"
        f"--- CONTEXT ---\n{context}\n\n"
        f"--- CHAT HISTORY ---\n{history}\n\n"
        f"USER QUESTION: {user_query}\n\n"
        f"ASSISTANT RESPONSE:"
    )
    messages=[
        SystemMessage(content=(
            "You are MPS Support Assistant.\n\n"
            "You are an information extraction assistant.\n\n"
            "Your task is to extract ONLY the exact sentence(s) from the context "
            "that directly answer the user's question.\n\n"
            "STRICT RULES:\n"
            "- Do NOT summarize.\n"
            "- Do NOT include extra details.\n"
            "- Do NOT add names, links, emails, phone numbers unless explicitly asked.\n"
            "- If multiple sentences exist, return only the most relevant one.\n"
            "- Keep answer under 3 sentences.\n"
            "- If answer not clearly present, say: "
            "'I do not have enough internal information to answer that.'"
        )),
        HumanMessage(content=(
    f"Context:\n{context}\n\n"
    f"Question: {user_query}\n\n"
    "Return ONLY the specific answer."
))

    ]
    response=chat_model.invoke(messages)
    return response.content
    


def escalation_message()->str:
    return (
         "I’m unable to resolve your issue with the available information. "
        "Would you like me to raise a support ticket for you?"
    )