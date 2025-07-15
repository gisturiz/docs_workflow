import os
import requests
import json
import logging
from datetime import datetime, timedelta, timezone
from shared.utils import get_secrets

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Ingests messages and their threads from specified Discord channels.
    Filters out messages from bots.
    """
    logger.info("Starting Discord ingestion...")
    secrets = get_secrets()
    DISCORD_BOT_TOKEN = secrets.get("DISCORD_BOT_TOKEN")
    
    if not DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN environment variable not set")
        raise ValueError("DISCORD_BOT_TOKEN environment variable not set")
    
    channel_ids = os.environ.get("DISCORD_CHANNEL_IDS", "").split(',')
    if not all(channel_ids):
        logger.error("DISCORD_CHANNEL_IDS environment variable not set or empty.")
        raise ValueError("DISCORD_CHANNEL_IDS environment variable not set or empty.")

    since_days = event.get("since_days", 7)
    after_timestamp = datetime.now(timezone.utc) - timedelta(days=since_days)

    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    all_conversations = []

    for channel_id in channel_ids:
        logger.info(f"Fetching messages from channel: {channel_id}")
        messages_url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=100"
        
        try:
            response = requests.get(messages_url, headers=headers)
            response.raise_for_status()
            messages = response.json()

            channel_info_res = requests.get(f"https://discord.com/api/v10/channels/{channel_id}", headers=headers)
            channel_info_res.raise_for_status()
            channel_name = channel_info_res.json().get('name', channel_id)

            for msg in messages:
                msg_timestamp = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                
                if msg_timestamp > after_timestamp and not msg.get('author', {}).get('bot', False):
                    author_info = msg.get('author', {})
                    conversation = {
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "main_message": msg.get('content', ''),
                        "author": author_info.get('username', 'Unknown'),
                        "message_id": msg['id'],
                        "quotes": [f"'{msg.get('content', '')}' - (from {author_info.get('username', 'Unknown')})"],
                        "thread_messages": []
                    }

                    if 'thread' in msg:
                        thread_id = msg['thread']['id']
                        logger.info(f"Fetching thread {thread_id} for message {msg['id']}")
                        thread_url = f"https://discord.com/api/v10/channels/{thread_id}/messages?limit=100"
                        thread_res = requests.get(thread_url, headers=headers)
                        if thread_res.ok:
                            thread_msgs = thread_res.json()
                            for thread_msg in reversed(thread_msgs):
                                if not thread_msg.get('author', {}).get('bot', False):
                                    thread_author = thread_msg.get('author', {})
                                    content = thread_msg.get('content', '')
                                    conversation['thread_messages'].append(content)
                                    conversation['quotes'].append(f"'{content}' - (from {thread_author.get('username', 'Unknown')})")
                    
                    all_conversations.append(conversation)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch data for channel {channel_id}: {e}")
            # Continue to the next channel instead of failing the whole function
            continue

    logger.info(f"Ingested {len(all_conversations)} conversations.")
    return {"conversations": all_conversations}