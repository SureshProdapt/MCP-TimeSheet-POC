import asyncio
import os
import sys
import json
from datetime import datetime, timedelta
import config
from llm_service import summarize_activity
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def get_dates_in_range(start_date, end_date):
    """
    Returns a list of date strings (YYYY-MM-DD) between start_date and end_date (inclusive).
    start_date and end_date can be datetime objects or strings.
    """
    if isinstance(start_date,  str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    # Handle pandas timestamp or other date objects if needed, assuming date objects for now based on app.py
    
    if isinstance(end_date, str):
         end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    delta = (end_date - start_date).days
    dates = []
    for i in range(delta + 1):
        day = start_date + timedelta(days=i)
        dates.append(day.strftime("%Y-%m-%d"))
    return dates

def find_last_in_progress_task(current_date_str, lookback_days=5):
    """
    Scans logs backwards from current_date to find the most recent 'In Progress' Jira task.
    Returns the task dict or None.
    """
    current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
    
    for i in range(1, lookback_days + 1):
        check_date = current_date - timedelta(days=i)
        check_date_str = check_date.strftime("%Y-%m-%d")
        log_file = f"logs/activity_{check_date_str}.json"
        
        if os.path.exists(log_file):
            try:
                with open(log_file, "r") as f:
                    data = json.load(f)
                    jira_entries = data.get("jira", [])
                    
                    # Look for In Progress tasks
                    for entry in jira_entries:
                        if entry.get("status", "").lower() == "in progress":
                            return entry
            except Exception:
                continue
    return None

async def fetch_timesheet_data(credentials, start_date, end_date):
    """
    Fetches timesheet data using the provided credentials and date range.
    """
    
    # Prepare environment variables for the subprocess
    server_env = os.environ.copy()
    server_env.update(credentials)

    # Define server parameters
    server_params = StdioServerParameters(
        command=sys.executable, 
        args=["mcp_server.py"],
        env=server_env
    )

    timesheet_data = []

    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            dates = get_dates_in_range(start_date, end_date)
            dates.reverse() # Newest to oldest usually prefers, but loop can be distinct. 
            # Actually, standard timesheet is usually chronological? 
            # Existing code did: dates.reverse() # Oldest to newest?
            # client.py L41: dates.reverse()
            # L40 generated [today, today-1...]. so reverse makes it [today-4, ... today].
            
            # Let's process chronological (Oldest to Newest) so "In Progress" logic makes sense if we generated logs sequentially?
            # Actually "find_last_in_progress_task" looks at *logs*.
            # Processing order doesn't strictly matter for *generation* if we rely on stored logs, 
            # BUT efficient carry-over might benefit from knowing the previous day.
            # However, the requirement is to look back 5 days *from the empty day*.
            # So regardless of processing order, we look at the file system.
            
            # We'll stick to Oldest -> Newest (Chronological)
            dates.sort() 

            project_key = credentials.get("JIRA_PROJECT_KEY", "PROJ")
            github_user = credentials.get("GITHUB_USERNAME", "user")

            for date in dates:
                # --- Fetch Jira Data ---
                daily_jira_entries = []
                jira_raw_content = ""
                try:
                    jira_resp = await session.call_tool("get_jira_activity", arguments={
                        "project_key": project_key, 
                        "date": date
                    })
                    jira_raw_content = jira_resp.content[0].text
                    
                    if not jira_raw_content.startswith("Error") and "No Jira activity" not in jira_raw_content:
                        try:
                            jira_entries = json.loads(jira_raw_content)
                            if isinstance(jira_entries, list):
                                daily_jira_entries = jira_entries
                        except json.JSONDecodeError:
                            pass
                except Exception as e:
                    jira_raw_content = f"Error: {str(e)}"

                # --- Fetch GitHub Data ---
                github_raw_content = ""
                daily_github_entries = []
                try:
                    github_resp = await session.call_tool("get_github_activity", arguments={
                        "username": github_user, 
                        "date": date
                    })
                    github_raw_content = github_resp.content[0].text
                    
                    if not github_raw_content.startswith("Error") and "No GitHub activity" not in github_raw_content:
                        try:
                            github_entries = json.loads(github_raw_content)
                            if isinstance(github_entries, list):
                                daily_github_entries = github_entries
                        except:
                            pass
                except Exception as e:
                   github_raw_content = f"Error: {str(e)}"

                # --- Save Raw Data ---
                try:
                    with open(f"logs/activity_{date}.json", "w") as f:
                        json.dump({
                            "date": date,
                            "jira": daily_jira_entries,
                            "github": daily_github_entries,
                            "raw_jira_response": jira_raw_content,
                            "raw_github_response": github_raw_content
                        }, f, indent=2)
                except Exception as e:
                    print(f"Failed to save log for {date}: {e}", file=sys.stderr)

                # --- Select Best Task ---
                selected_entry = None
                if daily_jira_entries:
                    # Prioritize: Done/Completed > In Progress > Others
                    def get_priority(entry):
                        status = entry.get("status", "").lower()
                        if status in ["done", "completed", "verified", "closed", "resolved"]:
                            return 0
                        elif status == "in progress":
                            return 1
                        else:
                            return 2
                    
                    daily_jira_entries.sort(key=get_priority)
                    selected_entry = daily_jira_entries[0]

                # --- Prepare LLM Context ---
                jira_context = ""
                if selected_entry:
                    jira_context = f"{selected_entry['key']}: {selected_entry['summary']}\nDescription: {selected_entry.get('description', '')[:500]}"
                
                github_context = ""
                if daily_github_entries:
                    github_context = "\n".join([f"- {i['summary']}" for i in daily_github_entries])

                # --- Generate Summary ---
                daily_summary = ""
                if selected_entry or github_context:
                    daily_summary = summarize_activity(jira_context, github_context, date)

                # --- Create Timesheet Row ---
                if selected_entry:
                    timesheet_data.append({
                        "Date": date,
                        "Project": selected_entry.get("project", project_key),
                        "Task": selected_entry.get("summary"),
                        "Task Description": selected_entry.get("description", ""),
                        "Status": selected_entry.get("status"),
                        "Remark": daily_summary 
                    })
                elif github_context:
                    # Fallback if no Jira but GitHub activity exists
                    timesheet_data.append({
                        "Date": date,
                        "Project": "GitHub/General",
                        "Task": "General Development Activities",
                        "Task Description": "See Remarks for details.",
                        "Status": "Completed", 
                        "Remark": daily_summary
                    })
                else:
                    # NO ACTIVITY FOUND
                    # Check for "In Progress" logic from previous days
                    last_task = find_last_in_progress_task(date)
                    
                    if last_task:
                        timesheet_data.append({
                            "Date": date,
                            "Project": last_task.get("project", project_key),
                            "Task": last_task.get("summary"),
                            "Task Description": last_task.get("description", ""),
                            "Status": "In Progress",
                            "Remark": f"Continuing work on {last_task.get('summary')}."
                        })
                    else:
                        timesheet_data.append({
                            "Date": date,
                            "Project": "N/A",
                            "Task": "N/A",
                            "Task Description": "No GitHub activity / work found",
                            "Status": "N/A",
                            "Remark": "No activity found."
                        })

    return timesheet_data


def get_data(credentials, start_date=None, end_date=None):
    # Default fallback if not provided (though UI restricts this)
    if not start_date or not end_date:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=5)

    data = asyncio.run(fetch_timesheet_data(credentials, start_date, end_date))
    
    # Sort by Date descending (newest first) for display
    data.sort(key=lambda x: x['Date'], reverse=True)
        
    return data

def _normalize_jira_status(status: str) -> str:
    return (status or "").strip().lower()

def _load_logs_in_range(start_date, end_date):
    dates = get_dates_in_range(start_date, end_date)
    logs = []
    for date_str in dates:
        log_file = f"logs/activity_{date_str}.json"
        if os.path.exists(log_file):
            try:
                with open(log_file, "r") as f:
                    data = json.load(f)
                    data['date'] = date_str
                    logs.append(data)
            except Exception:
                continue
    return logs

def generate_productivity_insights(start_date, end_date) -> dict:
    logs = _load_logs_in_range(start_date, end_date)
    
    total_commits = 0
    commits_per_day = {}
    commits_per_repo = {}
    
    total_jira_touched = 0
    tickets_completed = 0
    tickets_in_progress = 0
    in_progress_durations = {} 
    
    jira_projects = {}
    
    active_days_count = 0
    inactivity_streak = 0
    longest_inactivity_streak = 0
    
    context_switching_days = []
    
    dates = get_dates_in_range(start_date, end_date)
    
    for date_str in dates:
        commits_per_day[date_str] = 0
        
        day_log = next((l for l in logs if l.get('date') == date_str), None)
        
        if not day_log:
            inactivity_streak += 1
            if inactivity_streak > longest_inactivity_streak:
                longest_inactivity_streak = inactivity_streak
            continue
            
        jira_entries = day_log.get('jira', [])
        github_entries = day_log.get('github', [])
        
        if not jira_entries and not github_entries:
            inactivity_streak += 1
            if inactivity_streak > longest_inactivity_streak:
                longest_inactivity_streak = inactivity_streak
        else:
            active_days_count += 1
            inactivity_streak = 0
            
        commits_per_day[date_str] = len(github_entries)
        total_commits += len(github_entries)
        
        daily_repos = set()
        for gh in github_entries:
            repo = gh.get('repository', 'Unknown')
            daily_repos.add(repo)
            commits_per_repo[repo] = commits_per_repo.get(repo, 0) + 1
            
        daily_projects = set()
        for jira in jira_entries:
            key = jira.get('key')
            if not key: continue
            
            project = jira.get('project', 'Unknown')
            daily_projects.add(project)
            jira_projects[project] = jira_projects.get(project, 0) + 1
            
            status = _normalize_jira_status(jira.get('status'))
            
            if key not in in_progress_durations:
                in_progress_durations[key] = {'first_seen': date_str, 'last_seen': date_str, 'statuses': set()}
            in_progress_durations[key]['last_seen'] = date_str
            in_progress_durations[key]['statuses'].add(status)
            
        if len(daily_repos) + len(daily_projects) > 2:
            context_switching_days.append(date_str)
            
    total_jira_touched = len(in_progress_durations)
    
    completed_statuses = {"done", "closed", "resolved", "verified", "completed"}
    in_progress_times = []
    
    for key, data in in_progress_durations.items():
        statuses = data['statuses']
        if any(s in completed_statuses for s in statuses):
            tickets_completed += 1
        elif "in progress" in statuses:
            tickets_in_progress += 1
            
        first_date = datetime.strptime(data['first_seen'], "%Y-%m-%d").date()
        last_date = datetime.strptime(data['last_seen'], "%Y-%m-%d").date()
        days_active = (last_date - first_date).days + 1
        in_progress_times.append(days_active)
        
    avg_time_in_progress = sum(in_progress_times) / len(in_progress_times) if in_progress_times else 0.0
    
    total_jira_activity = sum(jira_projects.values())
    project_distribution = {k: round((v / total_jira_activity) * 100, 2) for k, v in jira_projects.items()} if total_jira_activity else {}
    
    total_gh_activity = total_commits
    repo_distribution = {k: round((v / total_gh_activity) * 100, 2) for k, v in commits_per_repo.items()} if total_gh_activity else {}
    
    return {
        "date_range": {
            "start": str(start_date),
            "end": str(end_date)
        },
        "commit_metrics": {
            "total_commits": total_commits,
            "commits_per_day": commits_per_day,
            "commits_per_repo": commits_per_repo
        },
        "jira_metrics": {
            "total_tickets_touched": total_jira_touched,
            "tickets_completed": tickets_completed,
            "tickets_in_progress": tickets_in_progress,
            "average_days_active": round(avg_time_in_progress, 2)
        },
        "distribution": {
            "project_distribution_percent": project_distribution,
            "repo_distribution_percent": repo_distribution
        },
        "consistency": {
            "active_days": active_days_count,
            "longest_inactivity_streak_days": longest_inactivity_streak,
            "context_switching_days": len(context_switching_days)
        },
        "raw_counts": {
            "Total Jira Updates": total_jira_activity,
            "Total Github Updates": total_gh_activity
        }
    }
