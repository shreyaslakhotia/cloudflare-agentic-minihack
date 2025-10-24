import logging
import json
import re
from typing import List, Dict
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from src.config.settings import settings
from src.models.schemas import ScrapeResult, SentimentBundle, SentimentEvidence, RiskSignal, RiskType
from src.agents.prompts import get_sentiment_prompt

logger = logging.getLogger(__name__)


class SentimentAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.1,
            api_key=settings.openai_api_key
        )
        self.min_sources = 3
        self.min_risk_sources = 2
        self.recency_cutoff_months = 12
    
    def _calculate_recency_weight(self, published_at: datetime) -> float:
        """Calculate weight based on content recency."""
        if not published_at:
            return 0.5
        
        age_months = (datetime.utcnow() - published_at).days / 30
        
        if age_months < 3:
            return 1.5
        elif age_months > 12:
            return 0.5
        else:
            return 1.0
    
    def _calculate_source_weight(self, source: str, tags: List[str]) -> float:
        """Calculate weight based on source reliability."""
        # Official sources and reputable news
        if any(domain in source.lower() for domain in ['gov', 'edu', 'reuters', 'bloomberg']):
            return 2.0
        
        # User-generated content
        if any(tag in tags for tag in ['REVIEW', 'DISCUSSION']):
            return 0.5
        
        return 1.0
    
    async def _analyze_dimension(self, dimension: str, results: List[ScrapeResult]) -> Dict:
        """Analyze sentiment for a specific dimension using LLM."""
        # Filter relevant results
        relevant_results = [
            r for r in results 
            if dimension.lower() in r.content_excerpt.lower() or 
               dimension.lower() in ' '.join(r.tags).lower()
        ]
        
        if len(relevant_results) < self.min_sources:
            return {
                "score": 0.0,
                "confidence": "low",
                "evidence": [],
                "note": f"Insufficient sources ({len(relevant_results)} < {self.min_sources})"
            }
        
        # Prepare context for LLM
        context = "\n\n".join([
            f"Source: {r.source}\nURL: {r.url}\nPublished: {r.published_at}\n"
            f"Quality: {r.quality_score}\nContent: {r.content_excerpt[:500]}"
            for r in relevant_results[:10]
        ])
        
        prompt_template = get_sentiment_prompt()
        
        documents_text = "\n\n".join([
            f"Doc ID: {r.doc_id}\nSource: {r.source}\nPublished: {r.published_at}\n"
            f"Content: {r.content_excerpt[:500]}"
            for r in relevant_results[:10]
        ])
        
        prompt = prompt_template.format(
            num_docs=len(relevant_results),
            documents=documents_text
        )
        
        response = await self.llm.ainvoke(prompt)
        
        # Parse response
        try:
            analysis = json.loads(response.content)
        except json.JSONDecodeError:
            json_match = re.search(r'```json\n(.*?)\n```', response.content, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(1))
            else:
                analysis = {"score": 0.0, "confidence": "low", "evidence": []}
        
        # Apply recency and source weighting
        weighted_score = analysis.get("score", 0.0)
        for result in relevant_results:
            recency_weight = self._calculate_recency_weight(result.published_at)
            source_weight = self._calculate_source_weight(result.source, result.tags)
            # Adjust score slightly based on weights (keep LLM score as primary)
            weighted_score *= (recency_weight * source_weight) ** 0.1
        
        analysis["score"] = max(-1.0, min(1.0, weighted_score))
        
        return analysis
    
    async def _detect_risks(self, results: List[ScrapeResult]) -> List[RiskSignal]:
        """Detect and categorize risk signals."""
        risks = []
        
        # Group results by risk keywords
        risk_keywords = {
            RiskType.LAYOFFS: ['layoff', 'firing', 'downsizing', 'workforce reduction', 'job cut'],
            RiskType.LEGAL: ['lawsuit', 'investigation', 'fine', 'penalty', 'regulation'],
            RiskType.CULTURE: ['toxic', 'harassment', 'discrimination', 'poor management'],
            RiskType.MARKET: ['declining', 'losses', 'competition', 'market share'],
            RiskType.VALUATION: ['bankruptcy', 'funding issues', 'valuation cut', 'stock drop']
        }
        
        for risk_type, keywords in risk_keywords.items():
            relevant_docs = []
            for result in results:
                content_lower = result.content_excerpt.lower()
                if any(keyword in content_lower for keyword in keywords):
                    relevant_docs.append(result)
            
            if len(relevant_docs) >= self.min_risk_sources:
                # Use LLM to assess severity
                context = "\n\n".join([
                    f"Source: {r.source}\nContent: {r.content_excerpt[:300]}"
                    for r in relevant_docs[:5]
                ])
                
                risk_prompt = (
                    f"Assess the severity of this risk on a scale of 1-5, where:\n"
                    f"1 = minor/isolated incident\n3 = recurring pattern\n5 = critical threat\n"
                    f"Return JSON with: severity (1-5), rationale (string)\n\n"
                    f"Risk type: {risk_type.value}\n\nEvidence:\n{context}"
                )
                
                try:
                    response = await self.llm.ainvoke(risk_prompt)
                    
                    try:
                        assessment = json.loads(response.content)
                    except json.JSONDecodeError:
                        json_match = re.search(r'```json\n(.*?)\n```', response.content, re.DOTALL)
                        if json_match:
                            assessment = json.loads(json_match.group(1))
                        else:
                            assessment = {"severity": 3}
                    
                    risks.append(RiskSignal(
                        type=risk_type,
                        severity=assessment.get("severity", 3),
                        refs=[doc.doc_id for doc in relevant_docs[:5]]
                    ))
                except Exception as e:
                    logger.error(f"Error assessing risk {risk_type}: {e}")
        
        return risks
    
    async def execute(self, scrape_results: List[ScrapeResult]) -> SentimentBundle:
        """Execute sentiment analysis on scraped results."""
        logger.info(f"Analyzing sentiment across {len(scrape_results)} documents")
        
        # Analyze each dimension
        dimensions = ['company', 'industry', 'role_type', 'seniority']
        scores = {}
        all_evidence = []
        
        for dimension in dimensions:
            analysis = await self._analyze_dimension(dimension, scrape_results)
            scores[dimension] = analysis.get("score", 0.0)
            
            # Convert evidence to SentimentEvidence objects
            for ev in analysis.get("evidence", []):
                all_evidence.append(SentimentEvidence(
                    doc_id=ev.get("doc_id", "unknown"),
                    quote_excerpt=ev.get("quote", ""),
                    rationale=ev.get("rationale", "")
                ))
        
        # Detect risks
        risk_signals = await self._detect_risks(scrape_results)
        
        bundle = SentimentBundle(
            scores=scores,
            evidence=all_evidence,
            risk_signals=risk_signals
        )
        
        logger.info(f"Sentiment analysis complete. Scores: {scores}, Risks: {len(risk_signals)}")
        
        return bundle
