import re
from typing import Dict, Any, List, Optional
from .store import DataStore
from .models import OwnershipCategory, UrgencyStatus

class GroundedQAEngine:
    def __init__(self, store: Optional[DataStore] = None):
        self.store = store or DataStore()

    def answer_question(self, question: str) -> Dict[str, Any]:
        """
        Answers executive queries strictly grounded in the loaded assignment data.
        If data is not loaded or evidence is not found, states so explicitly.
        Never hallucinates or invents commitments.
        """
        q = question.strip().lower()
        actions = self.store.load_actions()
        conflicts = self.store.load_conflicts()
        statuses = self.store.get_source_statuses()
        loaded_count = sum(1 for s in statuses if s["is_loaded"])

        # If zero assignment data has been loaded:
        if loaded_count == 0:
            return {
                "question": question,
                "grounded": True,
                "status": "No data loaded",
                "answer": "Source data not loaded: The assignment data pack (meeting transcripts, calendars, email threads, voice notes) has not yet been loaded into data/raw/. Unable to extract commitments or facts without the actual data pack.",
                "evidence": [],
                "items_count": 0
            }

        # Preset 1: "What did I promise?" or "What did I promise Raghav?"
        if "promise" in q or "commit" in q:
            # Check if specific counterparty mentioned
            target_person = None
            for name in ["raghav", "priya", "vikram", "sneha", "karan", "rohit", "ananya", "amit"]:
                if name in q:
                    target_person = name
                    break

            promises = []
            for act in actions:
                if act.get("ownership_category") == OwnershipCategory.MY_ACTION.value:
                    if target_person:
                        if act.get("counterparty") and target_person in act.get("counterparty").lower():
                            promises.append(act)
                        elif target_person in act.get("task", "").lower():
                            promises.append(act)
                    else:
                        promises.append(act)

            if not promises:
                if target_person:
                    return {
                        "question": question,
                        "grounded": True,
                        "status": "Found",
                        "answer": f"No commitments to {target_person.capitalize()} were identified in the currently loaded assignment data pack.",
                        "evidence": [],
                        "items_count": 0
                    }
                else:
                    return {
                        "question": question,
                        "grounded": True,
                        "status": "Found",
                        "answer": "No commitments made by Arjun Malhotra were identified in the loaded assignment data.",
                        "evidence": [],
                        "items_count": 0
                    }

            ans_lines = [f"Grounded in the loaded data pack, here are the commitments made by Arjun:"]
            evidence_list = []
            for idx, p in enumerate(promises, 1):
                dl_info = f" (Deadline: {p.get('raw_deadline')})" if p.get('raw_deadline') else ""
                ans_lines.append(f"{idx}. {p.get('task')}{dl_info}")
                for src in p.get("sources", []):
                    evidence_list.append(src)

            return {
                "question": question,
                "grounded": True,
                "status": "Found",
                "answer": "\n".join(ans_lines),
                "evidence": evidence_list,
                "items_count": len(promises)
            }

        # Preset 2: "What needs action today?"
        if "action today" in q or "needs action" in q or "today" in q:
            due_today = [
                a for a in actions 
                if a.get("urgency_status") in [UrgencyStatus.DUE_TODAY.value, UrgencyStatus.OVERDUE.value]
            ]
            if not due_today:
                return {
                    "question": question,
                    "grounded": True,
                    "status": "Found",
                    "answer": "No items are marked due today or overdue in the loaded assignment data.",
                    "evidence": [],
                    "items_count": 0
                }

            ans_lines = ["The following items require immediate action based on the loaded data:"]
            evidence_list = []
            for idx, item in enumerate(due_today, 1):
                owner = item.get("owner") or "Unassigned"
                urgency = item.get("urgency_status", "Due Today")
                ans_lines.append(f"{idx}. [{urgency}] {item.get('task')} (Owner: {owner})")
                for src in item.get("sources", []):
                    evidence_list.append(src)

            return {
                "question": question,
                "grounded": True,
                "status": "Found",
                "answer": "\n".join(ans_lines),
                "evidence": evidence_list,
                "items_count": len(due_today)
            }

        # Preset 3: "What commitments are due?"
        if "due" in q or "deadline" in q:
            due_items = [a for a in actions if a.get("raw_deadline") or a.get("normalized_deadline")]
            if not due_items:
                return {
                    "question": question,
                    "grounded": True,
                    "status": "Found",
                    "answer": "No explicit deadlines were identified in the loaded assignment data.",
                    "evidence": [],
                    "items_count": 0
                }

            ans_lines = ["The following commitments have explicit deadlines in the data:"]
            evidence_list = []
            for idx, item in enumerate(due_items, 1):
                ans_lines.append(f"{idx}. {item.get('task')} - Deadline: {item.get('raw_deadline')} ({item.get('urgency_status')})")
                for src in item.get("sources", []):
                    evidence_list.append(src)

            return {
                "question": question,
                "grounded": True,
                "status": "Found",
                "answer": "\n".join(ans_lines),
                "evidence": evidence_list,
                "items_count": len(due_items)
            }

        # Preset 4: "What are the conflicts?"
        if "conflict" in q or "overlap" in q:
            if not conflicts:
                return {
                    "question": question,
                    "grounded": True,
                    "status": "Found",
                    "answer": "No calendar conflicts or cross-source deadline contradictions were detected in the loaded data.",
                    "evidence": [],
                    "items_count": 0
                }

            ans_lines = ["Calendar conflicts detected from the loaded schedule:"]
            evidence_list = []
            for idx, c in enumerate(conflicts, 1):
                ans_lines.append(f"{idx}. {c.get('event_title')} ({c.get('start_time')} - {c.get('end_time')}) overlaps with {c.get('conflict_with')}.")
                evidence_list.append({
                    "channel": "Calendar",
                    "source_id": "Arjun Calendar",
                    "timestamp_or_date": c.get("start_time", ""),
                    "verbatim_quote": c.get("source_evidence", ""),
                    "context": c.get("description", "")
                })

            return {
                "question": question,
                "grounded": True,
                "status": "Found",
                "answer": "\n".join(ans_lines),
                "evidence": evidence_list,
                "items_count": len(conflicts)
            }

        # General Search across tasks
        matched = []
        words = [w for w in re.findall(r"\w{3,}", q) if w not in ["what", "when", "where", "which", "does", "have", "with"]]
        for act in actions:
            text_to_search = (act.get("task", "") + " " + str(act.get("owner", "")) + " " + str(act.get("counterparty", ""))).lower()
            if any(w in text_to_search for w in words):
                matched.append(act)

        if not matched:
            return {
                "question": question,
                "grounded": True,
                "status": "No matching evidence",
                "answer": f"No direct evidence found in the loaded assignment data regarding '{question}'.",
                "evidence": [],
                "items_count": 0
            }

        ans_lines = [f"Found {len(matched)} relevant item(s) in the loaded data:"]
        evidence_list = []
        for idx, item in enumerate(matched[:5], 1):
            ans_lines.append(f"{idx}. [{item.get('ownership_category')}] {item.get('task')} (Owner: {item.get('owner') or 'Unclear'})")
            for src in item.get("sources", []):
                evidence_list.append(src)

        return {
            "question": question,
            "grounded": True,
            "status": "Found",
            "answer": "\n".join(ans_lines),
            "evidence": evidence_list,
            "items_count": len(matched)
        }
