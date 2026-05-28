"""Preference Engine — Lightweight preference learning from user feedback."""
from datetime import datetime
from sqlalchemy.orm import Session


# Weight distribution for the three affinity types
TITLE_WEIGHT = 0.50
COMPANY_WEIGHT = 0.20
SKILL_WEIGHT = 0.30
MAX_BOOST = 0.15
MIN_SIGNALS = 5  # Minimum feedback signals before applying preference boost

# Stop words to filter from title keywords
STOP_WORDS = {"the", "and", "for", "with", "from", "into", "that", "this", "are", "was", "will"}


def _extract_title_keywords(title: str) -> list[str]:
    """Extract meaningful keywords from a job title."""
    if not title:
        return []
    words = title.lower().split()
    return [w for w in words if len(w) >= 4 and w not in STOP_WORDS]


def recompute_preferences(db: Session, user_id: int, job_title: str,
                           job_company: str, matched_skills: list[str] | None):
    """Recompute affected preference weights after new feedback.
    Uses SQL aggregation — no ML models."""
    from models import UserPreferenceHistory, UserLearnedPreferences

    try:
        # Get all signals for this user
        signals = db.query(UserPreferenceHistory).filter_by(user_id=user_id).all()
        if len(signals) < MIN_SIGNALS:
            return  # Not enough data yet

        # Recompute title keyword affinities
        title_keywords = _extract_title_keywords(job_title)
        for keyword in title_keywords:
            positive = sum(1 for s in signals
                          if s.signal_type in ("positive", "strong_positive")
                          and keyword in (s.job_title or "").lower())
            negative = sum(1 for s in signals
                          if s.signal_type == "negative"
                          and keyword in (s.job_title or "").lower())
            total = positive + negative
            affinity = (positive - negative) / total if total > 0 else 0.0
            _upsert_preference(db, user_id, "title", keyword, positive, negative, affinity)

        # Recompute company affinity
        if job_company:
            company_key = job_company.lower().strip()
            positive = sum(1 for s in signals
                          if s.signal_type in ("positive", "strong_positive")
                          and (s.job_company or "").lower().strip() == company_key)
            negative = sum(1 for s in signals
                          if s.signal_type == "negative"
                          and (s.job_company or "").lower().strip() == company_key)
            total = positive + negative
            affinity = (positive - negative) / total if total > 0 else 0.0
            _upsert_preference(db, user_id, "company", company_key, positive, negative, affinity)

        # Recompute skill affinities
        for skill in (matched_skills or []):
            skill_key = skill.lower().strip()
            if len(skill_key) < 3:
                continue
            positive = sum(1 for s in signals
                          if s.signal_type in ("positive", "strong_positive")
                          and skill_key in [sk.lower() for sk in (s.matched_skills or [])])
            negative = sum(1 for s in signals
                          if s.signal_type == "negative"
                          and skill_key in [sk.lower() for sk in (s.matched_skills or [])])
            total = positive + negative
            affinity = (positive - negative) / total if total > 0 else 0.0
            _upsert_preference(db, user_id, "skill", skill_key, positive, negative, affinity)

        db.commit()
    except Exception as e:
        try: db.rollback()
        except: pass
        print(f"  [learn] Preference recompute failed: {e}", flush=True)


def _upsert_preference(db: Session, user_id: int, pref_type: str, pref_key: str,
                        positive: int, negative: int, affinity: float):
    """Upsert a single preference weight."""
    from models import UserLearnedPreferences
    existing = db.query(UserLearnedPreferences).filter_by(
        user_id=user_id, preference_type=pref_type, preference_key=pref_key
    ).first()
    now = datetime.utcnow()
    if existing:
        existing.positive_count = positive
        existing.negative_count = negative
        existing.affinity_score = affinity
        existing.updated_at = now
    else:
        db.add(UserLearnedPreferences(
            user_id=user_id, preference_type=pref_type, preference_key=pref_key,
            positive_count=positive, negative_count=negative,
            affinity_score=affinity, updated_at=now
        ))


def compute_preference_boost(db: Session, user_id: int, job_title: str,
                              job_company: str, matched_skills: list[str] | None) -> tuple[float, str]:
    """Compute preference_boost in [-0.15, +0.15] and explanation string.
    Returns (0.0, "") if user has < MIN_SIGNALS feedback signals."""
    from models import UserPreferenceHistory, UserLearnedPreferences

    try:
        # Check if user has enough signals
        signal_count = db.query(UserPreferenceHistory).filter_by(user_id=user_id).count()
        if signal_count < MIN_SIGNALS:
            return (0.0, "")

        # Compute title affinity (average across title keywords)
        title_keywords = _extract_title_keywords(job_title)
        title_affinities = []
        for kw in title_keywords:
            pref = db.query(UserLearnedPreferences).filter_by(
                user_id=user_id, preference_type="title", preference_key=kw
            ).first()
            if pref:
                title_affinities.append(pref.affinity_score)
        title_affinity = sum(title_affinities) / len(title_affinities) if title_affinities else 0.0

        # Compute company affinity
        company_affinity = 0.0
        if job_company:
            pref = db.query(UserLearnedPreferences).filter_by(
                user_id=user_id, preference_type="company",
                preference_key=job_company.lower().strip()
            ).first()
            if pref:
                company_affinity = pref.affinity_score

        # Compute skill affinity (average across matched skills)
        skill_affinities = []
        for skill in (matched_skills or []):
            pref = db.query(UserLearnedPreferences).filter_by(
                user_id=user_id, preference_type="skill",
                preference_key=skill.lower().strip()
            ).first()
            if pref:
                skill_affinities.append(pref.affinity_score)
        skill_affinity = sum(skill_affinities) / len(skill_affinities) if skill_affinities else 0.0

        # Weighted sum → clamp to [-MAX_BOOST, +MAX_BOOST]
        raw = (title_affinity * TITLE_WEIGHT +
               company_affinity * COMPANY_WEIGHT +
               skill_affinity * SKILL_WEIGHT)
        boost = max(-MAX_BOOST, min(MAX_BOOST, raw * MAX_BOOST))

        # Build explanation
        parts = []
        if abs(title_affinity) > 0.1:
            direction = "+" if title_affinity > 0 else "-"
            parts.append(f"title {direction}")
        if abs(company_affinity) > 0.1:
            direction = "+" if company_affinity > 0 else "-"
            parts.append(f"company {direction}")
        if abs(skill_affinity) > 0.1:
            direction = "+" if skill_affinity > 0 else "-"
            parts.append(f"skills {direction}")

        explanation = ""
        if parts and abs(boost) > 0.01:
            explanation = f" [Preference: {', '.join(parts)} → {boost:+.2f}]"

        return (boost, explanation)
    except Exception as e:
        print(f"  [learn] Preference boost failed: {e}", flush=True)
        return (0.0, "")
