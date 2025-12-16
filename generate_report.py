import yaml
import csv
from datetime import datetime
import os
from dotenv import load_dotenv
import google.generativeai as genai
from jira import JIRA
from jira.exceptions import JIRAError

# --- Configuration ---
load_dotenv()
SQUAD_REGISTRY_PATH = 'squad_registry.yaml'
REPORT_OUTPUT_DIR = 'Reporting/Sprint_Reports'
CSV_HEADERS = [
    'Mega-Alliance',
    'Tribe',
    'Squad',
    'KPI Movement (Since Last Sprint)',
    'What was delivered in the last sprint?',
    'Key learnings from this last sprint',
    'What is planned for the next sprint?',
    'Demo'
]

# --- Jira Configuration ---
JIRA_URL = os.getenv("JIRA_URL")
JIRA_USERNAME = os.getenv("JIRA_USERNAME")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

if not all([JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN]):
    print("Error: Missing Jira configuration. Please set JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN in .env")
    exit(1)

try:
    jira = JIRA(server=JIRA_URL, basic_auth=(JIRA_USERNAME, JIRA_API_TOKEN))
    print(f"Connected to Jira at {JIRA_URL}")
except Exception as e:
    print(f"Error connecting to Jira: {e}")
    exit(1)

# --- Gemini Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("Warning: GEMINI_API_KEY not found in environment variables. LLM summarization will fail.")

GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")

# --- Helper Functions ---

def load_squad_registry(file_path):
    """Loads the squad mapping from a YAML file."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def get_sprints_for_board(board_id):
    """
    Fetches the last closed sprint and the current active (or next future) sprint for a board.
    Returns: (last_sprint, current_sprint, sprints_supported)
    """
    try:
        sprints = jira.sprints(board_id, state='active,closed,future', maxResults=50)
        # Sort sprints by end date (or id if dates missing) to ensure chronological order
        sprints = sorted(sprints, key=lambda x: getattr(x, 'endDate', 'Z') or 'Z') 
        
        last_sprint = None
        current_sprint = None

        closed_sprints = [s for s in sprints if s.state == 'closed']
        if closed_sprints:
            last_sprint = closed_sprints[-1]
        
        active_sprints = [s for s in sprints if s.state == 'active']
        if active_sprints:
            current_sprint = active_sprints[0]
        else:
            future_sprints = [s for s in sprints if s.state == 'future']
            if future_sprints:
                current_sprint = future_sprints[0]
                
        return last_sprint, current_sprint, True
        
    except JIRAError as e:
        if e.status_code == 400 and "does not support sprints" in e.text:
            print(f"Board {board_id} does not support sprints (likely Kanban).")
            return None, None, False
        print(f"Error fetching sprints for board {board_id}: {e}")
        return None, None, True # Sprints supported but failed
    except Exception as e:
        print(f"Unexpected error fetching sprints for board {board_id}: {e}")
        return None, None, True

def fetch_jira_tickets(board_id, sprint_id):
    """
    Fetches tickets for a given sprint ID.
    """
    if not sprint_id:
        return []
    
    jql = f"sprint = {sprint_id} ORDER BY rank ASC"
    return execute_jql(jql)

def fetch_kanban_tickets(project_key, ticket_type):
    """
    Fetches tickets for Kanban boards based on date or rank.
    Uses statusCategory instead of status to capture all done-like statuses (Done, Resolved, Closed).
    """
    if ticket_type == 'delivered':
        # Delivered in last 14 days - using statusCategory to catch Done, Resolved, Closed
        jql = f"project = {project_key} AND statusCategory = Done AND updated >= -14d ORDER BY updated DESC"
    elif ticket_type == 'planned':
        # Top of backlog (not in Done category)
        jql = f"project = {project_key} AND statusCategory != Done ORDER BY rank ASC"
    else:
        return []

    return execute_jql(jql, limit=15)

def execute_jql(jql, limit=50):
    try:
        issues = jira.search_issues(jql, maxResults=limit, fields="summary,status,issuetype,description")
        tickets = []
        for issue in issues:
            tickets.append(f"[{issue.key}] {issue.fields.summary} ({issue.fields.status.name})")
        return tickets
    except Exception as e:
        print(f"Error executing JQL '{jql}': {e}")
        return []

def summarize_with_llm(tickets, prompt_instruction, squad_name):
    """
    Summarizes tickets using the Gemini API.
    """
    if not tickets:
        return "No relevant items found in Jira."

    if not GEMINI_API_KEY:
        return "- " + "\n- ".join(tickets[:5]) + "\n(LLM Summarization unavailable)"

    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        
        ticket_list_str = "\n".join(tickets)
        full_prompt = f"""
        You are an expert Product Manager assistant. Your task is to summarize the following list of Jira tickets for the squad '{squad_name}' into a concise, outcome-focused report.
        
        Context: {prompt_instruction}
        
        Tickets:
        {ticket_list_str}
        
        Instructions:
        - Focus on value delivered and outcomes, not just technical tasks.
        - Group small bugs or minor tasks into a single bullet point (e.g., 'Maintenance: Fixed 3 minor UI bugs').
        - Use bullet points.
        - Keep it brief and suitable for an executive summary.
        - Do not use introductory or concluding phrases (e.g., 'Here is the summary'). Just return the bullet points.
        """
        
        response = model.generate_content(full_prompt)
        return response.text.strip()

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return "- " + "\n- ".join(tickets[:5]) + "\n(LLM Summarization failed)"

# --- Main Logic ---

def generate_sprint_report():
    squad_registry = load_squad_registry(SQUAD_REGISTRY_PATH)
    
    os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)
    
    current_date_str = datetime.now().strftime("%m-%d-%Y")
    report_filename = f"Sprint_Report_{current_date_str}.csv"
    report_path = os.path.join(REPORT_OUTPUT_DIR, report_filename)

    with open(report_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(CSV_HEADERS) # Write header row

        for squad_data in squad_registry['squads']:
            squad_name = squad_data['name']
            jira_board_id = squad_data['jira_board_id']
            jira_project_key = squad_data['jira_project']
            tribe = squad_data['tribe']
            
            print(f"Processing Squad: {squad_name} (Board: {jira_board_id})")
            
            last_sprint, current_sprint, sprints_supported = get_sprints_for_board(jira_board_id)
            
            delivered_summary = "No data found."
            learnings_summary = "No data found."
            planned_summary = "No data found."
            
            # --- Fetching Logic ---
            delivered_tickets = []
            planned_tickets = []

            if sprints_supported:
                # SPRINT MODE
                if last_sprint:
                    print(f"  - Found Last Sprint: {last_sprint.name} (ID: {last_sprint.id})")
                    all_last_tickets = fetch_jira_tickets(jira_board_id, last_sprint.id)
                    # Filter for completed tickets - checking for common done-like statuses
                    done_statuses = ["(Done)", "(Closed)", "(Resolved)", "(Complete)", "(Released)"]
                    delivered_tickets = [t for t in all_last_tickets if any(status in t for status in done_statuses)]
                else:
                    print("  - No closed sprint found.")

                if current_sprint:
                    print(f"  - Found Current Sprint: {current_sprint.name} (ID: {current_sprint.id})")
                    planned_tickets = fetch_jira_tickets(jira_board_id, current_sprint.id)
                else:
                    print("  - No active/future sprint found.")
            else:
                # KANBAN MODE
                print(f"  - Kanban Mode: Fetching recent Done (14d) and Top Backlog.")
                delivered_tickets = fetch_kanban_tickets(jira_project_key, 'delivered')
                planned_tickets = fetch_kanban_tickets(jira_project_key, 'planned')

            # --- Summarization ---
            if delivered_tickets:
                delivered_summary = summarize_with_llm(delivered_tickets, "Summarize these COMPLETED tickets into outcome-focused bullet points.", squad_name)
                learnings_summary = summarize_with_llm(delivered_tickets, "Extract key learnings, technical wins, or process improvements from these tickets.", squad_name)
            
            if planned_tickets:
                planned_summary = summarize_with_llm(planned_tickets, "Summarize these PLANNED tickets, focusing on goals and strategic value.", squad_name)

            # Mock KPI Movement & Demo (Placeholder)
            kpi_movement = "N/A (Manual Entry)" 
            demo_info = "To be confirmed"

            writer.writerow([
                "Consumer Mega-Alliance", 
                tribe,
                squad_name,
                kpi_movement,
                delivered_summary,
                learnings_summary,
                planned_summary,
                demo_info
            ])
            
    print(f"Report generated successfully at {report_path}")

if __name__ == "__main__":
    generate_sprint_report()

