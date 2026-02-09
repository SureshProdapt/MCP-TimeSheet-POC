import asyncio
import os
import csv
import sys
from datetime import datetime
import config
from llm_service import summarize_activity
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_client():
    # Define server parameters
    server_params = StdioServerParameters(
        command=sys.executable, # Use the same python interpreter
        args=["mcp_server.py"],
        env=os.environ.copy() # Pass current environment to subprocess
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # Get today's date
            today = datetime.now().strftime("%Y-%m-%d")
            
            print(f"Fetching data for {today}...")
            
            # Fetch Jira Data
            try:
                jira_data = await session.call_tool("get_jira_activity", arguments={
                    "project_key": config.JIRA_PROJECT_KEY, 
                    "date": today
                })
                jira_content = jira_data.content[0].text
            except Exception as e:
                jira_content = f"Error fetching Jira: {e}"

            # Fetch GitHub Data
            try:
                github_data = await session.call_tool("get_github_activity", arguments={
                    "username": config.GITHUB_OWNER, 
                    "date": today
                })
                github_content = github_data.content[0].text
            except Exception as e:
                github_content = f"Error fetching GitHub: {e}"

            # Summarize with LLM
            work_summary = summarize_activity(jira_content, github_content, today)

            # Write to CSV
            csv_file = "timesheet.csv"
            file_exists = os.path.isfile(csv_file)
            
            with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                if not file_exists:
                    writer.writerow(["Date", "Work Done"])
                
                writer.writerow([today, work_summary])
            
            print(f"Timesheet updated for {today}.")

if __name__ == "__main__":
    asyncio.run(run_client())
