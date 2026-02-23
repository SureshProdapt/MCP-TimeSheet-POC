import streamlit as st
import pandas as pd
import os
import io
import json
from client import get_data
from dotenv import load_dotenv

# Load existing .env if available to pre-fill
load_dotenv(override=True)

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
        "AUTHORIZED_HOURS": "8",
        "ACTIVITY_PROCESS_TRANSACTION": os.getenv("ACTIVITY_PROCESS_TRANSACTION", "Development"),
        "AUTHORIZED_UNITS": os.getenv("AUTHORIZED_UNITS", "1"),
        "UOM": os.getenv("UOM", "Hours"),
        "LOCATION": os.getenv("LOCATION", "Chennai - Guindy"),
        "WORK_ITEM": os.getenv("WORK_ITEM", "General"),
        "ANALYSIS_CODE": os.getenv("ANALYSIS_CODE", "N/A"),
        "BOOKED_HOURS": os.getenv("BOOKED_HOURS", "8"),
        "BOOKED_UNITS": os.getenv("BOOKED_UNITS", "1"),
        "PLANNED_HOURS": os.getenv("PLANNED_HOURS", "8"),
        "BALANCE_HOURS": os.getenv("BALANCE_HOURS", "0")
    }

if 'timesheet_df' not in st.session_state:
    st.session_state['timesheet_df'] = None

# Sidebar Navigation
page = st.sidebar.radio("Navigation", ["Dashboard", "Productivity Insights", "Credentials"])

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
        col1, col2 = st.columns(2)
        with col1:
            emp_id = st.text_input("Employee ID", value=st.session_state['credentials']['EMPLOYEE_ID'])
            emp_name = st.text_input("Employee Name", value=st.session_state['credentials']['EMPLOYEE_NAME'])
            billable = st.selectbox("Billable", ["Yes", "No"], index=0 if st.session_state['credentials']['BILLABLE'] == "Yes" else 1)
            role = st.text_input("Role", value=st.session_state['credentials']['ROLE'])
            site = st.selectbox("Site", ["Onshore", "Offshore"], index=1 if st.session_state['credentials']['SITE'] == "Offshore" else 0)
            auth_hours = st.text_input("Authorized Hours", value=st.session_state['credentials']['AUTHORIZED_HOURS'])
            auth_units = st.text_input("Authorized Units", value=st.session_state['credentials'].get('AUTHORIZED_UNITS', ''))
            uom = st.text_input("UOM", value=st.session_state['credentials'].get('UOM', ''))

        with col2:
            activity_proc = st.text_input("Activity / Process / Transaction", value=st.session_state['credentials'].get('ACTIVITY_PROCESS_TRANSACTION', ''))
            location = st.text_input("Location", value=st.session_state['credentials'].get('LOCATION', ''))
            work_item = st.text_input("Work Item", value=st.session_state['credentials'].get('WORK_ITEM', ''))
            analysis_code = st.text_input("Analysis Code", value=st.session_state['credentials'].get('ANALYSIS_CODE', ''))
            booked_hours = st.text_input("Booked Hours", value=st.session_state['credentials'].get('BOOKED_HOURS', ''))
            booked_units = st.text_input("Booked Units", value=st.session_state['credentials'].get('BOOKED_UNITS', ''))
            planned_hours = st.text_input("Planned Hours", value=st.session_state['credentials'].get('PLANNED_HOURS', ''))
            balance_hours = st.text_input("Balance Hours", value=st.session_state['credentials'].get('BALANCE_HOURS', ''))

    if st.button("Save Configuration"):
        st.session_state['credentials'].update({
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
            "AUTHORIZED_UNITS": auth_units,
            "UOM": uom,
            "ACTIVITY_PROCESS_TRANSACTION": activity_proc,
            "LOCATION": location,
            "WORK_ITEM": work_item,
            "ANALYSIS_CODE": analysis_code,
            "BOOKED_HOURS": booked_hours,
            "BOOKED_UNITS": booked_units,
            "PLANNED_HOURS": planned_hours,
            "BALANCE_HOURS": balance_hours,
            # Pass other config vars required by mcp_server or llm_service
            "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
            "GROQ_MODEL": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        })
        st.success("Credentials saved to session state!")

elif page == "Dashboard":
    st.title("Timesheet Dashboard")
    
    st.markdown("### Generate Timesheet")
    st.markdown("### Generate Timesheet")
    st.markdown("Fetch data based on your configuration and selected date range.")

    # Date Range Picker
    today = pd.Timestamp.now().date()
    default_start = today - pd.Timedelta(days=5)
    default_end = today
    
    date_range = st.date_input(
        "Select Date Range",
        value=(default_start, default_end),
        max_value=today,
        format="DD/MM/YYYY"
    )

    start_date = None
    end_date = None

    if isinstance(date_range, tuple):
        if len(date_range) == 2:
            start_date = date_range[0]
            end_date = date_range[1]
        elif len(date_range) == 1:
            start_date = date_range[0]
            end_date = start_date # If only one date selected, treat as single day range

    
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
                if not start_date or not end_date:
                    st.error("Please select a valid date range.")
                else:
                    with st.spinner(f"Fetching data from {start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}..."):
                        try:
                            # Pass credentials to client
                            # We need to map GITHUB_USERNAME to GITHUB_OWNER if config.py uses it so.
                            # client.py logic uses: project_key = credentials.get("JIRA_PROJECT_KEY")
                            # github_user = credentials.get("GITHUB_USERNAME")
                            
                            data = get_data(creds, start_date=start_date, end_date=end_date)
                            
                            if not data:
                                st.warning("No activity found for the selected date range.")
                            else:
                                # Process data into desired columns
                                # Columns: Employee Id | Employee Name | Date | Project | Task | Task Description | Authorized Hours | Billable | Role | site | status | Remark
                                
                                colored_data = []
                                for row in data:
                                    colored_data.append({
                                        "Employee ID": creds["EMPLOYEE_ID"],
                                        "Employee Name": creds["EMPLOYEE_NAME"],
                                        "Date": pd.to_datetime(row["Date"]).strftime('%d-%m-%Y'),
                                        "Project": row["Project"],
                                        "Activity / Process / Transaction": creds["ACTIVITY_PROCESS_TRANSACTION"],
                                        "Task": row["Task"],
                                        "Task Description": row["Task Description"],
                                        "Authorized Hours": creds["AUTHORIZED_HOURS"],
                                        "Authorized Units": creds["AUTHORIZED_UNITS"],
                                        "UOM": creds["UOM"],
                                        "Billable": creds["BILLABLE"],
                                        "Site": creds["SITE"],
                                        "Role": creds["ROLE"],
                                        "Location": creds["LOCATION"],
                                        "Work Item": creds["WORK_ITEM"],
                                        "Analysis Code": creds["ANALYSIS_CODE"],
                                        "Remarks": row["Remark"],
                                        "Status": row["Status"],
                                        "Booked Hours": creds["BOOKED_HOURS"],
                                        "Booked Units": creds["BOOKED_UNITS"],
                                        "Planned Hours": creds["PLANNED_HOURS"],
                                        "Balance Hours": creds["BALANCE_HOURS"]
                                    })
                                
                                df = pd.DataFrame(colored_data)
                                st.session_state['timesheet_df'] = df
                                st.success("Timesheet generated successfully!")
                                
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")

    # Display Data
    if st.session_state['timesheet_df'] is not None:
        st.markdown("### Timesheet Preview")

        # --- Column Selection ---
        df = st.session_state['timesheet_df']
        all_columns = list(df.columns)
        
        # Use st.popover for a cleaner "dropdown-like" UI with checkboxes
        # Requires Streamlit >= 1.33.0
        try:
             # Using a funnel/filter icon often represented by :material/filter_alt: or similar in new streamlit
             # Funnel icon: :material/filter_list:
             filter_container = st.popover("Filter Columns", icon=":material/filter_alt:")
        except AttributeError:
             # Fallback for older Streamlit versions
             filter_container = st.expander("Filter Columns")

        selected_columns = []
        with filter_container:
            st.write("Uncheck to hide columns:")
            for col in all_columns:
                # Default to True (checked)
                if st.checkbox(col, value=True, key=f"chk_{col}"):
                    selected_columns.append(col)
        
        if selected_columns:
            display_df = df[selected_columns]
        else:
            st.warning("No columns selected! Showing all columns.")
            display_df = df

        
        # Custom CSS for table to wrap text and improve column width, AND fix Date Picker range highlighting
        st.markdown("""
        <style>
        .timesheet-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        .timesheet-table th, .timesheet-table td {
            border: 1px solid #e0e0e0;
            padding: 10px;
            text-align: left;
            vertical-align: top;
        }
        .timesheet-table th {
            background-color: #f0f2f6;
            font-weight: 600;
        }
        .timesheet-table td {
            white-space: pre-wrap; /* Ensures text wrapping and preserves newlines */
            word-wrap: break-word;
        }
        /* Specific column widths */
        .timesheet-table th:nth-child(7), .timesheet-table td:nth-child(7) { /* Task Description */
            min-width: 250px;
        }
        .timesheet-table th:nth-child(17), .timesheet-table td:nth-child(17) { /* Remarks */
            min-width: 300px;
        }
        .timesheet-table th:nth-child(6), .timesheet-table td:nth-child(6) { /* Task */
            min-width: 200px;
        }
        .timesheet-table th:nth-child(3), .timesheet-table td:nth-child(3) { /* Date */
            min-width: 120px;
            white-space: nowrap;
        }
        
        /* Fix for Date Picker Range Highlighting */
        /* These selectors target BaseWeb calendar components used by Streamlit */
        div[data-baseweb="calendar"] div[aria-selected="true"] {
            background-color: #FF4B4B !important; /* Streamlit Red/Primary */
            color: white !important;
        }
        /* Try to target the range between start and end - often uses --in-range generic class or sibling logic which is hard in CSS alone */
        /* However, ensuring the selected days are bold/colored helps. */
        /* Streamlit usually handles the range background via js/inline styles, forcing it here might be tricky without exact classes */
        </style>
        """, unsafe_allow_html=True)

        # Render HTML table
        # escape=True ensures security, pre-wrap handles newlines
        html_table = display_df.to_html(classes="timesheet-table", index=False, escape=True)
        st.markdown(html_table, unsafe_allow_html=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📄 Download as CSV",
                data=csv,
                file_name=f"timesheet_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        with col2:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                display_df.to_excel(writer, index=False, sheet_name='Timesheet')
                
                # Auto-adjust column width (optional polish)
                worksheet = writer.sheets['Timesheet']
                for column_cells in worksheet.columns:
                    length = max(len(str(cell.value)) for cell in column_cells)
                    if length > 50: length = 50 # Cap width
                    worksheet.column_dimensions[column_cells[0].column_letter].width = length + 2

            st.download_button(
                label="📊 Download as Excel",
                data=buffer.getvalue(),
                file_name=f"timesheet_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

elif page == "Productivity Insights":
    st.title("Productivity Insights")
    st.markdown("Analyze your productivity across Jira and GitHub based on historical logs.")
    
    # Reuse date picker logic
    today = pd.Timestamp.now().date()
    default_start = today - pd.Timedelta(days=5)
    default_end = today
    
    date_range = st.date_input(
        "Select Date Range",
        value=(default_start, default_end),
        max_value=today,
        format="DD/MM/YYYY"
    )

    start_date = None
    end_date = None

    if isinstance(date_range, tuple):
        if len(date_range) == 2:
            start_date = date_range[0]
            end_date = date_range[1]
        elif len(date_range) == 1:
            start_date = date_range[0]
            end_date = start_date

    if st.button("Generate Productivity Insights"):
        if not start_date or not end_date:
            st.error("Please select a valid date range.")
        else:
            with st.spinner(f"Analyzing logs from {start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}..."):
                try:
                    from client import generate_productivity_insights
                    insights = generate_productivity_insights(str(start_date), str(end_date))
                    st.session_state['insights_data'] = insights
                    st.success("Insights generated successfully!")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

    if 'insights_data' in st.session_state and st.session_state['insights_data']:
        insights = st.session_state['insights_data']
        
        st.markdown("### Overview")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Active Days", insights['consistency']['active_days'])
        col2.metric("Total Commits", insights['commit_metrics']['total_commits'])
        col3.metric("Tickets Touched", insights['jira_metrics']['total_tickets_touched'])
        col4.metric("Tickets Completed", insights['jira_metrics']['tickets_completed'])
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("#### Commit Metrics")
            commits_per_day = insights['commit_metrics']['commits_per_day']
            if sum(commits_per_day.values()) > 0:
                st.bar_chart(pd.Series(commits_per_day, name="Commits"))
            else:
                st.info("No commits found in the selected range.")
                
            st.markdown("#### Repositories")
            if insights['commit_metrics']['commits_per_repo']:
                st.table(pd.Series(insights['commit_metrics']['commits_per_repo'], name="Commits"))
            else:
                st.info("No repository activity found.")
            
        with col_right:
            st.markdown("#### Jira Metrics")
            st.write(f"**In Progress Tickets:** {insights['jira_metrics']['tickets_in_progress']}")
            st.write(f"**Avg Days Active:** {insights['jira_metrics']['average_days_active']} days")
            
            st.markdown("#### Work Distribution")
            st.write("**Projects (%):**")
            if insights['distribution']['project_distribution_percent']:
                st.table(pd.Series(insights['distribution']['project_distribution_percent'], name="%"))
            else:
                st.info("No Jira projects touched.")
            
            st.write("**Repos (%):**")
            if insights['distribution']['repo_distribution_percent']:
                st.table(pd.Series(insights['distribution']['repo_distribution_percent'], name="%"))
            else:
                st.info("No Github repos touched.")
            
        st.markdown("#### Consistency")
        st.write(f"- **Longest Inactivity Streak:** {insights['consistency']['longest_inactivity_streak_days']} days (excluding missing days from start date to first activity)")
        st.write(f"- **Context Switching Days** (> 2 projects/repos modified): {insights['consistency']['context_switching_days']}")
        
        st.markdown("---")
        json_str = json.dumps(insights, indent=2)
        st.download_button(
            label="📄 Download Insights (JSON)",
            data=json_str,
            file_name=f"productivity_insights_{insights['date_range']['start']}_to_{insights['date_range']['end']}.json",
            mime="application/json",
            use_container_width=True
        )
