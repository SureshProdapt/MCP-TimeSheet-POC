import asyncio
from datetime import datetime, timedelta
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
def get_jira_activity(project_key: str, date: str, fetch_worklogs: bool = False) -> str:
    """
    Fetches Jira issues updated on a specific date for a given project.
    Optionally fetches worklogs for each issue.
    Returns a JSON string of list of dicts.
    
    Args:
        project_key: The Jira project key (e.g., 'PROJ').
        date: The date to filter by (YYYY-MM-DD).
    """
    import json
    import sys
    from jira import JIRA

    if not JIRA_URL or not JIRA_API_TOKEN:
        return json.dumps({"error": "Jira credentials not configured."})

    try:
        jira = JIRA(server=JIRA_URL, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))
        jql = f"project = {project_key} AND updated >= '{date}' AND updated < '{date} 23:59'"
        
        # Searching issues
        fields = "summary,status,updated,description,assignee,project"
        issues = jira.search_issues(jql, maxResults=50, fields=fields)
        
        issues_list = []
        for issue in issues:
            key = issue.key
            summary = issue.fields.summary if hasattr(issue.fields, 'summary') else ""
            status = issue.fields.status.name if hasattr(issue.fields, 'status') and issue.fields.status else ""
            project_name = issue.fields.project.name if hasattr(issue.fields, 'project') and issue.fields.project else ""
            
            desc_raw = issue.fields.description if hasattr(issue.fields, 'description') else ""
            description_text = str(desc_raw) if desc_raw else ""
            
            assignee_obj = issue.fields.assignee if hasattr(issue.fields, 'assignee') else None
            assignee_name = assignee_obj.displayName if assignee_obj else "Unassigned"
            updated = issue.fields.updated if hasattr(issue.fields, 'updated') else ""

            worklogs_list = []
            if fetch_worklogs:
                try:
                    worklogs = jira.worklogs(issue.id)
                    for wl in worklogs:
                        author_name = wl.author.displayName if hasattr(wl, 'author') and hasattr(wl.author, 'displayName') else "Unknown"
                        author_email = wl.author.emailAddress if hasattr(wl, 'author') and hasattr(wl.author, 'emailAddress') else ""
                        started_full = wl.started if hasattr(wl, 'started') else ""
                        started_date = started_full[:10] if started_full else ""
                        time_spent_sec = wl.timeSpentSeconds if hasattr(wl, 'timeSpentSeconds') else 0
                        
                        worklogs_list.append({
                            "author": author_name,
                            "author_email": author_email,
                            "date": started_date,
                            "time_spent_seconds": time_spent_sec
                        })
                except Exception as wl_err:
                    print(f"DEBUG: Error fetching worklog for {key}: {wl_err}", file=sys.stderr)

            issues_list.append({
                "key": key,
                "summary": summary,
                "status": status,
                "description": description_text,
                "assignee_name": assignee_name,
                "project": project_name,
                "updated": updated,
                "worklogs": worklogs_list
            })
            
        return json.dumps(issues_list)
    except Exception as e:
        return json.dumps({"error": f"Error fetching Jira data: {str(e)}"})

@mcp.tool()
def get_github_activity(username: str, date: str) -> str:
    """
    Fetches GitHub activity for a user across all repositories on a specific date.
    Returns JSON string.
    
    Args:
        username: The GitHub username.
        date: The date to filter by (YYYY-MM-DD).
    """
    import json
    import sys
    from github import Github
    
    if not GITHUB_TOKEN:
        return json.dumps({"error": "GitHub token not configured."})

    try:
        g = Github(GITHUB_TOKEN)
        activity_list = []
        user = g.get_user(username)
        
        # 1. Fetch other events (PRs, CreateEvents) using the Events API
        try:
            events = user.get_events()
            for event in events:
                if not event.created_at:
                    continue
                created_at = event.created_at.strftime("%Y-%m-%d")
                
                if created_at == date:
                    repo_name = event.repo.name if event.repo else "unknown"
                    event_type = event.type
                    
                    if event_type == "CreateEvent":
                        ref_type = event.payload.get("ref_type") if event.payload else ""
                        ref = event.payload.get("ref", "unknown") if event.payload else "unknown"
                        activity_list.append({
                            "type": event_type,
                            "repo": repo_name,
                            "ref": ref,
                            "ref_type": ref_type,
                            "summary": f"Created {ref_type} '{ref}'",
                            "key": f"create-{ref}-{event.created_at.isoformat()}"
                        })
                    elif event_type == "PullRequestEvent":
                        action = event.payload.get("action") if event.payload else ""
                        pr = event.payload.get("pull_request", {}) if event.payload else {}
                        title = pr.get("title", "")
                        pr_url = pr.get("html_url", "")
                        activity_list.append({
                            "type": event_type,
                            "repo": repo_name,
                            "action": action,
                            "summary": f"PR {action}: {title}",
                            "key": pr_url,
                            "description": f"Pull Request: {title} ({action})"
                        })
                elif created_at < date:
                    # Events are roughly ordered descending by date
                    break
        except Exception as event_err:
            print(f"DEBUG: Error fetching events: {event_err}", file=sys.stderr)

        # 2. Fetch commits for the exact date using Search API
        try:
            query = f"author:{username} committer-date:{date}"
            commits = g.search_commits(query=query, sort='committer-date', order='desc')
            
            seen_commits = set()
            for c in commits[:100]:
                if c.sha in seen_commits: continue
                seen_commits.add(c.sha)
                
                repo_name = c.repository.full_name if hasattr(c, 'repository') and c.repository else "unknown"
                    
                msg = c.commit.message if hasattr(c, 'commit') and c.commit and c.commit.message else ""
                summary = msg.split('\n')[0] if msg else ""
                
                activity_list.append({
                    "type": "Commit",
                    "repo": repo_name,
                    "key": c.sha,
                    "summary": summary,
                    "description": msg
                })
        except Exception as commit_err:
            print(f"DEBUG: Error fetching commits: {commit_err}", file=sys.stderr)

        return json.dumps(activity_list)
    except Exception as e:
        return json.dumps({"error": f"Error fetching GitHub data: {str(e)}"})

if __name__ == "__main__":
    mcp.run()
