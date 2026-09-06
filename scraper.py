import os
import json
import requests
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from dateutil import parser as date_parser
from html.parser import HTMLParser
from urllib.parse import urljoin
from bs4 import BeautifulSoup


class BaseJobScraper(ABC):
    """Abstract Base Class for all job fetching sources."""

    @abstractmethod
    def fetch_jobs(self) -> list[dict]:
        pass


class OpenRoboticsScraper(BaseJobScraper):
    def __init__(self):
        self.json_url = "https://discourse.openrobotics.org/c/jobs/15.json"
        self.base_url = "https://discourse.openrobotics.org/t"
        self.source_name = "Open Robotics Discourse"
        self.seen_jobs = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

    def _get_relative_activity(self, post_date: datetime) -> str:
        now = datetime.now(timezone.utc)
        diff = now - post_date
        seconds = diff.total_seconds()
        
        if seconds < 3600:
            minutes = max(1, int(seconds // 60))
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds // 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"

    def _cleanup_old_buffer(self, max_age_hours: int = 168):
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=max_age_hours)
        self.seen_jobs = {
            link: seen_time
            for link, seen_time in self.seen_jobs.items()
            if seen_time > cutoff_time
        }

    def fetch_jobs(self, max_age_hours: int = 48) -> list[dict]:
        try:
            response = requests.get(self.json_url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                print(f"[{self.source_name}] API failed with status: {response.status_code}")
                return []
        except Exception as e:
            print(f"[{self.source_name}] Request error: {e}")
            return []

        data = response.json()
        topics = data.get("topic_list", {}).get("topics", [])
        
        new_jobs = []
        now = datetime.now(timezone.utc)
        time_cutoff = now - timedelta(hours=max_age_hours)

        self._cleanup_old_buffer(max_age_hours=168)

        for topic in topics:
            if topic.get("pinned") or topic.get("pinned_globally"):
                continue

            title = topic.get("title", "")
            slug = topic.get("slug", "")
            topic_id = topic.get("id")
            clean_link = f"{self.base_url}/{slug}/{topic_id}"

            activity_str = topic.get("last_posted_at") or topic.get("created_at")
            if not activity_str:
                continue

            try:
                activity_date = date_parser.parse(activity_str)
                if activity_date.tzinfo is None:
                    activity_date = activity_date.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            if activity_date < time_cutoff or clean_link in self.seen_jobs:
                continue

            self.seen_jobs[clean_link] = now
            relative_activity = self._get_relative_activity(activity_date)

            new_jobs.append({
                "id": clean_link,
                "title": title,
                "link": clean_link,
                "source": self.source_name,
                "activity": relative_activity,
                "summary": f"Job Posting: {title}"
            })

        return new_jobs


class WorkdayJobScraper(BaseJobScraper):
    def __init__(self, company_name, wd_host, site_id, db_filename=None):
        self.company_name = company_name
        self.wd_host = wd_host
        self.site_id = site_id
        self.source_name = f"{company_name.capitalize()} ({site_id})"
        
        self.api_url = f"https://{self.wd_host}/wday/cxs/{self.company_name}/{self.site_id}/jobs"
        self.base_job_url = f"https://{self.wd_host}/en-US/{self.site_id}"
        
        self.db_filename = db_filename or f"seen_{self.company_name}_{self.site_id}_jobs.json"
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        self.seen_jobs = self._load_seen_jobs()

    def _load_seen_jobs(self) -> dict:
        if not os.path.exists(self.db_filename):
            return {}
        try:
            with open(self.db_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {link: datetime.fromisoformat(ts) for link, ts in data.items()}
        except Exception:
            return {}

    def _save_seen_jobs(self):
        try:
            data = {link: dt.isoformat() for link, dt in self.seen_jobs.items()}
            with open(self.db_filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving {self.db_filename}: {e}")

    def _cleanup_old_buffer(self, max_age_hours: int = 168):
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=max_age_hours)
        self.seen_jobs = {
            link: seen_time
            for link, seen_time in self.seen_jobs.items()
            if seen_time > cutoff_time
        }

    def fetch_jobs(self, searchText: str = "", page_size: int = 20) -> list[dict]:
        now = datetime.now(timezone.utc)
        self._cleanup_old_buffer(max_age_hours=168)
        new_jobs = []
        offset = 0
        total = None

        try:
            while total is None or offset < total:
                payload = {
                    "appliedFacets": {},
                    "limit": page_size,
                    "offset": offset,
                    "searchText": searchText
                }

                response = requests.post(
                    self.api_url, 
                    json=payload, 
                    headers=self.headers, 
                    timeout=10
                )

                if response.status_code != 200:
                    print(f"[{self.source_name}] API call failed at offset {offset} (Status {response.status_code})")
                    break

                data = response.json()
                total = data.get("total", 0)
                job_postings = data.get("jobPostings", [])

                if not job_postings:
                    break

                for job in job_postings:
                    external_path = job.get("externalPath", "")
                    title = job.get("title", "")
                    posted_text = job.get("postedOn", "")
                    location = job.get("locationsText", "Unspecified Location")

                    if not external_path:
                        continue

                    full_link = f"{self.base_job_url}{external_path}"

                    if full_link in self.seen_jobs:
                        continue

                    self.seen_jobs[full_link] = now

                    new_jobs.append({
                        "id": full_link,
                        "title": title,
                        "link": full_link,
                        "source": self.source_name,
                        "activity": posted_text,
                        "summary": f"Location: {location} | Posted: {posted_text}"
                    })

                offset += page_size

        except Exception as e:
            print(f"[{self.source_name}] Error fetching jobs: {e}")

        if new_jobs:
            self._save_seen_jobs()

        return new_jobs

class GreenhouseScraper(BaseJobScraper):
    """Scraper for companies hosting job boards on Greenhouse API."""
    def __init__(self, board_token: str = "arxroboticsgmbh", company_name: str = "ARX Robotics", db_filename: str = None):
        self.board_token = board_token
        self.company_name = company_name
        self.source_name = f"Greenhouse ({company_name})"
        self.api_url = f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs?content=true"
        self.db_filename = db_filename or f"seen_greenhouse_{self.board_token}_jobs.json"
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        
        self.seen_jobs = self._load_seen_jobs()

    def _load_seen_jobs(self) -> dict:
        if not os.path.exists(self.db_filename):
            return {}
        try:
            with open(self.db_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {link: datetime.fromisoformat(ts) for link, ts in data.items()}
        except Exception:
            return {}

    def _save_seen_jobs(self):
        try:
            data = {link: dt.isoformat() for link, dt in self.seen_jobs.items()}
            with open(self.db_filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving {self.db_filename}: {e}")

    def _cleanup_old_buffer(self, max_age_hours: int = 168):
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=max_age_hours)
        self.seen_jobs = {
            link: seen_time
            for link, seen_time in self.seen_jobs.items()
            if seen_time > cutoff_time
        }

    def fetch_jobs(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        self._cleanup_old_buffer(max_age_hours=168)
        new_jobs = []

        try:
            response = requests.get(self.api_url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                print(f"[{self.source_name}] API call failed (Status {response.status_code})")
                return []

            data = response.json()
            job_postings = data.get("jobs", [])

            for job in job_postings:
                full_link = job.get("absolute_url")
                title = job.get("title", "Untitled Role")
                location_info = job.get("location", {})
                location_name = location_info.get("name", "Unspecified Location")

                if not full_link or full_link in self.seen_jobs:
                    continue

                self.seen_jobs[full_link] = now

                new_jobs.append({
                    "id": full_link,
                    "title": title,
                    "link": full_link,
                    "source": self.source_name,
                    "activity": "Active Posting",
                    "summary": f"Location: {location_name}"
                })

        except Exception as e:
            print(f"[{self.source_name}] Error fetching jobs: {e}")

        if new_jobs:
            self._save_seen_jobs()

        return new_jobs

class SoftgardenHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_a_tag = False
        self.current_href = ""
        self.current_text = ""
        self.jobs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            # Filter specifically for individual job posting detail links
            if "/job/" in href:
                self.in_a_tag = True
                self.current_href = href
                self.current_text = ""

    def handle_data(self, data):
        if self.in_a_tag:
            self.current_text += data

    def handle_endtag(self, tag):
        if tag == "a" and self.in_a_tag:
            title = self.current_text.strip()
            if title and self.current_href:
                self.jobs.append({
                    "title": title,
                    "link": self.current_href
                })
            self.in_a_tag = False
            self.current_href = ""
            self.current_text = ""


class SoftgardenScraper(BaseJobScraper):
    """Scraper for companies using Softgarden ATS via HTML Board Parsing."""
    def __init__(self, tenant_domain: str = "neura-mobile-robots", company_name: str = "NEURA Mobile Robots", db_filename: str = None):
        self.tenant_domain = tenant_domain
        self.company_name = company_name
        self.source_name = f"Softgarden ({company_name})"
        self.board_url = f"https://{self.tenant_domain}.softgarden.io/"
        self.db_filename = db_filename or f"seen_softgarden_{self.tenant_domain}_jobs.json"
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        
        self.seen_jobs = self._load_seen_jobs()

    def _load_seen_jobs(self) -> dict:
        if not os.path.exists(self.db_filename):
            return {}
        try:
            with open(self.db_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {link: datetime.fromisoformat(ts) for link, ts in data.items()}
        except Exception:
            return {}

    def _save_seen_jobs(self):
        try:
            data = {link: dt.isoformat() for link, dt in self.seen_jobs.items()}
            with open(self.db_filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving {self.db_filename}: {e}")

    def _cleanup_old_buffer(self, max_age_hours: int = 168):
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=max_age_hours)
        self.seen_jobs = {
            link: seen_time
            for link, seen_time in self.seen_jobs.items()
            if seen_time > cutoff_time
        }

    def fetch_jobs(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        self._cleanup_old_buffer(max_age_hours=168)
        new_jobs = []

        try:
            response = requests.get(self.board_url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                print(f"[{self.source_name}] HTML fetch failed (Status {response.status_code})")
                return []

            parser = SoftgardenHTMLParser()
            parser.feed(response.text)

            for job in parser.jobs:
                full_link = job["link"]
                # Resolve relative links if necessary
                if full_link.startswith("/"):
                    full_link = f"https://{self.tenant_domain}.softgarden.io{full_link}"

                title = job["title"]

                if not full_link or full_link in self.seen_jobs:
                    continue

                self.seen_jobs[full_link] = now

                new_jobs.append({
                    "id": full_link,
                    "title": title,
                    "link": full_link,
                    "source": self.source_name,
                    "activity": "Active Posting",
                    "summary": f"Job Posting: {title}"
                })

        except Exception as e:
            print(f"[{self.source_name}] Error fetching Softgarden board: {e}")

        if new_jobs:
            self._save_seen_jobs()

        return new_jobs

class AshbyScraper(BaseJobScraper):
    """Scraper for companies using Ashby ATS (e.g., Sensmore)."""

    def __init__(self, organization_slug: str = "sensmore", db_filename: str = None):
        self.organization_slug = organization_slug
        self.source_name = f"Ashby ({organization_slug.title()})"
        # Direct public GET URL endpoint
        self.api_url = f"https://api.ashbyhq.com/posting-api/job-board/{self.organization_slug}"
        self.db_filename = db_filename or f"seen_ashby_{organization_slug}_jobs.json"
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        
        self.seen_jobs = self._load_seen_jobs()

    def _load_seen_jobs(self) -> dict:
        if not os.path.exists(self.db_filename):
            with open(self.db_filename, "w", encoding="utf-8") as f:
                json.dump({}, f)
            return {}
        try:
            with open(self.db_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {link: datetime.fromisoformat(ts) for link, ts in data.items()}
        except Exception:
            return {}

    def _save_seen_jobs(self):
        try:
            data = {link: dt.isoformat() for link, dt in self.seen_jobs.items()}
            with open(self.db_filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving {self.db_filename}: {e}")

    def fetch_jobs(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        new_jobs = []

        try:
            # Use GET request directly on the public URL
            response = requests.get(
                self.api_url, 
                headers=self.headers, 
                timeout=10
            )

            if response.status_code != 200:
                print(f"[{self.source_name}] API Request failed ({response.status_code})")
                return []

            data = response.json()
            jobs = data.get("jobs", [])

            for job in jobs:
                job_id = job.get("id")
                title = job.get("title")
                
                # Full public application link
                link = job.get("jobUrl") or f"https://jobs.ashbyhq.com/{self.organization_slug}/{job_id}"
                
                department = job.get("department", "Unspecified")
                location = job.get("location", "Remote/Unspecified")
                employment_type = job.get("employmentType", "Full Time")

                if link in self.seen_jobs:
                    continue

                self.seen_jobs[link] = now

                new_jobs.append({
                    "id": link,
                    "title": title,
                    "link": link,
                    "source": self.source_name,
                    "activity": "Active Posting",
                    "summary": f"Dept: {department} | Location: {location} | Type: {employment_type}"
                })

        except Exception as e:
            print(f"[{self.source_name}] Error fetching jobs: {e}")

        if new_jobs:
            self._save_seen_jobs()

        return new_jobs