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
            # 1. Identify active repositories from User Events
            events_url = f"https://api.github.com/users/{username}/events"
            params = {"per_page": 100}
            
            active_repos = set()
            activity_log = []
            page = 1
            
            # Scan events to find active repos and non-commit events
            while True:
                response = await client.get(events_url, headers=headers, params={**params, "page": page})
                response.raise_for_status()
                events = response.json()
                
                if not events:
                    break
                
                for event in events:
                    created_at = event.get("created_at", "")[:10] # YYYY-MM-DD
                    
                    if created_at == date:
                        repo_name = event.get("repo", {}).get("name")
                        event_type = event.get("type")
                        
                        if event_type == "PushEvent":
                            if repo_name:
                                active_repos.add(repo_name)
                        elif event_type == "CreateEvent":
                            # Also check commits for new branches/tags just in case
                            if repo_name:
                                active_repos.add(repo_name)
                            # Log creation event
                            ref_type = event.get("payload", {}).get("ref_type")
                            ref = event.get("payload", {}).get("ref", "unknown")
                            activity_log.append(f"Created {ref_type} '{ref}' in {repo_name}")
                        elif event_type == "PullRequestEvent":
                            repo_name = event.get("repo", {}).get("name", "unknown")
                            action = event.get("payload", {}).get("action")
                            title = event.get("payload", {}).get("pull_request", {}).get("title")
                            activity_log.append(f"PR {action} in {repo_name}: {title}")
                            
                    elif created_at < date:
                        # Events are sorted by date
                        break
                else:
                    # Continue to next page if we haven't broken out of the loop (meaning we haven't passed the date yet)
                    page += 1
                    if page > 3: break
                    continue
                break # Break out of while loop if we hit older dates

            # 2. Fetch specific commits for active repositories
            for repo in active_repos:
                try:
                    commits_url = f"https://api.github.com/repos/{repo}/commits"
                    commit_params = {
                        "author": username,
                        "since": f"{date}T00:00:00Z",
                        "until": f"{date}T23:59:59Z",
                        "per_page": 100
                    }
                    
                    # DEBUG: Fetching commits for repo
                    print(f"DEBUG: Fetching commits for {repo}", file=sys.stderr)
                    
                    resp = await client.get(commits_url, headers=headers, params=commit_params)
                    if resp.status_code == 200:
                        commits = resp.json()
                        print(f"DEBUG: Found {len(commits)} commits in {repo}", file=sys.stderr)
                        
                        for commit in commits:
                            msg = commit.get("commit", {}).get("message", "").split('\n')[0] # First line only
                            sha = commit.get("sha", "")[:7]
                            activity_log.append(f"Commit in {repo}: {msg} ({sha})")
                    else:
                        print(f"DEBUG: Failed to fetch commits for {repo}: {resp.status_code}", file=sys.stderr)
                        
                except Exception as repo_err:
                    print(f"DEBUG: Error fetching commits for {repo}: {repo_err}", file=sys.stderr)

            return "\n".join(activity_log) if activity_log else "No GitHub activity found for this date."
        except Exception as e:
            return f"Error fetching GitHub data: {str(e)}"

if __name__ == "__main__":
    mcp.run()
