# aggregator/tasks.py

import logging
from agents.text_agent import process_text_complaint
from agents.voice_agent import process_voice_complaint
from agents.image_agent import process_image_complaint
from agents.video_agent import process_video_complaint
from database import SessionLocal, Complaint, es

logger = logging.getLogger(__name__)

def process_complaint(data):
    logger.info(f"Starting to process complaint: {data}")
    complaint_type = data.get('type')
    content = data.get('content')
    
    if complaint_type == 'text':
        processed_data = process_text_complaint(content)
    elif complaint_type == 'voice':
        processed_data = process_voice_complaint(content)
    elif complaint_type == 'image':
        processed_data = process_image_complaint(content)
    elif complaint_type == 'video':
        processed_data = process_video_complaint(content)
    else:
        logger.error(f"Unknown complaint type: {complaint_type}")
        return None

    category = processed_data.get('category')
    logger.info(f"Complaint processed. Category: {category}")
    
    try:
        session = SessionLocal()
        new_complaint = Complaint(type=complaint_type, content=processed_data, category=category)
        session.add(new_complaint)
        session.commit()
        complaint_id = new_complaint.id
        
        es.index(index='complaints', id=complaint_id, body={
            'type': complaint_type,
            'content': processed_data.get('summary', ''),
            'category': category
        })
        
        logger.info(f"Processed complaint ID: {complaint_id}")
        return {
            'complaint_id': complaint_id,
            'category': category,
            'processed_data': processed_data
        }
    except Exception as e:
        logger.error(f"Error processing complaint: {str(e)}")
        return None
    finally:
        session.close()