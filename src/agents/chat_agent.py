import logging
import json
import re
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.memory import ConversationBufferMemory
from src.config.settings import settings
from src.models.schemas import AnalysisReport, ChatMemoryItem, ChatRole, ScrapeResult
from src.agents.prompts import get_chat_prompt

logger = logging.getLogger(__name__)


class ChatAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.3,
            api_key=settings.openai_api_key
        )
        self.sessions: Dict[str, List[ChatMemoryItem]] = {}
        self.reports: Dict[str, AnalysisReport] = {}
        self.scrape_results: Dict[str, List[ScrapeResult]] = {}
    
    def initialize_session(self, submission_id: str, report: AnalysisReport,
                          scrape_results: List[ScrapeResult]):
        """Initialize a chat session with context."""
        self.sessions[submission_id] = []
        self.reports[submission_id] = report
        self.scrape_results[submission_id] = scrape_results
        
        # Add system context
        context_msg = ChatMemoryItem(
            role=ChatRole.ASSISTANT,
            content=f"I'm ready to discuss your career analysis. I have insights on "
                   f"{len(report.recommendations)} recommendations, salary data, and growth outlook. "
                   f"What would you like to know?",
            linked_submission_id=submission_id,
            visibility="visible"
        )
        self.sessions[submission_id].append(context_msg)
    
    def _get_conversation_history(self, submission_id: str, limit: int = 10) -> str:
        """Get recent conversation history."""
        if submission_id not in self.sessions:
            return ""
        
        messages = self.sessions[submission_id][-limit:]
        history = []
        for msg in messages:
            if msg.visibility == "visible":
                history.append(f"{msg.role.value}: {msg.content}")
        
        return "\n".join(history)
    
    def _get_report_summary(self, report: AnalysisReport) -> str:
        """Generate a concise report summary for context."""
        summary = f"""
Top Recommendations:
{chr(10).join([f"- {r.title} at {r.company}" for r in report.recommendations[:3]])}

Salary Range: ${report.salary_insights.range.get('min', 0):,} - ${report.salary_insights.range.get('max', 0):,}
Growth Outlook: {report.growth_outlook.five_yr_view if report.growth_outlook else 'Unknown'}
Risk Signals: {len(report.match_scores)} opportunities analyzed

Key Gaps: {', '.join([g.gap for g in report.gaps_and_upskilling[:3]])}
"""
        return summary
    
    async def _retrieve_relevant_docs(self, query: str, submission_id: str) -> List[Dict[str, str]]:
        """Retrieve relevant scraped documents for the query."""
        if submission_id not in self.scrape_results:
            return []
        
        results = self.scrape_results[submission_id]
        
        # Simple keyword matching (in production, use vector similarity)
        query_lower = query.lower()
        relevant = []
        
        for result in results:
            content_lower = result.content_excerpt.lower()
            # Check if query keywords appear in content
            if any(word in content_lower for word in query_lower.split() if len(word) > 3):
                relevant.append({
                    "doc_id": result.doc_id,
                    "source": result.source,
                    "url": result.url,
                    "excerpt": result.content_excerpt[:200]
                })
        
        return relevant[:5]  # Top 5 relevant docs
    
    async def _handle_what_if(self, query: str, submission_id: str) -> str:
        """Handle what-if scenario queries."""
        report = self.reports.get(submission_id)
        if not report:
            return "I don't have the analysis data for this session."
        
        # Use LLM to extract the scenario change
        what_if_prompt = (
            f"The user is asking a what-if question. Extract:\n"
            f"- parameter (location/salary/role/industry)\n"
            f"- new_value (the hypothetical change)\n\n"
            f"Return JSON with: parameter, new_value, and a response acknowledging the scenario.\n\n"
            f"User question: {query}"
        )
        
        try:
            response = await self.llm.ainvoke(what_if_prompt)
            
            try:
                scenario = json.loads(response.content)
            except json.JSONDecodeError:
                json_match = re.search(r'```json\n(.*?)\n```', response.content, re.DOTALL)
                if json_match:
                    scenario = json.loads(json_match.group(1))
                else:
                    scenario = {}
            
            parameter = scenario.get("parameter", "unknown")
            new_value = scenario.get("new_value", "")
            
            # Generate scenario-based response
            if parameter == "location":
                return f"If you were targeting {new_value}, you'd want to consider: " \
                       f"cost of living adjustments, market depth in that area, and visa requirements. " \
                       f"Based on the current analysis, your top skills would still be valuable. " \
                       f"Would you like me to compare specific metrics?"
            
            elif parameter == "salary":
                return f"Adjusting your salary target to {new_value} would shift the focus. " \
                       f"From our analysis, roles in the {report.salary_insights.range} range are most common. " \
                       f"A higher/lower target might require different trade-offs in company size or location."
            
            else:
                return f"Interesting scenario! Changing {parameter} to {new_value} would impact your strategy. " \
                       f"Based on the analysis, I'd recommend revisiting the match scores and growth outlook."
        
        except Exception as e:
            logger.error(f"Error handling what-if: {e}")
            return "I can help with what-if scenarios. Could you rephrase your question?"
    
    async def chat(self, submission_id: str, user_message: str) -> Dict[str, Any]:
        """Process a chat message and return response."""
        if submission_id not in self.sessions:
            return {
                "content": "Session not found. Please start a new analysis.",
                "citations": [],
                "deep_dive_card": None
            }
        
        # Store user message
        user_msg = ChatMemoryItem(
            role=ChatRole.USER,
            content=user_message,
            linked_submission_id=submission_id,
            visibility="visible"
        )
        self.sessions[submission_id].append(user_msg)
        
        # Get context
        report = self.reports[submission_id]
        conversation_history = self._get_conversation_history(submission_id)
        report_summary = self._get_report_summary(report)
        
        # Check for what-if query
        if "what if" in user_message.lower() or "if i" in user_message.lower():
            response_content = await self._handle_what_if(user_message, submission_id)
            citations = []
        
        else:
            # Retrieve relevant documents
            relevant_docs = await self._retrieve_relevant_docs(user_message, submission_id)
            
            # Build context
            docs_context = "\n\n".join([
                f"[{doc['doc_id']}] {doc['source']}: {doc['excerpt']}"
                for doc in relevant_docs
            ])
            
            # Generate response using LLM
            prompt_template = get_chat_prompt()
            prompt_text = prompt_template.format(
                report_summary=report_summary,
                conversation_history=conversation_history,
                user_question=user_message
            )
            
            try:
                response = await self.llm.ainvoke(prompt_text)
                response_content = response.content
                
                # Extract citations
                citations = [doc["doc_id"] for doc in relevant_docs]
                
            except Exception as e:
                logger.error(f"Error generating chat response: {e}")
                response_content = "I encountered an error processing your question. Please try rephrasing."
                citations = []
        
        # Store assistant message
        assistant_msg = ChatMemoryItem(
            role=ChatRole.ASSISTANT,
            content=response_content,
            linked_submission_id=submission_id,
            visibility="visible"
        )
        self.sessions[submission_id].append(assistant_msg)
        
        return {
            "content": response_content,
            "citations": citations,
            "deep_dive_card": None  # Can be extended for complex queries
        }
    
    def get_conversation_history_full(self, submission_id: str) -> List[ChatMemoryItem]:
        """Get full conversation history."""
        return self.sessions.get(submission_id, [])
