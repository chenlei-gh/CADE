"""
Intent Engine — P0 Planner + Task Templates
============================================
Converts structured development intents into executable plans.

Layers:
  P0: Planner + Task Templates (this package)
  P1: Impact Analyzer (future)
  P2: Optimizer (future)
  P3: Interpreter (future)
  P4: Resolver (future)
"""

from intent.models import ActionStep, DevelopmentPlan, ImpactReport, Intent, IntentType, Severity
from intent.planner import Planner, merge_plans, plan, plan_batch
from intent.impact import analyze, analyze_batch
from intent.optimizer import compare, optimize, recommend, score_plan
