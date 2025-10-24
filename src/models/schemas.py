from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    PART_TIME = "part_time"


class VisaStatus(str, Enum):
    CITIZEN = "citizen"
    PERMANENT_RESIDENT = "permanent_resident"
    WORK_VISA = "work_visa"
    STUDENT_VISA = "student_visa"
    REQUIRES_SPONSORSHIP = "requires_sponsorship"


class Preferences(BaseModel):
    salary_target_min: Optional[int] = None
    salary_target_max: Optional[int] = None
    employment_type: List[EmploymentType] = []
    locations: List[str] = []
    visa_status: Optional[VisaStatus] = None
    remote_ok: bool = True
    interests: List[str] = []
    roles: List[str] = []
    industries: List[str] = []


class UserSubmission(BaseModel):
    submission_id: str = Field(default_factory=lambda: f"sub_{datetime.utcnow().timestamp()}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    resume_raw_uri: Optional[str] = None
    transcript_raw_uri: Optional[str] = None
    jd_text_or_url: Optional[str] = None
    user_prompt_text: str
    preferences: Preferences


class Education(BaseModel):
    institution: str
    degree: str
    major: Optional[str] = None
    gpa: Optional[float] = None
    year: Optional[int] = None


class Experience(BaseModel):
    company: str
    title: str
    start: Optional[str] = None
    end: Optional[str] = None
    highlights: List[str] = []


class ParsedProfile(BaseModel):
    skills: List[Dict[str, str]] = []  # {name, type: hard/soft/tools}
    education: List[Education] = []
    experience: List[Experience] = []
    certifications: List[str] = []
    projects: List[Dict[str, Any]] = []
    publications: List[str] = []
    seniority_inferred: Optional[str] = None
    location_history: List[str] = []


class ScrapeTargetType(str, Enum):
    COMPANY = "company"
    INDUSTRY = "industry"
    ROLE = "role"
    LOCATION = "location"
    SOURCE = "source"


class ScrapeTarget(BaseModel):
    type: ScrapeTargetType
    name_or_url: str
    priority: int = 1
    notes: Optional[str] = None


class ScrapeRequest(BaseModel):
    targets: List[ScrapeTarget]
    rate_limit_policy: str = "conservative"
    max_docs_per_source: int = 50
    time_window: int = 3600
    language: str = "en"


class ScrapeResult(BaseModel):
    doc_id: str
    source: str
    url: str
    title: str
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    content_excerpt: str
    content_full_uri: Optional[str] = None
    entities: List[str] = []
    tags: List[str] = []
    quality_score: float = 0.0
    toxicity_flags: List[str] = []
    robots_status: str = "allowed"
    cache_hit: bool = False


class RiskType(str, Enum):
    LAYOFFS = "layoffs"
    LEGAL = "legal"
    CULTURE = "culture"
    MARKET = "market"
    VALUATION = "valuation"


class RiskSignal(BaseModel):
    type: RiskType
    severity: int = Field(ge=1, le=5)
    refs: List[str] = []


class SentimentEvidence(BaseModel):
    doc_id: str
    quote_excerpt: str
    rationale: str


class SentimentBundle(BaseModel):
    scores: Dict[str, float] = {}  # company, industry, role_type, seniority: -1..1
    evidence: List[SentimentEvidence] = []
    risk_signals: List[RiskSignal] = []


class MatchScore(BaseModel):
    option_id: str
    type: str  # role|company|industry
    label: str
    score: float = Field(ge=0, le=100)


class Recommendation(BaseModel):
    title: str
    company: str
    location: str
    rationale: str
    steps_next: List[str] = []


class SalaryInsights(BaseModel):
    range: Dict[str, int] = {}  # min, max
    percentile_est: Optional[int] = None
    sources: List[str] = []


class GrowthOutlook(BaseModel):
    five_yr_view: str
    automation_risk: str
    trend_notes: str


class LocationNotes(BaseModel):
    col_index: Optional[float] = None
    market_depth: str
    visa_fit: str


class GapAndUpskilling(BaseModel):
    gap: str
    suggested_action: str
    resource_refs: List[str] = []


class Citation(BaseModel):
    source: str
    url: str
    doc_id: str


class ChartData(BaseModel):
    sentiment_series: List[Dict[str, Any]] = []
    salary_bands: List[Dict[str, Any]] = []
    risk_histogram: List[Dict[str, Any]] = []
    timeline: List[Dict[str, Any]] = []


class AnalysisReport(BaseModel):
    submission_id: str
    match_scores: List[MatchScore] = []
    recommendations: List[Recommendation] = []
    salary_insights: Optional[SalaryInsights] = None
    growth_outlook: Optional[GrowthOutlook] = None
    location_notes: Optional[LocationNotes] = None
    gaps_and_upskilling: List[GapAndUpskilling] = []
    negotiation_tips: List[str] = []
    assumptions: List[str] = []
    limitations: List[str] = []
    chart_data: ChartData = Field(default_factory=ChartData)
    citations: List[Citation] = []


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatMemoryItem(BaseModel):
    role: ChatRole
    content: str
    linked_submission_id: str
    visibility: str = "visible"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OrchestrationState(str, Enum):
    SUBMITTED = "submitted"
    PARSING = "parsing"
    SCRAPING = "scraping"
    ANALYZING_SENTIMENT = "analyzing_sentiment"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


class StatusResponse(BaseModel):
    submission_id: str
    state: OrchestrationState
    progress: float = 0.0
    message: str = ""
    started_at: datetime
    updated_at: datetime
