# src/handlers/debug_secrets.py

import os
import json
import logging

# We will import our existing utility function to test it directly
from shared.utils import get_secrets

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    A simple function to test if we can successfully read from Secrets Manager.
    """
    logger.info("--- STARTING SECRET DEBUGGING ---")
    
    # Log the environment variable to make sure it's being passed correctly
    secrets_arn = os.environ.get("SECRETS_ARN")
    logger.info(f"Attempting to read from Secrets ARN: {secrets_arn}")

    if not secrets_arn:
        logger.error("FATAL: SECRETS_ARN environment variable is not set!")
        return {"status": "failed", "reason": "SECRETS_ARN not set"}

    try:
        # Call the exact same function our other handlers use
        secrets = get_secrets()
        
        logger.info("Successfully called get_secrets().")
        
        # Check for the specific key we need
        discord_token = secrets.get("DISCORD_BOT_TOKEN")
        
        if discord_token:
            logger.info("SUCCESS: Found DISCORD_BOT_TOKEN in secrets.")
            # We'll just show the first few characters to confirm it's not empty
            logger.info(f"Token starts with: {discord_token[:8]}...")
            return {"status": "success", "token_found": True, "token_prefix": f"{discord_token[:8]}..."}
        else:
            logger.error("FAILURE: DISCORD_BOT_TOKEN key was NOT found in the retrieved secret.")
            logger.info(f"All keys found in secret: {list(secrets.keys())}")
            return {"status": "failed", "reason": "Key not in secret", "keys_found": list(secrets.keys())}

    except Exception as e:
        logger.error(f"An exception occurred while trying to get secrets: {e}", exc_info=True)
        return {"status": "failed", "reason": str(e)}