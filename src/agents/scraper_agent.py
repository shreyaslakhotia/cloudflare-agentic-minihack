"""
Web scraper agent with mock data support.
Gathers intelligence from company, industry, and role sources.
"""
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.models.schemas import ScrapeRequest, ScrapeResult, ScrapeTargetType
from src.cache.redis_client import cache

logger = logging.getLogger(__name__)


class ScraperAgent:
    def __init__(self):
        self.mock_data = self._generate_mock_data()
    
    def _generate_mock_data(self) -> List[Dict[str, Any]]:
        """Generate comprehensive mock scrape results."""
        now = datetime.utcnow()
        
        mock_docs = [
            # Company reviews
            {
                "source": "glassdoor.com",
                "type": ScrapeTargetType.COMPANY,
                "title": "Software Engineer Reviews at Tech Corp",
                "content": "Great work-life balance and innovative projects. Strong engineering culture with regular hackathons. Competitive compensation and benefits. Some concerns about recent reorganization.",
                "entities": ["Tech Corp", "Software Engineer", "work-life balance", "compensation"],
                "tags": ["REVIEW", "COMPANY_CULTURE", "COMPENSATION"],
                "published_at": now - timedelta(days=15),
                "quality_score": 0.85
            },
            {
                "source": "blind.com",
                "type": ScrapeTargetType.COMPANY,
                "title": "Tech Corp - Employee Discussion",
                "content": "TC ranges from 150K-250K for mid-level SWE. Stock grants are generous. Promotion timeline is clear. Remote work policy is flexible.",
                "entities": ["Tech Corp", "compensation", "stock", "remote work"],
                "tags": ["DISCUSSION", "COMPENSATION", "REMOTE"],
                "published_at": now - timedelta(days=30),
                "quality_score": 0.75
            },
            {
                "source": "linkedin.com",
                "type": ScrapeTargetType.COMPANY,
                "title": "Tech Corp Company Profile",
                "content": "Leading technology company specializing in cloud infrastructure and AI solutions. 5000+ employees globally. Recently secured Series D funding. Expanding engineering teams in multiple locations.",
                "entities": ["Tech Corp", "cloud", "AI", "funding"],
                "tags": ["COMPANY_INFO", "GROWTH", "FUNDING"],
                "published_at": now - timedelta(days=10),
                "quality_score": 0.90
            },
            # Industry trends
            {
                "source": "techcrunch.com",
                "type": ScrapeTargetType.INDUSTRY,
                "title": "Cloud Computing Market Growth Accelerates",
                "content": "Cloud computing market expected to grow 20% annually through 2028. Major drivers include AI/ML adoption and hybrid cloud solutions. Skills in Kubernetes and serverless architecture in high demand.",
                "entities": ["cloud computing", "AI", "Kubernetes", "market growth"],
                "tags": ["INDUSTRY_TREND", "MARKET_ANALYSIS", "SKILLS"],
                "published_at": now - timedelta(days=5),
                "quality_score": 0.92
            },
            {
                "source": "gartner.com",
                "type": ScrapeTargetType.INDUSTRY,
                "title": "2025 Technology Trends Report",
                "content": "AI engineering and platform engineering are top strategic trends. Organizations prioritizing cloud-native development. Strong demand for full-stack and DevOps skills.",
                "entities": ["AI", "platform engineering", "cloud-native", "DevOps"],
                "tags": ["INDUSTRY_REPORT", "TRENDS", "SKILLS_DEMAND"],
                "published_at": now - timedelta(days=20),
                "quality_score": 0.95
            },
            {
                "source": "stackoverflow.com",
                "type": ScrapeTargetType.INDUSTRY,
                "title": "Developer Survey 2025 Results",
                "content": "Python and JavaScript remain most popular. Cloud platforms and containerization skills see highest salary premiums. Remote work now standard for 65% of developers.",
                "entities": ["Python", "JavaScript", "cloud", "remote work", "salary"],
                "tags": ["SURVEY", "SKILLS", "COMPENSATION", "REMOTE"],
                "published_at": now - timedelta(days=45),
                "quality_score": 0.88
            },
            # Role-specific data
            {
                "source": "levels.fyi",
                "type": ScrapeTargetType.ROLE,
                "title": "Software Engineer Compensation Data",
                "content": "Average total compensation for mid-level SWE: $180K (base: $140K, stock: $30K, bonus: $10K). Senior level: $250K. Geographic variance: SF +20%, NYC +15%, Austin baseline.",
                "entities": ["Software Engineer", "compensation", "salary bands"],
                "tags": ["COMPENSATION", "ROLE_DATA", "SALARY_BANDS"],
                "published_at": now - timedelta(days=7),
                "quality_score": 0.93
            },
            {
                "source": "github.com",
                "type": ScrapeTargetType.ROLE,
                "title": "Top Skills for Software Engineers 2025",
                "content": "Most in-demand: System design, distributed systems, React/TypeScript, Python, Docker/K8s, CI/CD. Emerging: LLM integration, vector databases, edge computing.",
                "entities": ["system design", "React", "Python", "Docker", "Kubernetes"],
                "tags": ["SKILLS", "ROLE_REQUIREMENTS", "TRENDS"],
                "published_at": now - timedelta(days=12),
                "quality_score": 0.87
            },
            {
                "source": "indeed.com",
                "type": ScrapeTargetType.ROLE,
                "title": "Software Engineer Job Market Analysis",
                "content": "Job postings up 15% year-over-year. Highest demand in cloud services, fintech, and AI sectors. Hybrid roles (on-site 2-3 days) most common. Visa sponsorship available at 40% of companies.",
                "entities": ["job market", "demand", "hybrid work", "visa sponsorship"],
                "tags": ["JOB_MARKET", "TRENDS", "VISA", "WORK_MODEL"],
                "published_at": now - timedelta(days=18),
                "quality_score": 0.89
            },
            # Location-specific
            {
                "source": "numbeo.com",
                "type": ScrapeTargetType.LOCATION,
                "title": "Cost of Living: San Francisco vs Austin",
                "content": "SF COL index: 180. Austin: 110. Rent in SF: $3500 (1br), Austin: $1800. Effective purchasing power higher in Austin despite lower nominal salaries.",
                "entities": ["San Francisco", "Austin", "cost of living", "rent"],
                "tags": ["LOCATION", "COL", "HOUSING"],
                "published_at": now - timedelta(days=25),
                "quality_score": 0.82
            },
            # Risk signals
            {
                "source": "reuters.com",
                "type": ScrapeTargetType.COMPANY,
                "title": "Tech Layoffs Tracker Q4 2024",
                "content": "Several mid-size tech companies announced restructuring. However, cloud infrastructure and AI companies continue aggressive hiring. Market stabilizing after 2023 corrections.",
                "entities": ["layoffs", "restructuring", "hiring", "AI"],
                "tags": ["RISK", "LAYOFFS", "HIRING_TRENDS"],
                "published_at": now - timedelta(days=35),
                "quality_score": 0.90
            },
            {
                "source": "techradar.com",
                "type": ScrapeTargetType.INDUSTRY,
                "title": "AI Automation Impact on Developer Roles",
                "content": "AI coding assistants augment rather than replace developers. Demand shifting toward AI integration skills, prompt engineering, and system architecture. Junior roles may see compression.",
                "entities": ["AI", "automation", "job market", "skills evolution"],
                "tags": ["RISK", "AUTOMATION", "FUTURE_OUTLOOK"],
                "published_at": now - timedelta(days=40),
                "quality_score": 0.85
            },
            # Additional sources
            {
                "source": "ycombinator.com",
                "type": ScrapeTargetType.COMPANY,
                "title": "Startup Engineering Culture Discussion",
                "content": "Best startups offer equity, learning opportunities, and impact. Trade-offs: lower base salary, higher risk, longer hours. Great for career acceleration.",
                "entities": ["startup", "equity", "culture", "career growth"],
                "tags": ["STARTUP", "CULTURE", "CAREER_ADVICE"],
                "published_at": now - timedelta(days=22),
                "quality_score": 0.78
            },
            {
                "source": "medium.com",
                "type": ScrapeTargetType.ROLE,
                "title": "Transitioning from Mid to Senior Engineer",
                "content": "Key differences: system design ownership, mentoring juniors, cross-team collaboration, production operational excellence. Timeline: typically 4-6 years experience.",
                "entities": ["career progression", "senior engineer", "system design"],
                "tags": ["CAREER", "ROLE_PROGRESSION", "SKILLS"],
                "published_at": now - timedelta(days=28),
                "quality_score": 0.83
            },
            {
                "source": "stackoverflow.blog",
                "type": ScrapeTargetType.INDUSTRY,
                "title": "Remote Work Statistics 2025",
                "content": "68% of tech roles now remote or hybrid. Full remote: 35%, hybrid: 33%, on-site: 32%. Remote roles have 3x more applicants. Compensation parity increasingly common.",
                "entities": ["remote work", "hybrid", "statistics", "compensation"],
                "tags": ["REMOTE", "WORK_MODEL", "STATISTICS"],
                "published_at": now - timedelta(days=14),
                "quality_score": 0.91
            }
        ]
        
        return mock_docs
    
    def _create_scrape_result(self, doc: Dict[str, Any], index: int) -> ScrapeResult:
        """Convert mock doc to ScrapeResult."""
        doc_id = hashlib.sha256(f"{doc['source']}:{doc['title']}:{index}".encode()).hexdigest()[:16]
        url = f"https://{doc['source']}/{doc_id}"
        
        return ScrapeResult(
            doc_id=doc_id,
            source=doc['source'],
            url=url,
            title=doc['title'],
            published_at=doc.get('published_at'),
            content_excerpt=doc['content'][:300],
            entities=doc.get('entities', []),
            tags=doc.get('tags', []),
            quality_score=doc.get('quality_score', 0.8),
            cache_hit=False
        )
    
    async def execute(self, request: ScrapeRequest, submission_id: str) -> List[ScrapeResult]:
        """Execute scraping with mock data."""
        logger.info(f"[{submission_id}] Starting scrape for {len(request.targets)} targets (MOCK MODE)")
        
        results = []
        
        # Check if we have cached results for this request
        request_hash = hashlib.sha256(str(request.model_dump()).encode()).hexdigest()[:16]
        cache_key = f"scrape_request:{request_hash}"
        cached = await cache.get(cache_key)
        
        if cached:
            logger.info(f"[{submission_id}] Scrape results found in cache (HIT)")
            results = [ScrapeResult(**r) for r in cached]
            for r in results:
                r.cache_hit = True
            return results
        
        # Generate results based on target types
        target_types = {t.type for t in request.targets}
        
        for idx, doc in enumerate(self.mock_data):
            # Filter by target type if specified
            if target_types and doc['type'] not in target_types:
                continue
            
            result = self._create_scrape_result(doc, idx)
            results.append(result)
            
            # Respect max docs limit
            if len(results) >= request.max_docs_per_source:
                break
        
        # Cache results
        await cache.set(cache_key, [r.model_dump() for r in results], 86400)  # 24 hours
        
        logger.info(f"[{submission_id}] Scraping complete: {len(results)} documents collected")
        logger.info(f"[{submission_id}] Sources: {len(set(r.source for r in results))}, "
                   f"Avg quality: {sum(r.quality_score for r in results) / len(results):.2f}")
        
        return results
    
    async def scrape_job_description(self, jd_text_or_url: str, submission_id: str) -> Dict[str, Any]:
        """Parse job description from text or URL."""
        logger.info(f"[{submission_id}] Parsing job description")
        
        # If it looks like a URL, create a mock fetch
        if jd_text_or_url.startswith("http"):
            jd_text = """
            Senior Software Engineer - Cloud Infrastructure
            
            We're seeking an experienced software engineer to join our cloud platform team.
            
            Requirements:
            - 5+ years of software development experience
            - Strong proficiency in Python, Go, or Java
            - Experience with Kubernetes, Docker, and cloud platforms (AWS/GCP/Azure)
            - System design and distributed systems knowledge
            - CS degree or equivalent experience
            
            Nice to have:
            - Experience with Terraform, CI/CD pipelines
            - Background in DevOps or SRE
            - Open source contributions
            
            Compensation: $160K-$220K base + equity + benefits
            Location: San Francisco (Hybrid - 3 days/week)
            """
        else:
            jd_text = jd_text_or_url
        
        # Extract key info
        jd_data = {
            "title": "Senior Software Engineer",
            "company": "Tech Corp",
            "location": "San Francisco, CA",
            "employment_type": "full_time",
            "salary_range": {"min": 160000, "max": 220000},
            "required_skills": ["Python", "Kubernetes", "Docker", "AWS", "System Design"],
            "nice_to_have": ["Terraform", "CI/CD", "DevOps", "Go"],
            "seniority": "senior",
            "remote_policy": "hybrid",
            "raw_text": jd_text
        }
        
        logger.info(f"[{submission_id}] JD parsed: {jd_data['title']} at {jd_data['company']}")
        return jd_data
