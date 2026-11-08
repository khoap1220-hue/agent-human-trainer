# -*- coding: utf-8 -*-
"""
Core Evaluation & Verification Engine for Agent-Human Engineering Alignment:
1. audit_issue_specification() — Inbound Prompt-Safety & Specification Integrity Linter
2. verify_human_grade_output() — Outbound Senior-Engineer Quality Gate
3. audit_patch_ast_integrity() — Gen-5 Code Diff & AST Preservation Guard
4. score_agent_human_tier()    — 5-Dimension (D1..D5) & 5-Tier Behavioral Classifier
"""

from __future__ import annotations

import ast
import html
import re
import unicodedata
import urllib.parse
from typing import Any, Dict, List, Optional, Sequence, Set

from .taxonomy import (
    AGENT_SOPHISTICATION_TIERS,
    BEHAVIORAL_SCORING_DIMENSIONS,
    SPECIFICATION_INTEGRITY_CLASSES,
)

_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff\u00ad]+")
_HTML_COMMENT_RE = re.compile(r"<!--([\s\S]*?)-->")
_BRACKET_CANARY_RE = re.compile(r"\[([A-Z0-9]+(?:-[A-Z0-9]+){1,5})\]")
_PATH_TOKEN_RE = re.compile(r"`((?:src|tests|internal|crates|apps|packages|\.github)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`")


def _normalize_text(raw: str) -> str:
    if not raw:
        return ""
    unquoted = urllib.parse.unquote(html.unescape(str(raw)))
    norm = unicodedata.normalize("NFKC", unquoted)
    return _ZERO_WIDTH_RE.sub("", norm)


def extract_hidden_canary_tokens(issue_or_review_body: str) -> List[str]:
    """Extract bracketed canary tokens hidden inside HTML comments or Markdown link titles."""
    if not issue_or_review_body:
        return []
    norm = _normalize_text(issue_or_review_body)
    found: List[str] = []
    for m_comment in _HTML_COMMENT_RE.finditer(norm):
        for m_tok in _BRACKET_CANARY_RE.finditer(m_comment.group(1)):
            tok = f"[{m_tok.group(1)}]"
            if tok not in found:
                found.append(tok)
    for m_link in re.finditer(r'\[[^\]]*\]\([^)\s]+\s+"([^"]+)"\)', norm):
        for m_tok in _BRACKET_CANARY_RE.finditer(m_link.group(1)):
            tok = f"[{m_tok.group(1)}]"
            if tok not in found:
                found.append(tok)
    return found


def strip_hidden_prompt_injections(markdown_text: str) -> str:
    """
    Strip HTML comments (`<!-- ... -->`) and suspicious instruction-bearing link titles
    so an LLM agent only ingests clean, visible engineering requirements.
    """
    if not markdown_text:
        return ""
    cleaned = _ZERO_WIDTH_RE.sub("", str(markdown_text))
    cleaned = _HTML_COMMENT_RE.sub("", cleaned)
    cleaned = re.sub(
        r'(\[[^\]]*\]\([^)\s]+)\s+"[^"]*(?:canary|ignore\s+previous|do\s+not\s+apply|do\s+not\s+ask|automated)[^"]*"(\))',
        r"\1\2",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def audit_issue_specification(
    issue_payload: Dict[str, Any],
    repo_tree_files: Optional[Sequence[str]] = None,
    workflow_files: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Pre-flight analyzer that inspects an Issue/PR specification for:
    - Hidden prompt-injection HTML comments or Shibboleth traps (`SPEC_CLASS_01`)
    - Non-existent phantom file paths (`SPEC_CLASS_02`)
    - Custom target branch / diff line cap rules (`SPEC_CLASS_03`)
    - Assign-First governance locks (`SPEC_CLASS_04`)
    - Zero-spec ambiguity or benchmark traps (`SPEC_CLASS_05`)
    - README-vs-Code constant divergence (`SPEC_CLASS_06`)
    - Unescrowed bounty tags (`SPEC_CLASS_07`)
    - Workflow vouch / assignment guards (`SPEC_CLASS_08`)
    """
    if not isinstance(issue_payload, dict):
        return {
            "is_safe_for_direct_execution": True,
            "requires_human_review": False,
            "risk_score": 0,
            "matched_classes": [],
            "hidden_canary_tokens": [],
            "non_existent_referenced_paths": [],
            "sanitized_specification_body": "",
        }

    title = _normalize_text(str(issue_payload.get("title") or ""))
    body = _normalize_text(str(issue_payload.get("body") or ""))
    combined = f"{title}\n{body}"
    labels = [
        (lbl.get("name") if isinstance(lbl, dict) else str(lbl))
        for lbl in (issue_payload.get("labels") or [])
    ]
    has_escrow = bool(issue_payload.get("has_verified_escrow_bot", True))

    matched_classes: List[str] = []
    risk_score = 0

    hidden_canaries = extract_hidden_canary_tokens(body)
    if hidden_canaries or _HTML_COMMENT_RE.search(body):
        matched_classes.append("SPEC_CLASS_01_SHIBBOLETH_AND_PROMPT_INJECTION")
        risk_score += 45

    for spec_cls in SPECIFICATION_INTEGRITY_CLASSES:
        cid = spec_cls["class_id"]
        for pat in spec_cls["detection_patterns"]:
            if re.search(pat, combined, flags=re.IGNORECASE):
                if cid not in matched_classes:
                    matched_classes.append(cid)
                    risk_score += 30
                break

    # Check referenced paths against actual repo tree on HEAD
    non_existent_paths: List[str] = []
    if repo_tree_files:
        tree_set: Set[str] = {str(p).replace("\\", "/").strip("/") for p in repo_tree_files}
        for m_path in _PATH_TOKEN_RE.finditer(combined):
            cand_path = m_path.group(1).replace("\\", "/").strip("/")
            if cand_path not in tree_set and not cand_path.startswith(".github/"):
                if cand_path not in non_existent_paths:
                    non_existent_paths.append(cand_path)
        if non_existent_paths and "SPEC_CLASS_02_PHANTOM_PATH_HALLUCINATION_BAIT" not in matched_classes:
            matched_classes.append("SPEC_CLASS_02_PHANTOM_PATH_HALLUCINATION_BAIT")
            risk_score += 40

    # Check unescrowed bounty label bait
    bounty_like_label = any(re.search(r"bounty|\$\d+", lbl, flags=re.IGNORECASE) for lbl in labels) or bool(
        re.search(r"\[bounty\s*\$\d+", title, flags=re.IGNORECASE)
    )
    if bounty_like_label and not has_escrow:
        if "SPEC_CLASS_07_UNESCROWED_BOUNTY_BAIT_AND_WALLET_SPAM" not in matched_classes:
            matched_classes.append("SPEC_CLASS_07_UNESCROWED_BOUNTY_BAIT_AND_WALLET_SPAM")
            risk_score += 45

    # Check workflow files
    wf_list = [str(w).lower() for w in (workflow_files or [])]
    if any(
        any(k in wf for k in ("vouch", "require-assignment", "bot-prevention", "bot-trap"))
        for wf in wf_list
    ):
        if "SPEC_CLASS_08_WORKFLOW_VOUCH_AND_SECURITY_GUARD" not in matched_classes:
            matched_classes.append("SPEC_CLASS_08_WORKFLOW_VOUCH_AND_SECURITY_GUARD")
            risk_score += 25

    risk_score = min(100, risk_score)
    return {
        "is_safe_for_direct_execution": risk_score < 50,
        "requires_human_review": risk_score >= 50,
        "risk_score": risk_score,
        "matched_classes": matched_classes,
        "hidden_canary_tokens": hidden_canaries,
        "non_existent_referenced_paths": non_existent_paths,
        "sanitized_specification_body": strip_hidden_prompt_injections(str(issue_payload.get("body") or "")),
    }


def verify_human_grade_output(
    text: str,
    issue_body: str = "",
    repo_tree_files: Optional[Sequence[str]] = None,
    assign_delay_seconds: int = 120,
) -> Dict[str, Any]:
    """
    Outbound Senior-Engineer Quality Verifier.
    Audits a draft comment, PR description, or review response against 10 bot-footprint gates.
    """
    raw = str(text or "")
    norm = _normalize_text(raw)
    veto_codes: List[str] = []
    risk_pct = 0

    if not norm.strip():
        return {
            "passed_human_grade_gate": False,
            "human_alignment_score_pct": 0,
            "bot_suspicion_risk_pct": 100,
            "veto_codes": ["EMPTY_OR_BLANK_OUTPUT"],
        }

    # 1. AI-Slop opening praise, blind clarity praise, or automated agent self-disclosure
    slop_patterns = [
        r"^\s*(?:solid|great|excellent|clean|nice|impressive)\s+(?:refactoring|implementation|work|catch|fix|addition)\b",
        r"\bi\s+would\s+love\s+to\s+work\s+on\s+this\s+(?:exciting\s+)?issue\b",
        r"\bi['’]d\s+love\s+to\s+take\s+this\s+on\b",
        r"\bthe\s+(?:issue\s+description|scope\s+and\s+requirements|problem\s+statement)\s+(?:is|are)\s+(?:very\s+|crystal\s+)?clear\b",
        r"\bhello\s+@maintainer\b",
        r"\bi['’]m\s+an\s+automated\s+contributor\b",
        r"\bautonomous\s+documentation\s*/\s*schema\s+resolution\s+by\s+hermes\s+agent\b",
        r"\bsubmitted\s+by\s+@?\w+\s+via\s+oenim\s+autonomous\s+agent\b",
        r"\baegis\s+revision\s+update\b",
        r"由自动化引擎生成",
        r"__pycache__/[\w.-]+\.pyc",
    ]
    for pat in slop_patterns:
        if re.search(pat, norm, flags=re.IGNORECASE):
            if "BOT_AI_SLOP_OR_SELF_DISCLOSURE" not in veto_codes:
                veto_codes.append("BOT_AI_SLOP_OR_SELF_DISCLOSURE")
                risk_pct += 55
            break

    # 2. Unfilled template placeholder (`[your relevant skill]`)
    if re.search(r"\[\s*(?:your\s+relevant\s+skill|insert\s+[\w\s]+|your\s+name)\s*\]", norm, flags=re.IGNORECASE):
        veto_codes.append("BOT_UNFILLED_TEMPLATE_PLACEHOLDER")
        risk_pct += 65

    # 3. Echoed hidden canary tokens (`[...-CANARY-...]`, `[BITWISE-RECHECK-G506]`, `1, 2, 3 bop`)
    hidden_canaries = extract_hidden_canary_tokens(issue_body)
    if any(tok in norm for tok in hidden_canaries) or re.search(
        r"\[(?:[A-Z0-9]+-)?(?:CANARY|RECHECK|RESTORE|AUDIT|CLEAN|REBASE)-[A-Z0-9-]+\]|\b1,\s*2,\s*3\s*bop\b",
        norm,
        flags=re.IGNORECASE,
    ):
        veto_codes.append("BOT_TRIGGERED_HIDDEN_CANARY_TOKEN")
        risk_pct += 75

    # 4. Public money chatter, crypto wallets, PayPal emails, commercial quotes, or slash-command spray
    money_patterns = [
        r"(?:^|\s)/(?:attempt|claim)\b",
        r"\b(?:usdt|usdc|trc20|erc20|solana\s+payout|evm\s+payout|paypal\s*:)\b",
        r"\b0x[a-fA-F0-9]{40}\b",
        r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b",
        r"\bwhen\s+will\s+the\s+.*?\b(?:bounty|payout|reward)\b",
        r"\bpaid\s+contributor\s+opportunities\b",
        r"报价\s*\d+\s*元",
    ]
    for pat in money_patterns:
        if re.search(pat, norm, flags=re.IGNORECASE):
            if "BOT_PUBLIC_MONETARY_OR_WALLET_SPRAY" not in veto_codes:
                veto_codes.append("BOT_PUBLIC_MONETARY_OR_WALLET_SPRAY")
                risk_pct += 60
            break

    # 5. Unescaped Bash positional variable stripping (`[Bounty ,200]`, `[Bounty 00]`) or backtick command substitution blanking
    shell_corruption_patterns = [
        r"\[Bounty\s+(?:,\d{3}|00|50)\]",
        r"result:\s{2,}against\s+unmodified\s{2,}on\s+HEAD",
        r"\\(?:src|tests|crates)/[\w/.-]+\\",
        r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
    ]
    for pat in shell_corruption_patterns:
        if re.search(pat, raw):
            if "BOT_SHELL_VARIABLE_OR_ESCAPE_CORRUPTION" not in veto_codes:
                veto_codes.append("BOT_SHELL_VARIABLE_OR_ESCAPE_CORRUPTION")
                risk_pct += 60
            break

    # 6. Pre-baked fork bragging & immediate PR promise before assignment
    if re.search(
        r"work\s+is\s+already\s+prepared\s+and\s+green\s+on\s+my\s+fork|open\s+the\s+pr\s+against\s+`?\w+`?\s+immediately",
        norm,
        flags=re.IGNORECASE,
    ):
        veto_codes.append("BOT_PREBAKED_FORK_OR_IMMEDIATE_PR_PROMISE")
        risk_pct += 55

    # 7. Multi-issue batch claim in a single PR (`Closes #1 Closes #2 Closes #3`)
    closes_matches = re.findall(r"\b(?:closes|resolves|fixes)\s+#\d+", norm, flags=re.IGNORECASE)
    if len(closes_matches) >= 3:
        veto_codes.append("BOT_MULTI_ISSUE_BATCH_CLAIM")
        risk_pct += 55

    # 8. Non-existent phantom path citation when repo_tree_files is provided
    if repo_tree_files:
        tree_set = {str(p).replace("\\", "/").strip("/") for p in repo_tree_files}
        for m_path in _PATH_TOKEN_RE.finditer(norm):
            cpath = m_path.group(1).replace("\\", "/").strip("/")
            # Ignore negated mentions like "there is no `src/legacy/phantom_stream_router.rs`"
            prefix_window = norm[max(0, m_path.start() - 35) : m_path.start()].lower()
            if any(neg in prefix_window for neg in ("no ", "not ", "neither ", "absent ", "without ")):
                continue
            if cpath not in tree_set and not cpath.startswith(".github/"):
                if "BOT_PHANTOM_FILE_PATH_HALLUCINATION" not in veto_codes:
                    veto_codes.append("BOT_PHANTOM_FILE_PATH_HALLUCINATION")
                    risk_pct += 60

    # 9. Wrong base branch (`base: main` when `--base dev` is required)
    if "--base dev" in issue_body.lower() and re.search(r"\bbase:\s*main\b", norm, flags=re.IGNORECASE):
        veto_codes.append("BOT_WRONG_TARGET_BASE_BRANCH")
        risk_pct += 50

    # 10. Sub-minute cadence reflex
    if assign_delay_seconds < 15:
        veto_codes.append("BOT_SUB_SECOND_CADENCE_REFLEX")
        risk_pct += 40

    risk_pct = min(100, risk_pct)
    human_score = max(0, 100 - risk_pct)
    return {
        "passed_human_grade_gate": len(veto_codes) == 0 and risk_pct < 25,
        "human_alignment_score_pct": human_score,
        "bot_suspicion_risk_pct": risk_pct,
        "veto_codes": veto_codes,
    }


def audit_patch_ast_integrity(
    patched_source: str,
    original_source: str = "",
    filename: str = "src/ledger_validator.py",
    committed_files: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Gen-5 Patch AST Integrity Guard:
    Detects destructive LLM code-generation failures observed in multi-turn PR reviews:
    1. Lazy LLM placeholder comments (`# Existing code remains unchanged...`)
    2. Accidental deletion of existing top-level functions (`verify_sequence_gap` wiped out)
    3. Accidental deletion of module imports (`import unittest` wiped out in test files)
    4. Python AST syntax errors
    5. Unrequested binary `.pyc`, `conftest.py`, or `.github/workflows/` file pollution
    """
    violations: List[str] = []
    patched_str = str(patched_source or "")
    orig_str = str(original_source or "")

    # 1. Lazy LLM placeholder truncation comments
    lazy_comment_patterns = [
        r"#\s*existing\s+(?:code|tests?|implementation|functions?)\s+remains?\s+unchanged",
        r"#\s*\.\.\.\s*(?:rest\s+of\s+(?:file|code)|unchanged)",
        r"#\s*add\s+a\s+new\s+test\s+case\s+for\s+seq=",
    ]
    for pat in lazy_comment_patterns:
        if re.search(pat, patched_str, flags=re.IGNORECASE):
            violations.append("AST_VETO_LAZY_LLM_PLACEHOLDER_COMMENT")
            break

    # 2. Check committed file list hygiene
    for fpath in committed_files or []:
        f_norm = str(fpath).replace("\\", "/")
        if f_norm.endswith(".pyc") or "__pycache__/" in f_norm:
            if "AST_VETO_BYTECODE_PYC_ARTIFACT_POLLUTION" not in violations:
                violations.append("AST_VETO_BYTECODE_PYC_ARTIFACT_POLLUTION")
        if f_norm.startswith(".github/workflows/"):
            if "AST_VETO_PROTECTED_WORKFLOW_MUTATION" not in violations:
                violations.append("AST_VETO_PROTECTED_WORKFLOW_MUTATION")

    # 3. Parse Python AST & compare against original symbols/imports
    if filename.endswith(".py"):
        try:
            patched_tree = ast.parse(patched_str, filename=filename)
        except SyntaxError:
            violations.append("AST_VETO_PYTHON_SYNTAX_ERROR")
            patched_tree = None

        if patched_tree is not None and orig_str.strip():
            try:
                orig_tree = ast.parse(orig_str, filename=filename)
            except SyntaxError:
                orig_tree = None

            if orig_tree is not None:
                orig_funcs = {
                    node.name
                    for node in ast.walk(orig_tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                patched_funcs = {
                    node.name
                    for node in ast.walk(patched_tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                deleted_funcs = sorted(orig_funcs - patched_funcs)
                if deleted_funcs:
                    violations.append(f"AST_VETO_DELETED_EXISTING_FUNCTIONS:{','.join(deleted_funcs)}")

                orig_imports = {
                    node.names[0].name
                    for node in ast.walk(orig_tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names
                }
                patched_imports = {
                    node.names[0].name
                    for node in ast.walk(patched_tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names
                }
                if orig_imports and not patched_imports:
                    violations.append("AST_VETO_WIPED_ALL_MODULE_IMPORTS")

    return {
        "ast_integrity_passed": len(violations) == 0,
        "filename": filename,
        "violations": violations,
    }


def score_agent_human_tier(
    text: str,
    triggered_veto_codes: Optional[Sequence[str]] = None,
    bot_archetype: str = "",
    event_type: str = "issue_comment",
    inter_comment_delta_seconds: Optional[float] = None,
    detected_bot_risk_pct: int = 0,
) -> Dict[str, Any]:
    """
    5-Dimension (`D1..D5`) & 5-Tier Behavioral Classifier.
    Returns both the Human Alignment Score (`0–100`) and the Agent Tier classification (`TIER_0`..`TIER_5`).
    """
    codes = set(triggered_veto_codes or [])
    if not codes and detected_bot_risk_pct == 0:
        out_check = verify_human_grade_output(text)
        codes = set(out_check["veto_codes"])
        detected_bot_risk_pct = int(out_check["bot_suspicion_risk_pct"])

    if not codes and detected_bot_risk_pct < 25:
        return {
            "is_automated_bot": False,
            "tier_level": 0,
            "tier_id": "TIER_0_VERIFIED_HUMAN_ENGINEER",
            "label_name": "✅ Human-Grade: Senior-Engineer [A:95-100%]",
            "human_alignment_score": 100 - detected_bot_risk_pct,
            "composite_bot_risk_score": detected_bot_risk_pct,
            "sophistication_index": 98,
            "dimension_risk_scores": {
                "D1_context_and_ast_grounding_deficit": 0,
                "D2_prompt_and_canary_susceptibility": 0,
                "D3_cadence_and_workflow_violation": 0,
                "D4_cli_and_git_artifact_corruption": 0,
                "D5_self_disclosure_and_monetary_chatter": 0,
            },
        }

    # Determine Tier 1..5 based on behavioral archetype, event type, and triggered signals
    norm_text = _normalize_text(text)
    if (
        event_type == "fork_reconnaissance"
        or "BOT_AUTOMATED_CRON_FORK_RECONNAISSANCE" in codes
        or bot_archetype == "ARCHETYPE_D_STRING_CONCAT_ECHO_SCRIPT"
        or ("ARCHETYPE_I" in bot_archetype and "ForkEvent" in norm_text)
    ):
        tier_level = 1
        sophistication = 15
        dim_scores = {
            "D1_context_and_ast_grounding_deficit": 25,
            "D2_prompt_and_canary_susceptibility": 25,
            "D3_cadence_and_workflow_violation": 20,
            "D4_cli_and_git_artifact_corruption": 15,
            "D5_self_disclosure_and_monetary_chatter": 15,
        }
    elif (
        "BOT_UNFILLED_TEMPLATE_PLACEHOLDER" in codes
        or bot_archetype in ("ARCHETYPE_B_UNFILLED_PLACEHOLDER_SYBIL_BOT", "ARCHETYPE_C_ZERO_SPEC_BLIND_PRAISE_BOT")
    ):
        tier_level = 2
        sophistication = 34
        dim_scores = {
            "D1_context_and_ast_grounding_deficit": 25,
            "D2_prompt_and_canary_susceptibility": 24,
            "D3_cadence_and_workflow_violation": 18,
            "D4_cli_and_git_artifact_corruption": 15,
            "D5_self_disclosure_and_monetary_chatter": 14,
        }
    elif (
        "BOT_TRIGGERED_HIDDEN_CANARY_TOKEN" in codes
        or "BOT_TRIGGERED_HTML_COMMENT_CANARY" in codes
        or bot_archetype == "ARCHETYPE_E_HONEYPOT_OBEDIENT_LLM_BOT"
    ):
        tier_level = 3
        sophistication = 50
        dim_scores = {
            "D1_context_and_ast_grounding_deficit": 25,
            "D2_prompt_and_canary_susceptibility": 25,
            "D3_cadence_and_workflow_violation": 18,
            "D4_cli_and_git_artifact_corruption": 14,
            "D5_self_disclosure_and_monetary_chatter": 15,
        }
    elif (
        bot_archetype == "ARCHETYPE_A_META_PARROTING_LLM_AGENT"
        or (inter_comment_delta_seconds is not None and inter_comment_delta_seconds <= 10.0 and "src/" in norm_text)
    ):
        tier_level = 5
        sophistication = 86
        dim_scores = {
            "D1_context_and_ast_grounding_deficit": 10,
            "D2_prompt_and_canary_susceptibility": 22,
            "D3_cadence_and_workflow_violation": 18,
            "D4_cli_and_git_artifact_corruption": 13,
            "D5_self_disclosure_and_monetary_chatter": 15,
        }
    else:
        tier_level = 4
        sophistication = 72
        dim_scores = {
            "D1_context_and_ast_grounding_deficit": 18,
            "D2_prompt_and_canary_susceptibility": 20,
            "D3_cadence_and_workflow_violation": 20,
            "D4_cli_and_git_artifact_corruption": 15,
            "D5_self_disclosure_and_monetary_chatter": 14,
        }

    tier_spec = next(t for t in AGENT_SOPHISTICATION_TIERS if t["tier_level"] == tier_level)
    composite_risk = max(sum(dim_scores.values()), detected_bot_risk_pct, 90)
    composite_risk = min(100, composite_risk)
    return {
        "is_automated_bot": True,
        "tier_level": tier_level,
        "tier_id": tier_spec["tier_id"],
        "label_name": tier_spec["label_name"],
        "tier_name_vi": tier_spec["tier_name_vi"],
        "human_alignment_score": max(0, 100 - composite_risk),
        "composite_bot_risk_score": composite_risk,
        "sophistication_index": sophistication,
        "dimension_risk_scores": dim_scores,
    }
