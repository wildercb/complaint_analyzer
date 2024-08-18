# voice_agent.py
import os
import requests
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import language_v1
from pydub import AudioSegment
import io
import wave
import numpy as np
from scipy.io import wavfile
import noisereduce as nr
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Google Cloud clients
speech_client = speech.SpeechClient()
language_client = language_v1.LanguageServiceClient()


AGGREGATOR_URL = os.environ.get('AGGREGATOR_URL', 'http://localhost:5000/aggregate')

def enhance_audio(audio_content):
    # Convert to wav
    audio = AudioSegment.from_file(io.BytesIO(audio_content), format="mp3")
    buf = io.BytesIO()
    audio.export(buf, format="wav")
    buf.seek(0)

    # Read wav file
    with wave.open(buf, "rb") as wave_file:
        frame_rate = wave_file.getframerate()
        wav_data = np.frombuffer(wave_file.readframes(-1), dtype=np.int16)

    # Reduce noise
    reduced_noise = nr.reduce_noise(y=wav_data, sr=frame_rate)

    # Convert back to bytes
    enhanced_buf = io.BytesIO()
    wavfile.write(enhanced_buf, frame_rate, reduced_noise.astype(np.int16))
    return enhanced_buf.getvalue()

def process_voice_complaint(audio_content):
    logger.info("Processing voice complaint...")

    # Enhance audio
    enhanced_audio = enhance_audio(audio_content)

    # Transcribe audio
    audio = speech.RecognitionAudio(content=enhanced_audio)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
        enable_automatic_punctuation=True,
        enable_speaker_diarization=True,
        diarization_speaker_count=2,
    )

    response = speech_client.recognize(config=config, audio=audio)
    transcript = response.results[-1].alternatives[0].transcript

    # Perform sentiment analysis
    document = language_v1.Document(content=transcript, type_=language_v1.Document.Type.PLAIN_TEXT)
    sentiment = language_client.analyze_sentiment(request={'document': document}).document_sentiment

    # Perform entity analysis
    entities = language_client.analyze_entities(request={'document': document}).entities

    # Send to aggregator
    response = requests.post(AGGREGATOR_URL, json={
        'type': 'voice',
        'content': {
            'transcript': transcript,
            'sentiment': {
                'score': sentiment.score,
                'magnitude': sentiment.magnitude
            },
            'entities': [{
                'name': entity.name,
                'type': language_v1.Entity.Type(entity.type_).name,
                'salience': entity.salience
            } for entity in entities]
        },
        'category': 'Voice Complaint'  # You might want to determine this based on the content
    })

    if response.status_code == 202:
        logger.info(f"Voice complaint processed and sent to aggregator. Task ID: {response.json()['task_id']}")
    else:
        logger.error(f"Failed to send voice complaint to aggregator. Status code: {response.status_code}")

    return response.json()

if __name__ == '__main__':
    # For testing, you would need to provide an audio file
    with open('sample_complaint.mp3', 'rb') as audio_file:
        audio_content = audio_file.read()
    result = process_voice_complaint.delay(audio_content)
    print(f"Task ID: {result.id}")