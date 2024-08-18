# Complete Setup and Usage Guide for Multimodal Complaint Analysis System

## Part 1: Backend Setup

### Prerequisites

1. Install Python 3.9 or later from https://www.python.org/downloads/
2. Install Git from https://git-scm.com/download/win
3. Install Docker Desktop from https://www.docker.com/products/docker-desktop
4. Install Node.js and npm from https://nodejs.org/en/download/

### Step 1: Clone the Repository

1. Open Command Prompt
2. Navigate to where you want to store the project
3. Run:
   ```
   git clone https://github.com/your-username/complaint-analysis-system.git
   cd complaint-analysis-system
   ```

### Step 2: Set Up Virtual Environment

1. Create a virtual environment:
   ```
   python -m venv venv
   ```
2. Activate the virtual environment:
   ```
   venv\Scripts\activate
   ```

### Step 3: Install Backend Dependencies

1. Install required packages:
   ```
   pip install -r aggregator/requirements.txt
   ```

### Step 4: Set Up Environment Variables

1. Create a `.env` file in the root directory
2. Add the following content (replace with your actual values):
   ```
   POSTGRES_DB=complaints
   POSTGRES_USER=your_username
   POSTGRES_PASSWORD=your_password
   POSTGRES_HOST=localhost
   ELASTICSEARCH_URL=http://localhost:9200
   REDIS_HOST=localhost
   REDIS_PORT=6379
   CELERY_BROKER_URL=redis://localhost:6379/0
   OPENAI_API_KEY=your_openai_api_key
   GOOGLE_APPLICATION_CREDENTIALS=path/to/your/google-credentials.json
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   ```

### Step 5: Set Up Local Services

1. Start PostgreSQL:
   - Download and install PostgreSQL from https://www.postgresql.org/download/windows/
   - During installation, set the password for the 'postgres' user
   - Start the PostgreSQL service

2. Start Elasticsearch:
   - Download Elasticsearch from https://www.elastic.co/downloads/elasticsearch
   - Extract the downloaded file
   - Navigate to the extracted folder and run `bin\elasticsearch.bat`

3. Start Redis:
   - Download Redis for Windows from https://github.com/microsoftarchive/redis/releases
   - Install and start the Redis service

### Step 6: Initialize the Database

1. Run the Flask application once to initialize the database:
   ```
   python aggregator/app.py
   ```
2. Stop the application after it starts (Ctrl+C)

### Step 7: Start Celery Worker

1. Open a new Command Prompt
2. Activate the virtual environment:
   ```
   venv\Scripts\activate
   ```
3. Start the Celery worker:
   ```
   celery -A aggregator.app.celery worker --loglevel=info
   ```

### Step 8: Set Up AI Services

1. OpenAI (for GPT-4):
   - Sign up at https://openai.com/
   - Obtain an API key and add it to your `.env` file

2. Google Cloud (for Speech-to-Text and Video Intelligence):
   - Sign up for Google Cloud: https://cloud.google.com/
   - Create a new project
   - Enable Speech-to-Text and Video Intelligence APIs
   - Create a service account and download the JSON key
   - Add the path to this JSON key in your `.env` file

3. AWS (for Rekognition):
   - Sign up for AWS: https://aws.amazon.com/
   - Create an IAM user with Rekognition access
   - Obtain the access key and secret key
   - Add these to your `.env` file

## Part 2: Frontend Setup

### Step 1: Navigate to Frontend Directory

```
cd frontend
```

### Step 2: Install Frontend Dependencies

```
npm install
```

### Step 3: Set Up Frontend Environment Variables

1. Create a `.env` file in the `frontend` directory
2. Add the following:
   ```
   REACT_APP_API_URL=http://localhost:5000
   ```

### Step 4: Start the Frontend Development Server

```
npm start
```

The frontend should now be accessible at `http://localhost:3000`

## Part 3: Running the Full System

1. Start all backend services (PostgreSQL, Elasticsearch, Redis)
2. In one terminal, run the Flask backend:
   ```
   python aggregator/app.py
   ```
3. In another terminal, run the Celery worker:
   ```
   celery -A aggregator.app.celery worker --loglevel=info
   ```
4. In a third terminal, run the frontend:
   ```
   cd frontend
   npm start
   ```

## Part 4: Using the Frontend to Submit Multimodal Complaints

1. Open your web browser and go to `http://localhost:3000`

2. You should see a form with the following options:
   - Complaint Type (dropdown): Text, Voice, Image, Video
   - File Upload (for Voice, Image, Video)
   - Text Input (for Text complaints)
   - Submit Button

3. To submit a text complaint:
   - Select "Text" from the dropdown
   - Enter your complaint in the text area
   - Click Submit

4. To submit a voice complaint:
   - Select "Voice" from the dropdown
   - Click on the file upload area and select an audio file (.wav or .mp3)
   - Click Submit

5. To submit an image complaint:
   - Select "Image" from the dropdown
   - Click on the file upload area and select an image file (.jpg, .png, etc.)
   - Click Submit

6. To submit a video complaint:
   - Select "Video" from the dropdown
   - Click on the file upload area and select a video file (.mp4, .avi, etc.)
   - Click Submit

7. After submission, you should see a "Processing" message with a task ID

8. Use the "Check Status" feature with the task ID to see the progress and results

9. Use the "Search Complaints" feature to find processed complaints

## Troubleshooting

- If the frontend can't connect to the backend, ensure the REACT_APP_API_URL in the frontend .env file matches your backend URL
- For file upload issues, check the browser console for any error messages
- If certain complaint types aren't processing, ensure you've set up the corresponding AI service correctly (OpenAI, Google Cloud, AWS)
- For backend errors, check the Flask and Celery terminal outputs for error messages