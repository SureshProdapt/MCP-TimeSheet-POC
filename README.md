# MCP Timesheet Generator

This project automates the creation of daily timesheets by fetching data from Jira and GitHub using the Model Context Protocol (MCP) and summarizing it with an LLM.

## Architecture

- **MCP Server (`mcp_server.py`)**: Exposes tools to fetch activity from Jira and GitHub.
- **MCP Client (`client.py`)**: Connects to the server, aggregates data, and uses an LLM to generate a summary.
- **Output**: Writes the summary to `timesheet.csv`.

## Setup

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

2.  Configure environment variables:
    add `.env` file and add all the required credentials from `config.py`

## Usage

Run the client to generate the timesheet for today:

```bash
python client.py
```
