"""
Intent Engine — P0 Planner + Task Templates
============================================
Converts structured development intents into executable plans.

Layers:
  P0: Planner + Task Templates (this package)
  P1: Impact Analyzer (future)
  P3: Interpreter (future)
  P4: Resolver (future)

Naming note: `intent/` (singular, this package) is the Intent ENGINE
(Intent -> DevelopmentPlan via models/planner/impact). The sibling
`intents/` (plural) is the PUBLIC intent API (create_executable_command,
create_feature, ...). They differ by one letter — do not confuse them.
"""

from intent.models import ActionStep, DevelopmentPlan, ImpactReport, Intent, IntentType, Severity
from intent.planner import Planner, merge_plans, plan, plan_batch
from intent.impact import analyze, analyze_batch
