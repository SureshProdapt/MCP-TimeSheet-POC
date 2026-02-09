import config
# from openai import AzureOpenAI
from groq import Groq

# Initialize Client
llm_client = None

# if config.AZURE_OPENAI_ENDPOINT and config.AZURE_OPENAI_API_KEY:
#     llm_client = AzureOpenAI(
#         api_key=config.AZURE_OPENAI_API_KEY,
#         api_version=config.AZURE_OPENAI_API_VERSION,
#         azure_endpoint=config.AZURE_OPENAI_ENDPOINT
#     )

if config.GROQ_API_KEY:
    llm_client = Groq(api_key=config.GROQ_API_KEY)

def summarize_activity(jira_content: str, github_content: str, date: str) -> str:
    """
    Summarizes the daily activity using the configured LLM.
    """
    if not llm_client:
        print("Groq API key not configured, skipping summarization.")
        return "LLM not configured. Raw Data gathered."
        
    prompt = f"""
    Create a concise daily timesheet summary for the following activities on {date}.
    
    Jira Activity:
    {jira_content}
    
    GitHub Activity:
    {github_content}
    
    Format the output as a single paragraph describing the work done.
    """
    
    try:
        # Azure OpenAI Call (Commented out)
        # response = llm_client.chat.completions.create(
        #     model=config.AZURE_OPENAI_DEPLOYMENT_NAME,
        #     messages=[
        #         {"role": "system", "content": "You are a helpful assistant that summarizes work activity for timesheets."},
        #         {"role": "user", "content": prompt}
        #     ],
        #     max_tokens=150
        # )
        
        # Groq Call
        response = llm_client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes work activity for timesheets."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        error_msg = f"LLM Error: {e}"
        print(error_msg)
        return f"{error_msg}. Raw Data: {jira_content[:50]}... {github_content[:50]}..."
