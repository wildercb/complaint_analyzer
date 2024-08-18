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
from rq.job import Job
from redis import Redis

import logging
from opencensus.ext.flask.flask_middleware import FlaskMiddleware
from opencensus.trace import samplers
from opencensus.ext.azure.trace_exporter import AzureExporter
from prometheus_flask_exporter import PrometheusMetrics
from datetime import datetime

import sys

# Get the absolute path of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory
parent_dir = os.path.dirname(current_dir)
# Add the parent directory to sys.path
sys.path.append(parent_dir)

print("Current directory:", current_dir)
print("Parent directory:", parent_dir)
print("Python path:", sys.path)

# import the agent modules
from agents.text_agent import process_text_complaint
from agents.voice_agent import process_voice_complaint
from agents.image_agent import process_image_complaint
from agents.video_agent import process_video_complaint
from aggregator.tasks import process_complaint


def create_app():
    app = Flask(__name__)
    CORS(app)

    redis_conn = Redis(host=os.environ.get('REDIS_HOST', 'localhost'), port=int(os.environ.get('REDIS_PORT', 6379)))
    queue = Queue(connection=redis_conn)


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

    # send complaints 
    @app.route('/api/complaints', methods=['POST'])
    @metrics.counter('api_complaints_received', 'Number of complaints received via API')
    def submit_complaint():
        data = request.json
        job = queue.enqueue(process_complaint, data)
        return jsonify({'status': 'processing', 'job_id': job.id}), 202

    # Modify get_complaint_result route
    @app.route('/api/complaints/<job_id>', methods=['GET'])
    def get_complaint_result(job_id):
        try:
            job = Job.fetch(job_id, connection=redis_conn)
            if job.is_finished:
                result = job.result
                return jsonify({
                    'status': 'completed',
                    'result': result
                })
            else:
                return jsonify({
                    'status': 'processing',
                    'state': job.get_status(),
                    'info': str(job.meta)
                }), 202
        except Exception as e:
            app.logger.error(f"Error retrieving job result: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'An error occurred while retrieving the job result',
                'error': str(e)
            }), 500

        
    @app.route('/aggregate', methods=['POST'])
    @metrics.counter('complaints_received', 'Number of complaints received')
    def aggregate_complaint():
        data = request.json
        job = queue.enqueue(process_complaint, data)
        return jsonify({'status': 'processing', 'job_id': job.id}), 202

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

    @app.route('/status/<job_id>')
    def task_status(job_id):
        job = Job.fetch(job_id, connection=redis_conn)
        response = {
            'state': job.get_status(),
            'status': str(job.meta)
        }
        return jsonify(response)
    return app

app = create_app()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')