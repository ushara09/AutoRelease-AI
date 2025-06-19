import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import requests
import re
import base64
import json
from typing import List
from openai import OpenAI

load_dotenv()

JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8080", "http://127.0.0.1:8080", "null"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateReleaseNoteRequest(BaseModel):
    repo: str
    jira_tickets: List[str]  # Changed to support multiple tickets

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

def format_jira_ticket_for_prompt(jira_ticket):
    """
    Format JIRA ticket data for inclusion in the prompt
    """
    formatted = f"""
Ticket Key: {jira_ticket.get('key', 'N/A')}
Summary: {jira_ticket.get('summary', 'N/A')}
Status: {jira_ticket.get('status', 'N/A')}
Priority: {jira_ticket.get('priority', 'N/A')}
Issue Type: {jira_ticket.get('issue_type', 'N/A')}
Assignee: {jira_ticket.get('assignee', 'N/A')}
Reporter: {jira_ticket.get('reporter', 'N/A')}
Created: {jira_ticket.get('created', 'N/A')}
Updated: {jira_ticket.get('updated', 'N/A')}

Description:
{jira_ticket.get('description', 'No description available')}
"""
    return formatted.strip()

def format_multiple_jira_tickets_for_prompt(jira_tickets):
    """
    Format multiple JIRA tickets data for inclusion in the prompt
    """
    if not jira_tickets:
        return "No JIRA tickets available"
    
    formatted_tickets = []
    for i, ticket in enumerate(jira_tickets, 1):
        ticket_section = f"=== JIRA TICKET {i} ===\n"
        ticket_section += format_jira_ticket_for_prompt(ticket)
        ticket_section += "\n"
        formatted_tickets.append(ticket_section)
    
    return "\n".join(formatted_tickets)

def format_commit_diffs_for_prompt(commit_diffs):
    """
    Format commit diffs data for inclusion in the prompt (optimized for token limit)
    """
    if not commit_diffs:
        return "No commit diffs available"
    
    formatted_diffs = []
    max_commits = 10  # Limit number of commits to prevent overflow
    max_files_per_commit = 15  # Limit files per commit
    max_patch_lines = 30  # Limit patch lines per file
    
    for i, commit in enumerate(commit_diffs[:max_commits]):
        commit_section = f"Commit {i+1}: {commit.get('sha', 'N/A')[:8]}\nMessage: {commit.get('message', 'N/A')}\n"
        
        files = commit.get('files', [])[:max_files_per_commit]
        if len(commit.get('files', [])) > max_files_per_commit:
            commit_section += f"Files: {len(files)} shown (of {len(commit.get('files', []))} total)\n"
        else:
            commit_section += f"Files: {len(files)}\n"
        
        for file_info in files:
            filename = file_info.get('filename', 'Unknown')
            patch = file_info.get('patch', '')
            
            # Skip binary files or very large patches
            if not patch or 'Binary file' in patch:
                commit_section += f"- {filename}: Binary/No diff\n"
                continue
            
            # Clean and truncate patch
            patch_lines = patch.split('\n')
            
            # Remove diff headers and keep only meaningful content
            clean_lines = []
            for line in patch_lines:
                # Skip diff metadata lines
                if line.startswith('@@') or line.startswith('diff --git') or line.startswith('index '):
                    continue
                # Keep additions, deletions, and context
                if line.startswith(('+', '-', ' ')) and len(line.strip()) > 1:
                    # Remove excessive whitespace but keep indentation structure
                    clean_line = line.rstrip()
                    if len(clean_line) > 120:  # Truncate very long lines
                        clean_line = clean_line[:117] + "..."
                    clean_lines.append(clean_line)
            
            # Limit number of lines
            if len(clean_lines) > max_patch_lines:
                truncated_lines = clean_lines[:max_patch_lines]
                truncated_lines.append(f"... ({len(clean_lines) - max_patch_lines} more lines)")
                clean_lines = truncated_lines
            
            if clean_lines:
                commit_section += f"- {filename}:\n"
                commit_section += '\n'.join(clean_lines[:max_patch_lines]) + '\n'
            else:
                commit_section += f"- {filename}: No significant changes\n"
        
        commit_section += "\n"
        formatted_diffs.append(commit_section)
    
    if len(commit_diffs) > max_commits:
        formatted_diffs.append(f"... and {len(commit_diffs) - max_commits} more commits")
    
    return "\n".join(formatted_diffs)

def call_openai_with_prompt(prompt_text):
    """
    Send the populated prompt to OpenAI and return the response
    """
    try:
        logger.info("Sending prompt to OpenAI...")
        
        # Estimate token count (rough approximation: 1 token ≈ 4 characters)
        estimated_tokens = len(prompt_text) // 4
        max_tokens_for_prompt = 6000  # Leave room for response
        
        # If prompt is too long, truncate it intelligently
        if estimated_tokens > max_tokens_for_prompt:
            logger.warning(f"Prompt estimated at {estimated_tokens} tokens, truncating to fit context window")
            # Truncate to approximately 6000 tokens worth of characters
            max_chars = max_tokens_for_prompt * 4
            
            # Try to truncate at a natural boundary (end of a commit or section)
            truncation_point = max_chars
            for boundary in ["\n\nCommit ", "\nCommit ", "\n\n", "\n"]:
                last_boundary = prompt_text.rfind(boundary, 0, max_chars)
                if last_boundary > max_chars * 0.8:  # Don't truncate too aggressively
                    truncation_point = last_boundary
                    break
            
            prompt_text = prompt_text[:truncation_point] + "\n\n[Note: Content truncated due to length limits]"
            logger.info(f"Truncated prompt to approximately {len(prompt_text) // 4} tokens")
        
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",  # Has 128k context window vs 8k for gpt-4
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior technical release note writer. Be concise but comprehensive in your analysis."
                },
                {
                    "role": "user", 
                    "content": prompt_text
                }
            ],
            max_tokens=2000,
            temperature=0.3
        )
        
        logger.info("Successfully received response from OpenAI")
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {str(e)}")
        # If it's still a context length error, try with even more aggressive truncation
        if "context_length_exceeded" in str(e):
            logger.warning("Context length still exceeded, trying with more aggressive truncation")
            # More aggressive truncation
            max_chars = 4000 * 4  # Even more conservative
            if len(prompt_text) > max_chars:
                prompt_text = prompt_text[:max_chars] + "\n\n[Note: Content heavily truncated due to length limits]"
                try:
                    response = client.chat.completions.create(
                        model="gpt-4-turbo-preview",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a senior technical release note writer. Be concise but comprehensive."
                            },
                            {
                                "role": "user", 
                                "content": prompt_text
                            }
                        ],
                        max_tokens=1500,
                        temperature=0.3
                    )
                    logger.info("Successfully received response from OpenAI after aggressive truncation")
                    return response.choices[0].message.content
                except Exception as retry_e:
                    logger.error(f"Even aggressive truncation failed: {str(retry_e)}")
                    raise HTTPException(status_code=500, detail=f"Failed to generate release note even with truncation: {str(retry_e)}")
        
        raise HTTPException(status_code=500, detail=f"Failed to generate release note with OpenAI: {str(e)}")

@app.get("/repositories")
def get_repositories():
    """Get list of repositories for the configured GitHub owner"""
    if not all([GITHUB_TOKEN, GITHUB_OWNER]):
        missing_vars = []
        if not GITHUB_TOKEN:
            missing_vars.append("GITHUB_TOKEN")
        if not GITHUB_OWNER:
            missing_vars.append("GITHUB_OWNER")
        raise HTTPException(
            status_code=500, 
            detail=f"Missing environment variables: {', '.join(missing_vars)}"
        )
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        # Fetch repositories for the user/organization
        repos_url = f"https://api.github.com/users/{GITHUB_OWNER}/repos"
        logger.info(f"Fetching repositories for {GITHUB_OWNER}")
        
        all_repos = []
        page = 1
        
        # Handle pagination
        while True:
            response = requests.get(repos_url, headers=headers, params={
                "per_page": 100,
                "page": page,
                "sort": "updated",
                "direction": "desc"
            })
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch repositories: {response.text}")
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Failed to fetch repositories from GitHub: {response.text}"
                )
            
            repos_batch = response.json()
            if not repos_batch:
                break
                
            all_repos.extend(repos_batch)
            
            if len(repos_batch) < 100:
                break
                
            page += 1
            # Limit to prevent abuse
            if page > 10:
                break
        
        # Extract relevant repository information
        repo_list = []
        for repo in all_repos:
            repo_info = {
                "name": repo.get("name"),
                "full_name": repo.get("full_name"),
                "description": repo.get("description"),
                "private": repo.get("private", False),
                "updated_at": repo.get("updated_at"),
                "language": repo.get("language")
            }
            repo_list.append(repo_info)
        
        logger.info(f"Successfully fetched {len(repo_list)} repositories")
        return {
            "repositories": repo_list,
            "total_count": len(repo_list),
            "owner": GITHUB_OWNER
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while fetching repositories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Network error connecting to GitHub: {str(e)}")

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
    logger.info(f"Received request to generate release note for repo '{GITHUB_OWNER}/{data.repo}' and tickets '{', '.join(data.jira_tickets)}'")
    
    # Check if required environment variables are set
    if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_TOKEN, GITHUB_TOKEN, GITHUB_OWNER, OPENAI_API_KEY]):
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
        if not OPENAI_API_KEY:
            missing_vars.append("OPENAI_API_KEY")
        raise HTTPException(
            status_code=500, 
            detail=f"Missing environment variables: {', '.join(missing_vars)}"
        )
    
    # Type assertions since we validated they're not None above
    assert JIRA_BASE_URL and JIRA_EMAIL and JIRA_TOKEN and GITHUB_TOKEN and GITHUB_OWNER and OPENAI_API_KEY
    
    # Fetch all JIRA tickets content
    jira_tickets_content = []
    failed_tickets = []
    
    for ticket_key in data.jira_tickets:
        try:
            jira_content = fetch_jira_ticket_content(
                JIRA_BASE_URL,
                JIRA_EMAIL,
                JIRA_TOKEN,
                ticket_key
            )
            jira_tickets_content.append(jira_content)
            logger.info(f"Successfully fetched JIRA ticket content: {ticket_key} - {jira_content['summary']}")
        except Exception as e:
            logger.error(f"Failed to fetch JIRA ticket {ticket_key}: {str(e)}")
            failed_tickets.append(ticket_key)
    
    if not jira_tickets_content:
        raise HTTPException(status_code=500, detail=f"Failed to fetch any JIRA tickets. Failed tickets: {', '.join(failed_tickets)}")
    
    if failed_tickets:
        logger.warning(f"Some tickets failed to fetch: {', '.join(failed_tickets)}")
    
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

    # Create patterns for all tickets and find matching commits
    all_matching_commits = []
    ticket_commit_count = {}
    
    for ticket_key in data.jira_tickets:
        pattern = rf"^\[{re.escape(ticket_key)}\]"
        matching_commits = [
            c for c in all_commits if re.match(pattern, c['commit']['message'])
        ]
        ticket_commit_count[ticket_key] = len(matching_commits)
        all_matching_commits.extend(matching_commits)
        logger.info(f"Found {len(matching_commits)} commits matching pattern '[{ticket_key}]'.")
    
    # Remove duplicates (in case a commit mentions multiple tickets)
    unique_commits = {c['sha']: c for c in all_matching_commits}.values()
    unique_commits = list(unique_commits)
    
    logger.info(f"Total unique commits found: {len(unique_commits)}")

    commit_diffs = []
    for c in unique_commits:
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
        commit_diffs.append({
            "sha": sha,
            "message": c['commit']['message'],
            "files": files
        })

    logger.info(f"Found {len(commit_diffs)} commit diffs to process.")
    
    # Read the prompt template
    try:
        with open("prompt.txt", "r", encoding="utf-8") as f:
            prompt_template = f.read()
        logger.info("Successfully read prompt template")
    except FileNotFoundError:
        logger.error("prompt.txt file not found")
        raise HTTPException(status_code=500, detail="prompt.txt template file not found")
    except Exception as e:
        logger.error(f"Error reading prompt template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading prompt template: {str(e)}")
    
    # Format the data for the prompt
    formatted_jira_tickets = format_multiple_jira_tickets_for_prompt(jira_tickets_content)
    formatted_commit_diffs = format_commit_diffs_for_prompt(commit_diffs)
    
    # Replace placeholders in the prompt template
    populated_prompt = prompt_template.replace(
        "<PASTE_JIRA_TICKET_CONTENT_HERE>", 
        formatted_jira_tickets
    ).replace(
        "<PASTE_GIT_DIFFS_HERE>", 
        formatted_commit_diffs
    )
    
    logger.info("Successfully populated prompt template with JIRA and GitHub data")
    
    # Send to OpenAI and get the response
    release_note = call_openai_with_prompt(populated_prompt)
    
    return {
        "success": True,
        "release_note": release_note,
        "jira_tickets": data.jira_tickets,
        "successful_tickets": [ticket['key'] for ticket in jira_tickets_content],
        "failed_tickets": failed_tickets,
        "ticket_commit_counts": ticket_commit_count,
        "repository": f"{GITHUB_OWNER}/{data.repo}",
        "commits_processed": len(commit_diffs)
    }

@app.post("/generate-release-note-debug/")
def generate_release_note_debug(data: GenerateReleaseNoteRequest):
    """
    Debug endpoint that returns raw JIRA tickets and commit diffs without calling OpenAI
    """
    logger.info(f"Received debug request for repo '{GITHUB_OWNER}/{data.repo}' and tickets '{', '.join(data.jira_tickets)}'")
    
    # Check if required environment variables are set (excluding OpenAI for debug)
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
    
    # Fetch all JIRA tickets content
    jira_tickets_content = []
    failed_tickets = []
    
    for ticket_key in data.jira_tickets:
        try:
            jira_content = fetch_jira_ticket_content(
                JIRA_BASE_URL,
                JIRA_EMAIL,
                JIRA_TOKEN,
                ticket_key
            )
            jira_tickets_content.append(jira_content)
            logger.info(f"Successfully fetched JIRA ticket content: {ticket_key} - {jira_content['summary']}")
        except Exception as e:
            logger.error(f"Failed to fetch JIRA ticket {ticket_key}: {str(e)}")
            failed_tickets.append(ticket_key)
    
    if not jira_tickets_content:
        raise HTTPException(status_code=500, detail=f"Failed to fetch any JIRA tickets. Failed tickets: {', '.join(failed_tickets)}")
    
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

    # Create patterns for all tickets and find matching commits
    all_matching_commits = []
    ticket_commit_count = {}
    
    for ticket_key in data.jira_tickets:
        pattern = rf"^\[{re.escape(ticket_key)}\]"
        matching_commits = [
            c for c in all_commits if re.match(pattern, c['commit']['message'])
        ]
        ticket_commit_count[ticket_key] = len(matching_commits)
        all_matching_commits.extend(matching_commits)
        logger.info(f"Found {len(matching_commits)} commits matching pattern '[{ticket_key}]'.")
    
    # Remove duplicates (in case a commit mentions multiple tickets)
    unique_commits = {c['sha']: c for c in all_matching_commits}.values()
    unique_commits = list(unique_commits)

    result = []
    for c in unique_commits:
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
        "jira_tickets": jira_tickets_content,
        "failed_tickets": failed_tickets,
        "ticket_commit_counts": ticket_commit_count,
        "commit_diffs": result
    }

