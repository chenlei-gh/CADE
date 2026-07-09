"""
Optimizer — Score and rank development plans.
===============================================
Takes multiple DevelopmentPlans (alternatives or merged subsets)
and scores them to produce a ranked, recommended execution order.

P2: Layer on top of Planner + Impact Analyzer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from intent.models import DevelopmentPlan, Severity

# Scoring weights (sum = 100)
WEIGHTS = {
    "impact": 35,      # How much does this change affect the workspace?
    "risk": 30,        # How likely is this to break something?
    "simplicity": 20,  # Fewer steps = better
    "reuse": 15,       # Reuse existing interfaces/components?
}

# Severity → numeric penalty (higher = worse)
SEVERITY_PENALTY = {
    Severity.NONE: 0,
    Severity.LOW: 10,
    Severity.MEDIUM: 30,
    Severity.HIGH: 60,
    Severity.CRITICAL: 100,
}


def score_plan(plan: DevelopmentPlan, context: dict = None) -> dict:
    """
    Score a single plan from 0 (worst) to 100 (best).

    Returns breakdown of each factor.
    """
    scores = {}

    # Impact score (lower impact = higher score)
    impact_penalty = SEVERITY_PENALTY.get(plan.risk_level, 10)
    scores["impact"] = max(0, 100 - impact_penalty)

    # Risk score (fewer risky steps = higher score)
    risky_steps = [s for s in plan.steps
                   if s.action in ("create_interface", "modify_interface",
                                   "delete_command", "delete_module")]
    risk_ratio = len(risky_steps) / max(len(plan.steps), 1)
    scores["risk"] = max(0, 100 - int(risk_ratio * 100))

    # Simplicity score (fewer steps = better, normalized to 100)
    step_penalty = min(len(plan.steps) * 2, 100)
    scores["simplicity"] = max(0, 100 - step_penalty)

    # Reuse score (plans that reuse existing entities score higher)
    reuse_count = sum(1 for s in plan.steps
                      if s.action in ("ensure_module", "ensure_framework"))
    scores["reuse"] = min(100, reuse_count * 25)

    # Weighted total
    total = sum(scores[k] * WEIGHTS[k] / 100 for k in WEIGHTS)
    scores["total"] = round(total, 1)

    return scores


def optimize(plans: List[DevelopmentPlan], context: dict = None) -> List[dict]:
    """
    Score all plans and return ranked list with comparison data.

    Returns list of {plan, scores, rank} sorted by total descending.
    """
    if not plans:
        return []

    ranked = []
    for plan in plans:
        s = score_plan(plan, context)
        plan_detail = plan.to_dict()
        plan_detail["scores"] = s
        ranked.append(plan_detail)

    # Sort by total score descending
    ranked.sort(key=lambda x: x["scores"]["total"], reverse=True)

    # Assign ranks
    for i, item in enumerate(ranked):
        item["rank"] = i + 1

    return ranked


def recommend(plans: List[DevelopmentPlan], context: dict = None) -> Optional[dict]:
    """
    Return the single best plan with reasoning.

    Returns None if no plans provided.
    """
    ranked = optimize(plans, context)
    if not ranked:
        return None

    best = ranked[0]
    reason = _reason(best, ranked)

    return {
        "plan": best,
        "reason": reason,
        "alternatives_count": len(ranked) - 1,
        "score_margin": (
            round(best["scores"]["total"] - ranked[1]["scores"]["total"], 1)
            if len(ranked) > 1 else 0
        ),
    }


def compare(plans: List[DevelopmentPlan]) -> str:
    """
    Generate a human-readable comparison table of all plans.
    """
    ranked = optimize(plans)
    if not ranked:
        return "No plans to compare."

    lines = [
        f"{'Rank':<5} {'Intent':<30} {'Steps':<6} {'Risk':<10} {'Score':<7}",
        "-" * 60,
    ]
    for item in ranked:
        intent_name = item["intent"].get("name", "?")
        risk = item.get("risk_level", "low")
        lines.append(
            f"#{item['rank']:<4} {intent_name:<30} "
            f"{item['step_count']:<6} {risk:<10} {item['scores']['total']:<7}"
        )
    return "\n".join(lines)


# ─── Helpers ────────────────────────────────────────────────────

def _reason(best: dict, all_ranked: List[dict]) -> str:
    """Generate natural-language reasoning for the recommendation."""
    scores = best["scores"]
    intent_name = best["intent"].get("name", "this plan")
    risk = best.get("risk_level", "low")

    reasons = [f"✅ Recommended: {intent_name} (score: {scores['total']})"]

    # Strongest scoring factor
    factors = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for name, val in factors[:2]:
        if name != "total" and val >= 80:
            reasons.append(f"   • Strong {name}: {val}/100")

    # Risk note
    if risk in ("high", "critical", "CRITICAL", "HIGH"):
        reasons.append(f"   ⚠ High risk ({risk}) — snapshot before executing")

    # Margin note
    if len(all_ranked) > 1:
        margin = round(best["scores"]["total"] - all_ranked[1]["scores"]["total"], 1)
        reasons.append(f"   • Margin over #2: {margin} pts")

    return "\n".join(reasons)
