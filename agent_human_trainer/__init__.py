# -*- coding: utf-8 -*-
"""
Agent-Human Trainer — Open-Source Contrastive DPO/SFT Training Suite,
5-Tier Behavioral Scoring Engine (D1..D5), and AST Quality Gate for
aligning AI Coding Agents with Senior Human Engineering Standards.
"""

from .taxonomy import (
    AGENT_SOPHISTICATION_TIERS,
    ANONYMIZED_EMPIRICAL_SPECIMENS,
    BEHAVIORAL_SCORING_DIMENSIONS,
    CONTRASTIVE_ALIGNMENT_PAIRS,
    SPECIFICATION_INTEGRITY_CLASSES,
)
from .evaluator import (
    audit_issue_specification,
    audit_patch_ast_integrity,
    score_agent_human_tier,
    verify_human_grade_output,
)
from .dataset_exporter import (
    audit_public_community_cleanliness,
    export_all_community_datasets,
)

__version__ = "1.0.0"
__author__ = "Khoa Phan (@khoap1220-hue)"

__all__ = [
    "AGENT_SOPHISTICATION_TIERS",
    "ANONYMIZED_EMPIRICAL_SPECIMENS",
    "BEHAVIORAL_SCORING_DIMENSIONS",
    "CONTRASTIVE_ALIGNMENT_PAIRS",
    "SPECIFICATION_INTEGRITY_CLASSES",
    "audit_issue_specification",
    "audit_patch_ast_integrity",
    "audit_public_community_cleanliness",
    "export_all_community_datasets",
    "score_agent_human_tier",
    "verify_human_grade_output",
]
