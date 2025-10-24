import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any
from src.config.settings import settings
from src.cache.redis_client import cache
from src.models.schemas import (
    UserSubmission, OrchestrationState, StatusResponse,
    ParsedProfile, ScrapeRequest, ScrapeTarget, ScrapeTargetType
)
from src.parsers.document_parser import DocumentParser
from src.agents.scraper_agent import ScraperAgent
from src.agents.sentiment_agent import SentimentAgent
from src.agents.analyzer_agent import AnalyzerAgent
from src.agents.chat_agent import ChatAgent

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    def __init__(self):
        self.parser = DocumentParser()
        self.scraper = ScraperAgent()
        self.sentiment = SentimentAgent()
        self.analyzer = AnalyzerAgent()
        self.chat = ChatAgent()
        
        self.states: Dict[str, Dict[str, Any]] = {}
        self.reports: Dict[str, Any] = {}  # Store completed reports
    
    def _update_state(self, submission_id: str, state: OrchestrationState, 
                     progress: float, message: str):
        """Update orchestration state."""
        if submission_id not in self.states:
            self.states[submission_id] = {
                "started_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "state": state,
                "progress": progress,
                "message": message
            }
        else:
            self.states[submission_id].update({
                "updated_at": datetime.utcnow(),
                "state": state,
                "progress": progress,
                "message": message
            })
        
        logger.info(f"[{submission_id}] State: {state.value} | Progress: {progress}% | {message}")
    
    async def execute(self, submission: UserSubmission) -> Dict[str, Any]:
        """Execute the full workflow."""
        submission_id = submission.submission_id
        start_time = time.time()
        
        try:
            # Initialize state
            self._update_state(submission_id, OrchestrationState.SUBMITTED, 0, "Starting workflow")
            
            # Step 1: Parse artifacts
            self._update_state(submission_id, OrchestrationState.PARSING, 10, "Parsing resume and transcript")
            
            profile = None
            transcript_data = None
            
            if submission.resume_raw_uri and settings.enable_analyzer:
                profile = await self.parser.parse_resume(submission.resume_raw_uri, submission_id)
            
            if submission.transcript_raw_uri:
                transcript_data = await self.parser.parse_transcript(submission.transcript_raw_uri, submission_id)
            
            # If no resume, create minimal profile from preferences
            if not profile:
                profile = ParsedProfile(
                    skills=[{"name": skill, "type": "unknown"} for skill in submission.preferences.interests],
                    seniority_inferred="unknown"
                )
            
            self._update_state(submission_id, OrchestrationState.PARSING, 25, "Parsing complete")
            
            # Step 2: Build scrape request
            self._update_state(submission_id, OrchestrationState.SCRAPING, 30, "Planning scrape targets")
            
            targets = []
            
            # Add company targets from JD
            if submission.jd_text_or_url:
                targets.append(ScrapeTarget(
                    type=ScrapeTargetType.COMPANY,
                    name_or_url=submission.jd_text_or_url,
                    priority=1
                ))
            
            # Add industry targets
            for industry in submission.preferences.industries:
                targets.append(ScrapeTarget(
                    type=ScrapeTargetType.INDUSTRY,
                    name_or_url=industry,
                    priority=2
                ))
            
            # Add role targets
            for role in submission.preferences.roles:
                targets.append(ScrapeTarget(
                    type=ScrapeTargetType.ROLE,
                    name_or_url=role,
                    priority=2
                ))
            
            # Add location targets
            for location in submission.preferences.locations:
                targets.append(ScrapeTarget(
                    type=ScrapeTargetType.LOCATION,
                    name_or_url=location,
                    priority=3
                ))
            
            # If no targets, use generic job market scrape
            if not targets:
                targets.append(ScrapeTarget(
                    type=ScrapeTargetType.INDUSTRY,
                    name_or_url="technology",
                    priority=1
                ))
            
            scrape_request = ScrapeRequest(
                targets=targets,
                max_docs_per_source=settings.max_scrape_docs_per_source
            )
            
            # Step 3: Execute scraping
            self._update_state(submission_id, OrchestrationState.SCRAPING, 40, "Scraping web sources")
            
            scrape_results = []
            if settings.enable_scraper:
                scrape_results = await self.scraper.execute(scrape_request, submission_id)
            
            self._update_state(submission_id, OrchestrationState.SCRAPING, 55, 
                             f"Scraped {len(scrape_results)} documents")
            
            # Step 4: Analyze sentiment
            self._update_state(submission_id, OrchestrationState.ANALYZING_SENTIMENT, 60, 
                             "Analyzing sentiment and risks")
            
            sentiment_bundle = None
            if settings.enable_sentiment and scrape_results:
                sentiment_bundle = await self.sentiment.execute(scrape_results)
            
            # Create empty sentiment if disabled
            if not sentiment_bundle:
                from src.models.schemas import SentimentBundle
                sentiment_bundle = SentimentBundle(scores={}, evidence=[], risk_signals=[])
            
            self._update_state(submission_id, OrchestrationState.ANALYZING_SENTIMENT, 75, 
                             "Sentiment analysis complete")
            
            # Step 5: Generate analysis report
            self._update_state(submission_id, OrchestrationState.SYNTHESIZING, 80, 
                             "Synthesizing recommendations")
            
            report = None
            if settings.enable_analyzer:
                report = await self.analyzer.execute(submission, profile, scrape_results, sentiment_bundle)
            
            self._update_state(submission_id, OrchestrationState.SYNTHESIZING, 95, 
                             "Analysis complete")
            
            # Step 6: Initialize chat session
            if settings.enable_chat and report:
                self.chat.initialize_session(submission_id, report, scrape_results)
            
            # Mark complete
            self._update_state(submission_id, OrchestrationState.COMPLETED, 100, "Workflow complete")
            
            elapsed = time.time() - start_time
            logger.info(f"[{submission_id}] Workflow completed in {elapsed:.2f}s")
            
            # Store results
            result = {
                "submission_id": submission_id,
                "profile": profile,
                "scrape_results": scrape_results,
                "sentiment_bundle": sentiment_bundle,
                "report": report,
                "elapsed_seconds": elapsed
            }
            self.reports[submission_id] = result
            
            return result
        
        except Exception as e:
            logger.error(f"[{submission_id}] Workflow failed: {e}", exc_info=True)
            self._update_state(submission_id, OrchestrationState.FAILED, 0, f"Error: {str(e)}")
            raise
    
    def get_status(self, submission_id: str) -> StatusResponse:
        """Get current orchestration status."""
        if submission_id not in self.states:
            return StatusResponse(
                submission_id=submission_id,
                state=OrchestrationState.SUBMITTED,
                progress=0.0,
                message="Not found",
                started_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        
        state_data = self.states[submission_id]
        return StatusResponse(
            submission_id=submission_id,
            state=state_data["state"],
            progress=state_data["progress"],
            message=state_data["message"],
            started_at=state_data["started_at"],
            updated_at=state_data["updated_at"]
        )


# Global orchestrator instance
orchestrator = WorkflowOrchestrator()
