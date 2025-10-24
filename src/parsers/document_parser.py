"""
Document parser for resumes and transcripts.
Extracts structured data from PDFs and DOCX files.
"""
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
import pdfplumber
from docx import Document as DocxDocument
from src.models.schemas import ParsedProfile, Education, Experience
from src.cache.redis_client import cache

logger = logging.getLogger(__name__)


class DocumentParser:
    def __init__(self):
        self.skill_keywords = {
            "programming": ["python", "java", "javascript", "c++", "rust", "go", "typescript", "ruby", "php", "swift"],
            "web": ["react", "angular", "vue", "html", "css", "node.js", "django", "flask", "fastapi", "express"],
            "data": ["sql", "nosql", "mongodb", "postgresql", "mysql", "redis", "elasticsearch", "spark", "hadoop"],
            "cloud": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins", "ci/cd"],
            "ml": ["machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn", "nlp", "computer vision"],
            "tools": ["git", "jira", "confluence", "slack", "figma", "postman", "vs code"],
            "soft": ["leadership", "communication", "teamwork", "problem solving", "agile", "scrum"]
        }
        
        self.degree_patterns = [
            r"(bachelor|b\.?s\.?|b\.?a\.?|master|m\.?s\.?|m\.?a\.?|ph\.?d\.?|doctorate)\s+(of|in)?\s*([a-z\s]+)",
            r"(bachelor|master|phd|doctorate)\s*'?s?\s+(degree|of)?\s*(?:in)?\s*([a-z\s]+)"
        ]
        
        self.title_patterns = [
            r"(senior|junior|lead|principal|staff|intern|associate)?\s*(software|data|machine learning|ml|product|project|business)\s*(engineer|scientist|analyst|manager|developer|architect)",
            r"(cto|ceo|cfo|coo|vp|director|manager|supervisor|coordinator)"
        ]
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file."""
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            logger.info(f"Extracted {len(text)} chars from PDF: {file_path}")
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from PDF {file_path}: {e}")
            raise
    
    def _extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        try:
            doc = DocxDocument(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            logger.info(f"Extracted {len(text)} chars from DOCX: {file_path}")
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from DOCX {file_path}: {e}")
            raise
    
    def _extract_skills(self, text: str) -> List[Dict[str, str]]:
        """Extract skills from text."""
        skills = []
        text_lower = text.lower()
        
        for category, keywords in self.skill_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    skills.append({
                        "name": keyword.title(),
                        "type": category
                    })
        
        # Deduplicate
        seen = set()
        unique_skills = []
        for skill in skills:
            key = skill["name"].lower()
            if key not in seen:
                seen.add(key)
                unique_skills.append(skill)
        
        logger.info(f"Extracted {len(unique_skills)} unique skills")
        return unique_skills
    
    def _extract_education(self, text: str) -> List[Education]:
        """Extract education information."""
        education = []
        lines = text.split("\n")
        
        for i, line in enumerate(lines):
            for pattern in self.degree_patterns:
                match = re.search(pattern, line.lower())
                if match:
                    degree = match.group(1).title()
                    major = match.group(3).strip().title() if len(match.groups()) >= 3 else None
                    
                    # Look for institution in nearby lines
                    institution = "Unknown Institution"
                    for j in range(max(0, i-2), min(len(lines), i+3)):
                        if "university" in lines[j].lower() or "college" in lines[j].lower() or "institute" in lines[j].lower():
                            institution = lines[j].strip()
                            break
                    
                    # Look for year
                    year = None
                    year_match = re.search(r"(19|20)\d{2}", line)
                    if year_match:
                        year = int(year_match.group(0))
                    
                    education.append(Education(
                        institution=institution,
                        degree=degree,
                        major=major,
                        year=year
                    ))
                    break
        
        logger.info(f"Extracted {len(education)} education entries")
        return education
    
    def _extract_experience(self, text: str) -> List[Experience]:
        """Extract work experience."""
        experiences = []
        lines = text.split("\n")
        
        for i, line in enumerate(lines):
            for pattern in self.title_patterns:
                match = re.search(pattern, line.lower())
                if match:
                    title = line.strip()
                    
                    # Look for company in nearby lines
                    company = "Unknown Company"
                    for j in range(max(0, i-2), min(len(lines), i+3)):
                        # Skip if it's the same line
                        if j != i and len(lines[j].strip()) > 3:
                            # Check if it's not a common header
                            if not any(h in lines[j].lower() for h in ["experience", "education", "skills", "projects"]):
                                company = lines[j].strip()
                                break
                    
                    # Look for dates
                    start = None
                    end = None
                    date_match = re.search(r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4})\s*[-–—]\s*((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}|present)", line.lower())
                    if date_match:
                        start = date_match.group(1)
                        end = date_match.group(2)
                    
                    experiences.append(Experience(
                        company=company,
                        title=title,
                        start=start,
                        end=end,
                        highlights=[]
                    ))
                    break
        
        logger.info(f"Extracted {len(experiences)} experience entries")
        return experiences
    
    def _infer_seniority(self, text: str, experiences: List[Experience]) -> str:
        """Infer seniority level from text and experience."""
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ["senior", "lead", "principal", "staff", "architect", "director", "vp"]):
            return "senior"
        elif any(keyword in text_lower for keyword in ["junior", "entry", "intern", "associate"]):
            return "junior"
        elif len(experiences) > 5:
            return "senior"
        elif len(experiences) > 2:
            return "mid"
        else:
            return "junior"
    
    async def parse_resume(self, file_path: str, submission_id: str) -> ParsedProfile:
        """Parse resume file into structured profile."""
        logger.info(f"[{submission_id}] Parsing resume: {file_path}")
        
        # Check cache
        cached = await cache.get_resume(submission_id)
        if cached:
            logger.info(f"[{submission_id}] Resume found in cache (HIT)")
            return ParsedProfile(**cached)
        
        # Extract text based on file type
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            text = self._extract_text_from_pdf(file_path)
        elif path.suffix.lower() in [".docx", ".doc"]:
            text = self._extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        # Extract structured data
        skills = self._extract_skills(text)
        education = self._extract_education(text)
        experience = self._extract_experience(text)
        seniority = self._infer_seniority(text, experience)
        
        # Extract certifications (simple keyword matching)
        certifications = []
        cert_keywords = ["certification", "certified", "certificate"]
        for line in text.split("\n"):
            if any(keyword in line.lower() for keyword in cert_keywords):
                certifications.append(line.strip())
        
        profile = ParsedProfile(
            skills=skills,
            education=education,
            experience=experience,
            certifications=certifications[:5],  # Limit to 5
            seniority_inferred=seniority
        )
        
        # Cache result
        await cache.set_resume(submission_id, profile.model_dump())
        logger.info(f"[{submission_id}] Resume parsed successfully - {len(skills)} skills, {len(education)} degrees, {len(experience)} jobs")
        
        return profile
    
    async def parse_transcript(self, file_path: str, submission_id: str) -> Dict[str, Any]:
        """Parse academic transcript."""
        logger.info(f"[{submission_id}] Parsing transcript: {file_path}")
        
        # Check cache
        cached = await cache.get_transcript(submission_id)
        if cached:
            logger.info(f"[{submission_id}] Transcript found in cache (HIT)")
            return cached
        
        # Extract text
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            text = self._extract_text_from_pdf(file_path)
        elif path.suffix.lower() in [".docx", ".doc"]:
            text = self._extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        # Extract GPA
        gpa = None
        gpa_match = re.search(r"gpa[:\s]+([0-4]\.\d{1,2})", text.lower())
        if gpa_match:
            gpa = float(gpa_match.group(1))
        
        # Extract courses (simplified)
        courses = []
        course_keywords = ["course", "class", "subject"]
        for line in text.split("\n"):
            if any(keyword in line.lower() for keyword in course_keywords):
                courses.append(line.strip())
        
        transcript_data = {
            "gpa": gpa,
            "courses": courses[:20],  # Limit to 20
            "raw_text_length": len(text)
        }
        
        # Cache result
        await cache.set_transcript(submission_id, transcript_data)
        logger.info(f"[{submission_id}] Transcript parsed - GPA: {gpa}, Courses: {len(courses)}")
        
        return transcript_data
