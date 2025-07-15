import json
import openai
import logging

from shared.utils import get_secrets

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Takes the insight and relevant doc text, and asks an LLM to generate
    a specific, actionable documentation change.
    """
    logger.info("Generating documentation suggestion...")
    secrets = get_secrets()
    
    client = openai.OpenAI(api_key=secrets.get("OPENAI_API_KEY"))

    # The Step Functions Map state passes the item as the event
    insight = event
    doc = event.get('documentation', {})

    if not doc or not insight:
        logger.warning("Missing documentation or insight in the input event.")
        return {"llm_suggestion": "Could not generate suggestion due to missing input."}

    prompt = f"""
    You are an expert technical writer tasked with improving developer documentation based on user feedback.

    **User Feedback Insight:**
    {insight.get('summary', 'No summary provided.')}

    **Direct User Quotes:**
    - {"\n- ".join(insight.get('quotes', []))}

    **Existing Documentation from page {doc.get('url', 'N/A')}:**
    ---
    {doc.get('text', 'No documentation text found.')}
    ---

    **Your Task:**
    Based on the user feedback, suggest a specific, concrete change to the documentation to resolve their confusion.
    Your suggestion should be clear and easy for an engineer to implement.
    Format your response clearly. For example, use a "SUGGESTED CHANGE" section. If you are suggesting adding a new section, provide the full text for that section. If you are suggesting modifying existing text, show the "BEFORE" and "AFTER".
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        suggestion = response.choices[0].message.content.strip()
        
        logger.info("Suggestion generated successfully.")
        return {"llm_suggestion": suggestion}
    except Exception as e:
        logger.error(f"Error calling OpenAI to generate suggestion: {e}")
        return {"llm_suggestion": f"Failed to generate suggestion: {e}"}