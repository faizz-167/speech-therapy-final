# How to Run the Speech Therapy Platform (SpeechPath)

Follow this step-by-step guide to set up and run the application. The project is split into a **Next.js 16 Client** and a **FastAPI + Celery Backend**.

## Prerequisites

Before you begin, ensure you have the following installed on your system (specifically configured for Windows):
- **Python 3.13** (recommended)
- **Node.js 18+** (LTS recommended)
- **PostgreSQL** (running locally or via Docker)
- **Docker Desktop** or **Redis Server** (Redis is required for Celery queuing and WebSockets pub/sub)
- **FFmpeg** (required by `torchaudio` and `OpenAI Whisper` for audio processing)

> [!IMPORTANT]
> Use Python `3.13` for the backend virtual environment. The current pinned ML/database dependencies are not fully compatible with Python `3.14` yet, which can cause package builds such as `psycopg2-binary` and `openai-whisper` to fail during `pip install`.

---

## 1. Backend Setup & Configuration

Open a terminal and navigate to the project root.

### Create and activate a Virtual Environment
```bash
cd server
py -3.13 -m venv venv

# On Windows:
venv\Scripts\activate
# On Mac/Linux:
# source venv/bin/activate
```

### Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Configure Environment Variables
Inside the `server` directory, create a `.env` file referencing your database and Redis server. Fill in your Postgres credentials:

```env
DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/speechpath"
DATABASE_URL_SYNC="postgresql://user:password@localhost:5432/speechpath"
REDIS_URL="redis://localhost:6379/0"
SECRET_KEY="your-super-secret-key-change-this"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=10080
UPLOAD_DIR="uploads"
DEBUG=True
CORS_ORIGINS='["http://localhost:3000"]'
```

### Start Redis in Docker
If you do not want to install Redis locally, you can run it with Docker from the project root:

```bash
docker compose -f docker-compose.redis.yml up -d
```

Check that it is healthy:

```bash
docker compose -f docker-compose.redis.yml ps
```

Because the backend runs on your host machine in this project, keep:

```env
REDIS_URL="redis://localhost:6379/0"
```

Stop Redis later with:

```bash
docker compose -f docker-compose.redis.yml down
```

### Initialize Database and Seed Data
The database needs to be created first in Postgres (e.g., a DB called `speechpath`). Once created, run these to schema-sync and seed clinical content:

> [!WARNING]
> Running `reset_db.py` will drop all existing tables in the `public` schema and recreate them. Only do this for local development or fresh setups!

```bash
python reset_db.py
python seed_data.py
```

---

## 2. Running the Backend Services

To run the full backend, you will need **two separate terminals**. Ensure your virtual environment is activated in both terminals.

### Terminal 1: Run the FastAPI Server
This handles all API requests and WebSocket real-time connections.

```bash
cd server
# Ensure venv is activated
uvicorn app.main:app --reload
# Alternatively: fastapi dev app/main.py
```
*The server will start on `http://localhost:8000`.*

### Terminal 2: Run the Celery Worker
This handles heavy asynchronous tasks like Machine Learning scoring (Whisper, torchaudio forced alignment, emotion classification). 
Since this is Windows, the `--pool=solo` parameter is **critical**.

```bash
cd server
# Ensure venv is activated
celery -A app.celery_app worker --pool=solo --loglevel=info
```

---

## 3. Frontend Setup & Configuration

Open a **third terminal** for the frontend application.

### Install Node Dependencies

```bash
cd client
npm install
```

### Configure Environment Variables
Ensure a `.env.local` file exists in the `client` directory:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Start the Development Server

```bash
npm run dev
```
*The frontend will start on `http://localhost:3000`.*

---

## 4. Access the Platform

1. Open your browser and navigate to **[http://localhost:3000](http://localhost:3000)**.
2. The project features two roles: `Therapist` and `Patient`.
   - You can log in with a pre-seeded account if you modified the `seed_data.py` to create users, or you can register a new Therapist via the UI.
   - Patients require an approval code generated from an active Therapist dashboard to complete registration.
3. Once logged in, interact with the platform. Patient audio uploads will be routed directly to the Celery worker and stream back near instantly using WebSockets.
