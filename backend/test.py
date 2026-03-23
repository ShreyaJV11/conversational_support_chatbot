from app.services.graph_service import GraphService

try:
    graph = GraphService()
    emails = graph.get_unread_emails()

    print("✅ SUCCESS: Connected to Graph API")
    print("Emails:", emails)

except Exception as e:
    print("❌ ERROR OCCURRED")
    print(str(e))