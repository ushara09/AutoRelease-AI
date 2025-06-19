import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import requests
import re
import base64

load_dotenv()

JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")

def convert_adf_to_text(adf_content):
    """
    Convert Atlassian Document Format (ADF) to plain text
    
    Args:
        adf_content: ADF content (list or dict)
    
    Returns:
        str: Plain text representation
    """
    if not adf_content:
        return ""
    
    def process_node(node):
        if isinstance(node, str):
            return node
        
        if not isinstance(node, dict):
            return ""
        
        node_type = node.get('type', '')
        content = node.get('content', [])
        text = node.get('text', '')
        
        if node_type == 'text':
            return text
        elif node_type == 'hardBreak':
            return '\n'
        elif node_type == 'paragraph':
            paragraph_text = ''.join(process_node(child) for child in content)
            return paragraph_text + '\n\n' if paragraph_text.strip() else ''
        elif node_type in ['orderedList', 'bulletList']:
            list_text = ''
            for i, item in enumerate(content):
                if item.get('type') == 'listItem':
                    item_text = process_node(item)
                    if node_type == 'orderedList':
                        list_text += f"{i+1}. {item_text}"
                    else:
                        list_text += f"• {item_text}"
            return list_text
        elif node_type == 'listItem':
            item_text = ''.join(process_node(child) for child in content).strip()
            return item_text + '\n'
        elif node_type in ['heading', 'codeBlock', 'blockquote']:
            return ''.join(process_node(child) for child in content) + '\n\n'
        elif content:
            # For any other node type with content, process children
            return ''.join(process_node(child) for child in content)
        
        return ''
    
    if isinstance(adf_content, list):
        return ''.join(process_node(node) for node in adf_content).strip()
    else:
        return process_node(adf_content).strip()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateReleaseNoteRequest(BaseModel):
    repo: str
    jira_ticket: str

def fetch_jira_ticket_content(jira_base_url: str, jira_email: str, jira_api_token: str, ticket_key: str):
    """
    Fetch JIRA ticket content using JIRA REST API
    
    Args:
        jira_base_url: Base URL of JIRA instance (e.g., "https://company.atlassian.net")
        jira_email: Email address of JIRA user
        jira_api_token: JIRA API token for authentication
        ticket_key: JIRA ticket key (e.g., "PROJ-123")
    
    Returns:
        dict: JIRA ticket data including summary, description, status, etc.
    """
    logger.info(f"Fetching JIRA ticket content for: {ticket_key}")
    
    # Create basic auth string (email:api_token encoded in base64)
    auth_string = f"{jira_email}:{jira_api_token}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # JIRA REST API endpoint to get issue details
    jira_api_url = f"{jira_base_url.rstrip('/')}/rest/api/3/issue/{ticket_key}"
    
    try:
        logger.info(f"Making request to JIRA API: {jira_api_url}")
        response = requests.get(jira_api_url, headers=headers)
        
        if response.status_code == 200:
            ticket_data = response.json()
            logger.info(f"Successfully fetched JIRA ticket: {ticket_key}")
            
            # Extract relevant information
            fields = ticket_data.get('fields', {})
            
            # Convert ADF description to human-readable text
            description_adf = fields.get('description', {}).get('content', []) if fields.get('description') else []
            description_text = convert_adf_to_text(description_adf)
            
            result = {
                "key": ticket_data.get('key'),
                "summary": fields.get('summary'),
                "description": description_text,
                "status": fields.get('status', {}).get('name'),
                "priority": fields.get('priority', {}).get('name'),
                "assignee": fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None,
                "reporter": fields.get('reporter', {}).get('displayName'),
                "created": fields.get('created'),
                "updated": fields.get('updated'),
                "issue_type": fields.get('issuetype', {}).get('name')
            }
            
            return result
            
        elif response.status_code == 401:
            logger.error("JIRA authentication failed - check email and API token")
            raise HTTPException(status_code=401, detail="JIRA authentication failed. Check your email and API token.")
        elif response.status_code == 404:
            logger.error(f"JIRA ticket not found: {ticket_key}")
            raise HTTPException(status_code=404, detail=f"JIRA ticket '{ticket_key}' not found.")
        else:
            logger.error(f"JIRA API request failed with status {response.status_code}: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch JIRA ticket: {response.text}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while connecting to JIRA: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Network error connecting to JIRA: {str(e)}")

@app.get("/test-jira/{ticket_key}")
def test_jira_connection(ticket_key: str):
    """Test endpoint to verify JIRA connection using environment variables"""
    # Using environment variables
    if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_TOKEN]):
        missing_vars = []
        if not JIRA_BASE_URL:
            missing_vars.append("JIRA_BASE_URL")
        if not JIRA_EMAIL:
            missing_vars.append("JIRA_EMAIL")
        if not JIRA_TOKEN:
            missing_vars.append("JIRA_TOKEN")
        raise HTTPException(
            status_code=500, 
            detail=f"Missing environment variables: {', '.join(missing_vars)}"
        )
    
    # Type assertions since we validated they're not None above
    assert JIRA_BASE_URL and JIRA_EMAIL and JIRA_TOKEN
    return fetch_jira_ticket_content(JIRA_BASE_URL, JIRA_EMAIL, JIRA_TOKEN, ticket_key)

@app.post("/generate-release-note/")
def generate_release_note(data: GenerateReleaseNoteRequest):
    logger.info(f"Received request to generate release note for repo '{GITHUB_OWNER}/{data.repo}' and ticket '{data.jira_ticket}'")
    
    # Check if required environment variables are set
    if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_TOKEN, GITHUB_TOKEN, GITHUB_OWNER]):
        missing_vars = []
        if not JIRA_BASE_URL:
            missing_vars.append("JIRA_BASE_URL")
        if not JIRA_EMAIL:
            missing_vars.append("JIRA_EMAIL")
        if not JIRA_TOKEN:
            missing_vars.append("JIRA_TOKEN")
        if not GITHUB_TOKEN:
            missing_vars.append("GITHUB_TOKEN")
        if not GITHUB_OWNER:
            missing_vars.append("GITHUB_OWNER")
        raise HTTPException(
            status_code=500, 
            detail=f"Missing environment variables: {', '.join(missing_vars)}"
        )
    
    # Type assertions since we validated they're not None above
    assert JIRA_BASE_URL and JIRA_EMAIL and JIRA_TOKEN and GITHUB_TOKEN and GITHUB_OWNER
    
    # First, fetch JIRA ticket content
    try:
        jira_content = fetch_jira_ticket_content(
            JIRA_BASE_URL,
            JIRA_EMAIL,
            JIRA_TOKEN,
            data.jira_ticket
        )
        logger.info(f"Successfully fetched JIRA ticket content: {jira_content['summary']}")
    except Exception as e:
        logger.error(f"Failed to fetch JIRA ticket content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch JIRA ticket: {str(e)}")
    
    # Continue with GitHub commit fetching
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    commits_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{data.repo}/commits"
    all_commits = []
    page = 1

    # Fetch all commits with pagination (up to 1000 commits)
    logger.info("Fetching commits from GitHub...")
    while True:
        resp = requests.get(commits_url, headers=headers, params={"per_page": 100, "page": page})
        logger.info(f"Requested page {page} of commits. Status: {resp.status_code}")
        if resp.status_code != 200:
            logger.error(f"Failed to fetch commits from GitHub: {resp.text}")
            raise HTTPException(status_code=resp.status_code, detail="Failed to fetch commits from GitHub.")
        batch = resp.json()
        if not batch:
            logger.info("No more commits found, ending pagination.")
            break
        all_commits.extend(batch)
        if len(batch) < 100:
            logger.info("Last page of commits reached.")
            break
        page += 1
        if page > 10:
            logger.warning("Hard limit of 1000 commits reached, stopping pagination to prevent abuse.")
            break

    logger.info(f"Total commits fetched: {len(all_commits)}")

    pattern = rf"^\[{re.escape(data.jira_ticket)}\]"
    matching_commits = [
        c for c in all_commits if re.match(pattern, c['commit']['message'])
    ]
    logger.info(f"Found {len(matching_commits)} commits matching pattern '[{data.jira_ticket}]'.")

    result = []
    for c in matching_commits:
        sha = c['sha']
        commit_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{data.repo}/commits/{sha}"
        logger.info(f"Fetching diff for commit {sha}...")
        commit_resp = requests.get(commit_url, headers=headers)
        if commit_resp.status_code != 200:
            logger.warning(f"Failed to fetch diff for commit {sha}: {commit_resp.text}")
            continue
        commit_data = commit_resp.json()
        files = [
            {
                "filename": f.get("filename", ""),
                "patch": f.get("patch", ""),
            }
            for f in commit_data.get("files", [])
        ]
        logger.info(f"Commit {sha}: {len(files)} files with diffs.")
        result.append({
            "sha": sha,
            "message": c['commit']['message'],
            "files": files
        })

    logger.info(f"Returning {len(result)} commit diffs to client.")
    return {
        "jira_ticket": jira_content,
        "commit_diffs": result
    }

