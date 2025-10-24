import logging
import json
import re
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from src.config.settings import settings
from src.models.schemas import (
    ParsedProfile, ScrapeResult, SentimentBundle, AnalysisReport,
    MatchScore, Recommendation, SalaryInsights, GrowthOutlook,
    LocationNotes, GapAndUpskilling, Citation, ChartData, UserSubmission
)
from src.agents.prompts import get_analyzer_prompt

logger = logging.getLogger(__name__)


class AnalyzerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.2,
            api_key=settings.openai_api_key
        )
        self.top_n = 5
        self.min_confidence = 0.6
    
    def _extract_opportunities(self, profile: ParsedProfile, jd_text: str, 
                             scrape_results: List[ScrapeResult]) -> List[Dict[str, Any]]:
        """Extract distinct opportunities from all sources."""
        opportunities = []
        
        # From scraped results
        for result in scrape_results:
            if 'JOB' in result.tags or 'COMPANY' in result.tags:
                opportunities.append({
                    "source": "scrape",
                    "company": result.source,
                    "role": result.title,
                    "location": "Unknown",
                    "doc_id": result.doc_id
                })
        
        # From JD
        if jd_text:
            opportunities.append({
                "source": "jd",
                "company": "Target Company",
                "role": "Target Role",
                "location": "As specified",
                "doc_id": "jd_primary"
            })
        
        # Deduplicate
        seen = set()
        unique_opps = []
        for opp in opportunities:
            key = (opp["company"], opp["role"])
            if key not in seen:
                seen.add(key)
                unique_opps.append(opp)
        
        return unique_opps[:20]  # Limit for performance
    
    async def _score_opportunity(self, opportunity: Dict[str, Any], profile: ParsedProfile,
                                sentiment: SentimentBundle, scrape_results: List[ScrapeResult],
                                preferences: Dict[str, Any]) -> MatchScore:
        """Score a single opportunity across all dimensions."""
        # Prepare context
        user_skills = [s.get("name", "") for s in profile.skills]
        user_experience = [f"{e.title} at {e.company}" for e in profile.experience]
        
        context = f"""
Opportunity: {opportunity['role']} at {opportunity['company']}
User Skills: {', '.join(user_skills[:10])}
User Experience: {', '.join(user_experience[:3])}
Seniority: {profile.seniority_inferred}
Sentiment Scores: {sentiment.scores}
Risk Signals: {len(sentiment.risk_signals)} risks detected
Preferences: {preferences}
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Score this opportunity on 5 dimensions (0-100 scale):
            1. Skills Alignment (0-30): overlap with requirements
            2. Growth Potential (0-25): industry trends + company trajectory
            3. Stability & Risk (0-20): inverse of risk severity
            4. Compensation Fit (0-15): alignment with salary targets
            5. Location & Logistics (0-10): visa, COL, remote compatibility
            
            Return JSON with: dimension_scores (dict), total_score (0-100), rationale (string)"""),
            ("user", context)
        ])
        
        try:
            chain = prompt | self.llm
            response = await chain.ainvoke({})
            
            try:
                scoring = json.loads(response.content)
            except json.JSONDecodeError:
                json_match = re.search(r'```json\n(.*?)\n```', response.content, re.DOTALL)
                if json_match:
                    scoring = json.loads(json_match.group(1))
                else:
                    scoring = {"total_score": 50}
            
            return MatchScore(
                option_id=opportunity.get("doc_id", "unknown"),
                type="role",
                label=f"{opportunity['role']} at {opportunity['company']}",
                score=scoring.get("total_score", 50)
            )
        except Exception as e:
            logger.error(f"Error scoring opportunity: {e}")
            return MatchScore(
                option_id=opportunity.get("doc_id", "unknown"),
                type="role",
                label=f"{opportunity['role']} at {opportunity['company']}",
                score=0
            )
    
    async def _generate_recommendations(self, top_opportunities: List[Dict[str, Any]],
                                      profile: ParsedProfile, sentiment: SentimentBundle,
                                      scrape_results: List[ScrapeResult]) -> List[Recommendation]:
        """Generate detailed recommendations for top opportunities."""
        recommendations = []
        
        for opp in top_opportunities[:self.top_n]:
            context = f"""
Opportunity: {opp['role']} at {opp['company']}
User Profile: {profile.seniority_inferred} with skills in {[s.get('name') for s in profile.skills[:5]]}
Sentiment: Company sentiment = {sentiment.scores.get('company', 0.0)}
"""
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """Generate a career recommendation with:
                - title, company, location
                - rationale (2-3 sentences)
                - steps_next (3-5 actionable tasks)
                
                Return JSON format."""),
                ("user", context)
            ])
            
            try:
                chain = prompt | self.llm
                response = await chain.ainvoke({})
                
                try:
                    rec_data = json.loads(response.content)
                except json.JSONDecodeError:
                    json_match = re.search(r'```json\n(.*?)\n```', response.content, re.DOTALL)
                    if json_match:
                        rec_data = json.loads(json_match.group(1))
                    else:
                        rec_data = {}
                
                recommendations.append(Recommendation(
                    title=rec_data.get("title", opp['role']),
                    company=rec_data.get("company", opp['company']),
                    location=rec_data.get("location", opp.get('location', 'Unknown')),
                    rationale=rec_data.get("rationale", "Strong potential match"),
                    steps_next=rec_data.get("steps_next", [])
                ))
            except Exception as e:
                logger.error(f"Error generating recommendation: {e}")
        
        return recommendations
    
    async def _analyze_salary(self, scrape_results: List[ScrapeResult], 
                            profile: ParsedProfile) -> SalaryInsights:
        """Analyze salary data."""
        salary_docs = [r for r in scrape_results if 'SALARY_DATA' in r.tags]
        
        if not salary_docs:
            return SalaryInsights(range={"min": 0, "max": 0}, sources=[])
        
        context = "\n".join([f"{r.source}: {r.content_excerpt[:200]}" for r in salary_docs[:5]])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""Extract salary insights for {profile.seniority_inferred}.
            Return JSON: range {{min, max}}, percentile_est, sources"""),
            ("user", context)
        ])
        
        try:
            chain = prompt | self.llm
            response = await chain.ainvoke({})
            insights = json.loads(response.content) if response.content.startswith('{') else {}
            
            return SalaryInsights(
                range=insights.get("range", {"min": 0, "max": 0}),
                percentile_est=insights.get("percentile_est"),
                sources=insights.get("sources", [])
            )
        except Exception as e:
            logger.error(f"Error analyzing salary: {e}")
            return SalaryInsights(range={"min": 0, "max": 0}, sources=[])
    
    async def _analyze_growth(self, sentiment: SentimentBundle, 
                            scrape_results: List[ScrapeResult]) -> GrowthOutlook:
        """Analyze growth outlook."""
        return GrowthOutlook(
            five_yr_view="stable",
            automation_risk="medium",
            trend_notes=f"Industry sentiment: {sentiment.scores.get('industry', 0.0)}"
        )
    
    async def _analyze_location(self, scrape_results: List[ScrapeResult],
                               preferences: Dict[str, Any]) -> LocationNotes:
        """Analyze location factors."""
        return LocationNotes(
            col_index=100.0,
            market_depth="Moderate",
            visa_fit="Case dependent"
        )
    
    async def _identify_gaps(self, profile: ParsedProfile, 
                           top_opportunities: List[Dict[str, Any]]) -> List[GapAndUpskilling]:
        """Identify skill gaps."""
        return [
            GapAndUpskilling(
                gap="Cloud platforms (AWS/Azure)",
                suggested_action="Complete AWS Solutions Architect certification",
                resource_refs=["https://aws.amazon.com/certification/"]
            )
        ]
    
    def _generate_chart_data(self, sentiment: SentimentBundle, 
                           salary_insights: SalaryInsights,
                           risk_signals: List) -> ChartData:
        """Generate chart data."""
        sentiment_series = [{"label": k, "score": v} for k, v in sentiment.scores.items()]
        
        return ChartData(
            sentiment_series=sentiment_series,
            salary_bands=[],
            risk_histogram=[],
            timeline=[]
        )
    
    def _extract_citations(self, scrape_results: List[ScrapeResult]) -> List[Citation]:
        """Extract citations."""
        return [
            Citation(source=r.source, url=r.url, doc_id=r.doc_id)
            for r in sorted(scrape_results, key=lambda x: x.quality_score, reverse=True)[:10]
        ]
    
    async def execute(self, submission: UserSubmission, profile: ParsedProfile,
                    scrape_results: List[ScrapeResult], sentiment: SentimentBundle) -> AnalysisReport:
        """Execute full analysis."""
        logger.info(f"Starting analysis for {submission.submission_id}")
        
        opportunities = self._extract_opportunities(profile, submission.jd_text_or_url or "", scrape_results)
        
        match_scores = []
        for opp in opportunities:
            score = await self._score_opportunity(opp, profile, sentiment, scrape_results, submission.preferences.model_dump())
            match_scores.append(score)
        
        match_scores.sort(key=lambda x: x.score, reverse=True)
        top_opportunities = [opp for opp in opportunities if any(ms.option_id == opp.get("doc_id") for ms in match_scores[:self.top_n])]
        
        recommendations = await self._generate_recommendations(top_opportunities, profile, sentiment, scrape_results)
        salary_insights = await self._analyze_salary(scrape_results, profile)
        growth_outlook = await self._analyze_growth(sentiment, scrape_results)
        location_notes = await self._analyze_location(scrape_results, submission.preferences.model_dump())
        gaps = await self._identify_gaps(profile, top_opportunities)
        chart_data = self._generate_chart_data(sentiment, salary_insights, sentiment.risk_signals)
        citations = self._extract_citations(scrape_results)
        
        report = AnalysisReport(
            submission_id=submission.submission_id,
            match_scores=match_scores,
            recommendations=recommendations,
            salary_insights=salary_insights,
            growth_outlook=growth_outlook,
            location_notes=location_notes,
            gaps_and_upskilling=gaps,
            negotiation_tips=["Research market rates", "Highlight unique skills"],
            assumptions=["Market data is current", "User is open to opportunities"],
            limitations=[f"Analysis based on {len(scrape_results)} sources"],
            chart_data=chart_data,
            citations=citations
        )
        
        logger.info(f"Analysis complete for {submission.submission_id}")
        return report