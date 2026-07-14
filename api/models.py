"""Pydantic models for the Job Search Agent API."""
from pydantic import BaseModel, Field
from typing import Optional


class JobResult(BaseModel):
    title: str
    company: str
    location: str = ""
    url: str = ""
    score: int = 0
    note: str = ""
    salary: Optional[str] = None
    description: str = ""
    source: str = ""


class ScoreRequest(BaseModel):
    title: str
    description: str
    company: str
    location: str = "Remote"


class ScoreResponse(BaseModel):
    score: int
    note: str
    title: str
    company: str


class SearchRequest(BaseModel):
    query: str
    location: str = "Remote"
    threshold: int = Field(default=65, ge=0, le=100)
    max_results: int = Field(default=10, ge=1, le=50)
    require_visa: bool = True
    exclude_companies: list[str] = []
    locations: list[str] = []
    skills: list[str] = []
    job_type: str = ""
    work_mode: str = ""


class SearchResponse(BaseModel):
    jobs: list[JobResult]
    total: int
    query: str


class ResumeInfo(BaseModel):
    key: str
    filename: str
    exists: bool
    is_default: bool
    size_kb: int = 0


class ListResumesResponse(BaseModel):
    registered: list[ResumeInfo]
    unregistered: list[str]
    default_key: str


class ResumeUploadWithKeyRequest(BaseModel):
    key: str = ""


class DigestSendRequest(BaseModel):
    schedule: str = "now"
    email: str = ""


class ResumeUploadResponse(BaseModel):
    name: str
    email: str
    current_role: str
    core_skills: list[str]
    years_experience: int
    missing_fields: list[str]


class ProfileResponse(BaseModel):
    name: str
    current_role: str
    core_skills: list[str]
    years_experience: int
    seniority_keywords: list[str]


class TrackerJob(BaseModel):
    title: str
    company: str
    url: str = ""
    score: int = 0
    status: str = "new"
    date_found: str = ""
    date_updated: str = ""
    notes: str = ""


class TrackerUpdateRequest(BaseModel):
    title: str
    company: str
    status: str = Field(..., pattern="^(applied|rejected|offer)$")
    notes: str = ""


class TrackerAddRequest(BaseModel):
    title: str
    company: str
    url: str = ""
    score: int = 0
    description: str = ""
    salary: str = ""
    location: str = ""


class TrackerResponse(BaseModel):
    jobs: list[TrackerJob]
    total: int


class ProfileUpdateRequest(BaseModel):
    full_name: str = ""
    current_role: str = ""
    years_experience: int = 0
    core_skills: list[str] = []


class DigestPreferences(BaseModel):
    enabled: bool = True
    frequency: str = "weekly"
    email: str = ""
