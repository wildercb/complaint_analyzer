# video_agent.py
import os
import requests
import io
from google.cloud import videointelligence
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import language_v1
import cv2
import numpy as np
from celery import Celery
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Google Cloud clients
video_client = videointelligence.VideoIntelligenceServiceClient()
speech_client = speech.SpeechClient()
language_client = language_v1.LanguageServiceClient()

# Initialize Celery
celery = Celery('video_agent', broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'))

AGGREGATOR_URL = os.environ.get('AGGREGATOR_URL', 'http://localhost:5000/aggregate')

def extract_audio(video_content):
    # Save video content to a temporary file
    temp_video = 'temp_video.mp4'
    with open(temp_video, 'wb') as f:
        f.write(video_content)

    # Extract audio using OpenCV
    video = cv2.VideoCapture(temp_video)
    fps = video.get(cv2.CAP_PROP_FPS)
    audio_output = 'temp_audio.wav'
    os.system(f"ffmpeg -i {temp_video} -ab 160k -ac 2 -ar 44100 -vn {audio_output}")

    # Read the audio file
    with open(audio_output, 'rb') as audio_file:
        audio_content = audio_file.read()

    # Clean up temporary files
    os.remove(temp_video)
    os.remove(audio_output)

    return audio_content, fps

@celery.task
def process_video_complaint(video_content):
    logger.info("Processing video complaint...")

    # Extract audio from video
    audio_content, fps = extract_audio(video_content)

    # Perform video analysis
    features = [videointelligence.Feature.LABEL_DETECTION,
                videointelligence.Feature.OBJECT_TRACKING,
                videointelligence.Feature.TEXT_DETECTION]

    operation = video_client.annotate_video(
        request={"features": features, "input_content": video_content}
    )
    logger.info("Waiting for video analysis to complete...")
    result = operation.result(timeout=90)

    # Process video labels
    labels = []
    for label in result.annotation_results[0].segment_label_annotations:
        labels.append({
            'description': label.entity.description,
            'confidence': label.segments[0].confidence
        })

    # Process tracked objects
    objects = []
    for obj in result.annotation_results[0].object_annotations:
        objects.append({
            'description': obj.entity.description,
            'confidence': obj.confidence
        })

    # Process detected text
    texts = []
    for text in result.annotation_results[0].text_annotations:
        texts.append({
            'text': text.text,
            'confidence': text.segments[0].confidence
        })

    # Perform speech recognition on extracted audio
    audio = speech.RecognitionAudio(content=audio_content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=44100,
        language_code="en-US",
        enable_automatic_punctuation=True,
    )

    response = speech_client.recognize(config=config, audio=audio)
    transcript = ' '.join([result.alternatives[0].transcript for result in response.results])

    # Perform sentiment analysis on transcript
    document = language_v1.Document(content=transcript, type_=language_v1.Document.Type.PLAIN_TEXT)
    sentiment = language_client.analyze_sentiment(request={'document': document}).document_sentiment

    # Prepare content for aggregator
    content = {
        'labels': labels,
        'objects': objects,
        'texts': texts,
        'transcript': transcript,
        'sentiment': {
            'score': sentiment.score,
            'magnitude': sentiment.magnitude
        }
    }

    # Determine category based on detected objects and labels
    categories = set([obj['description'] for obj in objects] + [label['description'] for label in labels])
    category = 'General Video Complaint'
    if 'product' in categories or 'merchandise' in categories:
        category = 'Product-related Video Complaint'
    elif 'store' in categories or 'shop' in categories:
        category = 'In-store Video Complaint'
    elif 'website' in categories or 'app' in categories:
        category = 'Digital Service Video Complaint'

    # Send to aggregator
    response = requests.post(AGGREGATOR_URL, json={
        'type': 'video',
        'content': content,
        'category': category
    })

    if response.status_code == 202:
        logger.info(f"Video complaint processed and sent to aggregator. Task ID: {response.json()['task_id']}")
    else:
        logger.error(f"Failed to send video complaint to aggregator. Status code: {response.status_code}")

    return response.json()

if __name__ == '__main__':
    # For testing, you would need to provide a video file
    with open('sample_complaint.mp4', 'rb') as video_file:
        video_content = video_file.read()
    result = process_video_complaint.delay(video_content)
    print(f"Task ID: {result.id}")