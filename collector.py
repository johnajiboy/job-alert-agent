"""
collector.py
Component 2: Data Collector

Pulls raw job postings from free, keyless job-board APIs and RSS feeds.
No scraping of LinkedIn/Facebook/X is done here on purpose: scraping those
platforms breaks their Terms of Service and their markup changes constantly,
which makes it an unreliable foundation for a "runs every 2 hours forever"
agent. These sources are free, public, and designed to be consumed
programmatically, which is why they're the more robust substitute.
"""

import time
import requests
import feedparser
from dateutil import parser as dateparser
from datetime import datetime, timezone

REMOTEOK_URL = "https://remoteok.com/api"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
ARBEITNOW_URL = "https://arbeitnow.com/api/job-board-api"
WWR_RSS_URL = "https://weworkremotely.com/remote-jobs.rss"

HEADERS = {"User-Agent": "JobAlertAgent/1.0 (+https://github.com/yourname/job-alert-agent)"}


def _now():
    return datetime.now(timezone.utc)


def fetch_remoteok():
    jobs = []
    try:
        resp = requests.get(REMOTEOK_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for item in data:
            if "id" not in item:
                continue  # first element is metadata, not a job
            jobs.append({
                "id": f"remoteok_{item.get('id')}",
                "title": item.get("position", ""),
                "company": item.get("company", ""),
                "url": item.get("url", ""),
                "posted_at": item.get("date", ""),
                "source": "RemoteOK",
                "description": item.get("description", "")[:500],
            })
    except Exception as e:
        print(f"[collector] RemoteOK fetch failed: {e}")
    return jobs


def fetch_remotive():
    jobs = []
    try:
        resp = requests.get(REMOTIVE_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("jobs", []):
            jobs.append({
                "id": f"remotive_{item.get('id')}",
                "title": item.get("title", ""),
                "company": item.get("company_name", ""),
                "url": item.get("url", ""),
                "posted_at": item.get("publication_date", ""),
                "source": "Remotive",
                "description": (item.get("description") or "")[:500],
            })
    except Exception as e:
        print(f"[collector] Remotive fetch failed: {e}")
    return jobs


def fetch_arbeitnow():
    jobs = []
    try:
        resp = requests.get(ARBEITNOW_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("data", []):
            jobs.append({
                "id": f"arbeitnow_{item.get('slug')}",
                "title": item.get("title", ""),
                "company": item.get("company_name", ""),
                "url": item.get("url", ""),
                "posted_at": datetime.fromtimestamp(
                    item.get("created_at", time.time()), tz=timezone.utc
                ).isoformat() if item.get("created_at") else "",
                "source": "Arbeitnow",
                "description": (item.get("description") or "")[:500],
            })
    except Exception as e:
        print(f"[collector] Arbeitnow fetch failed: {e}")
    return jobs


def fetch_weworkremotely():
    jobs = []
    try:
        feed = feedparser.parse(WWR_RSS_URL)
        for entry in feed.entries:
            jobs.append({
                "id": f"wwr_{entry.get('id', entry.get('link'))}",
                "title": entry.get("title", ""),
                "company": "",  # WWR often embeds company in the title
                "url": entry.get("link", ""),
                "posted_at": entry.get("published", ""),
                "source": "WeWorkRemotely",
                "description": (entry.get("summary") or "")[:500],
            })
    except Exception as e:
        print(f"[collector] WeWorkRemotely fetch failed: {e}")
    return jobs


def _is_recent(posted_at: str, max_age_hours: int) -> bool:
    if not posted_at:
        return True  # keep jobs with unknown timestamps rather than drop them
    try:
        dt = dateparser.parse(posted_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_hours = (_now() - dt).total_seconds() / 3600
        return age_hours <= max_age_hours
    except Exception:
        return True


def _matches_keywords(job: dict, keywords: list) -> bool:
    haystack = f"{job.get('title', '')} {job.get('description', '')}".lower()
    return any(kw.lower() in haystack for kw in keywords)


def collect_jobs(config: dict) -> list:
    """Fetch from all enabled sources, then filter by keyword + freshness."""
    all_jobs = []
    sources = config.get("sources", {})

    if sources.get("remoteok"):
        all_jobs += fetch_remoteok()
    if sources.get("remotive"):
        all_jobs += fetch_remotive()
    if sources.get("arbeitnow"):
        all_jobs += fetch_arbeitnow()
    if sources.get("weworkremotely_rss"):
        all_jobs += fetch_weworkremotely()

    keywords = config.get("keywords", [])
    max_age_hours = config.get("max_age_hours", 6)

    filtered = [
        j for j in all_jobs
        if _matches_keywords(j, keywords) and _is_recent(j.get("posted_at", ""), max_age_hours)
    ]

    print(f"[collector] fetched {len(all_jobs)} raw jobs, {len(filtered)} passed keyword/freshness filter")
    return filtered
