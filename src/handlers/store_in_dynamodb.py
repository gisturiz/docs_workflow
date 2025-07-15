import os
import json
import boto3
from decimal import Decimal


def handler(event, context):
    """
    Stores the created ticket information in DynamoDB for the feedback loop.
    """
    print(
        f"Storing ticket {event['ticket']['ticket_identifier']} in DynamoDB...")
    DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE")
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(DYNAMODB_TABLE)

    ticket_info = event.get('ticket', {})
    doc_info = event.get('documentation', {})
    suggestion_info = event.get('suggestion', {})

    item = {
        "ticket_id": ticket_info.get('ticket_id'),
        "ticket_identifier": ticket_info.get('ticket_identifier'),
        "ticket_url": ticket_info.get('ticket_url'),
        "insight_summary": event.get('summary'),
        "llm_suggestion": suggestion_info.get('llm_suggestion'),
        "doc_url": doc_info.get('url'),
        "status": "Triage"
    }

    # Filter out any keys with None values before saving
    item_to_save = {k: v for k, v in item.items() if v is not None}

    # Convert floats to Decimals for DynamoDB if necessary
    item_to_save = json.loads(json.dumps(item_to_save), parse_float=Decimal)

    table.put_item(Item=item_to_save)
    print("Successfully stored ticket in DynamoDB.")
    return {
        "status": "SUCCESS",
        "ticket_identifier": item_to_save.get('ticket_identifier')
    }
