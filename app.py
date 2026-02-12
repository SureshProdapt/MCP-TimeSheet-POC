import streamlit as st
import pandas as pd
import os
from client import get_data
from dotenv import load_dotenv

# Load existing .env if available to pre-fill
load_dotenv()

st.set_page_config(page_title="Timesheet Generator", layout="wide")

# Initialize Session State
if 'credentials' not in st.session_state:
    st.session_state['credentials'] = {
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
        "GITHUB_USERNAME": os.getenv("GITHUB_OWNER", ""), # client.py expects GITHUB_USERNAME logic or config uses GITHUB_OWNER
        "JIRA_URL": os.getenv("JIRA_URL", ""),
        "JIRA_EMAIL": os.getenv("JIRA_EMAIL", ""),
        "JIRA_API_TOKEN": os.getenv("JIRA_API_TOKEN", ""),
        "JIRA_PROJECT_KEY": os.getenv("JIRA_PROJECT_KEY", ""),
        # Prodapt Details
        "EMPLOYEE_ID": "",
        "EMPLOYEE_NAME": "",
        "BILLABLE": "Yes",
        "ROLE": "Developer",
        "SITE": "Offshore",
        "AUTHORIZED_HOURS": "8"
    }

if 'timesheet_df' not in st.session_state:
    st.session_state['timesheet_df'] = None

# Sidebar Navigation
page = st.sidebar.radio("Navigation", ["Dashboard", "Credentials"])

if page == "Credentials":
    st.header("Configuration")
    
    with st.expander("GitHub Credentials", expanded=True):
        gh_token = st.text_input("GitHub Token", value=st.session_state['credentials']['GITHUB_TOKEN'], type="password")
        gh_user = st.text_input("GitHub Username", value=st.session_state['credentials']['GITHUB_USERNAME'])

    with st.expander("Jira Credentials", expanded=True):
        jira_url = st.text_input("Jira URL", value=st.session_state['credentials']['JIRA_URL'])
        jira_email = st.text_input("Jira Email", value=st.session_state['credentials']['JIRA_EMAIL'])
        jira_token = st.text_input("Jira API Token", value=st.session_state['credentials']['JIRA_API_TOKEN'], type="password")
        jira_proj = st.text_input("Jira Project Key", value=st.session_state['credentials']['JIRA_PROJECT_KEY'])

    with st.expander("Prodapt Details", expanded=True):
        emp_id = st.text_input("Employee ID", value=st.session_state['credentials']['EMPLOYEE_ID'])
        emp_name = st.text_input("Employee Name", value=st.session_state['credentials']['EMPLOYEE_NAME'])
        billable = st.selectbox("Billable", ["Yes", "No"], index=0 if st.session_state['credentials']['BILLABLE'] == "Yes" else 1)
        role = st.text_input("Role", value=st.session_state['credentials']['ROLE'])
        site = st.selectbox("Site", ["Onshore", "Offshore"], index=1 if st.session_state['credentials']['SITE'] == "Offshore" else 0)
        auth_hours = st.text_input("Authorized Hours", value=st.session_state['credentials']['AUTHORIZED_HOURS'])

    if st.button("Save Configuration"):
        st.session_state['credentials'] = {
            "GITHUB_TOKEN": gh_token,
            "GITHUB_USERNAME": gh_user,
            "JIRA_URL": jira_url,
            "JIRA_EMAIL": jira_email,
            "JIRA_API_TOKEN": jira_token,
            "JIRA_PROJECT_KEY": jira_proj,
            "EMPLOYEE_ID": emp_id,
            "EMPLOYEE_NAME": emp_name,
            "BILLABLE": billable,
            "ROLE": role,
            "SITE": site,
            "AUTHORIZED_HOURS": auth_hours,
            # Pass other config vars required by mcp_server or llm_service
            "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
            "GROQ_MODEL": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        }
        st.success("Credentials saved to session state!")

elif page == "Dashboard":
    st.title("Timesheet Dashboard")
    
    st.markdown("### Generate Timesheet")
    st.markdown("Fetch data from the last 5 days based on your configuration.")
    
    if st.button("Generate Timesheet"):
        creds = st.session_state['credentials']
        
        # Validation
        if not creds["GITHUB_TOKEN"] or not creds["JIRA_TOKEN"] if "JIRA_TOKEN" in creds else False: 
            # Note: JIRA_API_TOKEN key in creds
            pass

        if not creds["JIRA_API_TOKEN"]:
            st.error("Jira API Token is missing. Please configure it in the Credentials tab.")
        elif not creds["GITHUB_TOKEN"]:
            st.error("GitHub Token is missing. Please configure it in the Credentials tab.")
        else:
            with st.spinner("Fetching data from Jira and GitHub... This may take a minute..."):
                try:
                    # Pass credentials to client
                    # We need to map GITHUB_USERNAME to GITHUB_OWNER if config.py uses it so.
                    # client.py logic uses: project_key = credentials.get("JIRA_PROJECT_KEY")
                    # github_user = credentials.get("GITHUB_USERNAME")
                    
                    data = get_data(creds)
                    
                    if not data:
                        st.warning("No activity found for the past 5 days.")
                    else:
                        # Process data into desired columns
                        # Columns: Employee Id | Employee Name | Date | Project | Task | Task Description | Authorized Hours | Billable | Role | site | status | Remark
                        
                        colored_data = []
                        for row in data:
                            colored_data.append({
                                "Employee Id": creds["EMPLOYEE_ID"],
                                "Employee Name": creds["EMPLOYEE_NAME"],
                                "Date": row["Date"],
                                "Project": row["Project"],
                                "Task": row["Task"],
                                "Task Description": row["Task Description"],
                                "Authorized Hours": creds["AUTHORIZED_HOURS"],
                                "Billable": creds["BILLABLE"],
                                "Role": creds["ROLE"],
                                "Site": creds["SITE"],
                                "Status": row["Status"],
                                "Remark": row["Remark"]
                            })
                        
                        df = pd.DataFrame(colored_data)
                        st.session_state['timesheet_df'] = df
                        st.success("Timesheet generated successfully!")
                        
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

    # Display Data
    if st.session_state['timesheet_df'] is not None:
        st.dataframe(
            st.session_state['timesheet_df'], 
            use_container_width=True,
            column_config={
                "Task Description": st.column_config.TextColumn(
                    "Task Description",
                    width="large"
                ),
                "Remark": st.column_config.TextColumn(
                    "Remark",
                    width="large"
                )
            }
        )
        
        csv = st.session_state['timesheet_df'].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Timesheet as CSV",
            data=csv,
            file_name=f"timesheet_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
