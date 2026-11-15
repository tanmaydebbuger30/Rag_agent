"""The control catalog: binding requirement text, looked up exactly by control_id.

In-scope controls come from the human-reviewed controls.yaml. The other
§164.308 and §164.312 controls are parsed from the same eCFR XML; they are
retrievable distractors, never assessed in V1.
"""
from functools import lru_cache

import yaml

from backend.app.config import CONTROLS_YAML, CRITERIA_YAML
from backend.app.ingestion.ecfr_parser import parse_controls
from backend.app.schemas.regulatory import Control


@lru_cache
def all_controls() -> dict[str, Control]:
    reviewed = {c["control_id"]: Control(**c) for c in yaml.safe_load(CONTROLS_YAML.read_text(encoding="utf-8"))}
    controls = {c.control_id: c for c in parse_controls("164.312") + parse_controls("164.308")}
    controls.update(reviewed)               # the reviewed file wins for in-scope controls
    return controls


def in_scope_controls() -> list[Control]:
    return [c for c in all_controls().values() if c.in_scope_v1]


def get_control(control_id: str) -> Control:
    """Deterministic requirement lookup. Raises KeyError for unknown ids."""
    return all_controls()[control_id]


@lru_cache
def criteria() -> dict[str, dict]:
    """Assessment criteria, aliases, contradiction / alternative patterns per in-scope control."""
    return yaml.safe_load(CRITERIA_YAML.read_text(encoding="utf-8"))
