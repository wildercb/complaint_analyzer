# text_agent.py
import openai
import requests
import os
import spacy
from textblob import TextBlob
from transformers import pipeline
from celery import Celery
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI
openai.api_key = os.environ.get('OPENAI_API_KEY')

# Initialize spaCy
nlp = spacy.load("en_core_web_sm")

# Initialize sentiment analysis pipeline
sentiment_pipeline = pipeline("sentiment-analysis")

# Initialize Celery
celery = Celery('text_agent', broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'))

AGGREGATOR_URL = os.environ.get('AGGREGATOR_URL', 'http://localhost:5000/aggregate')

@celery.task
def process_text_complaint(text):
    logger.info(f"Processing complaint: {text[:50]}...")

    # Use GPT-4 to analyze and categorize the complaint
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an AI assistant that categorizes customer complaints."},
            {"role": "user", "content": f"Categorize this complaint and provide a brief summary: {text}"}
        ]
    )
    
    analysis = response.choices[0].message['content']
    
    # Extract category and summary from the GPT-4 response
    lines = analysis.split('\n')
    category = lines[0].split(':')[-1].strip()
    summary = '\n'.join(lines[1:])

    # Perform named entity recognition
    doc = nlp(text)
    entities = [(ent.text, ent.label_) for ent in doc.ents]

    # Perform sentiment analysis
    sentiment = sentiment_pipeline(text)[0]

    # Perform subjectivity analysis
    blob = TextBlob(text)
    subjectivity = blob.sentiment.subjectivity

    # Extract key phrases (simplified)
    key_phrases = [chunk.text for chunk in doc.noun_chunks]

    # Send to aggregator
    response = requests.post(AGGREGATOR_URL, json={
        'type': 'text',
        'content': {
            'original': text,
            'summary': summary,
            'entities': entities,
            'sentiment': sentiment,
            'subjectivity': subjectivity,
            'key_phrases': key_phrases
        },
        'category': category
    })

    if response.status_code == 202:
        logger.info(f"Complaint processed and sent to aggregator. Task ID: {response.json()['task_id']}")
    else:
        logger.error(f"Failed to send complaint to aggregator. Status code: {response.status_code}")

    return response.json()

if __name__ == '__main__':
    # For testing
    sample_complaint = "I've been trying to reach customer service for days about a wrong charge on my card, but no one is responding!"
    result = process_text_complaint.delay(sample_complaint)
    print(f"Task ID: {result.id}")