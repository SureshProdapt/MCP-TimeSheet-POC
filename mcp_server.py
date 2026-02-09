import os
import sys
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastMCP
mcp = FastMCP("Timesheet Data Fetcher")

# Configuration
JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

@mcp.tool()
async def get_jira_activity(project_key: str, date: str) -> str:
    """
    Fetches Jira issues updated on a specific date for a given project.
    
    Args:
        project_key: The Jira project key (e.g., 'PROJ').
        date: The date to filter by (YYYY-MM-DD).
    """
    if not JIRA_URL or not JIRA_API_TOKEN:
        return f"Error: Jira credentials not configured. Please check your .env file."

    jql = f"project = {project_key} AND updated >= '{date}' AND updated < '{date} 23:59'"
    
    # API v3 search/jql endpoint
    url = f"{JIRA_URL}/rest/api/3/search/jql"
    
    async with httpx.AsyncClient() as client:
        try:
            # Use POST /rest/api/3/search/jql
            # Payload requires 'jql' and 'fields'
            payload = {
                "jql": jql,
                "fields": ["summary", "status", "updated"],
                "maxResults": 50
            }
            
            # DEBUG: Print configuration (masking token)
            print(f"DEBUG: URL={url}, User={JIRA_EMAIL}", file=sys.stderr)

            response = await client.post(
                url,
                json=payload,
                auth=(JIRA_EMAIL, JIRA_API_TOKEN),
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )
            
            # DEBUG: Print raw response
            print(f"DEBUG: Status={response.status_code}", file=sys.stderr)
            if response.status_code != 200:
                print(f"DEBUG: Response Body={response.text}", file=sys.stderr)
                
            response.raise_for_status()
            data = response.json()
            
            # DEBUG: Print found issues count
            issues_found = data.get("issues", [])
            print(f"DEBUG: Found {len(issues_found)} issues", file=sys.stderr)
            
            issues = []
            for issue in issues_found:
                key = issue.get("key")
                summary = issue["fields"].get("summary")
                status = issue["fields"]["status"].get("name")
                issues.append(f"{key}: {summary} ({status})")
            
            return "\n".join(issues) if issues else "No Jira activity found."
        except Exception as e:
            return f"Error fetching Jira data: {str(e)}"

@mcp.tool()
async def get_github_activity(username: str, date: str) -> str:
    """
    Fetches GitHub activity for a user across all repositories on a specific date.
    
    Args:
        username: The GitHub username.
        date: The date to filter by (YYYY-MM-DD).
    """
    if not GITHUB_TOKEN:
        return f"Error: GitHub token not configured. Please check your .env file."

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Fetch user events (300 events is a reasonable daily limit to check)
            # This endpoint lists public events performed by a user
            # For private events, the token must have repo scope and we use /users/{username}/events
            events_url = f"https://api.github.com/users/{username}/events"
            params = {"per_page": 100} 
            
            activity_log = []
            page = 1
            
            while True:
                response = await client.get(events_url, headers=headers, params={**params, "page": page})
                response.raise_for_status()
                events = response.json()
                
                if not events:
                    break
                
                for event in events:
                    created_at = event.get("created_at", "")[:10] # YYYY-MM-DD
                    
                    if created_at == date:
                        event_type = event.get("type")
                        repo_name = event.get("repo", {}).get("name", "unknown")
                        
                        if event_type == "PushEvent":
                            commits = event.get("payload", {}).get("commits", [])
                            for commit in commits:
                                msg = commit.get("message")
                                activity_log.append(f"Pushed to {repo_name}: {msg}")
                        elif event_type == "PullRequestEvent":
                            action = event.get("payload", {}).get("action")
                            title = event.get("payload", {}).get("pull_request", {}).get("title")
                            activity_log.append(f"PR {action} in {repo_name}: {title}")
                        elif event_type == "CreateEvent":
                             ref_type = event.get("payload", {}).get("ref_type")
                             activity_log.append(f"Created {ref_type} in {repo_name}")
                    
                    elif created_at < date:
                        # Events are sorted by date, so if we go past the date, we can stop
                        return "\n".join(activity_log) if activity_log else "No GitHub activity found for this date."

                page += 1
                if page > 3: # Limit to 3 pages to avoid excessive requests
                    break
            
            return "\n".join(activity_log) if activity_log else "No GitHub activity found for this date."
        except Exception as e:
            return f"Error fetching GitHub data: {str(e)}"

if __name__ == "__main__":
    mcp.run()
