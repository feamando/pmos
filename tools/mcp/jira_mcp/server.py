import argparse
import json
import os
import sys
from typing import List, Optional

from atlassian import Confluence, Jira
from mcp.server.fastmcp import FastMCP

# --- Configuration ---
# Add common directory to path to import config_loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import config_loader

# Initialize FastMCP
mcp = FastMCP("jira-mcp")


# --- Services ---
def get_jira():
    conf = config_loader.get_jira_config()
    if not conf["url"] or not conf["username"] or not conf["api_token"]:
        raise ValueError("Jira configuration missing in .env")

    return Jira(
        url=conf["url"],
        username=conf["username"],
        password=conf["api_token"],
        cloud=True,
    )


def get_confluence():
    conf = config_loader.get_jira_config()
    if not conf["url"] or not conf["username"] or not conf["api_token"]:
        raise ValueError("Jira/Confluence configuration missing in .env")

    return Confluence(
        url=conf["url"],
        username=conf["username"],
        password=conf["api_token"],
        cloud=True,
    )


# --- Tools ---


@mcp.tool()
def search_issues(jql: str, limit: int = 10) -> str:
    """
    Search for Jira issues using JQL.
    """
    try:
        jira = get_jira()
        issues = jira.jql(jql, limit=limit)
        results = issues.get("issues", [])

        if not results:
            return "No issues found."

        output = []
        for issue in results:
            key = issue["key"]
            summary = issue["fields"]["summary"]
            status = issue["fields"]["status"]["name"]
            priority = issue["fields"].get("priority", {}).get("name", "None")
            output.append(f"[{key}] {summary} (Status: {status}, Priority: {priority})")

        return "\n".join(output)
    except Exception as e:
        return f"Error searching issues: {str(e)}"


@mcp.tool()
def get_issue(issue_key: str) -> str:
    """
    Get details of a specific Jira issue.
    """
    try:
        jira = get_jira()
        issue = jira.issue(issue_key)

        fields = issue["fields"]
        summary = fields["summary"]
        description = fields.get("description", "No description.")
        status = fields["status"]["name"]
        priority = fields.get("priority", {}).get("name", "None")
        assignee = fields.get("assignee", {})
        assignee_name = (
            assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
        )

        # Comments (last 3)
        comments_data = fields.get("comment", {}).get("comments", [])
        recent_comments = []
        for c in comments_data[-3:]:
            author = c.get("author", {}).get("displayName", "Unknown")
            body = c.get("body", "")
            recent_comments.append(f"- {author}: {body[:200]}...")

        output = [
            f"Issue: {issue_key}",
            f"Summary: {summary}",
            f"Status: {status} | Priority: {priority} | Assignee: {assignee_name}",
            "-" * 40,
            "Description:",
            str(description)[:1000] + ("..." if len(str(description)) > 1000 else ""),
            "-" * 40,
            "Recent Comments:",
            "\n".join(recent_comments) if recent_comments else "No comments.",
        ]
        return "\n".join(output)
    except Exception as e:
        return f"Error fetching issue {issue_key}: {str(e)}"


@mcp.tool()
def get_page(page_id: str) -> str:
    """
    Get content of a Confluence page.
    """
    try:
        conf = get_confluence()
        page = conf.get_page_by_id(page_id, expand="body.storage")

        title = page["title"]
        body = page.get("body", {}).get("storage", {}).get("value", "")

        # Basic HTML stripping could happen here, but keeping raw for now or simple text
        # For simplicity, let's just return it.

        return f"Page: {title} (ID: {page_id})\n\n{body[:3000]}"
    except Exception as e:
        return f"Error fetching page {page_id}: {str(e)}"


@mcp.tool()
def search_pages(cql: str, limit: int = 5) -> str:
    """
    Search Confluence pages using CQL.
    """
    try:
        conf = get_confluence()
        results = conf.cql(cql, limit=limit)
        base_url = config_loader.get_jira_config()["url"]

        output = []
        for page in results.get("results", []):
            title = page["title"]
            pid = page["content"]["id"]
            url = page["content"]["_links"]["webui"]
            output.append(f"[{pid}] {title} - {base_url}/wiki{url}")

        return "\n".join(output) if output else "No pages found."
    except Exception as e:
        return f"Error searching pages: {str(e)}"


if __name__ == "__main__":
    # CLI Mode support
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        sys.argv.pop(1)
        parser = argparse.ArgumentParser(description="Jira/Confluence CLI")
        subparsers = parser.add_subparsers(dest="command", required=True)

        # Search Issues
        p_search = subparsers.add_parser("search_issues")
        p_search.add_argument("jql", help="JQL Query")

        # Get Issue
        p_issue = subparsers.add_parser("get_issue")
        p_issue.add_argument("key", help="Issue Key (e.g. PROJ-123)")

        # Search Pages
        p_pages = subparsers.add_parser("search_pages")
        p_pages.add_argument("cql", help="CQL Query")

        # Get Page
        p_page = subparsers.add_parser("get_page")
        p_page.add_argument("id", help="Page ID")

        args = parser.parse_args()

        # if not config: check removed, get_jira() handles validation

        if args.command == "search_issues":
            print(search_issues(args.jql))
        elif args.command == "get_issue":
            print(get_issue(args.key))
        elif args.command == "search_pages":
            print(search_pages(args.cql))
        elif args.command == "get_page":
            print(get_page(args.id))
    else:
        mcp.run()
