"""Paths and runtime settings shared by ingestion, retrieval and the API."""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "regulatory"
PROCESSED_DIR = DATA_DIR / "processed"
FRAMEWORK_DIR = DATA_DIR / "frameworks" / "hipaa_security_rule"

ECFR_XML = RAW_DIR / "ecfr_45_164_subpartC.xml"
HHS_PDF = RAW_DIR / "techsafeguards.pdf"
NIST_PDF = RAW_DIR / "NIST.SP.800-66r2.pdf"

CONTROLS_YAML = FRAMEWORK_DIR / "controls.yaml"
CRITERIA_YAML = FRAMEWORK_DIR / "assessment_criteria.yaml"
REGULATORY_CHUNKS = PROCESSED_DIR / "regulatory_chunks.jsonl"

SAMPLE_EVIDENCE_DIR = DATA_DIR / "sample_evidence"
EVAL_DIR = DATA_DIR / "eval"
EVAL_RESULTS_DIR = REPO_ROOT / "eval_results"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

# Runtime state (assessments, uploaded evidence). Not committed.
STATE_DIR = Path(os.environ.get("CG_STATE_DIR", REPO_ROOT / "var"))
DB_PATH = STATE_DIR / "complianceguard.sqlite3"

# Assessor: "rules" (deterministic, offline) or "llm" (Claude; needs ANTHROPIC_API_KEY).
ASSESSOR = os.environ.get("CG_ASSESSOR", "rules")
LLM_MODEL = os.environ.get("CG_LLM_MODEL", "claude-opus-5-5")

# Dense retrieval is optional: it needs a local embedding model (fastembed downloads it once).
DENSE_ENABLED = os.environ.get("CG_DENSE", "0") == "1"
DENSE_MODEL = os.environ.get("CG_DENSE_MODEL", "BAAI/bge-small-en-v1.5")
