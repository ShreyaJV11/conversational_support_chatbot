import os
import requests
from requests.auth import HTTPBasicAuth
from app.services.ingestion_service import ingest_file
import logging

logger = logging.getLogger(__name__)

# ==========================================================
# 1. GITHUB CONNECTOR (Codebase)
# ==========================================================

def sync_github_file(repo_url: str, file_path: str, bot_id: int, github_token: str) -> dict:
    """Fetches a raw code file from GitHub and routes it to AST-Aware ingestion."""
    
    # Convert standard GitHub URL to the raw content URL
    raw_url = repo_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    
    headers = {"Authorization": f"token {github_token}"}
    response = requests.get(raw_url, headers=headers)
    
    if response.status_code == 200:
        temp_dir = f"uploads/{bot_id}"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, os.path.basename(file_path))
        
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(response.text)
            
        return ingest_file(
            file_path=temp_path,
            bot_id=bot_id,
            source_system="github",
            source_url=f"{repo_url}/blob/main/{file_path}",
            is_verified=True
        )
    
    logger.error(f"GitHub Sync Failed: {response.status_code} - {response.text}")
    return {"error": "Failed to sync from GitHub"}


# ==========================================================
# 2. JIRA CONNECTOR (Support Tickets)
# ==========================================================

def sync_jira_ticket(jira_domain: str, ticket_id: str, email: str, api_token: str, bot_id: int) -> dict:
    """Fetches ticket details (Title, Description) for RAG support context."""
    
    url = f"https://{jira_domain}.atlassian.net/rest/api/3/issue/{ticket_id}"
    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}
    
    response = requests.get(url, headers=headers, auth=auth)
    
    if response.status_code == 200:
        issue_data = response.json()
        
        # Extract title and description
        title = issue_data.get('fields', {}).get('summary', 'No Title')
        
        # Jira's v3 API uses Atlassian Document Format (ADF) for descriptions.
        # For a production system, you'd parse ADF to text. Here we grab raw data.
        description_raw = issue_data.get('fields', {}).get('description', {})
        description = str(description_raw) 
        
        content = f"JIRA TICKET: {ticket_id}\nTITLE: {title}\nDESCRIPTION: {description}\n"
        
        temp_dir = f"uploads/{bot_id}"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{ticket_id}.txt")
        
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return ingest_file(
            file_path=temp_path,
            bot_id=bot_id,
            source_system="jira",
            source_url=f"https://{jira_domain}.atlassian.net/browse/{ticket_id}",
            is_verified=True
        )
        
    logger.error(f"Jira Sync Failed: {response.status_code} - {response.text}")
    return {"error": "Failed to sync from Jira"}


# ==========================================================
# 3. CONFLUENCE CONNECTOR (Official Documentation)
# ==========================================================

def sync_confluence_page(confluence_domain: str, page_id: str, email: str, api_token: str, bot_id: int) -> dict:
    """Fetches a wiki page, strips HTML, and ingests it as verified documentation."""
    
    url = f"https://{confluence_domain}.atlassian.net/wiki/api/v2/pages/{page_id}?body-format=storage"
    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}
    
    response = requests.get(url, headers=headers, auth=auth)
    
    if response.status_code == 200:
        page_data = response.json()
        title = page_data.get('title', 'Untitled Page')
        html_body = page_data.get('body', {}).get('storage', {}).get('value', '')
        
        # Quick and dirty HTML strip (Use BeautifulSoup in production for cleaner text)
        import re
        clean_text = re.sub(r'<[^>]+>', ' ', html_body)
        
        content = f"CONFLUENCE PAGE: {title}\n\n{clean_text}"
        
        temp_dir = f"uploads/{bot_id}"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"confluence_{page_id}.txt")
        
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return ingest_file(
            file_path=temp_path,
            bot_id=bot_id,
            source_system="confluence",
            source_url=f"https://{confluence_domain}.atlassian.net/wiki/spaces/SPACE/pages/{page_id}",
            is_verified=True
        )
        
    logger.error(f"Confluence Sync Failed: {response.status_code} - {response.text}")
    return {"error": "Failed to sync from Confluence"}


# ==========================================================
# 4. SALESFORCE CONNECTOR (Customer Cases)
# ==========================================================

def sync_salesforce_case(instance_url: str, access_token: str, case_id: str, bot_id: int) -> dict:
    """Fetches a Salesforce Case by ID and ingests the subject and description."""
    
    url = f"{instance_url}/services/data/v58.0/sobjects/Case/{case_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        case_data = response.json()
        subject = case_data.get("Subject", "No Subject")
        description = case_data.get("Description", "No Description")
        
        content = f"SALESFORCE CASE: {case_id}\nSUBJECT: {subject}\nDESCRIPTION: {description}\n"
        
        temp_dir = f"uploads/{bot_id}"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"sf_{case_id}.txt")
        
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return ingest_file(
            file_path=temp_path,
            bot_id=bot_id,
            source_system="salesforce",
            source_url=f"{instance_url}/lightning/r/Case/{case_id}/view",
            is_verified=True
        )

    logger.error(f"Salesforce Sync Failed: {response.status_code} - {response.text}")
    return {"error": "Failed to sync from Salesforce"}