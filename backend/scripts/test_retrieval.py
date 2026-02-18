from app.services.retrieval_service import retrieve_chunks

if __name__ == "__main__":
    query = "How do I install the extension?"

    chunks = retrieve_chunks(query, top_k=3)

    print("\n--- Retrieved Chunks ---\n")

    if not chunks:
        print("❌ No chunks retrieved")
    else:
        for i, chunk in enumerate(chunks, 1):
            print(f"{i}. {chunk}\n")
           

