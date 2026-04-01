import requests
import json

# FastAPI ka local URL
BASE_URL = "http://127.0.0.1:8000/api/chat"

def test_bot(name, email, query, scenario_name):
    print(f"\n--- Testing Scenario: {scenario_name} ---")
    payload = {
        "name": name,
        "email": email,
        "query": query
    }
    
    try:
        response = requests.post(BASE_URL, json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"User: {query}")
            print(f"Bot: {data['answer']}")
            if data.get('sources'):
                print(f"Sources Found: {len(data['sources'])} chunks")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    # Test User Details
    user_email = "user_tester@highwirepress.com"
    user_name = "user"

    # 1. Technical Question (RAG Test)
    test_bot(user_name, user_email, "Who is Naresh Kumar Singh?", "Initial Technical Query")

    # 2. Context/Memory Question (Memory Test)
    # Isse pata chalega ki bot ko Naresh yaad hai ya nahi
    test_bot(user_name, user_email, "What is his role in JCore?", "Memory/Context Check")

    # 3. Out of Domain Question (Safety Layer Test)
    test_bot(user_name, user_email, "How do I bake a cake?", "Domain Guardrail Test")

    # 4. Another HighWire Product
    test_bot(user_name, user_email, "What is HighWire Reader?", "Specific Product Test")