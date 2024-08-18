# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS

from elasticsearch import Elasticsearch, ElasticsearchException
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from redis import Redis
from rq import Queue
from celery import Celery
from celery.result import AsyncResult
import logging
from opencensus.ext.flask.flask_middleware import FlaskMiddleware
from opencensus.trace import samplers
from opencensus.ext.azure.trace_exporter import AzureExporter
from prometheus_flask_exporter import PrometheusMetrics
from datetime import datetime

# Import agents
import sys
agents_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'agents'))
sys.path.append(agents_dir)

# Now import the agent modules
from text_agent import process_text_complaint
from voice_agent import process_voice_complaint
from image_agent import process_image_complaint
from video_agent import process_video_complaint


def create_app():
    app = Flask(__name__)
    CORS(app)

    celery = Celery(app.name, broker='redis://redis:6379/0')
    celery.conf.update(app.config)

    # Distributed tracing
    middleware = FlaskMiddleware(
        app,
        # exporter=AzureExporter(connection_string="InstrumentationKey=<your-instrumentation-key>"),
        sampler=samplers.ProbabilitySampler(rate=1.0),
    )

    # Prometheus metrics
    metrics = PrometheusMetrics(app)

    # Logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    db_user = os.environ.get('POSTGRES_USER', 'postgres')
    db_pass = os.environ.get('POSTGRES_PASSWORD', 'postgres')
    db_host = os.environ.get('POSTGRES_HOST', 'localhost')
    db_port = os.environ.get('POSTGRES_PORT', '5433')
    db_name = 'complaints'
    db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    # Database setup function
    def setup_database():
        db_name = os.environ.get('POSTGRES_DB', 'complaints')
        db_user = os.environ.get('POSTGRES_USER', 'user')
        db_pass = os.environ.get('POSTGRES_PASSWORD', 'password')
        db_host = os.environ.get('POSTGRES_HOST', 'localhost')

        # Connect to default 'postgres' database to create new database if it doesn't exist
        conn = psycopg2.connect(dbname='postgres', user=db_user, password=db_pass, host=db_host)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Create database if it doesn't exist
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{db_name}'")
        exists = cur.fetchone()
        if not exists:
            cur.execute(f'CREATE DATABASE {db_name}')
            logger.info(f"Database '{db_name}' created.")
        else:
            logger.info(f"Database '{db_name}' already exists.")

        cur.close()
        conn.close()

        # Initialize SQLAlchemy
        db_url = f"postgresql://{db_user}:{db_pass}@{db_host}/{db_name}"
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)

        Base = declarative_base()

        class Complaint(Base):
            __tablename__ = 'complaints'

            id = Column(Integer, primary_key=True)
            type = Column(String(50), nullable=False)
            content = Column(JSON, nullable=False)
            category = Column(String(100), nullable=False)
            created_at = Column(DateTime, default=datetime.utcnow)

        Base.metadata.create_all(engine)

        logger.info("Database setup completed.")
        return engine, Session, Complaint

    def setup_elasticsearch():
        if not es.indices.exists(index="complaints"):
            es.indices.create(index="complaints", body={
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                },
                "mappings": {
                    "properties": {
                        "type": {"type": "keyword"},
                        "content": {"type": "text"},
                        "category": {"type": "keyword"}
                    }
                }
            })
        logger.info("Elasticsearch index 'complaints' setup completed.")

    # Run database setup before first request
    with app.app_context():
        # engine, Session, Complaint = setup_database()
        def initialize_database():
            global engine, Session, Complaint
            engine, Session, Complaint = setup_database()

        # Initialize Elasticsearch
        es = Elasticsearch([os.environ.get('ELASTICSEARCH_URL', 'http://localhost:9200')])

        # Initialize Redis and RQ
        redis_conn = Redis(host=os.environ.get('REDIS_HOST', 'localhost'),
                        port=int(os.environ.get('REDIS_PORT', 6379)))
        task_queue = Queue(connection=redis_conn)

    # Initialize Celery
    celery = Celery(app.name, 
                    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
                    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'))

    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    @celery.task
    def process_complaint(data):
        logger.debug(f"Starting to process complaint: {data}")
        logger.info(f"Starting to process complaint: {data}")
        complaint_type = data.get('type')
        content = data.get('content')
        
        # Process the complaint based on its type
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
            # Create a new session for this task
            Session = sessionmaker(bind=engine)
            session = Session()
            
            new_complaint = Complaint(type=complaint_type, content=processed_data, category=category)
            session.add(new_complaint)
            session.commit()
            complaint_id = new_complaint.id
            
            # Index in Elasticsearch
            es.index(index='complaints', id=complaint_id, body={
                'type': complaint_type,
                'content': processed_data.get('summary', ''),  # Only index the summary if available
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



    @celery.task
    def optimize_elasticsearch_index():
        try:
            es.indices.forcemerge(index="complaints", max_num_segments=1)
            logger.info("Elasticsearch index 'complaints' optimized.")
        except ElasticsearchException as e:
            logger.error(f"Error optimizing Elasticsearch index: {str(e)}")

    # Schedule this task to run periodically, e.g., once a day
    @celery.on_after_configure.connect
    def setup_periodic_tasks(sender, **kwargs):
        sender.add_periodic_task(
            86400.0,  # 24 hours in seconds
            optimize_elasticsearch_index.s(),
            name='optimize_elasticsearch_daily'
        )


    # send complaints 
    @app.route('/api/complaints', methods=['POST'])
    @metrics.counter('api_complaints_received', 'Number of complaints received via API')
    def submit_complaint():
        data = request.json
        task = process_complaint.delay(data)
        return jsonify({'status': 'processing', 'task_id': str(task.id)}), 202

    @app.route('/api/complaints/<task_id>', methods=['GET'])
    def get_complaint_result(task_id):
        try:
            task = AsyncResult(task_id, app=celery)
            if task.ready():
                result = task.result
                return jsonify({
                    'status': 'completed',
                    'result': result
                })
            else:
                return jsonify({
                    'status': 'processing',
                    'state': task.state,
                    'info': str(task.info)
                }), 202
        except Exception as e:
            app.logger.error(f"Error retrieving task result: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'An error occurred while retrieving the task result',
                'error': str(e)
            }), 500
        
    @app.route('/aggregate', methods=['POST'])
    @metrics.counter('complaints_received', 'Number of complaints received')
    def aggregate_complaint():
        data = request.json
        task = process_complaint.delay(data)
        return jsonify({'status': 'processing', 'task_id': str(task.id)}), 202

    @app.route('/search', methods=['GET'])
    @metrics.counter('complaints_searched', 'Number of complaint searches')
    def search_complaints():
        query = request.args.get('q', '')
        try:
            results = es.search(index='complaints', body={
                'query': {
                    'multi_match': {
                        'query': query,
                        'fields': ['content', 'category']
                    }
                }
            })
            return jsonify(results['hits']['hits'])
        except Exception as e:
            logger.error(f"Error searching complaints: {str(e)}")
            return jsonify({'error': 'An error occurred while searching'}), 500

    @app.route('/status/<task_id>')
    def task_status(task_id):
        task = celery.AsyncResult(task_id)
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'Pending...'
            }
        elif task.state != 'FAILURE':
            response = {
                'state': task.state,
                'status': task.info.get('status', '')
            }
        else:
            response = {
                'state': task.state,
                'status': str(task.info),
            }
        return jsonify(response)
    return app

app = create_app()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')