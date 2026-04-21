import os
import sys

# Ensure Python can find the 'app' module
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.services.ingestion_service import ingest_file

def run_mock_ingestion(bot_id=1):
    base_path = f"uploads/{bot_id}"
    os.makedirs(base_path, exist_ok=True)

    # 1. Fake Confluence Data (HTML)
    conf_path = os.path.join(base_path, "conf_mock.html")
    with open(conf_path, "w", encoding="utf-8") as f:
        f.write("<h1>JCore Deployment Guide</h1><p>Step 1: Clone the repository.</p><p>Step 2: Run docker-compose up.</p>")

    # 2. Fake Jira Data (JSON/Text)
    jira_path = os.path.join(base_path, "jira_mock.txt")
    with open(jira_path, "w", encoding="utf-8") as f:
        f.write('{"issue": "Login Failure", "description": "Users cannot login due to expired JWT token. Fix by refreshing token."}')

    # 3. Fake GitHub Data (Code)
    code_path = os.path.join(base_path, "github_mock.py")
    with open(code_path, "w", encoding="utf-8") as f:
        f.write("def login_user(token):\n    if not token:\n        return 'Token Expired'\n    return 'Success'")

    print("⏳ Ingesting Confluence...")
    ingest_file(conf_path, bot_id, "confluence", "https://confluence.company.com/jcore", True)
    
    print("⏳ Ingesting Jira...")
    ingest_file(jira_path, bot_id, "jira", "https://jira.company.com/browse/BUG-123", True)
    
    print("⏳ Ingesting GitHub...")
    ingest_file(code_path, bot_id, "github", "https://github.com/company/repo/blob/main/login.py", True)

    print("✅ MOCK INGESTION COMPLETE!")

if __name__ == "__main__":
    run_mock_ingestion()