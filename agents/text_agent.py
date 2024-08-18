# text_agent.py
import os
import json
import logging
from typing import Dict, Any
import requests
import openai
from rq import Queue
from redis import Redis

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI
openai.api_key = os.environ.get('OPENAI_API_KEY')

# Initialize Redis and RQ
redis_conn = Redis(host=os.environ.get('REDIS_HOST', 'localhost'), 
                   port=int(os.environ.get('REDIS_PORT', 6379)))
queue = Queue(connection=redis_conn)

AGGREGATOR_URL = os.environ.get('AGGREGATOR_URL', 'http://localhost:5000/aggregate')

def classify_issue(text: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a complaint classifier. Classify the following complaint into one of these categories: 'Problem with a purchase shown on your statement', 'Fees or interest', 'Closing your account', 'Getting a credit card', 'Problem when making payments', 'Other features, terms, or problems'."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message['content'].strip()

def classify_sub_issue(text: str, issue: str) -> str:
    sub_issues = {
        "Problem with a purchase shown on your statement": [
            "Credit card company isn't resolving a dispute about a purchase on your statement",
            "Overcharged for something you did purchase with the card",
            "Card was charged for something you did not purchase with the card"
        ],
        "Fees or interest": [
            "Problem with fees",
            "Charged too much interest"
        ],
        "Closing your account": [
            "Company closed your account"
        ],
        "Getting a credit card": [
            "Card opened without my consent or knowledge"
        ],
        "Problem when making payments": [
            "Problem during payment process"
        ]
    }
    
    if issue in sub_issues:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are a complaint sub-classifier. Classify the following complaint into one of these sub-categories: {', '.join(sub_issues[issue])}."},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message['content'].strip()
    return "Other sub-issue"

def extract_entities(text: str) -> Dict[str, list]:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Extract monetary amounts and dates from the following text. Return the result as a JSON object with keys 'monetary_amounts' and 'dates', each containing a list of extracted values."},
            {"role": "user", "content": text}
        ]
    )
    return json.loads(response.choices[0].message['content'])

def extract_key_phrases(text: str) -> list:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Extract up to 10 key phrases from the following text. Return the result as a JSON array."},
            {"role": "user", "content": text}
        ]
    )
    return json.loads(response.choices[0].message['content'])

def process_text_complaint(text: str) -> Dict[str, Any]:
    logger.info(f"Processing complaint: {text[:50]}...")

    # Use GPT-3.5 to analyze and categorize the complaint
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an AI assistant that categorizes customer complaints. Provide a category and a brief summary."},
            {"role": "user", "content": f"Categorize this complaint and provide a brief summary: {text}"}
        ]
    )
    
    analysis = response.choices[0].message['content']
    
    # Extract category and summary from the GPT-3.5 response
    lines = analysis.split('\n')
    category = lines[0].split(':')[-1].strip()
    summary = '\n'.join(lines[1:])

    # Classify issue and sub-issue
    issue = classify_issue(text)
    sub_issue = classify_sub_issue(text, issue)

    # Perform sentiment analysis
    sentiment_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Perform sentiment analysis on the following text. Return the result as a JSON object with keys 'label' (either 'POSITIVE' or 'NEGATIVE') and 'score' (a float between 0 and 1)."},
            {"role": "user", "content": text}
        ]
    )
    sentiment = json.loads(sentiment_response.choices[0].message['content'])

    # Extract entities
    entities = extract_entities(text)

    # Extract key phrases
    key_phrases = extract_key_phrases(text)

    # Prepare structured output
    structured_output = {
        "product": "Credit card",
        "issue": issue,
        "sub_issue": sub_issue,
        "summary": summary,
        "entities": entities,
        "sentiment": sentiment,
        "key_phrases": key_phrases,
        "original_text": text
    }

    # Send to aggregator
    response = requests.post(AGGREGATOR_URL, json={
        'type': 'text',
        'content': structured_output,
        'category': category
    })

    if response.status_code == 202:
        logger.info(f"Complaint processed and sent to aggregator. Task ID: {response.json()['task_id']}")
    else:
        logger.error(f"Failed to send complaint to aggregator. Status code: {response.status_code}")

    return response.json()

if __name__ == '__main__':
    # For testing
    sample_complaint = "I've been trying to reach customer service for days about a wrong charge of $50.00 on my card from 05/15/2024, but no one is responding!"
    result = queue.enqueue(process_text_complaint, sample_complaint)
    print(f"Job ID: {result.id}")