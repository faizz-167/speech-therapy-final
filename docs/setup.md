# Setup Guide

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ (3.13 recommended) |
| Node.js | 18+ LTS |
| Docker | Any recent version (for Redis) |
| PostgreSQL | Hosted on Neon (connection string in .env) |
| Git | Any recent version |

---

## 1. Clone the Repository

```bash
git clone <repo-url>
cd sppech-therapy-final
```

---

## 2. Start Redis

Redis is used for Celery job queue and WebSocket pub/sub.

```bash
docker compose -f docker-compose.redis.yml up -d
```

Verify: `docker ps` should show a Redis container on port `6379`.

---

## 3. Backend Setup

### 3a. Create virtual environment

```bash
cd server
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3b. Install dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, SQLAlchemy, Celery, Whisper, SpeechBrain, spaCy, HuggingFace, etc. Expect this to take several minutes on first run due to ML library sizes.

### 3c. Download spaCy model

```bash
python -m spacy download en_core_web_sm
```

### 3d. Configure environment

Create `server/.env`:

```env
# Database (PostgreSQL via Neon or local)
DATABASE_URL=postgresql+asyncpg://user:password@host/dbname
DATABASE_URL_SYNC=postgresql://user:password@host/dbname

# Redis
REDIS_URL=redis://localhost:6379/0

# Auth
SECRET_KEY=your-very-long-random-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# File uploads
UPLOAD_DIR=uploads

# CORS — frontend origin
CORS_ORIGINS=["http://localhost:3000"]

# Development mode
DEBUG=true
```

**Note:** Two database URLs are required:
- `DATABASE_URL` — async (used by FastAPI with asyncpg)
- `DATABASE_URL_SYNC` — sync (used by Celery with psycopg2)

### 3e. Initialize the database

```bash
# Drop and recreate schema
python reset_db.py

# Load clinical seed data (defects, tasks, prompts, baseline assessments)
python seed_data.py
```

### 3f. Start the API server (Terminal 1)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API available at: http://localhost:8000  
Interactive docs: http://localhost:8000/docs

### 3g. Start Celery worker (Terminal 2)

```bash
# Must be in server/ with venv activated
celery -A app.celery_app worker --pool=solo --loglevel=info
```

`--pool=solo` is required on Windows. On Linux/macOS you can use `--pool=prefork` for better performance.

---

## 4. Frontend Setup

```bash
cd client
npm install
```

### 4a. Configure environment

Create `client/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### 4b. Start the dev server (Terminal 3)

```bash
npm run dev
```

Frontend available at: http://localhost:3000

---

## 5. Verify Everything Works

1. Open http://localhost:3000
2. Register a therapist account
3. Register a patient account (use the therapist's code)
4. Log in as therapist → approve the patient, assign defects
5. Generate and approve a plan
6. Log in as patient → complete baseline → do a session

---

## Project Structure Quick Reference

```
sppech-therapy-final/
├── server/                   # FastAPI backend
│   ├── app/                  # Application code
│   ├── requirements.txt
│   ├── reset_db.py           # Dev: recreate schema
│   ├── seed_data.py          # Dev: load clinical data
│   └── .env                  # Server environment variables
├── client/                   # Next.js frontend
│   ├── app/                  # Pages
│   ├── components/
│   ├── package.json
│   └── .env.local            # Client environment variables
├── docker-compose.redis.yml  # Redis container
└── docs/                     # This documentation
```

---

## Common Issues

### Celery tasks not running
- Ensure Redis is running: `docker ps`
- Ensure Celery worker is started in the `server/` directory with venv activated
- Check `REDIS_URL` matches in `.env`

### ML models fail to load
- First run downloads models from HuggingFace — requires internet
- Ensure sufficient disk space (~5–10 GB for all models)
- Whisper model size can be changed in `ml/whisper_asr.py` (base/small/medium)

### Database connection errors
- Verify `DATABASE_URL` and `DATABASE_URL_SYNC` are correct
- Neon free tier pauses connections after inactivity — first request may be slow
- Run `reset_db.py` only once; re-running drops all data

### CORS errors in browser
- Ensure `CORS_ORIGINS` in `.env` matches the frontend URL exactly
- Include the port: `http://localhost:3000`

### WebSocket not connecting
- Ensure `NEXT_PUBLIC_WS_URL` uses `ws://` not `http://`
- WebSocket endpoint is at `/ws/{patient_id}` on the FastAPI server

---

## Production Considerations

| Area | Recommendation |
|------|---------------|
| Auth | Rotate `SECRET_KEY`, shorten token expiry |
| Database | Use connection pooling (PgBouncer) |
| Celery | Use `--pool=prefork` with multiple workers |
| ML | Run ML worker separately with GPU support |
| Files | Move `UPLOAD_DIR` to S3 or object storage |
| CORS | Restrict to production domain only |
| Debug | Set `DEBUG=false` |
| HTTPS | Put behind nginx with TLS |
| Redis | Use Redis Cluster or managed Redis (Upstash) |
