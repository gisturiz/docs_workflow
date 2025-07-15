import os
import boto3
import json

_secrets_cache = None

def get_secrets():
    """
    Retrieves secrets.
    If running locally (AWS_SAM_LOCAL is true), it reads secrets directly from environment variables.
    Otherwise, it fetches them from AWS Secrets Manager and caches the result.
    """
    global _secrets_cache
    if _secrets_cache:
        return _secrets_cache

    # Check if we are in a local SAM environment
    if os.environ.get("AWS_SAM_LOCAL"):
        print("Running in local mode. Loading secrets from environment variables.")
        _secrets_cache = {
            "DISCORD_BOT_TOKEN": os.environ.get("DISCORD_BOT_TOKEN"),
            "DISCORD_CHANNEL_IDS": os.environ.get("DISCORD_CHANNEL_IDS"),
            "LINEAR_API_KEY": os.environ.get("LINEAR_API_KEY"),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "PINECONE_API_KEY": os.environ.get("PINECONE_API_KEY"),
            "PINECONE_ENVIRONMENT": os.environ.get("PINECONE_ENVIRONMENT"),
            "PINECONE_INDEX_NAME": os.environ.get("PINECONE_INDEX_NAME"),
        }
        return _secrets_cache

    # --- Deployed environment logic ---
    secret_arn = os.environ.get("SECRETS_ARN")
    if not secret_arn:
        raise ValueError("SECRETS_ARN environment variable not set.")

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager')

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_arn)
        secret = get_secret_value_response['SecretString']
        _secrets_cache = json.loads(secret)
        return _secrets_cache
    except Exception as e:
        print(f"Error retrieving secrets from AWS Secrets Manager: {e}")
        raise e