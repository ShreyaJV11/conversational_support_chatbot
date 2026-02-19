import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpoint,ChatHuggingFace
from langchain_core.messages import SystemMessage,HumanMessage
 
load_dotenv()
llm=HuggingFaceEndpoint(
repo_id="HuggingFaceH4/zephyr-7b-beta",
huggingfacehub_api_token=os.getenv("HF_TOKEN"),
task="conversational",
temperature=0.3
)
chat_model=ChatHuggingFace(llm=llm)
#main function that generates answers
def get_answers(history:str,context:str,user_query:str,)->str:
    messages=[
        SystemMessage(content=(
            "You are a HighWire Support Bot. Use the PROVIDED CONTEXT ONLY. "
            "1. Answer ONLY using the provided context.\n"
            "2. Do NOT use external knowledge.\n"
            "3. Do NOT make assumptions.\n"
            "4. If the answer is not clearly present in the context, respond with:\n"
            "   'I do not have enough internal information to answer that.'\n"
            "5. If the question is unrelated to HighWirePress or its systems, respond with:\n"
            "   'Sorry, I can only answer questions related to HighWirePress systems and services.'\n"
            "6. If the question is vague or ambiguous, ask the user to clarify.\n"
            "7. Keep answers concise and professional.\n\n"
           
        )),
        HumanMessage(content=f"CHAT HISTORY:\n{history}\n\nUSER QUESTION: {user_query}")
    ]
    response=chat_model.invoke(messages)
    return response.content
    


def escalation_message()->str:
    return (
         "I’m unable to resolve your issue with the available information. "
        "Would you like me to raise a support ticket for you?"
    )