# MCP Timesheet Generator - Deep Dive Documentation

This document provides an in-depth technical overview of the **MCP Timesheet Generator**, extending the basic `README.md` with a detailed breakdown of the application's architecture, core components, data flow, and inner workings based on the source code.

---

## 🏗️ Architecture Overview

The project is built on a client-server architecture using the **Model Context Protocol (MCP)**, integrated with a **Streamlit** frontend and an **LLM service** for intelligent summarization.

The architecture consists of the following layers:
1. **Frontend (UI)**: Built with Streamlit (`app.py`), providing an interactive dashboard for configuration, timesheet generation, and insights visualization.
2. **Orchestration / Client Logic**: Managed by `client.py`, which acts as an intermediary. It communicates with the MCP server to fetch data, interacts with the LLM service to summarize activities, and processes raw data into structured timesheet formats.
3. **MCP Server**: Handled by `mcp_server.py` using `FastMCP`. It exposes standardized tools to securely connect to external APIs (Jira, GitHub) and retrieve raw activity logs.
4. **LLM Service**: Managed by `llm_service.py`, integrating with Groq (or Azure OpenAI) to generate natural language summaries of the fetched technical data.

---

## 🧩 Core Components

### 1. `app.py` (Streamlit Dashboard)
This is the entry point for the user. It manages a multi-page interface:
- **Credentials**: Allows users to input and persist GitHub, Jira, and LLM API keys via Streamlit's session state. It also captures specific metadata (Employee ID, Role, Site, etc.) needed for timesheet formatting.
- **Dashboard**: The main engine for generating timesheets. It provides a date range picker and triggers `client.py`'s `get_data` function. The resulting timesheet is displayed in a customizable, text-wrapped data table with options to export to CSV or Excel (`openpyxl`).
- **Productivity Insights**: Generates analytical dashboards comparing active work days, context-switching metrics, commits per repo, and Jira ticket velocity.

### 2. `client.py` (Orchestrator engine)
This file is the brain of the application's data processing logic.
- **`fetch_timesheet_data()`**: Automates the timesheet generation over a set date range.
  - Spawns the MCP server as a subprocess (`StdioServerParameters`).
  - Calls the MCP tools (`get_jira_activity`, `get_github_activity`) day by day.
  - Caches raw API responses locally in the `logs/` directory (e.g., `logs/activity_YYYY-MM-DD.json`).
  - **Task Prioritization Logic**: Evaluates multiple Jira tickets worked on in a single day and selects one primary task for the timesheet row. It prioritizes completed statuses (Done, Closed, Resolved) over "In Progress", and "In Progress" over others.
  - Handles days with no Jira data by falling back to GitHub general commits, or carrying over the previous day's "In Progress" task (`find_last_in_progress_task`).
- **`generate_productivity_insights()`**: Parses historical JSON logs to calculate metrics like longest inactivity streaks, context switching (modifying >2 projects/repos in a day), and project distribution.

### 3. `mcp_server.py` (The MCP Server)
Built using `fastmcp`, this script exposes two main tools to the MCP client via `stdio`:
- **`@mcp.tool() get_jira_activity`**: Executes a JQL search (`updated >= 'YYYY-MM-DD' AND updated < 'YYYY-MM-DD 23:59'`) against the Jira API. It parses the Atlassian Document Format (ADF) description into plain text and extracts key fields (summary, status, assignee, project).
- **`@mcp.tool() get_github_activity`**: Connects to the GitHub API. It first fetches all user events to identify active repositories on a specific date (PushEvents, CreateEvents, PullRequestEvents). It then fetches the exact commits made by the user in those active repositories within the 24-hour window.

### 4. `llm_service.py` (Summarization Engine)
- Accepts the prioritized Jira task details and the aggregated GitHub commit messages for a given day.
- Uses the **Groq API** (currently configured for the `llama-3.1-8b-instant` model) to synthesize the granular technical data into a concise, professional, single-paragraph summary suitable for a timesheet ("Remark" column).

---

## 🔄 Data Flow: Timesheet Generation

1. **User Request**: User selects a date range in `app.py` and clicking "Generate".
2. **Client Initialization**: `app.py` calls `client.get_data()` with credentials and dates.
3. **MCP Server Startup**: `client.py` initializes a standard I/O connection to `mcp_server.py`.
4. **Data Acquisition (Iteration)**: For each individual date in the range:
   - Client calls `get_jira_activity`. MCP server queries the Jira REST API, parses ADF, and returns JSON.
   - Client calls `get_github_activity`. MCP server queries GitHub Events/Commits, and returns JSON.
   - Client aggregates and caches this output to `logs/activity_YYYY-MM-DD.json`.
5. **Data Formatting**:
   - `client.py` selects the most critical Jira task of the day.
   - Calls `llm_service.summarize_activity()` to generate a human-readable "Remark" paragraph based on Jira/GitHub output.
6. **Delivery**: The synthesized timesheet row is sent back to `app.py`.
7. **Presentation**: `app.py` displays a Streamlit dataframe populated with user metadata and dynamically generated activity descriptions, enabling the final Excel/CSV export.

---

## 🛠️ Key Technical Details

- **Fault Tolerance**: If GitHub fails, it relies on Jira. If Jira fails, it relies on GitHub. If both fail, it scans the file system logs for the last task marked "In Progress" and carries it over to maintain timesheet continuity.
- **Extensible Configuration**: Through `.env` and `config.py`, the system seamlessly supports migrating between LLM providers (e.g., Azure OpenAI logic is integrated but commented out) and managing strict metadata mappings (e.g., UOM, Analysis Codes).
- **Local Persistence**: The `logs/` directory acts as a local database, allowing the separate "Productivity Insights" tab to rapidly generate analytics without making continuous, rate-limited API calls to Jira/GitHub.
