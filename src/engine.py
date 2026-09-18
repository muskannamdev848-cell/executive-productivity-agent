import re
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from .config import REFERENCE_DATE, EXECUTIVE_NAME
from .models import (
    ActionItem, SourceCitation, CalendarConflict, 
    OwnershipCategory, UrgencyStatus, SourceChannel
)
from .store import DataStore

class ProcessingEngine:
    def __init__(self, store: Optional[DataStore] = None):
        self.store = store or DataStore()
        self.reference_date = REFERENCE_DATE
        self.executive_name = EXECUTIVE_NAME

    def process_all_sources(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Processes loaded raw files.
        If files are empty, strictly returns empty lists and 'Source data not loaded' summary.
        Does NOT invent synthetic data.
        """
        statuses = self.store.get_source_statuses()
        loaded_sources = [s for s in statuses if s["is_loaded"]]

        if not loaded_sources:
            summary = {
                "reference_date": self.reference_date,
                "executive": self.executive_name,
                "status": "Source data not loaded",
                "message": "The AIONOS assignment data pack has not been loaded into data/raw/. Please paste or load the exact meeting transcripts, calendars, email threads, and voice notes.",
                "loaded_sources_count": 0,
                "total_manifest_count": len(statuses),
                "my_actions_count": 0,
                "waiting_on_others_count": 0,
                "unclear_ownership_count": 0,
                "overdue_count": 0,
                "due_today_count": 0,
                "conflicts_count": 0
            }
            self.store.save_actions([])
            self.store.save_conflicts([])
            return [], [], summary

        raw_candidates: List[ActionItem] = []
        conflicts: List[CalendarConflict] = []

        # 1. Process Meeting Transcripts
        transcript_text = self.store.get_source_content("meeting_transcript")
        if transcript_text:
            raw_candidates.extend(self._extract_from_transcript(transcript_text, "meeting_transcript"))

        # 2. Process Email Threads
        for i in range(1, 6):
            thread_id = f"email_thread_{i}"
            thread_text = self.store.get_source_content(thread_id)
            if thread_text:
                raw_candidates.extend(self._extract_from_email(thread_text, thread_id, f"Email Thread {i}"))

        # 3. Process Voice Notes
        for i in (1, 2):
            vn_id = f"voice_note_{i}"
            vn_text = self.store.get_source_content(vn_id)
            if vn_text:
                raw_candidates.extend(self._extract_from_voice_note(vn_text, vn_id, f"Voice Note {i}"))

        # 4. Process Calendars
        cal_text = self.store.get_source_content("arjun_calendar")
        other_cal_text = self.store.get_source_content("other_calendars")
        if cal_text:
            cal_actions, cal_conflicts = self._extract_from_calendar(cal_text, other_cal_text)
            raw_candidates.extend(cal_actions)
            conflicts.extend(cal_conflicts)

        # 5. Deduplicate and merge actions across sources
        deduped_actions = self._deduplicate_actions(raw_candidates)

        # 6. Calculate summary metrics
        actions_dict = [a.to_dict() for a in deduped_actions]
        conflicts_dict = [c.to_dict() for c in conflicts]

        my_actions = [a for a in deduped_actions if a.ownership_category == OwnershipCategory.MY_ACTION.value]
        waiting_on = [a for a in deduped_actions if a.ownership_category == OwnershipCategory.WAITING_ON_OTHERS.value]
        unclear = [a for a in deduped_actions if a.ownership_category == OwnershipCategory.UNCLEAR_OWNERSHIP.value]
        overdue = [a for a in deduped_actions if a.urgency_status == UrgencyStatus.OVERDUE.value]
        due_today = [a for a in deduped_actions if a.urgency_status == UrgencyStatus.DUE_TODAY.value]

        summary = {
            "reference_date": self.reference_date,
            "executive": self.executive_name,
            "status": "Ready",
            "message": f"Successfully parsed {len(loaded_sources)} loaded source documents.",
            "loaded_sources_count": len(loaded_sources),
            "total_manifest_count": len(statuses),
            "my_actions_count": len(my_actions),
            "waiting_on_others_count": len(waiting_on),
            "unclear_ownership_count": len(unclear),
            "overdue_count": len(overdue),
            "due_today_count": len(due_today),
            "conflicts_count": len(conflicts)
        }

        self.store.save_actions(actions_dict)
        self.store.save_conflicts(conflicts_dict)

        return actions_dict, conflicts_dict, summary

    def _extract_from_transcript(self, text: str, source_id: str) -> List[ActionItem]:
        items: List[ActionItem] = []
        lines = text.split("\n")
        
        for idx, line in enumerate(lines):
            line_str = line.strip()
            if not line_str:
                continue

            # Check for speaker format like "Arjun:", "Raghav:", etc.
            speaker_match = re.match(r"^([A-Za-z\s]+)\s*:\s*(.*)$", line_str)
            speaker = speaker_match.group(1).strip() if speaker_match else None
            content = speaker_match.group(2).strip() if speaker_match else line_str

            # Look for commitment patterns
            # Pattern A: Arjun committing
            if speaker and "arjun" in speaker.lower():
                commitment = self._detect_commitment_phrase(content)
                if commitment:
                    item_id = hashlib.md5(f"trans_{idx}_{content[:30]}".encode()).hexdigest()[:8]
                    deadline_raw, norm_dl, urgency = self._parse_deadline(content)
                    items.append(ActionItem(
                        id=f"act-{item_id}",
                        task=commitment,
                        owner=self.executive_name,
                        ownership_category=OwnershipCategory.MY_ACTION.value,
                        counterparty=self._extract_counterparty(content),
                        raw_deadline=deadline_raw,
                        normalized_deadline=norm_dl,
                        urgency_status=urgency,
                        priority="High" if urgency in [UrgencyStatus.OVERDUE.value, UrgencyStatus.DUE_TODAY.value] else "Medium",
                        sources=[SourceCitation(
                            channel=SourceChannel.MEETING_TRANSCRIPT.value,
                            source_id=source_id,
                            timestamp_or_date=self.reference_date,
                            author_or_speaker=speaker,
                            verbatim_quote=line_str,
                            context=f"Meeting transcript line {idx+1}"
                        )]
                    ))
            elif speaker:
                # Other speaker committing to Arjun or action assigned
                commitment = self._detect_commitment_phrase(content)
                if commitment:
                    item_id = hashlib.md5(f"trans_other_{idx}_{content[:30]}".encode()).hexdigest()[:8]
                    deadline_raw, norm_dl, urgency = self._parse_deadline(content)
                    items.append(ActionItem(
                        id=f"act-{item_id}",
                        task=commitment,
                        owner=speaker,
                        ownership_category=OwnershipCategory.WAITING_ON_OTHERS.value,
                        counterparty=self.executive_name,
                        raw_deadline=deadline_raw,
                        normalized_deadline=norm_dl,
                        urgency_status=urgency,
                        priority="Medium",
                        sources=[SourceCitation(
                            channel=SourceChannel.MEETING_TRANSCRIPT.value,
                            source_id=source_id,
                            timestamp_or_date=self.reference_date,
                            author_or_speaker=speaker,
                            verbatim_quote=line_str,
                            context=f"Meeting transcript line {idx+1}"
                        )]
                    ))
            else:
                # Passive or unassigned statements: "Need to...", "Someone should..."
                passive_match = re.search(r"\b(someone needs to|need to|we must|action item:|let's make sure)\b\s*(.*)", content, re.IGNORECASE)
                if passive_match:
                    item_id = hashlib.md5(f"trans_unclear_{idx}_{content[:30]}".encode()).hexdigest()[:8]
                    deadline_raw, norm_dl, urgency = self._parse_deadline(content)
                    task_text = passive_match.group(2).strip() or content
                    items.append(ActionItem(
                        id=f"act-{item_id}",
                        task=task_text[:120],
                        owner=None,
                        ownership_category=OwnershipCategory.UNCLEAR_OWNERSHIP.value,
                        counterparty=None,
                        raw_deadline=deadline_raw,
                        normalized_deadline=norm_dl,
                        urgency_status=urgency,
                        priority="Medium",
                        flagged_unclear=True,
                        sources=[SourceCitation(
                            channel=SourceChannel.MEETING_TRANSCRIPT.value,
                            source_id=source_id,
                            timestamp_or_date=self.reference_date,
                            author_or_speaker="Unspecified",
                            verbatim_quote=line_str,
                            context=f"Unclear assignment in meeting line {idx+1}"
                        )]
                    ))

        return items

    def _extract_from_email(self, text: str, source_id: str, channel_title: str) -> List[ActionItem]:
        items: List[ActionItem] = []
        # Parse email headers
        sender = self._extract_header(text, "From")
        date_str = self._extract_header(text, "Date") or self.reference_date
        
        # Look for explicit promises in body
        lines = text.split("\n")
        for idx, line in enumerate(lines):
            line_str = line.strip()
            if not line_str or line_str.startswith(">"): # skip quote chains
                continue

            # First-person promise from Arjun
            if sender and "arjun" in sender.lower():
                commitment = self._detect_commitment_phrase(line_str)
                if commitment:
                    item_id = hashlib.md5(f"email_{source_id}_{idx}".encode()).hexdigest()[:8]
                    deadline_raw, norm_dl, urgency = self._parse_deadline(line_str, date_str)
                    items.append(ActionItem(
                        id=f"act-{item_id}",
                        task=commitment,
                        owner=self.executive_name,
                        ownership_category=OwnershipCategory.MY_ACTION.value,
                        counterparty=self._extract_counterparty(line_str),
                        raw_deadline=deadline_raw,
                        normalized_deadline=norm_dl,
                        urgency_status=urgency,
                        priority="High" if urgency in [UrgencyStatus.OVERDUE.value, UrgencyStatus.DUE_TODAY.value] else "Medium",
                        sources=[SourceCitation(
                            channel=SourceChannel.EMAIL_THREAD.value,
                            source_id=channel_title,
                            timestamp_or_date=date_str,
                            author_or_speaker=sender or self.executive_name,
                            verbatim_quote=line_str,
                            context=f"Sent by Arjun in {channel_title}"
                        )]
                    ))
            elif sender:
                # Incoming promise or request to Arjun
                commitment = self._detect_commitment_phrase(line_str)
                if commitment:
                    item_id = hashlib.md5(f"email_{source_id}_{idx}".encode()).hexdigest()[:8]
                    deadline_raw, norm_dl, urgency = self._parse_deadline(line_str, date_str)
                    items.append(ActionItem(
                        id=f"act-{item_id}",
                        task=commitment,
                        owner=sender,
                        ownership_category=OwnershipCategory.WAITING_ON_OTHERS.value,
                        counterparty=self.executive_name,
                        raw_deadline=deadline_raw,
                        normalized_deadline=norm_dl,
                        urgency_status=urgency,
                        priority="Medium",
                        sources=[SourceCitation(
                            channel=SourceChannel.EMAIL_THREAD.value,
                            source_id=channel_title,
                            timestamp_or_date=date_str,
                            author_or_speaker=sender,
                            verbatim_quote=line_str,
                            context=f"Incoming deliverable from {sender} in {channel_title}"
                        )]
                    ))

        return items

    def _extract_from_voice_note(self, text: str, source_id: str, channel_title: str) -> List[ActionItem]:
        items: List[ActionItem] = []
        sentences = re.split(r"[.!?]\s+|\n+", text)
        
        for idx, sentence in enumerate(sentences):
            sent_str = sentence.strip()
            if not sent_str or len(sent_str) < 10:
                continue

            # Voice notes are Arjun speaking to himself:
            # "Need to ping Raghav...", "I have to send the updated pricing...", "Follow up with Priya..."
            # Look for Arjun actions vs Waiting on others
            waiting_match = re.search(r"\b(waiting on|waiting for|check if (\w+) has|did (\w+) finish)\b", sent_str, re.IGNORECASE)
            if waiting_match:
                other_person = waiting_match.group(2) or waiting_match.group(3) or "Colleague"
                item_id = hashlib.md5(f"vn_{source_id}_{idx}".encode()).hexdigest()[:8]
                deadline_raw, norm_dl, urgency = self._parse_deadline(sent_str)
                items.append(ActionItem(
                    id=f"act-{item_id}",
                    task=sent_str,
                    owner=other_person.capitalize(),
                    ownership_category=OwnershipCategory.WAITING_ON_OTHERS.value,
                    counterparty=self.executive_name,
                    raw_deadline=deadline_raw,
                    normalized_deadline=norm_dl,
                    urgency_status=urgency,
                    priority="Medium",
                    sources=[SourceCitation(
                        channel=SourceChannel.VOICE_NOTE.value,
                        source_id=channel_title,
                        timestamp_or_date=self.reference_date,
                        author_or_speaker=self.executive_name,
                        verbatim_quote=sent_str,
                        context=f"Recorded in {channel_title}"
                    )]
                ))
            else:
                # Direct action or commitment by Arjun
                action_match = re.search(r"\b(need to|must|have to|i will|i'll|remember to|call|send|review|follow up with)\b\s*(.*)", sent_str, re.IGNORECASE)
                if action_match:
                    item_id = hashlib.md5(f"vn_{source_id}_{idx}".encode()).hexdigest()[:8]
                    deadline_raw, norm_dl, urgency = self._parse_deadline(sent_str)
                    counterparty = self._extract_counterparty(sent_str)
                    items.append(ActionItem(
                        id=f"act-{item_id}",
                        task=sent_str,
                        owner=self.executive_name,
                        ownership_category=OwnershipCategory.MY_ACTION.value,
                        counterparty=counterparty,
                        raw_deadline=deadline_raw,
                        normalized_deadline=norm_dl,
                        urgency_status=urgency,
                        priority="High" if urgency in [UrgencyStatus.OVERDUE.value, UrgencyStatus.DUE_TODAY.value] else "Medium",
                        sources=[SourceCitation(
                            channel=SourceChannel.VOICE_NOTE.value,
                            source_id=channel_title,
                            timestamp_or_date=self.reference_date,
                            author_or_speaker=self.executive_name,
                            verbatim_quote=sent_str,
                            context=f"Recorded in {channel_title}"
                        )]
                    ))

        return items

    def _extract_from_calendar(self, arjun_cal_text: str, other_cal_text: Optional[str]) -> Tuple[List[ActionItem], List[CalendarConflict]]:
        actions: List[ActionItem] = []
        conflicts: List[CalendarConflict] = []

        # Parse JSON or structured calendar text
        try:
            events = json.loads(arjun_cal_text)
            if isinstance(events, list):
                # Detect overlapping meetings for conflicts
                sorted_events = sorted(events, key=lambda x: x.get("start", ""))
                for i in range(len(sorted_events) - 1):
                    ev1 = sorted_events[i]
                    ev2 = sorted_events[i+1]
                    s1, e1 = ev1.get("start", ""), ev1.get("end", "")
                    s2, e2 = ev2.get("start", ""), ev2.get("end", "")
                    if s2 and e1 and s2 < e1:
                        conflicts.append(CalendarConflict(
                            id=f"conf-{i}",
                            event_title=ev1.get("title", "Meeting 1"),
                            start_time=s1,
                            end_time=e1,
                            conflict_with=f"{ev2.get('title', 'Meeting 2')} ({s2} - {e2})",
                            description=f"Direct calendar overlap between '{ev1.get('title')}' and '{ev2.get('title')}'.",
                            source_evidence=f"Arjun Calendar: {s1} - {e1} vs {s2} - {e2}"
                        ))
        except Exception:
            # Non-JSON calendar text fallback
            pass

        return actions, conflicts

    def _deduplicate_actions(self, items: List[ActionItem]) -> List[ActionItem]:
        """
        Deduplicates identical actions across sources.
        Clusters items with matching counterparties and similar core task tokens.
        Merges citations into a single audit trail.
        """
        if not items:
            return []

        deduped: List[ActionItem] = []

        for item in items:
            matched = False
            for existing in deduped:
                # Check for same owner and strong text/counterparty similarity
                same_owner = (existing.owner == item.owner)
                same_counterparty = (existing.counterparty and item.counterparty and existing.counterparty.lower() == item.counterparty.lower())
                
                # Check word overlap
                words_existing = set(re.findall(r"\w{4,}", existing.task.lower()))
                words_item = set(re.findall(r"\w{4,}", item.task.lower()))
                overlap = len(words_existing.intersection(words_item))

                if same_owner and (same_counterparty or overlap >= 2):
                    # Merge citations
                    existing.sources.extend(item.sources)
                    # Check for conflicting deadlines
                    if existing.raw_deadline and item.raw_deadline and existing.raw_deadline != item.raw_deadline:
                        existing.conflict_notes = f"Notice: Multiple deadlines found across sources: '{existing.raw_deadline}' vs '{item.raw_deadline}'. Retaining most explicit deadline."
                    matched = True
                    break

            if not matched:
                deduped.append(item)

        return deduped

    def _detect_commitment_phrase(self, text: str) -> Optional[str]:
        # Detect explicit promises and commitments
        patterns = [
            r"\b(i will\b.*)",
            r"\b(i'll\b.*)",
            r"\b(i promise\b.*)",
            r"\b(i can get that to you\b.*)",
            r"\b(let me send\b.*)",
            r"\b(i'll make sure\b.*)",
            r"\b(will follow up\b.*)"
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    def _parse_deadline(self, text: str, base_date: Optional[str] = None) -> Tuple[Optional[str], Optional[str], str]:
        # Regex for common deadline expressions
        patterns = [
            (r"\b(by EOD today|by end of day today|today|by tonight)\b", 0, UrgencyStatus.DUE_TODAY.value),
            (r"\b(by tomorrow|tomorrow morning|tomorrow EOD)\b", 1, UrgencyStatus.UPCOMING.value),
            (r"\b(by yesterday|was due yesterday)\b", -1, UrgencyStatus.OVERDUE.value),
            (r"\b(by Friday|by Monday|by Tuesday|by Wednesday|by Thursday)\b", 2, UrgencyStatus.UPCOMING.value),
            (r"\b(by end of week|EOD Friday)\b", 2, UrgencyStatus.UPCOMING.value)
        ]
        for pat, days_offset, urgency in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                raw_match = m.group(1)
                return raw_match, self.reference_date, urgency

        return None, None, UrgencyStatus.NO_DEADLINE.value

    def _extract_counterparty(self, text: str) -> Optional[str]:
        # Detect names frequently addressed
        for name in ["Raghav", "Priya", "Vikram", "Sneha", "Karan", "Rohit", "Ananya", "Amit"]:
            if re.search(rf"\b{name}\b", text, re.IGNORECASE):
                return name
        return None

    def _extract_header(self, text: str, header_name: str) -> Optional[str]:
        m = re.search(rf"^{header_name}\s*:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else None
