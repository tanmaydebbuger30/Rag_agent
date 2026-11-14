from typing import Literal
from pydantic import BaseModel


class Control(BaseModel):
    framework : str # HIPAA
    section : str #"164.312"
    control_id : str #"164..312(a)(2)(i)"
    parent_id : str | None # the standard it belongs to; None for standards
    control_name : str #"Unique User Identification"
    level : Literal ["standard", "implementation_specification"]
    requirement_type : Literal["required", "addressable"]
    safeguard_category : str #Technical
    requirement_text : str  #verbatim body text fromeCFR
    citation : str #45 CFR § 164.312(a)(2)(i)
    in_scope_v1 : bool 