# System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                        │
│  ┌────────────┐                            ┌──────────────┐ │
│  │  Frontend  │ ◄──────────────────────────►│ curl/Postman │ │
│  │ (HTML/JS)  │        HTTP/JSON           │   (Testing)  │ │
│  └────────────┘                            └──────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                         API LAYER                           │
│                    FastAPI (main.py)                        │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │ /submit  │ /status  │ /report  │  /chat   │ /health  │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   ORCHESTRATION LAYER                       │
│               WorkflowOrchestrator (workflow.py)            │
│                                                             │
│  Pipeline: SUBMITTED → PARSING → SCRAPING →                │
│            ANALYZING_SENTIMENT → SYNTHESIZING → COMPLETED  │
└───────────────────────────┬─────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │   PARSING   │  │  SCRAPING   │  │  ANALYSIS   │
    │   STAGE     │  │   STAGE     │  │   STAGE     │
    └─────────────┘  └─────────────┘  └─────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      AGENT LAYER                            │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │ DocumentParser   │  │ ScraperAgent     │               │
│  │ - parse_resume() │  │ - execute()      │               │
│  │ - parse_trans..()│  │ - 15 mock docs   │               │
│  └──────────────────┘  └──────────────────┘               │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │ SentimentAgent   │  │ AnalyzerAgent    │               │
│  │ - execute()      │  │ - execute()      │               │
│  │ - GPT-4 scoring  │  │ - recommendations│               │
│  └──────────────────┘  └──────────────────┘               │
│                                                             │
│  ┌──────────────────┐                                      │
│  │ ChatAgent        │                                      │
│  │ - chat()         │                                      │
│  │ - what-if()      │                                      │
│  └──────────────────┘                                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
┌─────────────────┐  ┌────────────┐  ┌──────────────┐
│    OpenAI API   │  │   Redis    │  │ File Storage │
│   GPT-4 Turbo   │  │  Caching   │  │   uploads/   │
└─────────────────┘  └────────────┘  └──────────────┘
```

## Data Flow

### 1. Submit Analysis Flow

```
User submits resume + preferences
         │
         ▼
    POST /submit
         │
         ├─ Save files to uploads/
         ├─ Parse preferences
         ├─ Create UserSubmission
         │
         ▼
Background task starts workflow
         │
         └─ Return submission_id immediately
```

### 2. Workflow Execution

```
WorkflowOrchestrator.execute()
         │
         ├─ State: PARSING (10%)
         │  └─ DocumentParser.parse_resume()
         │     ├─ Extract text (PDF/DOCX)
         │     ├─ Extract skills, education, experience
         │     └─ Cache in Redis
         │
         ├─ State: SCRAPING (40%)
         │  └─ ScraperAgent.execute()
         │     ├─ Generate 15 mock documents
         │     ├─ Filter by targets
         │     └─ Cache results
         │
         ├─ State: ANALYZING_SENTIMENT (60%)
         │  └─ SentimentAgent.execute()
         │     ├─ Analyze each dimension
         │     ├─ Call GPT-4 for scoring
         │     └─ Detect risk signals
         │
         ├─ State: SYNTHESIZING (80%)
         │  └─ AnalyzerAgent.execute()
         │     ├─ Extract opportunities
         │     ├─ Score each (GPT-4)
         │     ├─ Generate recommendations
         │     └─ Create AnalysisReport
         │
         └─ State: COMPLETED (100%)
            └─ Initialize chat session
```

### 3. Chat Interaction

```
POST /chat/{submission_id}
         │
         ├─ Retrieve stored report
         ├─ Get conversation history
         │
         ├─ Is "what-if" question?
         │  ├─ Yes: Extract scenario
         │  └─ No:  Retrieve relevant docs
         │
         ├─ Call GPT-4 with context
         │  └─ Report + History + Docs
         │
         └─ Return grounded response
```

## Component Interactions

### Resume Parsing

```
resume.pdf → DocumentParser → ParsedProfile
                    │
                    ├─ pdfplumber (extract text)
                    ├─ Regex patterns (skills, edu, exp)
                    ├─ Entity extraction
                    │
                    └─ Redis Cache
                       Key: resume:{submission_id}
                       TTL: 7 days
```

### Scraping (Mock)

```
ScrapeRequest → ScraperAgent → List[ScrapeResult]
                      │
                      ├─ Generate 15 mock docs
                      │  ├─ Company (3 docs)
                      │  ├─ Industry (5 docs)
                      │  ├─ Role (4 docs)
                      │  └─ Risk (3 docs)
                      │
                      └─ Redis Cache
                         Key: scrape_request:{hash}
                         TTL: 24 hours
```

### Sentiment Analysis

```
List[ScrapeResult] → SentimentAgent → SentimentBundle
                           │
                           ├─ For each dimension:
                           │  ├─ Filter relevant docs
                           │  ├─ Build context
                           │  ├─ Call GPT-4
                           │  └─ Parse JSON response
                           │
                           └─ Detect risks:
                              ├─ Pattern matching
                              ├─ GPT-4 severity assessment
                              └─ Return RiskSignal[]
```

### Analysis & Recommendations

```
Profile + Scrape + Sentiment → AnalyzerAgent → AnalysisReport
                                      │
                                      ├─ Extract opportunities
                                      ├─ Score each (GPT-4)
                                      ├─ Rank by score
                                      │
                                      ├─ Top 5 → Recommendations
                                      ├─ Salary insights
                                      ├─ Growth outlook
                                      └─ Skill gaps
```

## Caching Strategy

```
┌─────────────────────────────────────────────────┐
│                Redis Cache Keys                 │
├─────────────────────────────────────────────────┤
│ resume:{submission_id}         → TTL: 7 days    │
│ transcript:{submission_id}     → TTL: 7 days    │
│ scrape:{url_hash}              → TTL: 1 day     │
│ scrape_request:{request_hash}  → TTL: 1 day     │
│ gpt:{prompt_hash}              → TTL: 1 hour    │
└─────────────────────────────────────────────────┘
```

## State Machine

```
                  ┌──────────────┐
                  │  SUBMITTED   │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │   PARSING    │ (10-25%)
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  SCRAPING    │ (30-55%)
                  └──────┬───────┘
                         │
                         ▼
            ┌────────────────────────┐
            │ ANALYZING_SENTIMENT    │ (60-75%)
            └────────────┬───────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ SYNTHESIZING │ (80-95%)
                  └──────┬───────┘
                         │
                    ┌────┴────┐
                    ▼         ▼
              ┌──────────┐  ┌──────────┐
              │COMPLETED │  │  FAILED  │
              └──────────┘  └──────────┘
```

## Error Handling

```
Try-Catch at each stage
         │
         ├─ Log error with context
         │  └─ submission_id, stage, stack trace
         │
         ├─ Update state to FAILED
         │  └─ Set progress to 0
         │
         └─ Return error message
            └─ Available via /status endpoint
```

## Observability

```
Every operation logs:
┌─────────────────────────────────────────┐
│ Timestamp                               │
│ Logger name (module)                    │
│ Level (INFO/DEBUG/ERROR)                │
│ [submission_id]                         │
│ Message with details                    │
│ Cache hits/misses                       │
│ Timing information                      │
└─────────────────────────────────────────┘

Example:
2025-10-24 12:00:05 - workflow - INFO - [sub_123] State: scraping | Progress: 40% | Scraping web sources
2025-10-24 12:00:10 - redis_client - DEBUG - Cache HIT: scrape_request:abc123
2025-10-24 12:00:30 - workflow - INFO - [sub_123] Workflow completed in 30.45s
```

## Technology Stack

```
┌────────────────────────────────────────┐
│ Frontend:  HTML, JavaScript, Chart.js │
├────────────────────────────────────────┤
│ API:       FastAPI, Uvicorn            │
├────────────────────────────────────────┤
│ AI:        LangChain, OpenAI GPT-4     │
├────────────────────────────────────────┤
│ Cache:     Redis (async)               │
├────────────────────────────────────────┤
│ Parsing:   pdfplumber, python-docx     │
├────────────────────────────────────────┤
│ Schemas:   Pydantic v2                 │
├────────────────────────────────────────┤
│ Deploy:    Docker, Docker Compose      │
└────────────────────────────────────────┘
```

## Scalability Considerations

### Current Architecture (MVP)
- In-memory state storage
- Single API instance
- Shared Redis cache
- Synchronous GPT-4 calls

### Future Enhancements
- PostgreSQL for persistent storage
- Message queue (Celery/RabbitMQ)
- Load balancer
- Multiple API instances
- Async GPT-4 batching
- Vector database for embeddings
- Kubernetes deployment

---

This architecture supports:
✅ Fast analysis (30-60s)
✅ Caching for performance
✅ State tracking
✅ Error recovery
✅ Extensibility
