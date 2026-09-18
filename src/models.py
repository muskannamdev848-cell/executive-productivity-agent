from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any

class SourceChannel(str, Enum):
    MEETING_TRANSCRIPT = "Meeting Transcript"
    EMAIL_THREAD = "Email Thread"
    CALENDAR = "Calendar"
    VOICE_NOTE = "Voice Note"

class OwnershipCategory(str, Enum):
    MY_ACTION = "My Action"                   # Explicitly owned by Arjun Malhotra
    WAITING_ON_OTHERS = "Waiting on Others"   # Owned by counterparty / colleague
    UNCLEAR_OWNERSHIP = "Unclear Ownership"   # Ambiguous or no explicit owner in text (FLAGGED)

class UrgencyStatus(str, Enum):
    OVERDUE = "Overdue"                       # Deadline earlier than reference date
    DUE_TODAY = "Due Today"                   # Deadline on reference date
    UPCOMING = "Upcoming"                     # Deadline in future
    NO_DEADLINE = "No Deadline Specified"     # No explicit deadline in source

@dataclass
class SourceCitation:
    channel: str                              # Meeting Transcript, Email Thread, Calendar, Voice Note
    source_id: str                            # e.g. "Email Thread 3", "Voice Note 1"
    timestamp_or_date: str                    # Explicit date/time from source
    author_or_speaker: Optional[str] = None   # Speaker or email sender
    verbatim_quote: str = ""                  # Exact quote supporting this item
    context: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ActionItem:
    id: str                                   # Unique identifier / hash
    task: str                                 # Clear imperative description
    owner: Optional[str]                      # Arjun Malhotra, named person, or None
    ownership_category: str                   # My Action, Waiting on Others, Unclear Ownership
    counterparty: Optional[str] = None        # Stakeholder promised to or blocked by
    raw_deadline: Optional[str] = None        # Exact verbatim phrase ("by EOD today", "Friday 5 PM")
    normalized_deadline: Optional[str] = None # ISO format "YYYY-MM-DD"
    urgency_status: str = UrgencyStatus.NO_DEADLINE.value
    priority: str = "Medium"                  # High, Medium, Low
    status: str = "Pending"                   # Pending, In Progress, Completed, Needs Clarification
    sources: List[SourceCitation] = field(default_factory=list)
    conflict_notes: Optional[str] = None      # Conflict explanation across sources
    flagged_unclear: bool = False             # Flagged if ownership or deadline lacks clarity

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["sources"] = [s.to_dict() if hasattr(s, "to_dict") else s for s in self.sources]
        return data

@dataclass
class CalendarConflict:
    id: str
    event_title: str
    start_time: str
    end_time: str
    conflict_with: str
    description: str
    source_evidence: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class SourceStatus:
    id: str                                   # e.g., "meeting_transcript", "email_thread_1"
    title: str                                # Human readable title
    channel: str                              # Meeting Transcript, Email, Voice Note, Calendar
    file_path: str                            # Path on disk
    is_loaded: bool                           # True if actual data is present
    char_count: int = 0
    preview: str = "Source data not loaded"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
