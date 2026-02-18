from app.services.retrieval_service import retrieve_chunks
from app.services.llm_service import get_answers

if __name__=="__main__":
    query = "what is JCore?"
    print("\nRunning full RAG Pipeline ...\n")
    chunks,is_domain=retrieve_chunks(query,top_k=3)
    if not chunks:
        print(" No relevant chunks found.")
    else:
        print("Retrieved Chunks:\n")
        for i, chunk in enumerate(chunks,1):
            print(f"{i}. {chunk}\n")
        context="\n\n".join(chunks)
        answer=get_answers(context,query)
        print("\n--- LLM answer ---\n")
        print(answer)