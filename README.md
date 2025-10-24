# Career Advice Platform

AI-powered career guidance platform with multi-agent orchestration using LangChain, GPT-4, and Redis.

## Features

- **Resume & Transcript Parsing**: Extract structured data from PDF/DOCX documents
- **Web Intelligence Gathering**: Mock scraper with 15+ realistic data sources
- **Sentiment Analysis**: GPT-powered evaluation of risks and opportunities
- **Personalized Recommendations**: AI-driven career advice with match scoring
- **Interactive Chat**: Follow-up questions and what-if scenario analysis
- **Redis Caching**: Optimized performance with intelligent caching
- **Observability**: Structured logging with submission tracking

## Quick Start

### Prerequisites

- Python 3.10+ (3.11 recommended)
- Redis 7+ (for caching)
- OpenAI API key (GPT-4 access)

### Installation (Local)

```bash
# Navigate to project directory
cd cloudflare-agentic-minihack

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model (required for NLP)
python -m spacy download en_core_web_sm
```

### Configuration

```bash
# The .env file is already created with the API key
# Verify your settings:
cat .env

# Key settings:
# OPENAI_API_KEY - Your OpenAI API key (already configured)
# REDIS_URL - Redis connection (default: redis://localhost:6379)
# LOG_LEVEL - Logging verbosity (default: INFO)
```

### Run with Docker (Recommended)

```bash
# Start all services (Redis + API)
docker-compose up -d

# Check logs
docker-compose logs -f api

# Access API at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Run Locally (Development)

**Terminal 1 - Start Redis:**
```bash
# Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or if installed locally
redis-server
```

**Terminal 2 - Start API Server:**
```bash
# Activate virtual environment first
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Start FastAPI server
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 3 - Open Frontend (Optional):**
```bash
# Serve frontend
cd frontend
python -m http.server 8080

# Visit http://localhost:8080
```

## Testing the System

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Expected output:
```json
{
  "status": "healthy",
  "redis": "connected",
  "feature_flags": {
    "scraper": true,
    "sentiment": true,
    "analyzer": true,
    "chat": true
  }
}
```

### 2. Submit Analysis (Using curl)

Create a test resume file `test_resume.txt`:
```
John Doe
Software Engineer

SKILLS
Python, JavaScript, React, AWS, Docker, Kubernetes

EDUCATION
B.S. Computer Science, Stanford University, 2020

EXPERIENCE
Senior Software Engineer, Tech Corp, 2020-2024
- Built cloud infrastructure
- Led team of 5 engineers
```

Submit the analysis:
```bash
curl -X POST http://localhost:8000/submit \
  -F "resume=@test_resume.txt" \
  -F "user_prompt=I want to transition into a senior role at a cloud company" \
  -F "salary_min=150000" \
  -F "salary_max=250000" \
  -F "locations=San Francisco,Austin" \
  -F "industries=cloud,technology" \
  -F "roles=Senior Software Engineer,Principal Engineer" \
  -F "remote_ok=true"
```

Expected response:
```json
{
  "submission_id": "sub_1234567890",
  "status": "submitted",
  "message": "Analysis started. Check /status/{submission_id} for progress."
}
```

### 3. Check Status

```bash
curl http://localhost:8000/status/sub_1234567890
```

Watch progress through stages:
- `submitted` → `parsing` → `scraping` → `analyzing_sentiment` → `synthesizing` → `completed`

### 4. Get Report

```bash
curl http://localhost:8000/report/sub_1234567890
```

Expected output includes:
- 3-5 personalized recommendations
- Match scores (0-100) for each opportunity
- Salary insights with ranges
- Growth outlook and automation risk
- Skill gaps and upskilling suggestions
- Negotiation tips
- Evidence citations from 10+ sources

### 5. Chat with AI

```bash
curl -X POST http://localhost:8000/chat/sub_1234567890 \
  -H "Content-Type: application/json" \
  -d '{"message": "What if I learned Kubernetes? How would that change my opportunities?"}'
```

Expected response:
```json
{
  "content": "If you learned Kubernetes, it would significantly improve...",
  "citations": ["doc1", "doc5"],
  "deep_dive_card": null
}
```

## API Endpoints

### Core Endpoints

- **POST /submit** - Submit new career analysis
  - Accepts: resume (file), transcript (file), preferences (form data)
  - Returns: submission_id
  
- **GET /status/{submission_id}** - Check analysis progress
  - Returns: state, progress (0-100), message
  
- **GET /report/{submission_id}** - Retrieve completed analysis
  - Returns: Full AnalysisReport with recommendations
  
- **POST /chat/{submission_id}** - Interactive Q&A
  - Accepts: {"message": "your question"}
  - Returns: AI response with citations
  
- **GET /artifacts/{submission_id}** - Get stored artifacts
  - Returns: Links to parsed resume, transcript, scrape data
  
- **GET /health** - System health check
  - Returns: Service status and feature flags

### API Documentation

Interactive API docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## System Architecture

```
┌─────────────┐
│   Frontend  │ (HTML/JS)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  FastAPI    │ (Orchestration)
│  Endpoints  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│  Workflow Orchestrator      │
│  (PARSE → SCRAPE → ANALYZE) │
└──────┬──────────────────────┘
       │
       ├──► DocumentParser (PDF/DOCX)
       ├──► ScraperAgent (Mock Data)
       ├──► SentimentAgent (GPT-4)
       ├──► AnalyzerAgent (GPT-4)
       └──► ChatAgent (GPT-4)
       │
       ▼
┌─────────────┐
│   Redis     │ (Caching)
└─────────────┘
```

## Observability

All operations log:
- **Submission ID**: Track requests end-to-end
- **Timing**: Step duration and total elapsed time
- **Cache Hits/Misses**: Performance optimization tracking
- **Document Counts**: Sources processed per stage
- **Error Context**: Full stack traces for debugging

Example log output:
```
2025-10-24 12:00:00 - workflow - INFO - [sub_123] State: parsing | Progress: 10% | Parsing resume and transcript
2025-10-24 12:00:05 - document_parser - INFO - [sub_123] Resume parsed successfully - 15 skills, 2 degrees, 3 jobs
2025-10-24 12:00:06 - redis_client - DEBUG - Cache HIT: resume:sub_123
2025-10-24 12:00:10 - scraper_agent - INFO - [sub_123] Scraping complete: 15 documents collected
2025-10-24 12:00:30 - workflow - INFO - [sub_123] Workflow completed in 30.45s
```

## Mock Data

The system uses realistic mock data for scraping:
- **15 documents** across 5 source types
- **Company reviews** (Glassdoor, Blind, LinkedIn)
- **Industry trends** (TechCrunch, Gartner, Stack Overflow)
- **Salary data** (Levels.fyi, Indeed)
- **Risk signals** (Layoffs, automation impact)
- All cached in Redis for fast subsequent runs

## Expected Output

A typical analysis produces:
- ✅ **3-5 ranked recommendations** with rationale
- ✅ **Match scores** (0-100) for skills, growth, stability, compensation
- ✅ **Salary range**: $160K-$220K (example)
- ✅ **10+ evidence citations** from mock sources
- ✅ **Sentiment scores** across 4 dimensions (-1 to +1)
- ✅ **Risk signals** with severity levels (1-5)
- ✅ **Chart-ready data** for visualization
- ✅ **Conversation capability** for 3-5 follow-up questions

## Troubleshooting

### Redis Connection Failed
```bash
# Check Redis is running
docker ps | grep redis

# Or start Redis
docker run -d -p 6379:6379 redis:7-alpine
```

### Import Errors
```bash
# Ensure virtual environment is activated
venv\Scripts\activate  # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### OpenAI API Errors
```bash
# Verify API key in .env
echo $OPENAI_API_KEY

# Check rate limits and billing
# Visit: https://platform.openai.com/usage
```

### Port Already in Use
```bash
# Use different port
uvicorn src.api.main:app --port 8001
```

## Development

### Run Tests
```bash
# (Tests to be implemented)
pytest tests/
```

### Code Structure
```
src/
├── api/          # FastAPI endpoints
├── agents/       # LangChain agents (sentiment, analyzer, chat)
├── cache/        # Redis client
├── config/       # Settings management
├── models/       # Pydantic schemas
├── orchestration/# Workflow coordination
└── parsers/      # Document parsing (PDF/DOCX)
```

### Adding Features
1. Define schema in `src/models/schemas.py`
2. Implement agent in `src/agents/`
3. Add to workflow in `src/orchestration/workflow.py`
4. Expose via API in `src/api/main.py`

## License

See LICENSE file.

## Support

For issues or questions, check:
- API logs: `docker-compose logs -f api`
- Redis status: `docker-compose exec redis redis-cli ping`
- Health endpoint: http://localhost:8000/health