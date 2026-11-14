"""SQLite persistence for assessments, their evidence and human review decisions.

One row per assessment with the full result as JSON, plus one row per evidence
chunk. Enough for a single-node demo; a multi-user deployment would normalize
findings and reviews into their own tables (and use Postgres).
"""
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from backend.app import config
from backend.app.schemas.chunks import EvidenceChunk

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    org_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_chunks (
    assessment_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (assessment_id, chunk_id)
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def save_assessment(assessment: dict, evidence: list[EvidenceChunk]) -> None:
    with _lock, connect() as conn:
        conn.execute("INSERT OR REPLACE INTO assessments VALUES (?, ?, ?, ?)",
                     (assessment["id"], assessment["org_name"], assessment["created_at"], json.dumps(assessment)))
        conn.executemany("INSERT OR REPLACE INTO evidence_chunks VALUES (?, ?, ?)",
                         [(assessment["id"], c.chunk_id, c.model_dump_json()) for c in evidence])


def update_assessment(assessment: dict) -> None:
    with _lock, connect() as conn:
        conn.execute("UPDATE assessments SET data = ? WHERE id = ?", (json.dumps(assessment), assessment["id"]))


def get_assessment(assessment_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT data FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
    return json.loads(row[0]) if row else None


def list_assessments() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT data FROM assessments ORDER BY created_at DESC").fetchall()
    out = []
    for (data,) in rows:
        a = json.loads(data)
        out.append({k: a[k] for k in ("id", "org_name", "created_at", "assessor", "summary", "documents", "review_status")})
    return out


def get_evidence(assessment_id: str) -> list[EvidenceChunk]:
    with connect() as conn:
        rows = conn.execute("SELECT data FROM evidence_chunks WHERE assessment_id = ? ORDER BY chunk_id",
                            (assessment_id,)).fetchall()
    return [EvidenceChunk(**json.loads(d)) for (d,) in rows]
