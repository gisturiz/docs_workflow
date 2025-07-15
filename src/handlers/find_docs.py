import json
import openai
import pinecone
import logging

from shared.utils import get_secrets

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Takes a clustered insight and finds the most relevant documentation page
    from the vector database.
    """
    insight_summary = event.get('summary', '')
    if not insight_summary:
        logger.warning("Input event is missing a 'summary'. Cannot find docs.")
        return {}

    logger.info(f"Finding relevant docs for insight: {insight_summary[:80]}...")
    secrets = get_secrets()
    
    openai_client = openai.OpenAI(api_key=secrets.get("OPENAI_API_KEY"))

    pc = pinecone.Pinecone(api_key=secrets.get("PINECONE_API_KEY"))
    index_name = secrets.get("PINECONE_INDEX_NAME")
    
    if index_name not in pc.list_indexes().names():
        logger.error(f"Pinecone index '{index_name}' does not exist.")
        raise ValueError(f"Pinecone index '{index_name}' does not exist.")
        
    index = pc.Index(index_name)

    try:
        # 1. Embed the insight summary using the new syntax
        response = openai_client.embeddings.create(
            input=[insight_summary], 
            model="text-embedding-3-small"
        )
        query_vector = response.data[0].embedding

        # 2. Query Pinecone
        query_response = index.query(
            vector=query_vector,
            top_k=1,
            include_metadata=True
        )

        if query_response.get('matches'):
            match = query_response['matches'][0]
            logger.info(f"Found match with score {match.get('score', 'N/A')}: {match.get('metadata', {}).get('url', 'N/A')}")
            # Return the metadata directly, which should contain text, url, etc.
            return match.get('metadata', {})
        else:
            logger.warning("No relevant documentation found in Pinecone.")
            return {}
            
    except Exception as e:
        logger.error(f"An error occurred during vector search: {e}")
        raise e