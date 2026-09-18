import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from .config import RAW_DATA_DIR, PROCESSED_DATA_DIR, REFERENCE_DATE, EXECUTIVE_NAME
from .models import ActionItem, SourceCitation, CalendarConflict, SourceStatus, OwnershipCategory, UrgencyStatus

SOURCE_MANIFEST = [
    {
        "id": "meeting_transcript",
        "title": "Executive Sales & Strategy Meeting Transcript",
        "channel": "Meeting Transcript",
        "rel_path": "transcripts/meeting_transcript.txt"
    },
    {
        "id": "arjun_calendar",
        "title": "Arjun Malhotra - Master Schedule",
        "channel": "Calendar",
        "rel_path": "calendars/arjun_calendar.json"
    },
    {
        "id": "other_calendars",
        "title": "Team & Stakeholder Calendars",
        "channel": "Calendar",
        "rel_path": "calendars/other_calendars.json"
    },
    {
        "id": "email_thread_1",
        "title": "Email Thread 1",
        "channel": "Email Thread",
        "rel_path": "emails/thread_1.txt"
    },
    {
        "id": "email_thread_2",
        "title": "Email Thread 2",
        "channel": "Email Thread",
        "rel_path": "emails/thread_2.txt"
    },
    {
        "id": "email_thread_3",
        "title": "Email Thread 3",
        "channel": "Email Thread",
        "rel_path": "emails/thread_3.txt"
    },
    {
        "id": "email_thread_4",
        "title": "Email Thread 4",
        "channel": "Email Thread",
        "rel_path": "emails/thread_4.txt"
    },
    {
        "id": "email_thread_5",
        "title": "Email Thread 5",
        "channel": "Email Thread",
        "rel_path": "emails/thread_5.txt"
    },
    {
        "id": "voice_note_1",
        "title": "Arjun's Voice Note 1",
        "channel": "Voice Note",
        "rel_path": "voice_notes/voice_note_1.txt"
    },
    {
        "id": "voice_note_2",
        "title": "Arjun's Voice Note 2",
        "channel": "Voice Note",
        "rel_path": "voice_notes/voice_note_2.txt"
    },
    {
        "id": "people_directory",
        "title": "People & Stakeholder Directory",
        "channel": "Directory",
        "rel_path": "directory/people.json"
    }
]

class DataStore:
    def __init__(self):
        self.raw_dir = RAW_DATA_DIR
        self.processed_dir = PROCESSED_DATA_DIR
        self.ensure_structure()

    def ensure_structure(self):
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        for entry in SOURCE_MANIFEST:
            file_path = self.raw_dir / entry["rel_path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if not file_path.exists():
                file_path.touch()

    def get_source_statuses(self) -> List[Dict[str, Any]]:
        results = []
        for entry in SOURCE_MANIFEST:
            file_path = self.raw_dir / entry["rel_path"]
            is_loaded = False
            char_count = 0
            preview = "Source data not loaded"

            if file_path.exists():
                content = file_path.read_text(encoding="utf-8", errors="ignore").strip()
                if len(content) > 0:
                    is_loaded = True
                    char_count = len(content)
                    preview = content[:200] + ("..." if len(content) > 200 else "")

            results.append({
                "id": entry["id"],
                "title": entry["title"],
                "channel": entry["channel"],
                "rel_path": entry["rel_path"],
                "is_loaded": is_loaded,
                "char_count": char_count,
                "preview": preview
            })
        return results

    def get_source_content(self, source_id: str) -> Optional[str]:
        for entry in SOURCE_MANIFEST:
            if entry["id"] == source_id:
                file_path = self.raw_dir / entry["rel_path"]
                if file_path.exists():
                    text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
                    return text if text else None
        return None

    def update_source_content(self, source_id: str, content: str) -> bool:
        for entry in SOURCE_MANIFEST:
            if entry["id"] == source_id:
                file_path = self.raw_dir / entry["rel_path"]
                file_path.write_text(content.strip(), encoding="utf-8")
                return True
        return False

    def load_actions(self) -> List[Dict[str, Any]]:
        actions_file = self.processed_dir / "actions.json"
        if actions_file.exists():
            try:
                with open(actions_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_actions(self, actions: List[Dict[str, Any]]):
        actions_file = self.processed_dir / "actions.json"
        with open(actions_file, "w", encoding="utf-8") as f:
            json.dump(actions, f, indent=2)

    def load_conflicts(self) -> List[Dict[str, Any]]:
        conflicts_file = self.processed_dir / "conflicts.json"
        if conflicts_file.exists():
            try:
                with open(conflicts_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_conflicts(self, conflicts: List[Dict[str, Any]]):
        conflicts_file = self.processed_dir / "conflicts.json"
        with open(conflicts_file, "w", encoding="utf-8") as f:
            json.dump(conflicts, f, indent=2)
