import os
import json
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.config import BASE_DIR, REFERENCE_DATE, EXECUTIVE_NAME
from src.store import DataStore
from src.engine import ProcessingEngine
from src.qa import GroundedQAEngine

STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

store = DataStore()
engine = ProcessingEngine(store)
qa_engine = GroundedQAEngine(store)

# Run initial processing on start
engine.process_all_sources()

class ExecutiveAgentHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/dashboard":
            self.send_json(self.get_dashboard_data())
            return
        elif path == "/api/sources":
            self.send_json({"sources": store.get_source_statuses()})
            return
        elif path.startswith("/api/source/"):
            source_id = path.split("/")[-1]
            content = store.get_source_content(source_id)
            self.send_json({
                "source_id": source_id,
                "content": content if content is not None else "",
                "is_loaded": content is not None and len(content) > 0
            })
            return
        elif path == "/api/actions":
            actions = store.load_actions()
            self.send_json({"actions": actions})
            return
        elif path == "/api/conflicts":
            conflicts = store.load_conflicts()
            self.send_json({"conflicts": conflicts})
            return
        
        # Default static file serving
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        data = json.loads(body) if body else {}

        if path == "/api/qa":
            question = data.get("question", "")
            res = qa_engine.answer_question(question)
            self.send_json(res)
            return
        elif path == "/api/process":
            actions, conflicts, summary = engine.process_all_sources()
            self.send_json({
                "status": "success",
                "summary": summary,
                "actions_count": len(actions),
                "conflicts_count": len(conflicts)
            })
            return
        elif path == "/api/source/update":
            source_id = data.get("source_id", "")
            content = data.get("content", "")
            updated = store.update_source_content(source_id, content)
            if updated:
                engine.process_all_sources()
                self.send_json({"status": "success", "source_id": source_id})
            else:
                self.send_json({"status": "error", "message": "Invalid source ID"}, 400)
            return

        self.send_error(404, "Endpoint not found")

    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def get_dashboard_data(self) -> Dict[str, Any]:
        statuses = store.get_source_statuses()
        actions = store.load_actions()
        conflicts = store.load_conflicts()

        loaded_sources = [s for s in statuses if s["is_loaded"]]

        priorities = [a for a in actions if a.get("urgency_status") in ["Due Today", "Overdue"]]
        my_actions = [a for a in actions if a.get("ownership_category") == "My Action"]
        waiting_on = [a for a in actions if a.get("ownership_category") == "Waiting on Others"]
        unclear = [a for a in actions if a.get("ownership_category") == "Unclear Ownership"]

        return {
            "executive": EXECUTIVE_NAME,
            "title": "VP Sales",
            "reference_date": REFERENCE_DATE,
            "data_pack_status": {
                "loaded_count": len(loaded_sources),
                "total_count": len(statuses),
                "all_loaded": len(loaded_sources) == len(statuses),
                "is_empty": len(loaded_sources) == 0,
                "status_label": "Fully Loaded" if len(loaded_sources) == len(statuses) else ("Partially Loaded" if len(loaded_sources) > 0 else "Source data not loaded")
            },
            "metrics": {
                "priorities_today": len(priorities),
                "my_commitments": len(my_actions),
                "waiting_on_others": len(waiting_on),
                "calendar_conflicts": len(conflicts),
                "unclear_ownership": len(unclear),
                "total_action_items": len(actions)
            },
            "priorities": priorities,
            "commitments": my_actions,
            "follow_ups": waiting_on,
            "unclear_items": unclear,
            "calendar_conflicts": conflicts,
            "sources": statuses
        }

def run_server(port: int = 8000):
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, ExecutiveAgentHandler)
    print(f"Executive Productivity Agent Server running at http://localhost:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
