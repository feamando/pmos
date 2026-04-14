#!/usr/bin/env python3
"""
Meeting Prep Tool (v5.0)

Orchestrator for meeting preparation: fetches calendar events, classifies
meetings, gathers context, synthesizes pre-reads, manages series files,
uploads to Google Drive, and links pre-reads to Calendar events.

Port from v4.x meeting_prep.py (2,473 lines -> ~800 lines) via extraction of:
  - participant_context.py  (Brain lookups, domain detection)
  - agenda_generator.py     (prompt building, output cleaning)
  - llm_synthesizer.py      (LLM abstraction)
  - task_inference.py        (action-item completion inference)
  - series_intelligence.py   (series history analysis)

ZERO hardcoded values -- all from config.

Usage:
    python meeting_prep.py                    # Prep all meetings in next 24h
    python meeting_prep.py --hours 8          # Next 8 hours only
    python meeting_prep.py --meeting "1on1"   # Prep specific meeting by title
    python meeting_prep.py --list             # List upcoming meetings
    python meeting_prep.py --dry-run          # Show what would be generated
    python meeting_prep.py --cleanup          # Archive orphaned meeting preps
"""

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# v5 core imports
# ---------------------------------------------------------------------------

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from config_loader import get_config
    except ImportError:
        get_config = None

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.connector_bridge import get_auth
except ImportError:
    try:
        from connector_bridge import get_auth
    except ImportError:
        get_auth = None

try:
    from pm_os_base.tools.core.plugin_deps import check_plugin
except ImportError:
    try:
        from plugin_deps import check_plugin
    except ImportError:
        def check_plugin(name: str) -> bool:
            return False

# ---------------------------------------------------------------------------
# Sibling module imports
# ---------------------------------------------------------------------------

try:
    from meeting.participant_context import ParticipantContextResolver
except ImportError:
    from participant_context import ParticipantContextResolver

try:
    from meeting.agenda_generator import AgendaGenerator
except ImportError:
    from agenda_generator import AgendaGenerator

try:
    from meeting.llm_synthesizer import (
        SynthesisResult,
        TemplateSynthesizer,
        get_synthesizer,
    )
except ImportError:
    from llm_synthesizer import (
        SynthesisResult,
        TemplateSynthesizer,
        get_synthesizer,
    )

try:
    from meeting.task_inference import TaskCompletionInferrer
except ImportError:
    try:
        from task_inference import TaskCompletionInferrer
    except ImportError:
        TaskCompletionInferrer = None

try:
    from meeting.series_intelligence import SeriesIntelligence
except ImportError:
    try:
        from series_intelligence import SeriesIntelligence
    except ImportError:
        SeriesIntelligence = None


# ---------------------------------------------------------------------------
# Google API (accessed via connector_bridge in Claude sessions)
# ---------------------------------------------------------------------------

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.metadata",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")[:50]


def extract_names_from_title(title: str) -> List[str]:
    """Extract potential participant names from meeting title."""
    cleaned = re.sub(
        r"^\s*(1:1s?|sync|weekly|bi-weekly|meeting|call)[:\s]+",
        "", title, flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*(1:1s?|1on1|sync|weekly|bi-weekly|meeting|call).*$",
        "", cleaned, flags=re.IGNORECASE,
    )
    parts = re.split(r"[:/\-<> ]", cleaned)
    names = []
    for part in parts:
        part = part.strip()
        if len(part) >= 2 and not re.match(r"^\d+", part):
            names.append(part.title())
    return names


def _get_latest_context_file(context_dir: Path) -> Optional[str]:
    """Return latest daily-context file path."""
    pattern = str(context_dir / "*-context.md")
    files = glob(pattern)
    if not files:
        return None
    files.sort()
    return files[-1]


# ---------------------------------------------------------------------------
# Authentication (via connector_bridge for Claude sessions)
# ---------------------------------------------------------------------------


def get_credentials(config):
    """Get authenticated Google credentials using connector_bridge or OAuth."""
    if not GOOGLE_LIBS_AVAILABLE:
        raise ImportError(
            "Google API client libraries not installed. "
            "Install with: pip install google-api-python-client google-auth-oauthlib"
        )

    google_creds_path = config.get("google.credentials_file", "")
    google_token_path = config.get("google.token_file", "")

    creds = None
    if google_token_path and os.path.exists(google_token_path):
        try:
            creds = Credentials.from_authorized_user_file(google_token_path, SCOPES)
        except Exception:
            pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                if os.path.exists(google_token_path):
                    os.remove(google_token_path)
                return get_credentials(config)
        else:
            if not google_creds_path or not os.path.exists(google_creds_path):
                logger.error("Google credentials file not found at %s", google_creds_path)
                raise FileNotFoundError(
                    f"Google credentials not found at {google_creds_path}. "
                    "Configure google.credentials_file in config.yaml."
                )
            flow = InstalledAppFlow.from_client_secrets_file(google_creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        if google_token_path:
            os.makedirs(os.path.dirname(google_token_path), exist_ok=True)
            with open(google_token_path, "w") as token:
                token.write(creds.to_json())

    return creds


def get_calendar_service(creds=None, config=None):
    if not creds:
        creds = get_credentials(config)
    return build("calendar", "v3", credentials=creds)


def get_drive_service(creds=None, config=None):
    if not creds:
        creds = get_credentials(config)
    return build("drive", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Output path routing
# ---------------------------------------------------------------------------


def get_meeting_output_path(
    config, paths, meeting_type: str, attendees: list,
    meeting_summary: str = None,
) -> Path:
    """
    Determine the correct output path for a meeting prep file.

    Routing:
      1. 1:1 with direct report  -> /team/reports/{person}/1on1s/
      2. 1:1 with manager        -> /team/manager/{person}/1on1s/
      3. 1:1 with stakeholder    -> /team/stakeholders/{person}/1on1s/
      4. Product-related meeting  -> /products/{product}/discussions/
      5. Default                  -> config output_dir or planning/Meeting_Prep/
    """
    user_dir = paths.user
    default_output = Path(
        config.get(
            "meeting_prep.output_dir",
            str(user_dir / "planning" / "Meeting_Prep"),
        )
    )

    user_email = config.get("user.email", "").lower()
    if not user_email:
        return default_output

    other_attendees = [a.lower() for a in attendees if a.lower() != user_email]

    if meeting_type == "1on1" and len(other_attendees) == 1:
        other_email = other_attendees[0]

        # Check reports
        reports = config.get("team.reports", [])
        for report in reports:
            if isinstance(report, dict) and report.get("email", "").lower() == other_email:
                report_path = user_dir / "team" / "reports" / report.get("id", "") / "1on1s"
                if report_path.exists():
                    return report_path

        # Check manager
        manager = config.get("team.manager", {})
        if isinstance(manager, dict) and manager.get("email", "").lower() == other_email:
            mgr_path = user_dir / "team" / "manager" / manager.get("id", "") / "1on1s"
            if mgr_path.exists():
                return mgr_path

        # Check stakeholders
        stakeholders = config.get("team.stakeholders", [])
        for sh in stakeholders:
            if isinstance(sh, dict) and sh.get("email", "").lower() == other_email:
                sh_path = user_dir / "team" / "stakeholders" / sh.get("id", "") / "1on1s"
                if sh_path.exists():
                    return sh_path

    # Product routing
    if meeting_summary:
        summary_lower = meeting_summary.lower()
        products = config.get("products.items", [])
        org_id = config.get("organization.id", "")
        for product in products:
            if not isinstance(product, dict):
                continue
            product_name = product.get("name", "").lower()
            product_id = product.get("id", "")
            if product_name and product_name in summary_lower:
                if org_id:
                    p_path = user_dir / "products" / org_id / product_id / "discussions"
                else:
                    p_path = user_dir / "products" / product_id / "discussions"
                if p_path.exists():
                    return p_path

    return default_output


# ---------------------------------------------------------------------------
# Meeting Manager
# ---------------------------------------------------------------------------


class MeetingManager:
    """Orchestrates meeting preparation: classify, context, synthesize, publish."""

    def __init__(
        self,
        config,
        paths,
        drive_service,
        calendar_service,
        quick_mode: bool = False,
    ):
        self.config = config
        self.paths = paths
        self.drive = drive_service
        self.calendar = calendar_service
        self.quick_mode = quick_mode

        # Extracted modules
        self.participant_resolver = ParticipantContextResolver(config, paths)
        self.agenda_gen = AgendaGenerator(config)

        # Config-driven folder name
        self._drive_folder_name = config.get(
            "meeting_prep.drive_folder", "Meeting Pre-Reads"
        )
        self.prep_folder_id = self._get_or_create_drive_folder(self._drive_folder_name)

        # Output directories (config-driven)
        user_dir = paths.user
        base_output = Path(
            config.get(
                "meeting_prep.output_dir",
                str(user_dir / "planning" / "Meeting_Prep"),
            )
        )
        self.output_dir = base_output
        self.series_dir = base_output / "Series"
        self.adhoc_dir = base_output / "AdHoc"
        self.archive_dir = base_output / "Archive"
        self.cache_dir = base_output / ".cache"

        # Thread locks for API writes
        self._drive_write_lock = threading.Lock()
        self._calendar_write_lock = threading.Lock()

        # Ensure directories
        for d in (self.series_dir, self.adhoc_dir, self.archive_dir, self.cache_dir):
            d.mkdir(parents=True, exist_ok=True)

    # -- Existing prep detection ---------------------------------------------

    def has_existing_prep(self, event: dict) -> bool:
        """Check if meeting prep already exists (filesystem only, no API calls)."""
        start_raw = event.get("start", {}).get("dateTime", "")
        if not start_raw:
            return False
        try:
            start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            date_str = start_dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return False

        slug = slugify(event.get("summary", ""))
        if not slug:
            return False

        if bool(event.get("recurringEventId")):
            filepath = self.series_dir / f"Series-{slug}.md"
            if not filepath.exists():
                return False
            try:
                content = filepath.read_text(encoding="utf-8")
                return f"[{date_str}] Upcoming Meeting" in content
            except OSError:
                return False
        else:
            filepath = self.adhoc_dir / f"Meeting-{date_str}-{slug}.md"
            return filepath.exists()

    # -- Classification ------------------------------------------------------

    def classify_meeting(self, event: Dict) -> Dict:
        """Classify meeting type and extract metadata."""
        summary = event.get("summary", "").lower()
        description = event.get("description", "") or ""
        attendees = event.get("attendees", [])
        recurrence_id = event.get("recurringEventId")

        title_names = extract_names_from_title(event.get("summary", ""))
        user_name = self.config.get("user.name", "").split()[0].lower()
        other_person_name = next(
            (tn for tn in title_names if tn.lower() != user_name), None
        )

        # Classify attendees via participant_resolver
        participants, external_count = self.participant_resolver.classify_attendees(
            attendees
        )

        # Override displayName from title if only 1 external and no name
        if len(participants) == 1 and not participants[0].get("displayName"):
            if other_person_name:
                participants[0]["name"] = other_person_name

        # Meeting type classification
        meeting_type = "other"
        interview_keywords = self.config.get(
            "meeting_prep.interview_keywords", ["virtual interview"]
        )
        if any(kw in summary for kw in interview_keywords):
            meeting_type = "interview"
        elif len(participants) == 1:
            meeting_type = "1on1"
        elif external_count > 0:
            meeting_type = "external"
        elif any(w in summary for w in ("standup", "sync", "daily")):
            meeting_type = "standup"
        elif any(w in summary for w in ("review", "retro", "demo")):
            meeting_type = "review"
        elif any(w in summary for w in ("planning", "sprint", "grooming")):
            meeting_type = "planning"
        elif len(participants) > 5:
            meeting_type = "large_meeting"

        is_series = bool(recurrence_id)
        recurrence_frequency = (
            self._get_recurrence_frequency(event) if is_series else None
        )
        prep_depth = (
            self._get_prep_depth(meeting_type, recurrence_frequency, len(participants))
            if is_series
            else "standard"
        )

        # Topic extraction
        topics: List[str] = []
        topic_patterns = [
            r"(?:discuss|review|update on|status of|planning for)\s+(.+?)(?:\s*[-|,]|$)",
            r"(?:re:|regarding:?)\s*(.+?)(?:\s*[-|,]|$)",
        ]
        combined = f"{summary} {description}"
        for pattern in topic_patterns:
            topics.extend(re.findall(pattern, combined, re.IGNORECASE))
        if not any(g in summary for g in ("1:1", "sync", "meeting")):
            topics.insert(0, event.get("summary", ""))

        return {
            "meeting_type": meeting_type,
            "is_series": is_series,
            "series_id": recurrence_id,
            "recurrence_frequency": recurrence_frequency,
            "prep_depth": prep_depth,
            "participants": participants,
            "topics": list(set(topics))[:5],
            "summary": event.get("summary", "Untitled"),
            "description": description,
            "start": event.get("start", {}).get("dateTime", ""),
            "event_id": event.get("id", ""),
            "html_link": event.get("htmlLink", ""),
        }

    def _get_recurrence_frequency(self, event: Dict) -> str:
        recurrence = event.get("recurrence", [])
        if recurrence:
            for rule in recurrence:
                rule_upper = rule.upper()
                if "DAILY" in rule_upper:
                    return "daily"
                elif "WEEKLY" in rule_upper:
                    return "biweekly" if "INTERVAL=2" in rule_upper else "weekly"
                elif "MONTHLY" in rule_upper:
                    return "quarterly" if "INTERVAL=3" in rule_upper else "monthly"
                elif "YEARLY" in rule_upper:
                    return "yearly"

        summary = event.get("summary", "").lower()
        freq_map = {
            "daily": ("daily", "standup", "stand-up"),
            "weekly": ("weekly", "week"),
            "biweekly": ("biweekly", "bi-weekly", "fortnightly"),
            "monthly": ("monthly", "month"),
            "quarterly": ("quarterly", "quarter"),
        }
        for freq, keywords in freq_map.items():
            if any(w in summary for w in keywords):
                return freq
        return "unknown"

    def _get_prep_depth(
        self, meeting_type: str, frequency: str, participant_count: int
    ) -> str:
        if self.quick_mode:
            return "quick"
        if frequency == "daily" or meeting_type == "standup":
            return "minimal"
        if meeting_type == "1on1" and frequency in ("weekly", "biweekly"):
            return "quick"
        if meeting_type == "large_meeting" or participant_count > 5:
            return "quick"
        if meeting_type == "interview":
            return "detailed"
        if meeting_type == "external":
            return "detailed"
        return "standard"

    # -- Context gathering ---------------------------------------------------

    def gather_context(self, classified: Dict, with_jira: bool = False) -> Dict:
        """Gather context from Brain, Daily Context, GDrive, Series History."""
        context: Dict[str, Any] = {
            "participant_context": [],
            "topic_context": [],
            "action_items": [],
            "context_summary": "",
            "past_notes": "",
            "series_history": [],
            "jira_issues": [],
        }

        participant_names = [p["name"] for p in classified["participants"]]

        # Brain context (via extracted participant_context module)
        context["participant_context"] = self.participant_resolver.resolve_participants(
            classified["participants"]
        )

        # Related projects
        context["topic_context"] = self.participant_resolver.get_related_projects(
            participant_names
        )

        # Action items from daily context
        context["action_items"] = self._extract_action_items_for_participants(
            participant_names
        )

        # Enrich with task inference
        if (
            context["action_items"]
            and TaskCompletionInferrer is not None
            and self.config.get("meeting_prep.task_inference.enabled", True)
        ):
            try:
                inferrer = TaskCompletionInferrer.from_config(
                    config=self.config, paths=self.paths
                )
                context["action_items"] = inferrer.enrich_items(context["action_items"])
                logger.info(
                    "Enriched %d action items with completion inference",
                    len(context["action_items"]),
                )
            except Exception as exc:
                logger.warning("Task inference error: %s", exc)

        # Daily context key decisions
        context_dir = self.paths.user / "context"
        ctx_file = _get_latest_context_file(context_dir)
        if ctx_file:
            try:
                with open(ctx_file, "r", encoding="utf-8") as f:
                    content = f.read()
                match = re.search(
                    r"##\s*(?:Key Decisions|Decisions)[^\n]*\n(.*?)(?=\n##|\Z)",
                    content, re.DOTALL | re.IGNORECASE,
                )
                if match:
                    context["context_summary"] = match.group(1)[:1500]
            except OSError as exc:
                logger.warning("Error reading context file: %s", exc)

        # Past notes from GDrive
        self._gather_past_notes(classified, context)

        # Series history + intelligence
        if classified["is_series"]:
            slug = slugify(classified["summary"])
            context["series_history"] = self._get_series_history(slug, max_entries=10)
            if context["series_history"] and SeriesIntelligence is not None:
                try:
                    si = SeriesIntelligence()
                    outcomes = si.extract_outcomes(context["series_history"])
                    context["series_intelligence"] = {
                        "summary": si.synthesize_history(outcomes),
                        "open_commitments": [
                            {
                                "owner": c.owner, "description": c.description,
                                "date": c.source_date, "status": c.status,
                            }
                            for c in si.get_open_commitments(outcomes)
                        ],
                        "recurring_topics": si.get_recurring_topics(outcomes, min_count=2),
                        "unresolved_questions": si.get_unresolved_questions(outcomes),
                        "recent_decisions": si.get_recent_decisions(outcomes, limit=5),
                    }
                    logger.info(
                        "Series Intelligence: %d open commitments, %d recurring topics",
                        len(context["series_intelligence"]["open_commitments"]),
                        len(context["series_intelligence"]["recurring_topics"]),
                    )
                except Exception as exc:
                    logger.warning("Series Intelligence error: %s", exc)
                    context["series_intelligence"] = None

        return context

    def _extract_action_items_for_participants(
        self, participant_names: List[str]
    ) -> List[Dict]:
        """Extract action items from daily context mentioning participants."""
        context_dir = self.paths.user / "context"
        ctx_file = _get_latest_context_file(context_dir)
        if not ctx_file:
            return []
        try:
            with open(ctx_file, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return []

        action_section = re.search(
            r"## Action Items.*?\n(.*?)(?=\n---|\Z)", content, re.DOTALL
        )
        if not action_section:
            return []

        items: List[Dict] = []
        pattern = r"- \[([x ])\] \*\*([^*]+)\*\*:?\s*(.+?)(?=\n- \[|\n###|\Z)"
        for match in re.finditer(pattern, action_section.group(1), re.DOTALL):
            completed = match.group(1) == "x"
            owner = match.group(2).strip()
            task = match.group(3).strip().replace("\n", " ")
            for pname in participant_names:
                pname_parts = pname.lower().split()
                owner_lower = owner.lower()
                if any(part in owner_lower for part in pname_parts) or any(
                    part in pname.lower() for part in owner_lower.split()
                ):
                    items.append(
                        {"owner": owner, "task": task[:200], "completed": completed}
                    )
                    break
        return items

    def _gather_past_notes(self, classified: Dict, context: Dict):
        """Fetch past meeting notes from GDrive based on meeting type."""
        meeting_type = classified["meeting_type"]

        if meeting_type == "interview":
            # Load frameworks from config paths
            frameworks_dir = self.config.get(
                "meeting_prep.frameworks_dir",
                str(self.paths.user / "context" / "Frameworks"),
            )
            for key, filename in [
                ("career_framework", "Product_Career_Framework.md"),
                ("company_dna", "Company_DNA.md"),
            ]:
                fpath = os.path.join(frameworks_dir, filename)
                if os.path.exists(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            context[key] = f.read()
                    except OSError:
                        pass

            # Find similar interviews
            parts = classified["summary"].split("|")
            role = parts[-1].strip() if len(parts) > 1 else classified["summary"]
            role = re.sub(r"\[.*?\]", "", role).strip()
            logger.info("Searching for past interviews for role: %s", role)
            context["past_notes"] = self._find_similar_interviews(role)

        elif meeting_type in ("1on1", "standup", "review", "planning", "external"):
            notes_file = self._search_gdrive_notes_enhanced(
                classified["summary"], classified["participants"]
            )
            if notes_file:
                logger.info("Found past notes: %s", notes_file.get("name", ""))
                content = self._read_gdrive_file(notes_file["id"])
                context["past_notes"] = content[:2500]

    # -- Synthesis -----------------------------------------------------------

    def synthesize_content(self, classified: Dict, context: Dict) -> str:
        """Synthesize pre-read content using LLM or template."""
        meeting_type = classified["meeting_type"]
        participant_count = len(classified.get("participants", []))

        # Skip LLM for low-value meetings
        skip_llm = meeting_type == "standup" or (
            meeting_type == "large_meeting" and participant_count >= 8
        )
        if skip_llm:
            logger.info(
                "Template-only for %s (%d participants)",
                meeting_type, participant_count,
            )
            synthesizer = TemplateSynthesizer()
            prompt = self.agenda_gen.build_synthesis_prompt(classified, context)
            result = synthesizer.synthesize(prompt, context)
            content = self.agenda_gen.clean_output(result.content)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            return f"*Automatically generated by {result.model_id} on {timestamp}*\n\n{content}"

        prompt = self.agenda_gen.build_synthesis_prompt(classified, context)
        synthesizer = get_synthesizer(config=self.config)
        result = synthesizer.synthesize(prompt, context)

        if not result.success:
            logger.warning("Synthesis error (%s): %s", result.model_id, result.error)
            content = f"## Pre-Read: {classified['summary']}\n*Template fallback*\n"
            model_id = "Template"
        else:
            content = self.agenda_gen.clean_output(result.content)
            model_id = result.model_id

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"*Automatically generated by {model_id} on {timestamp}*\n\n{content}"

    # -- Cache ---------------------------------------------------------------

    def _compute_context_hash(self, classified: Dict, context: Dict) -> str:
        hash_input = {
            "meeting_type": classified["meeting_type"],
            "participants": sorted(
                p.get("email", "") for p in classified.get("participants", [])
            ),
            "action_items_hash": hashlib.md5(
                json.dumps(
                    context.get("action_items", []), sort_keys=True, default=str
                ).encode()
            ).hexdigest(),
            "context_summary": str(context.get("context_summary", ""))[:500],
            "series_intelligence": str(context.get("series_intelligence", ""))[:500],
        }
        return hashlib.sha256(
            json.dumps(hash_input, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

    def _get_cache_path(self, classified: Dict) -> Path:
        start_raw = classified.get("start", "")
        try:
            start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            date_str = start_dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date_str = datetime.now().strftime("%Y-%m-%d")
        slug = slugify(classified.get("summary", ""))
        return self.cache_dir / f"{date_str}-{slug}.json"

    def _check_cache(self, classified: Dict, context: Dict) -> Optional[str]:
        cache_path = self._get_cache_path(classified)
        if not cache_path.exists():
            return None
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            current_hash = self._compute_context_hash(classified, context)
            if cached.get("context_hash") == current_hash:
                logger.info("Cache hit: %s", classified.get("summary", "Unknown"))
                return cached["content"]
            logger.info("Cache stale: %s", classified.get("summary", "Unknown"))
            return None
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def _write_cache(self, classified: Dict, context: Dict, content: str):
        cache_path = self._get_cache_path(classified)
        try:
            cache_data = {
                "context_hash": self._compute_context_hash(classified, context),
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "meeting_type": classified["meeting_type"],
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f)
        except OSError as exc:
            logger.warning("Cache write error: %s", exc)

    # -- File generation / upload --------------------------------------------

    def generate_file(self, classified: Dict, content: str) -> str:
        """Generate/update file based on meeting type (Series vs AdHoc)."""
        start_dt = datetime.fromisoformat(classified["start"].replace("Z", "+00:00"))
        date_str = start_dt.strftime("%Y-%m-%d")
        slug = slugify(classified["summary"])

        if classified["is_series"]:
            filename = f"Series-{slug}.md"
            filepath = self.series_dir / filename
            new_entry = f"\n## [{date_str}] Upcoming Meeting\n\n{content}\n\n---\n"

            if filepath.exists():
                existing = filepath.read_text(encoding="utf-8")
                if f"[{date_str}] Upcoming Meeting" in existing:
                    logger.info("Entry for %s already exists in %s", date_str, filename)
                    return str(filepath)
                if existing.startswith("# Meeting Series"):
                    parts = existing.split("\n", 1)
                    final = parts[0] + "\n" + new_entry + parts[1]
                else:
                    final = (
                        f"# Meeting Series: {classified['summary']}\n\n"
                        f"{new_entry}\n{existing}"
                    )
            else:
                final = (
                    f"# Meeting Series: {classified['summary']}\n"
                    f"**Cadence:** Recurring\n\n{new_entry}"
                )

            filepath.write_text(final, encoding="utf-8")
        else:
            filename = f"Meeting-{date_str}-{slug}.md"
            filepath = self.adhoc_dir / filename
            filepath.write_text(content, encoding="utf-8")

        return str(filepath)

    def upload_to_drive(self, filepath: str) -> str:
        """Upload file to GDrive and return WebViewLink."""
        with self._drive_write_lock:
            filename = os.path.basename(filepath)
            query = (
                f"name = '{filename}' and '{self.prep_folder_id}' in parents "
                f"and trashed = false"
            )
            results = (
                self.drive.files()
                .list(q=query, fields="files(id, webViewLink)")
                .execute()
            )
            files = results.get("files", [])
            media = MediaFileUpload(filepath, mimetype="text/markdown")

            if files:
                file_id = files[0]["id"]
                try:
                    self.drive.files().update(
                        fileId=file_id, media_body=media
                    ).execute()
                    self._set_permissions(file_id)
                    return files[0]["webViewLink"]
                except HttpError as exc:
                    if exc.resp.status == 403 and "appNotAuthorizedToFile" in str(exc):
                        logger.warning("Cannot update existing Drive file; creating new")
                    else:
                        raise

            file_metadata = {
                "name": filename,
                "parents": [self.prep_folder_id],
                "mimeType": "text/markdown",
            }
            file = (
                self.drive.files()
                .create(body=file_metadata, media_body=media, fields="id, webViewLink")
                .execute()
            )
            file_id = file.get("id")
            self._set_permissions(file_id)
            return file.get("webViewLink")

    def link_to_calendar(self, event_id: str, link: str):
        """Append pre-read link to calendar event description."""
        with self._calendar_write_lock:
            event = (
                self.calendar.events()
                .get(calendarId="primary", eventId=event_id)
                .execute()
            )
            description = event.get("description", "")
            if link in description:
                return
            new_desc = (
                f"{description}\n\n<b>AI Pre-Read:</b> <a href='{link}'>{link}</a>"
            )
            self.calendar.events().patch(
                calendarId="primary",
                eventId=event_id,
                body={"description": new_desc},
            ).execute()
            logger.info("Linked pre-read to calendar event")

    def archive_file(self, filepath: str, reason: str = "cancelled") -> str:
        if not os.path.exists(filepath):
            return ""
        filename = os.path.basename(filepath)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        archived_name = f"{timestamp}-{reason}-{filename}"
        archive_path = str(self.archive_dir / archived_name)
        shutil.move(filepath, archive_path)
        logger.info("Archived: %s -> %s", filename, archived_name)
        return archive_path

    def cleanup_orphaned_preps(self, dry_run: bool = False) -> Dict[str, List[str]]:
        """Scan for meeting prep files without corresponding calendar events."""
        results: Dict[str, List[str]] = {"archived": [], "updated": [], "kept": []}

        logger.info("Fetching upcoming calendar events for cleanup...")
        event_lookup = self._get_upcoming_event_summaries(days_ahead=60)
        by_slug = event_lookup["by_slug"]

        # AdHoc files
        adhoc_files = glob(str(self.adhoc_dir / "Meeting-*.md"))
        for filepath in adhoc_files:
            filename = os.path.basename(filepath)
            match = re.match(r"Meeting-\d{4}-\d{2}-\d{2}-(.+)\.md", filename)
            if not match:
                continue
            slug = match.group(1)
            if slug in by_slug:
                results["kept"].append(filepath)
            else:
                logger.info("Archiving orphaned adhoc: %s", filename)
                if not dry_run:
                    self.archive_file(filepath, reason="cancelled")
                results["archived"].append(filepath)

        # Series files
        series_files = glob(str(self.series_dir / "Series-*.md"))
        for filepath in series_files:
            filename = os.path.basename(filepath)
            match = re.match(r"Series-(.+)\.md", filename)
            if not match:
                continue
            slug = match.group(1)
            if slug in by_slug:
                results["kept"].append(filepath)
            else:
                logger.info("Archiving ended series: %s", filename)
                if not dry_run:
                    self.archive_file(filepath, reason="series-ended")
                results["archived"].append(filepath)

        return results

    # -- Private GDrive helpers ----------------------------------------------

    def _get_or_create_drive_folder(self, folder_name: str) -> str:
        query = (
            f"name = '{folder_name}' and "
            f"mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        results = (
            self.drive.files().list(q=query, fields="files(id, name)").execute()
        )
        files = results.get("files", [])
        if files:
            return files[0]["id"]
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        file = (
            self.drive.files()
            .create(body=file_metadata, fields="id")
            .execute()
        )
        return file.get("id")

    def _read_gdrive_file(self, file_id: str) -> str:
        try:
            content = (
                self.drive.files()
                .export(fileId=file_id, mimeType="text/plain")
                .execute()
            )
            return content.decode("utf-8") if isinstance(content, bytes) else content
        except Exception as exc:
            logger.warning("GDrive read error: %s", exc)
            return ""

    def _search_gdrive_notes_enhanced(
        self, meeting_title: str, participants: List[Dict]
    ) -> Optional[Dict]:
        searches: List[str] = []
        cleaned = re.sub(
            r"\s*(1:1s?|sync|weekly|meeting)\s*",
            "", meeting_title, flags=re.IGNORECASE,
        ).strip()
        if cleaned:
            searches.append(cleaned.replace(":", " ").replace("/", " "))

        user_name = self.config.get("user.name", "").split()[0]
        for p in participants:
            name = p["name"].split()[0] if p["name"] else ""
            if name and len(name) > 2:
                searches.append(f"{name} 1:1")
                if user_name:
                    searches.append(f"{name} {user_name}")

        for query_text in searches:
            if not query_text or len(query_text) < 3:
                continue
            query = (
                f"name contains '{query_text}' "
                f"and mimeType = 'application/vnd.google-apps.document' "
                f"and trashed = false"
            )
            try:
                results = (
                    self.drive.files()
                    .list(
                        q=query, orderBy="modifiedTime desc",
                        pageSize=5, fields="files(id, name, modifiedTime)",
                    )
                    .execute()
                )
                files = results.get("files", [])
                if files:
                    return files[0]
            except Exception as exc:
                logger.warning("GDrive search '%s' error: %s", query_text, exc)
        return None

    def _find_similar_interviews(self, role_name: str) -> str:
        query = (
            f"name contains 'Interview' and name contains '{role_name}' "
            f"and mimeType = 'application/vnd.google-apps.document' "
            f"and trashed = false"
        )
        try:
            results = (
                self.drive.files()
                .list(
                    q=query, orderBy="createdTime desc",
                    pageSize=3, fields="files(id, name)",
                )
                .execute()
            )
            files = results.get("files", [])
            content = ""
            for f in files:
                text = self._read_gdrive_file(f["id"])
                content += f"### Past Interview: {f['name']}\n{text[:1000]}...\n\n"
            return content
        except Exception as exc:
            logger.warning("Error searching similar interviews: %s", exc)
            return ""

    def _get_series_history(
        self, series_slug: str, max_entries: int = 3
    ) -> List[Dict]:
        filepath = self.series_dir / f"Series-{series_slug}.md"
        if not filepath.exists():
            return []
        try:
            content = filepath.read_text(encoding="utf-8")
        except OSError:
            return []

        pattern = r"## \[(\d{4}-\d{2}-\d{2})\][^\n]*\n(.*?)(?=## \[|\Z)"
        matches = list(re.finditer(pattern, content, re.DOTALL))
        history: List[Dict] = []
        for match in matches:
            if "Upcoming Meeting" in match.group(0):
                continue
            date = match.group(1)
            entry_content = match.group(2)
            key_points = re.findall(
                r"^\s*[-*]\s+(.+)$", entry_content, re.MULTILINE
            )[:5]
            history.append(
                {"date": date, "summary": entry_content[:600], "key_points": key_points}
            )
            if len(history) >= max_entries:
                break
        return history

    def _get_upcoming_event_summaries(self, days_ahead: int = 30) -> Dict:
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)
        events_result = (
            self.calendar.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=200,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        by_slug: Dict[str, List] = {}
        for event in events_result.get("items", []):
            attendees = event.get("attendees", [])
            declined = any(
                a.get("self") and a.get("responseStatus") == "declined"
                for a in attendees
            )
            if declined or event.get("status") == "cancelled":
                continue
            slug = slugify(event.get("summary", ""))
            if slug not in by_slug:
                by_slug[slug] = []
            by_slug[slug].append(event)
        return {"by_slug": by_slug}

    def _set_permissions(self, file_id: str):
        """Set Drive file permissions from config."""
        share_domain = self.config.get("meeting_prep.share_domain", "")
        if not share_domain:
            return
        try:
            permission = {
                "type": "domain",
                "role": "writer",
                "domain": share_domain,
            }
            self.drive.permissions().create(
                fileId=file_id, body=permission, fields="id"
            ).execute()
            logger.info("Permissions set: Edit access for %s", share_domain)
        except Exception as exc:
            logger.warning("Could not set permissions: %s", exc)

    def fetch_events(self, hours: int = 24) -> List[Dict]:
        """Fetch upcoming calendar events."""
        now = datetime.now(timezone.utc)
        time_max = now + timedelta(hours=hours)
        events_result = (
            self.calendar.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=50,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        filtered: List[Dict] = []
        for event in events_result.get("items", []):
            attendees = event.get("attendees", [])
            if any(
                a.get("self") and a.get("responseStatus") == "declined"
                for a in attendees
            ):
                continue
            if "dateTime" not in event.get("start", {}):
                continue
            other_attendees = [
                a for a in attendees
                if not a.get("self")
                and "resource.calendar.google.com" not in a.get("email", "")
            ]
            if not other_attendees:
                continue
            filtered.append(event)
        return filtered


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------


def _process_single_meeting(
    manager: MeetingManager,
    event: dict,
    with_jira: bool,
    upload: bool,
    dry_run: bool,
    force: bool = False,
) -> dict:
    """Process a single meeting. Returns result dict."""
    summary = event.get("summary", "Untitled")
    try:
        if not dry_run and not force and manager.has_existing_prep(event):
            return {"summary": summary, "success": True, "skipped": True}

        classified = manager.classify_meeting(event)
        context = manager.gather_context(classified, with_jira=with_jira)

        if dry_run:
            preview = manager.synthesize_content(classified, context)[:200]
            return {"summary": summary, "success": True, "dry_run": True, "preview": preview}

        cached_content = None
        if not force:
            cached_content = manager._check_cache(classified, context)

        content = cached_content or manager.synthesize_content(classified, context)
        if not cached_content:
            manager._write_cache(classified, context, content)

        filepath = manager.generate_file(classified, content)

        link = None
        if upload:
            link = manager.upload_to_drive(filepath)
            manager.link_to_calendar(classified["event_id"], link)

        return {
            "summary": summary, "success": True, "filepath": filepath,
            "link": link, "cached": cached_content is not None,
        }
    except Exception as exc:
        logger.error("Failed to process %s: %s", summary, exc)
        return {"summary": summary, "success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Meeting Prep Tool (v5.0)")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--meeting", type=str)
    parser.add_argument("--list", action="store_true", help="List upcoming meetings")
    parser.add_argument("--upload", action="store_true", help="Upload to Drive")
    parser.add_argument("--cleanup", action="store_true", help="Archive orphaned preps")
    parser.add_argument("--with-jira", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Minimal prep depth")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Force re-processing")
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Load config + paths
    config = get_config() if get_config else None
    paths = get_paths() if get_paths else None
    if not config or not paths:
        logger.error("Cannot load PM-OS config or paths")
        return

    is_quick = args.quick or config.get("meeting_prep.default_depth") == "quick"
    if args.workers is None:
        args.workers = config.get("meeting_prep.workers", 5)

    logger.info("Authenticating...")
    creds = get_credentials(config)
    drive_service = get_drive_service(creds)
    calendar_service = get_calendar_service(creds)

    manager = MeetingManager(
        config=config, paths=paths,
        drive_service=drive_service,
        calendar_service=calendar_service,
        quick_mode=is_quick,
    )

    logger.info("Fetching meetings (next %dh)...", args.hours)
    events = manager.fetch_events(args.hours)

    if args.meeting:
        events = [
            e for e in events if args.meeting.lower() in e.get("summary", "").lower()
        ]

    if args.cleanup:
        results = manager.cleanup_orphaned_preps(dry_run=args.dry_run)
        tag = " (DRY RUN)" if args.dry_run else ""
        logger.info(
            "Cleanup%s: %d archived, %d updated, %d kept",
            tag, len(results["archived"]), len(results["updated"]), len(results["kept"]),
        )
        return

    if args.list:
        print(f"\n## Upcoming Meetings (Next {args.hours}h)\n")
        for event in events:
            start = event.get("start", {}).get("dateTime", "TBD")
            if start and "T" in start:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                start = dt.strftime("%Y-%m-%d %H:%M")
            print(f"- **{start}** | {event.get('summary', 'Untitled')}")
        return

    if not events:
        logger.info("No meetings found.")
        return

    workers = min(args.workers, len(events))
    logger.info("Processing %d meetings with %d worker(s)...", len(events), workers)

    results = []
    if workers <= 1:
        for event in events:
            result = _process_single_meeting(
                manager, event, args.with_jira, args.upload, args.dry_run, args.force
            )
            results.append(result)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _process_single_meeting,
                    manager, event, args.with_jira, args.upload, args.dry_run, args.force,
                ): event
                for event in events
            }
            for future in as_completed(futures):
                results.append(future.result())

    skipped = sum(1 for r in results if r.get("skipped"))
    cached = sum(1 for r in results if r.get("cached"))
    succeeded = sum(1 for r in results if r["success"] and not r.get("skipped"))
    failed = sum(1 for r in results if not r["success"])
    cache_note = f", {cached} cached" if cached else ""
    logger.info(
        "Summary: %d succeeded%s, %d failed, %d skipped",
        succeeded, cache_note, failed, skipped,
    )
    for r in results:
        if not r["success"]:
            logger.error("FAILED: %s -- %s", r["summary"], r.get("error", "unknown"))


if __name__ == "__main__":
    main()
