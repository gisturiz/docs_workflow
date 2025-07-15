import json
import openai
import numpy as np
from sklearn.cluster import DBSCAN
from collections import defaultdict
import logging

from shared.utils import get_secrets

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Takes conversations, groups them by channel, and uses a batch LLM call per channel
    to identify trends. It then clusters these trends to create final insights.
    """
    logger.info("Starting batched insight clustering by channel...")
    secrets = get_secrets()
    
    client = openai.OpenAI(api_key=secrets.get("OPENAI_API_KEY"))
    
    conversations = event.get("conversations", [])
    if not conversations:
        logger.info("No conversations to process.")
        return {"clusters": []}

    conversations_by_channel = defaultdict(list)
    for conv in conversations:
        conversations_by_channel[conv['channel_name']].append(conv)
    
    logger.info(f"Grouped conversations into {len(conversations_by_channel)} channels.")

    extracted_issues = []
    for channel_name, channel_convos in conversations_by_channel.items():
        logger.info(f"Processing batch for channel: {channel_name} ({len(channel_convos)} conversations)")

        formatted_convos = []
        for i, conv in enumerate(channel_convos):
            full_text = conv['main_message'] + "\n" + "\n".join(conv['thread_messages'])
            formatted_convos.append(f"Conversation {i}:\n---\n{full_text}\n---")

        batch_prompt = f"""
        You are an expert developer support analyst. Your task is to identify recurring issues and trends from the following conversations in the '{channel_name}' support channel.

        Analyze all conversations and group them by the underlying problem. For each distinct problem you identify, provide a concise summary.

        Your response MUST be a valid JSON object with a single key "identified_issues", which is an array of objects. Each object in the array represents a distinct issue and must have the following keys:
        - "summary": A one-sentence summary of the recurring problem or trend.
        - "conversation_indices": A list of integer indexes for all conversations that relate to this summary.

        Example Response:
        {{
          "identified_issues": [
            {{
              "summary": "Users are consistently confused about the correct value for the 'aud' (audience) claim in JWT authentication.",
              "conversation_indices": [0, 5, 12]
            }}
          ]
        }}

        Here are the conversations:

        {"\n\n".join(formatted_convos)}
        """

        try:
            response = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[{"role": "user", "content": batch_prompt}],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            for issue in result.get("identified_issues", []):
                all_quotes = []
                for index in issue['conversation_indices']:
                    if index < len(channel_convos):
                        all_quotes.extend(channel_convos[index]['quotes'])
                
                extracted_issues.append({
                    "summary": issue['summary'],
                    "original_quotes": all_quotes,
                    "channel_name": channel_name
                })
        except Exception as e:
            logger.error(f"Error processing batch for channel {channel_name}: {e}")
            continue

    if not extracted_issues:
        logger.info("LLM did not identify any actionable issues in any channel.")
        return {"clusters": []}

    logger.info(f"Embedding {len(extracted_issues)} identified issues...")
    summaries = [issue['summary'] for issue in extracted_issues]
    
    response = client.embeddings.create(
        input=summaries, 
        model="text-embedding-3-small"
    )
    embeddings = [item.embedding for item in response.data]
    
    logger.info("Clustering embeddings to consolidate final insights...")
    clustering = DBSCAN(eps=0.3, min_samples=1, metric="cosine").fit(embeddings)
    labels = clustering.labels_
    
    final_clusters = []
    unique_labels = set(labels)
    for label in unique_labels:
        if label == -1:
            continue
        
        cluster_indices = np.where(labels == label)[0]
        cluster_issues = [extracted_issues[i] for i in cluster_indices]
        
        all_quotes = []
        for issue in cluster_issues:
            all_quotes.extend(issue['original_quotes'])
        
        final_summary = cluster_issues[0]['summary']
        
        final_clusters.append({
            "summary": final_summary,
            "quotes": all_quotes,
            "channel_name": cluster_issues[0]['channel_name']
        })

    logger.info(f"Generated {len(final_clusters)} final insights.")
    return {"clusters": final_clusters}
