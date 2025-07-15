import os
import json
import requests
import logging

from shared.utils import get_secrets

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Creates a ticket in the Linear Triage project with all the collected information.
    """
    logger.info("Creating Linear ticket...")
    secrets = get_secrets()
    LINEAR_API_KEY = secrets.get("LINEAR_API_KEY")
    LINEAR_PROJECT_ID = os.environ.get("LINEAR_PROJECT_ID")
    LINEAR_TEAM_ID = os.environ.get("LINEAR_TEAM_ID")

    if not all([LINEAR_API_KEY, LINEAR_PROJECT_ID, LINEAR_TEAM_ID]):
        logger.error(
            "Missing one or more Linear environment variables: API Key, Project ID, or Team ID.")
        raise ValueError("Missing Linear environment variables.")

    doc = event.get('documentation', {})
    suggestion = event.get('suggestion', {}).get(
        'llm_suggestion', 'No suggestion provided.')

    # The 'insight' data is now at the top level of the event.
    title = f"Doc Improvement: {event.get('summary', 'Untitled Issue')[:80]}"

    description = f"""
**Insight from Discord**
A recurring issue was identified in the `{event.get('channel_name', 'N/A')}` channel related to: *{event.get('summary', 'N/A')}*

**Direct User Quotes**
> {"\n> ".join(event.get('quotes', []))}

**Relevant Documentation**
This feedback appears to relate to the following documentation page:
[{doc.get('url', 'N/A')}]({doc.get('url', 'N/A')})

**Suggested Change**
The following change is recommended to address the user feedback:
---
{suggestion}
    """
    query = """
    mutation IssueCreate($title: String!, $description: String!, $projectId: String!, $teamId: String!) {
      issueCreate(input: {
        title: $title,
        description: $description,
        projectId: $projectId,
        teamId: $teamId
      }) {
        success
        issue {
          id
          identifier
          url
        }
      }
    }
    """

    variables = {
        "title": title,
        "description": description,
        "projectId": LINEAR_PROJECT_ID,
        "teamId": LINEAR_TEAM_ID
    }

    headers = {"Authorization": LINEAR_API_KEY,
               "Content-Type": "application/json"}

    try:
        response = requests.post("https://api.linear.app/graphql",
                                 json={"query": query, "variables": variables}, headers=headers)
        response.raise_for_status()

        result = response.json()
        if 'errors' in result:
            logger.error(f"GraphQL API returned errors: {result['errors']}")
            raise Exception(f"GraphQL errors: {result['errors']}")

        if result.get('data', {}).get('issueCreate', {}).get('success'):
            issue_data = result['data']['issueCreate']['issue']
            logger.info(
                f"Successfully created Linear ticket: {issue_data['identifier']}")
            return {
                "ticket_id": issue_data['id'],
                "ticket_identifier": issue_data['identifier'],
                "ticket_url": issue_data['url']
            }
        else:
            logger.error(
                f"Linear ticket creation failed. Full response: {result}")
            raise Exception(
                f"Linear ticket creation failed. Response: {result}")

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error creating Linear ticket: {e}")
        logger.error(f"Response Body: {e.response.text}")
        raise e
