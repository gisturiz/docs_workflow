import os
import json
import boto3

def handler(event, context):
    """
    Processes incoming webhooks from Linear to update ticket status in DynamoDB.
    Triggered by API Gateway.
    """
    print("Processing Linear webhook...")
    DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE")
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(DYNAMODB_TABLE)

    try:
        body = json.loads(event.get("body", "{}"))
        
        # We only care about updates
        if body.get("action") != "update":
            return {"statusCode": 200, "body": "OK (Not an update action)"}

        data = body.get("data", {})
        updated_from = body.get("updatedFrom", {})
        
        # Check if the status (state) was changed
        if "stateId" in updated_from:
            ticket_id = data.get("id")
            new_status = data.get("state", {}).get("name")
            
            if ticket_id and new_status:
                print(f"Updating ticket {ticket_id} to status '{new_status}'")
                table.update_item(
                    Key={"ticket_id": ticket_id},
                    UpdateExpression="SET #s = :s",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":s": new_status}
                )
        
        return {"statusCode": 200, "body": "Webhook processed successfully."}

    except Exception as e:
        print(f"Error processing webhook: {e}")
        # Return 200 even on error so Linear doesn't retry indefinitely
        return {"statusCode": 200, "body": "Error processing webhook."}