from .base import Rule
from .security import SECURITY_RULES
from .quality import QUALITY_RULES
from .ai_patterns import AI_PATTERN_RULES

ALL_RULES: list[Rule] = SECURITY_RULES + QUALITY_RULES + AI_PATTERN_RULES

__all__ = ["Rule", "ALL_RULES"]
