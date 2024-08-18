# image_agent.py
import os
import requests
import io
from google.cloud import vision
from google.cloud import language_v1
import cv2
import numpy as np
from PIL import Image
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Google Cloud clients
vision_client = vision.ImageAnnotatorClient()
language_client = language_v1.LanguageServiceClient()

AGGREGATOR_URL = os.environ.get('AGGREGATOR_URL', 'http://localhost:5000/aggregate')

def enhance_image(image_content):
    # Convert bytes to numpy array
    nparr = np.frombuffer(image_content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Denoise
    denoised = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)

    # Enhance contrast
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    cl = clahe.apply(l)
    enhanced_lab = cv2.merge((cl,a,b))
    enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    # Convert back to bytes
    is_success, buffer = cv2.imencode(".jpg", enhanced)
    return buffer.tobytes()

def process_image_complaint(image_content):
    logger.info("Processing image complaint...")

    # Enhance image
    enhanced_image = enhance_image(image_content)

    # Perform image analysis
    image = vision.Image(content=enhanced_image)
    
    # Detect text
    text_detection_response = vision_client.text_detection(image=image)
    texts = text_detection_response.text_annotations
    
    # Detect labels
    label_detection_response = vision_client.label_detection(image=image)
    labels = label_detection_response.label_annotations
    
    # Detect objects
    object_detection_response = vision_client.object_localization(image=image)
    objects = object_detection_response.localized_object_annotations
    
    # Perform sentiment analysis on detected text
    if texts:
        document = language_v1.Document(content=texts[0].description, type_=language_v1.Document.Type.PLAIN_TEXT)
        sentiment = language_client.analyze_sentiment(request={'document': document}).document_sentiment
    else:
        sentiment = None

    # Prepare content for aggregator
    content = {
        'text': texts[0].description if texts else '',
        'labels': [{'description': label.description, 'score': label.score} for label in labels],
        'objects': [{'name': obj.name, 'score': obj.score} for obj in objects],
        'sentiment': {'score': sentiment.score, 'magnitude': sentiment.magnitude} if sentiment else None
    }

    # Determine category based on detected objects and labels
    categories = set([obj.name for obj in objects] + [label.description for label in labels])
    category = 'General Image Complaint'
    if 'receipt' in categories or 'document' in categories:
        category = 'Document-related Complaint'
    elif 'product' in categories or 'merchandise' in categories:
        category = 'Product-related Complaint'
    elif 'error' in categories or 'warning' in categories:
        category = 'Error or Warning Complaint'

    # Send to aggregator
    response = requests.post(AGGREGATOR_URL, json={
        'type': 'image',
        'content': content,
        'category': category
    })

    if response.status_code == 202:
        logger.info(f"Image complaint processed and sent to aggregator. Task ID: {response.json()['task_id']}")
    else:
        logger.error(f"Failed to send image complaint to aggregator. Status code: {response.status_code}")

    return response.json()

if __name__ == '__main__':
    # For testing, you would need to provide an image file
    with open('sample_complaint.jpg', 'rb') as image_file:
        image_content = image_file.read()
    result = process_image_complaint.delay(image_content)
    print(f"Task ID: {result.id}")