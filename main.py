"""
MonkeyKing — Main Entry Point

Usage:
  python main.py              → Start dashboard + initialize pipeline
  python main.py --scan       → Run job scanner only
  python main.py --dashboard  → Start dashboard only
"""
import sys
import os
import argparse

# Ensure monkeyking is in path
sys.path.insert(0, os.path.dirname(__file__))

from config.loader import Config
from db.models import init_db
from pathlib import Path


def ensure_dirs():
    """Create required directories."""
    base = Path(__file__).parent / "data"
    dirs = [
        base,
        base / "tailored_cvs",
        base / "screenshots",
        base / "logs",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def start_dashboard():
    """Start the FastAPI dashboard."""
    import uvicorn
    from dashboard.api import app
    print("\n🐵 MonkeyKing Dashboard starting...")
    print("   Open: http://localhost:8501\n")
    uvicorn.run(app, host="0.0.0.0", port=8501, log_level="info")


def run_pipeline_info():
    """Print pipeline info and instructions for Kiro."""
    config = Config()
    companies = config.target_companies
    roles = config.job_preferences.get("target_roles", [])

    print("\n🐵 MonkeyKing — AI Job Application Bot")
    print("=" * 50)
    print(f"Target roles: {len(roles)}")
    for r in roles:
        print(f"  → {r}")
    print(f"\nTarget companies: {len(companies)}")
    for c in companies:
        print(f"  → {c['name']} ({c['careers_url']})")
    print(f"\nMin match score: {config.job_preferences.get('min_match_score', 0.6)}")
    print(f"Max applications per run: {config.job_preferences.get('max_applications_per_run', 100)}")
    print("\n📋 To run the full pipeline, use Kiro agentic chat:")
    print('   "Run MonkeyKing scan for all target companies"')
    print('   "Match and score all found jobs"')
    print('   "Generate tailored CVs for top matches"')
    print('   "Apply to all matched jobs"')


def run_batch_scan(concurrent=5, visible=False):
    """Run the autonomous batch scanner."""
    import asyncio
    from agents.batch_scanner import BatchScanner
    scanner = BatchScanner(max_concurrent=concurrent, headless=not visible)
    return asyncio.run(scanner.run())


def run_google_scan(concurrent=5, visible=False):
    """Run the Google-powered job scanner."""
    import asyncio
    from agents.google_scanner import GoogleScanner
    scanner = GoogleScanner(max_concurrent=concurrent, headless=not visible)
    return asyncio.run(scanner.run())


def run_batch_apply(limit=100, concurrent=3, visible=False, job_ids=None, dry_run=True):
    """Run the autonomous batch applier."""
    import asyncio
    from agents.batch_applier import BatchApplier
    applier = BatchApplier(max_concurrent=concurrent, headless=not visible, dry_run=dry_run)
    return asyncio.run(applier.run(job_ids=job_ids, limit=limit))


def main():
    parser = argparse.ArgumentParser(description="MonkeyKing — AI Job Application Bot")
    parser.add_argument("--dashboard", action="store_true", help="Start dashboard only")
    parser.add_argument("--scan", action="store_true", help="Show scan plan")
    parser.add_argument("--init", action="store_true", help="Initialize database only")
    parser.add_argument("--batch-scan", action="store_true", help="Run autonomous batch scanner")
    parser.add_argument("--google-scan", action="store_true", help="Run Google-powered job scanner")
    parser.add_argument("--batch-apply", action="store_true", help="Run autonomous batch applier")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually submit applications (default is dry run)")
    parser.add_argument("--limit", type=int, default=100, help="Max jobs for batch apply")
    parser.add_argument("--concurrent", type=int, default=5, help="Concurrent browser sessions")
    parser.add_argument("--visible", action="store_true", help="Show browser windows")
    parser.add_argument("--job-ids", type=str, help="Comma-separated job IDs to apply to")
    args = parser.parse_args()

    ensure_dirs()

    # Always init DB
    Session = init_db()
    print("✅ Database initialized")

    if args.init:
        print("Database ready at monkeyking/data/monkeyking.db")
        return

    if args.batch_scan:
        run_batch_scan(concurrent=args.concurrent, visible=args.visible)
        return

    if args.google_scan:
        run_google_scan(concurrent=args.concurrent, visible=args.visible)
        return

    if args.batch_apply:
        job_ids = None
        if args.job_ids:
            job_ids = [int(x.strip()) for x in args.job_ids.split(",")]
        run_batch_apply(
            limit=args.limit, concurrent=args.concurrent,
            visible=args.visible, job_ids=job_ids,
            dry_run=not args.no_dry_run,
        )
        return

    if args.dashboard:
        start_dashboard()
        return

    if args.scan:
        run_pipeline_info()
        return

    # Default: show info + start dashboard
    run_pipeline_info()
    print("\n" + "=" * 50)
    start_dashboard()


if __name__ == "__main__":
    main()
