# MCP Timesheet Generator

This project automates the creation of daily timesheets by fetching data from Jira and GitHub using the Model Context Protocol (MCP) and summarizing it with an LLM. It generates a single row per day, prioritizing "Done" tasks, and provides a polished UI for reviewing and downloading the data.

## Features

- **Automated Data Fetching**: Retrieves activity from Jira (issues updated) and GitHub (commits, PRs).
- **Smart Summarization**: Uses an LLM (Groq/Llama) to generate concise, task-focused summaries.
- **Single Row per Day**: Prioritizes completed tasks to create a clean, corporate-ready timesheet.
- **Data Logging**: Saves all raw fetched data to JSON logs for audit/history.
- **UI Dashboard**: Built with Streamlit, offering:
  - Text wrapping for readability.
  - Editable configuration.
  - Export to **CSV** and **Excel**.

## Prerequisites

- Python 3.10+
- A Jira account (URL, Email, API Token).
- A GitHub account (Personal Access Token).
- A Groq Cloud API Key (for LLM summarization).

## Installation & Setup

Follow these steps to set up the project on your local machine:

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Create a Virtual Environment (Recommended)

It's best practice to use a virtual environment to manage dependencies.

**Windows:**

```bash
python -m venv venv
.\venv\Scripts\activate
```

**Mac/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configuration

Create a `.env` file in the root directory. Add the following credentials:

```ini
# Jira Credentials
JIRA_URL="https://your-domain.atlassian.net"
JIRA_EMAIL="your-email@example.com"
JIRA_API_TOKEN="your-jira-api-token"
JIRA_PROJECT_KEY="PROJ"

# GitHub Credentials
GITHUB_TOKEN="your-github-personal-access-token"
GITHUB_USERNAME="your-github-username"

# LLM Configuration (Groq)
GROQ_API_KEY="gsk_..."
GROQ_MODEL="llama-3.1-8b-instant"

# Optional: Employee Details for Pre-filling UI
EMPLOYEE_ID="12345"
EMPLOYEE_NAME="John Doe"
ROLE="Developer"
```

## Running the Application

To start the Timesheet Generator dashboard:

```bash
streamlit run app.py
```

This will open the application in your default web browser (usually at `http://localhost:8501`).

## Usage Guide

1. **Dashboard**: The main page shows a "Generate Timesheet" button.
2. **Configuration**: Use the sidebar to update/verify your credentials if needed.
3. **Generate**: Click "Generate Timesheet". The app will:
   - Fetch data for the last 5 days.
   - Select the most relevant task for each day.
   - Generate summaries.
   - Display the result in a table.
4. **Download**: Use the buttons below the table to download the report as **CSV** or **Excel**.

## Project Structure

- `app.py`: Main Streamlit application.
- `client.py`: Handles data fetching, prioritization logic, and LLM calls.
- `mcp_server.py`: MCP tools for interfacing with Jira/GitHub APIs.
- `llm_service.py`: Helper for LLM interaction.
- `logs/`: Directory where raw data logs are saved (JSON format).
