import json

import pytest

from app.api.routes import documents
from app.services.rag_service import _trace_callback


def test_run_root_rejects_path_traversal():
    with pytest.raises(documents.HTTPException) as exc:
        documents._run_root("../secret")
    assert exc.value.status_code == 400


def test_trace_records_sequence_and_elapsed(tmp_path):
    class Run:
        analysis_id = "abc"
        def __init__(self):
            self.events = []
            self.status = []
        def append_jsonl(self, name, event):
            self.events.append((name, event))
        def write_json(self, name, payload):
            self.status.append((name, payload))

    run = Run()
    received = []
    trace = _trace_callback(run, received.append)
    trace({"type": "progress", "stage": "extract", "message": "Started"})
    trace({"type": "progress", "stage": "complete", "message": "Done"})
    assert [event[1]["sequence"] for event in run.events] == [1, 2]
    assert all("elapsed_seconds" in event[1] for event in run.events)
    assert received[-1]["stage"] == "complete"
    assert run.status[-1][1]["status"] == "COMPLETED"
