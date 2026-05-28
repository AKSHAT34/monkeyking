"""SQLite database models for MonkeyKing."""
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Boolean,
    create_engine, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
from pathlib import Path

Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    company = Column(String(300), nullable=False)
    location = Column(String(300))
    url = Column(String(2000), nullable=False, unique=True)
    description = Column(Text)
    requirements = Column(Text)
    salary_range = Column(String(200))
    job_type = Column(String(50))  # remote, onsite, hybrid
    match_score = Column(Float, default=0.0)
    matched_skills = Column(Text)  # JSON list of matched skills
    missing_skills = Column(Text)  # JSON list of missing skills
    status = Column(String(50), default="found")  # found, matched, cv_created, applied, rejected, error
    source_page = Column(String(2000))
    discovered_at = Column(DateTime, default=datetime.utcnow)
    applied_at = Column(DateTime, nullable=True)

    cv = relationship("TailoredCV", back_populates="job", uselist=False)
    application = relationship("Application", back_populates="job", uselist=False)


class TailoredCV(Base):
    __tablename__ = "tailored_cvs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    file_path = Column(String(1000))
    tailored_summary = Column(Text)
    tailored_skills = Column(Text)
    ats_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="cv")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    status = Column(String(50), default="pending")  # pending, submitted, confirmed, failed, error
    cv_file_used = Column(String(1000))
    cover_letter = Column(Text)
    screening_answers = Column(Text)  # JSON of Q&A
    error_message = Column(Text)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="application")
    account = relationship("Account", back_populates="applications")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(300), nullable=False)  # company name or portal
    portal_url = Column(String(2000))
    username = Column(String(300))
    email_used = Column(String(300))
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    applications = relationship("Application", back_populates="account")


class RunLog(Base):
    __tablename__ = "run_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_type = Column(String(100))  # scan, match, tailor, apply, full
    status = Column(String(50))  # running, completed, failed
    jobs_found = Column(Integer, default=0)
    jobs_matched = Column(Integer, default=0)
    cvs_created = Column(Integer, default=0)
    applications_sent = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    log_details = Column(Text)


def init_db(db_path: str = None):
    """Initialize the database and create all tables."""
    if db_path is None:
        db_path = str(Path(__file__).parent.parent / "data" / "monkeyking.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
