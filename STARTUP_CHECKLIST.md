# 🚀 Startup Checklist

Follow these steps to get the Career Advice Platform running:

## ✅ Prerequisites Check

- [ ] Python 3.10+ installed
  ```bash
  python --version
  ```

- [ ] Docker installed (for Redis)
  ```bash
  docker --version
  ```

- [ ] OpenAI API key configured
  - Check `.env` file exists
  - `OPENAI_API_KEY` is set

## 🔧 Installation Steps

### Quick Setup (Windows)
```bash
# Run the automated setup script
quickstart.bat
```

### Manual Setup
1. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # macOS/Linux
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Download spaCy model**
   ```bash
   python -m spacy download en_core_web_sm
   ```

## 🏃 Running the System

### Option A: Docker Compose (Easiest)
```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop everything
docker-compose down
```

### Option B: Manual (Development)

**Terminal 1 - Redis:**
```bash
docker run -d --name career-redis -p 6379:6379 redis:7-alpine
```

**Terminal 2 - API Server:**
```bash
venv\Scripts\activate
python -m uvicorn src.api.main:app --reload --port 8000
```

## ✔️ Verification

1. **Check API is running**
   ```bash
   curl http://localhost:8000/health
   ```
   
   Expected output:
   ```json
   {
     "status": "healthy",
     "redis": "connected",
     "feature_flags": {...}
   }
   ```

2. **Run integration test**
   ```bash
   python test_system.py
   ```
   
   This will:
   - Submit a test resume
   - Wait for analysis to complete
   - Retrieve the report
   - Test chat functionality

3. **Open API docs**
   - Visit: http://localhost:8000/docs
   - Interactive Swagger UI for testing endpoints

## 📊 Expected Timeline

Full analysis takes approximately **30-60 seconds**:

- **Parsing**: 5-10 seconds
- **Scraping**: 10-15 seconds (mock data)
- **Sentiment Analysis**: 10-20 seconds (GPT-4 calls)
- **Analysis & Recommendations**: 10-20 seconds (GPT-4 calls)

Progress can be monitored via `/status/{submission_id}`

## 🎯 Quick Test

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Submit analysis
curl -X POST http://localhost:8000/submit \
  -F "resume=@sample_resume.txt" \
  -F "user_prompt=I want a senior role at a cloud company" \
  -F "salary_min=150000" \
  -F "salary_max=250000" \
  -F "locations=San Francisco,Austin" \
  -F "industries=cloud,technology" \
  -F "roles=Senior Software Engineer" \
  -F "remote_ok=true"

# Output: {"submission_id": "sub_1234567890", ...}

# 3. Check status (replace with your submission_id)
curl http://localhost:8000/status/sub_1234567890

# 4. Get report (once completed)
curl http://localhost:8000/report/sub_1234567890

# 5. Chat with AI
curl -X POST http://localhost:8000/chat/sub_1234567890 \
  -H "Content-Type: application/json" \
  -d '{"message": "What are my top skills?"}'
```

## 🐛 Troubleshooting

### Issue: Import errors
**Solution:** Ensure virtual environment is activated
```bash
venv\Scripts\activate
pip install -r requirements.txt
```

### Issue: Redis connection failed
**Solution:** Start Redis container
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### Issue: Port 8000 already in use
**Solution:** Use a different port
```bash
python -m uvicorn src.api.main:app --port 8001
```

### Issue: OpenAI API errors
**Solution:** Check API key and billing
```bash
# Verify key in .env
cat .env | findstr OPENAI_API_KEY

# Test with a simple call
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## 📝 Environment Variables

Check your `.env` file has:
```bash
OPENAI_API_KEY=sk-...         # Your OpenAI API key
OPENAI_MODEL=gpt-4-turbo-preview
REDIS_URL=redis://localhost:6379
CACHE_ENABLED=true
LOG_LEVEL=INFO
ENABLE_SCRAPER=true
ENABLE_SENTIMENT=true
ENABLE_ANALYZER=true
ENABLE_CHAT=true
```

## 🎉 Success Indicators

You're ready when you see:
- ✅ Health endpoint returns `"status": "healthy"`
- ✅ Redis shows `"connected"`
- ✅ API docs accessible at http://localhost:8000/docs
- ✅ Test script completes all checks
- ✅ Logs show structured output with submission IDs

## 🔗 Useful Links

- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Frontend: Open `frontend/index.html` in browser
- Logs: `docker-compose logs -f api` (if using Docker)

## 📞 Support

If you encounter issues:
1. Check the logs for error messages
2. Verify all prerequisites are met
3. Review the troubleshooting section
4. Check the COMPLETION_SUMMARY.md for detailed implementation notes

---

**Ready to start?** Run: `quickstart.bat` (Windows) or follow manual setup above!
