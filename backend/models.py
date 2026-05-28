"""Database models for MonkeyKing Web App."""
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Boolean,
    create_engine, ForeignKey, JSON, Enum as SAEnum, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from datetime import datetime
from pathlib import Path
import enum, os

Base = declarative_base()

DB_PATH = os.environ.get("MK_DB_PATH", str(Path(__file__).parent / "data" / "monkeyking.db"))


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(300), unique=True, nullable=False, index=True)
    hashed_password = Column(String(500), nullable=True)  # null for OAuth users
    name = Column(String(300), nullable=False)
    auth_provider = Column(String(50), default="local")  # local, google
    google_id = Column(String(300), nullable=True)
    avatar_url = Column(String(1000), nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all,delete")
    cvs = relationship("UploadedCV", back_populates="user", cascade="all,delete")
    jobs = relationship("UserJob", back_populates="user", cascade="all,delete")
    searches = relationship("SearchRun", back_populates="user", cascade="all,delete")


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    phone = Column(String(50))
    location = Column(String(300))
    linkedin = Column(String(500))
    notice_period = Column(String(100))
    current_salary = Column(String(200))
    expected_salary = Column(String(200))
    preferred_locations = Column(JSON, default=list)
    target_roles = Column(JSON, default=list)  # user-selected from suggestions
    work_authorization = Column(String(200))
    willing_to_relocate = Column(Boolean, default=True)
    years_experience = Column(Integer, default=0)
    # Extracted from CV by DeepSeek
    extracted_skills = Column(JSON, default=list)
    extracted_experience = Column(JSON, default=list)
    extracted_education = Column(JSON, default=list)
    extracted_certifications = Column(JSON, default=list)
    extracted_projects = Column(JSON, default=list)
    extracted_summary = Column(Text, default="")
    suggested_roles = Column(JSON, default=list)  # AI-suggested job titles
    # Settings columns (nullable for SQLite ALTER TABLE compatibility)
    notifications_enabled = Column(Boolean, default=False)
    schedule_frequency = Column(String(50), default="off")  # "daily", "every_3_days", "weekly", "off"
    linkedin_scraping_enabled = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")


class UploadedCV(Base):
    __tablename__ = "uploaded_cvs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    filename = Column(String(500))
    file_path = Column(String(1000))
    file_type = Column(String(20))  # pdf, docx
    raw_text = Column(Text)
    parsed_data = Column(JSON)  # full DeepSeek extraction
    is_primary = Column(Boolean, default=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="cvs")


class ApplicationStatus(enum.Enum):
    NOT_STARTED = "not_started"
    STARTED = "started"
    IN_PROCESS = "in_process"
    DOCUMENT_MISSING = "document_missing"
    APPLIED = "applied"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    REJECTED = "rejected"
    OFFER_RECEIVED = "offer_received"


class UserJob(Base):
    __tablename__ = "user_jobs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    job_id = Column(Integer, ForeignKey("jobs.id"))
    status = Column(String(50), default=ApplicationStatus.NOT_STARTED.value)
    tailored_cv_path = Column(String(1000))
    tailored_cv_docx_path = Column(String(1000))
    cover_letter_path = Column(String(1000))
    cover_letter_docx_path = Column(String(1000))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="jobs")
    job = relationship("Job")


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    company = Column(String(300), nullable=False)
    location = Column(String(300))
    url = Column(String(2000), nullable=False, unique=True, index=True)
    description = Column(Text)
    requirements = Column(Text)
    salary_range = Column(String(200))
    job_type = Column(String(50))
    source = Column(String(100))  # company_website, google_search
    last_verified = Column(DateTime, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)


class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=False)
    careers_url = Column(String(2000), nullable=False)
    category = Column(String(100))
    country = Column(String(100), default="India")
    added_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SearchRun(Base):
    __tablename__ = "search_runs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    status = Column(String(50), default="running")  # running, completed, failed
    companies_searched = Column(Integer, default=0)
    jobs_found = Column(Integer, default=0)
    jobs_matched = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    progress_log = Column(JSON, default=list)  # [{company, status, jobs_found, jobs_matched}]

    user = relationship("User", back_populates="searches")


class UserJobMatch(Base):
    """Per-user match scores for jobs."""
    __tablename__ = "user_job_matches"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    job_id = Column(Integer, ForeignKey("jobs.id"))
    search_run_id = Column(Integer, ForeignKey("search_runs.id"), nullable=True)
    match_score = Column(Float, default=0.0)
    match_reason = Column(Text)  # DeepSeek explanation
    matched_skills = Column(JSON, default=list)
    missing_skills = Column(JSON, default=list)
    relevance_summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserLLMSettings(Base):
    """Per-user LLM API key configuration."""
    __tablename__ = "user_llm_settings"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    active_provider = Column(String(50), default="deepseek")  # deepseek, openai, anthropic, google, groq, mistral
    # API keys (encrypted at rest in production)
    deepseek_key = Column(String(500), nullable=True)
    openai_key = Column(String(500), nullable=True)
    anthropic_key = Column(String(500), nullable=True)
    google_key = Column(String(500), nullable=True)
    groq_key = Column(String(500), nullable=True)
    mistral_key = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="llm_settings")


class ScanHistory(Base):
    """Tracks which scan method succeeded/failed per company."""
    __tablename__ = "scan_history"
    __table_args__ = (
        UniqueConstraint("company_id", "method_name", name="uq_scan_history_company_method"),
    )

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    method_name = Column(String(50), nullable=False)
    success = Column(Boolean, nullable=False)
    jobs_found = Column(Integer, default=0)
    last_attempted = Column(DateTime, nullable=False)
    last_success = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, default=0)


class VisionNavCache(Base):
    """Caches vision agent navigation paths per company."""
    __tablename__ = "vision_nav_cache"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), unique=True, nullable=False)
    navigation_steps = Column(JSON, nullable=False)
    final_url = Column(String(2000), nullable=False)
    last_verified = Column(DateTime, nullable=False)
    success_count = Column(Integer, default=0)


class UserPreferenceHistory(Base):
    """Records user feedback signals (save/apply/reject) for preference learning."""
    __tablename__ = "user_preference_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    signal_type = Column(String(20), nullable=False)
    job_title = Column(String(500))
    job_company = Column(String(300))
    matched_skills = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserLearnedPreferences(Base):
    """Stores computed preference weights derived from user feedback."""
    __tablename__ = "user_learned_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "preference_type", "preference_key",
                         name="uq_user_learned_pref"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    preference_type = Column(String(20), nullable=False)
    preference_key = Column(String(300), nullable=False)
    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    affinity_score = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        echo=False,
        connect_args={"timeout": 30, "check_same_thread": False},
        pool_pre_ping=True,
    )
    # Enable WAL mode for concurrent read/write
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
