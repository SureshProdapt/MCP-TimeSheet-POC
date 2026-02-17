import asyncio
import os
import sys
import json
from datetime import datetime, timedelta
import config
from llm_service import summarize_activity
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def fetch_timesheet_data(credentials):
    """
    Fetches timesheet data using the provided credentials.
    credentials: dict containing JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, GITHUB_TOKEN, etc.
    Returns a list of dictionaries representing the timesheet entries.
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

            # Calculate date range (last 5 days)
            today = datetime.now()
            dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)]
            dates.reverse() # Oldest to newest
            
            project_key = credentials.get("JIRA_PROJECT_KEY", "PROJ")
            github_user = credentials.get("GITHUB_USERNAME", "user")

            for date in dates:
                # print(f"Processing {date}...", file=sys.stderr)
                
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
                    
                    # Sort by priority, then maybe by key or something stable
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
                        "Status": "Completed", # Assumption for general work
                        "Remark": daily_summary
                    })

    return timesheet_data


def scan_logs(limit=5, exclude_dates=None):
    """
    Scans the logs directory for recent activity files and constructs timesheet data.
    Filters for days where Jira activity was found.
    exclude_dates: list of date strings to skip (e.g. ["2026-02-12"])
    """
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        return []
    
    if exclude_dates is None:
        exclude_dates = []

    log_files = [f for f in os.listdir(logs_dir) if f.startswith("activity_") and f.endswith(".json")]
    log_files.sort(reverse=True) # Newest first

    fallback_data = []
    count = 0

    for log_file in log_files:
        if count >= limit:
            break
            
        try:
            with open(os.path.join(logs_dir, log_file), "r") as f:
                data = json.load(f)
                
            date = data.get("date")
            
            # Skip if date is already in the main list
            if date in exclude_dates:
                continue

            jira_entries = data.get("jira", [])
            github_entries = data.get("github", [])
            
            # STRICT REQUIREMENT: Only include if Jira activity was found
            if not jira_entries:
                continue

            # --- Logic Reuse: Select Best Task & Summary ---
            # Select Best Task
            selected_entry = None
            if jira_entries:
                 def get_priority(entry):
                    status = entry.get("status", "").lower()
                    if status in ["done", "completed", "verified", "closed", "resolved"]:
                        return 0
                    elif status == "in progress":
                        return 1
                    else:
                        return 2
                 jira_entries.sort(key=get_priority)
                 selected_entry = jira_entries[0]

            jira_context = ""
            if selected_entry:
                jira_context = f"{selected_entry['key']}: {selected_entry['summary']}\nDescription: {selected_entry.get('description', '')[:500]}"
            
            github_context = ""
            if github_entries:
                github_context = "\n".join([f"- {i['summary']}" for i in github_entries])
            
            daily_summary = ""
            if selected_entry or github_context:
                 daily_summary = summarize_activity(jira_context, github_context, date)

            # Create Row (Only Jira driven as per requirement)
            if selected_entry:
                fallback_data.append({
                    "Date": date,
                    "Project": selected_entry.get("project", "Unknown"),
                    "Task": selected_entry.get("summary"),
                    "Task Description": selected_entry.get("description", ""),
                    "Status": selected_entry.get("status"),
                    "Remark": daily_summary 
                })
            
            count += 1
            
        except Exception as e:
            print(f"Error parsing log {log_file}: {e}", file=sys.stderr)

    return fallback_data

# Wrapper to run loop
def get_data(credentials):
    data = asyncio.run(fetch_timesheet_data(credentials))
    
    # Check if we have enough days (aiming for 5)
    desired_days = 5
    current_count = len(data)
    
    if current_count < desired_days:
        needed = desired_days - current_count
        # Collect dates we already have
        existing_dates = [row['Date'] for row in data]
        
        print(f"Only found {current_count} days from API. Backfilling {needed} days from logs...", file=sys.stderr)
        
        # Scan logs for the rest
        backfill_data = scan_logs(limit=needed, exclude_dates=existing_dates)
        
        # Combine
        data.extend(backfill_data)
        
        # Sort by Date descending (newest first) to keep it tidy
        data.sort(key=lambda x: x['Date'], reverse=True)
        
    return data
