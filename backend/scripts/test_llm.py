from app.services.llm_service import get_answers 
fake_context="HighWirePress provides publishing platform services."
print("\n----Test 1: Domain Question----\n")
print(get_answers(fake_context,"What service does HighWirePress provide?"))
print("\n----Test 2: Out of Domain Question----\n")
print(get_answers(fake_context,"What is the capital of France?"))



# from app.services.llm_service import get_answers

# if __name__ == "__main__":
#     context = """
#     To install the HighWire extension:
#     1. Log in using your @highwirepress.com account.
#     2. Visit the Chrome Web Store link.
#     3. Click Install.
#     """

#     query = "How do I install the extension?"

#     response = get_answers(context, query)

#     print("\n--- LLM Response ---\n")
#     print(response)
