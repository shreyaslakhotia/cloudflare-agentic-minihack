import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import shutil
from typing import Optional
from src.config.settings import settings
from src.cache.redis_client import cache
from src.models.schemas import UserSubmission, Preferences, EmploymentType, VisaStatus
from src.orchestration.workflow import orchestrator

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Storage directory
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting Career Advice Platform API")
    await cache.connect()
    
    yield
    
    # Shutdown
    logger.info("Shutting down API")
    await cache.close()


app = FastAPI(
    title="Career Advice Platform API",
    description="AI-powered career guidance with multi-agent orchestration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def run_workflow(submission: UserSubmission):
    """Background task to run workflow."""
    try:
        await orchestrator.execute(submission)
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")


@app.post("/submit")
async def submit_analysis(
    background_tasks: BackgroundTasks,
    resume: Optional[UploadFile] = File(None),
    transcript: Optional[UploadFile] = File(None),
    jd_text_or_url: Optional[str] = Form(None),
    user_prompt: str = Form(...),
    salary_min: Optional[int] = Form(None),
    salary_max: Optional[int] = Form(None),
    employment_types: Optional[str] = Form(None),
    locations: Optional[str] = Form(None),
    visa_status: Optional[str] = Form(None),
    remote_ok: bool = Form(True),
    interests: Optional[str] = Form(None),
    roles: Optional[str] = Form(None),
    industries: Optional[str] = Form(None)
):
    """
    Submit a new career analysis request.
    
    Files:
    - resume: PDF/DOC/TXT
    - transcript: PDF/TXT
    
    Text fields:
    - jd_text_or_url: Job description text or URL
    - user_prompt: User's career goals and constraints
    - Other fields: preferences
    """
    import time
    submission_id = f"sub_{int(time.time() * 1000)}"
    
    # Save uploaded files
    resume_path = None
    transcript_path = None
    
    if resume:
        resume_path = UPLOAD_DIR / f"{submission_id}_resume_{resume.filename}"
        with open(resume_path, "wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)
    
    if transcript:
        transcript_path = UPLOAD_DIR / f"{submission_id}_transcript_{transcript.filename}"
        with open(transcript_path, "wb") as buffer:
            shutil.copyfileobj(transcript.file, buffer)
    
    # Parse preferences
    preferences = Preferences(
        salary_target_min=salary_min,
        salary_target_max=salary_max,
        employment_type=[EmploymentType(t.strip()) for t in employment_types.split(",")] if employment_types else [],
        locations=[loc.strip() for loc in locations.split(",")] if locations else [],
        visa_status=VisaStatus(visa_status) if visa_status else None,
        remote_ok=remote_ok,
        interests=[i.strip() for i in interests.split(",")] if interests else [],
        roles=[r.strip() for r in roles.split(",")] if roles else [],
        industries=[ind.strip() for ind in industries.split(",")] if industries else []
    )
    
    # Create submission
    submission = UserSubmission(
        submission_id=submission_id,
        resume_raw_uri=str(resume_path) if resume_path else None,
        transcript_raw_uri=str(transcript_path) if transcript_path else None,
        jd_text_or_url=jd_text_or_url,
        user_prompt_text=user_prompt,
        preferences=preferences
    )
    
    # Start workflow in background
    background_tasks.add_task(run_workflow, submission)
    
    logger.info(f"Submitted new analysis: {submission_id}")
    
    return {
        "submission_id": submission_id,
        "status": "submitted",
        "message": "Analysis started. Check /status/{submission_id} for progress."
    }


@app.get("/status/{submission_id}")
async def get_status(submission_id: str):
    """Get the current status of an analysis."""
    status = orchestrator.get_status(submission_id)
    return status.model_dump()


@app.get("/report/{submission_id}")
async def get_report(submission_id: str):
    """Get the analysis report for a completed submission."""
    status = orchestrator.get_status(submission_id)
    
    if status.state.value != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Analysis not complete. Current state: {status.state.value}"
        )
    
    # Retrieve report from orchestrator's stored results
    if submission_id not in orchestrator.reports:
        raise HTTPException(status_code=404, detail="Report not found")
    
    result = orchestrator.reports[submission_id]
    report = result.get("report")
    
    if not report:
        raise HTTPException(status_code=500, detail="Report generation failed")
    
    return {
        "submission_id": submission_id,
        "report": report.model_dump(),
        "elapsed_seconds": result.get("elapsed_seconds", 0)
    }


@app.post("/chat/{submission_id}")
async def chat_with_agent(submission_id: str, message: dict):
    """
    Chat with the career advice agent about the analysis.
    
    Body: {"message": "Your question here"}
    """
    status = orchestrator.get_status(submission_id)
    
    if status.state.value != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Analysis not complete. Current state: {status.state.value}"
        )
    
    user_message = message.get("message", "")
    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    if not settings.enable_chat:
        raise HTTPException(status_code=503, detail="Chat feature is disabled")
    
    # Execute chat
    response = await orchestrator.chat.chat(submission_id, user_message)
    
    return response


@app.get("/artifacts/{submission_id}")
async def get_artifacts(submission_id: str):
    """Get links to parsed artifacts and scrape bundle."""
    status = orchestrator.get_status(submission_id)
    
    if status.state.value == "submitted":
        raise HTTPException(status_code=400, detail="Analysis not yet started")
    
    # Return file paths (in production, use presigned URLs)
    artifacts = {
        "submission_id": submission_id,
        "resume": str(UPLOAD_DIR / f"{submission_id}_resume_*"),
        "transcript": str(UPLOAD_DIR / f"{submission_id}_transcript_*"),
        "scrape_bundle": f"scrape_{submission_id}.json"
    }
    
    return artifacts


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    redis_ok = cache.enabled and cache.client is not None
    
    return {
        "status": "healthy",
        "redis": "connected" if redis_ok else "disconnected",
        "feature_flags": {
            "scraper": settings.enable_scraper,
            "sentiment": settings.enable_sentiment,
            "analyzer": settings.enable_analyzer,
            "chat": settings.enable_chat
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
