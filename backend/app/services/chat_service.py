from app.services.retrieval_serviceimport retrieve_context
from app.services.llm_service import generate_answer

def run_chat_workflow(user_query:str)->str:
    context=retrieve_context(user_query)
    if not context or context.strip()=="":
        return "I'm sorry,I couldn't find any specific answer on that question
    final_response=generate_answer(context,user_query)
    return final_response
    