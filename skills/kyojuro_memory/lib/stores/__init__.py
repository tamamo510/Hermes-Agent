"""kyojuro_memory.lib.stores — Persistent stores for structured memory.

Each store is a thin SQLite wrapper backed by a single database file under
`../../stores/`. Stores are independent and can be used standalone.

Phase 1.1 (this PR) covers:
- SupplementStore: F-1 supplement intake records
- SymptomStore:    F-2 symptom timeline (with severity validation, resolution tracking)
- RoutineStore:    F-3 lifestyle pattern events (with JSON details)

Future phases will add:
- conversation_log_store (Phase 1.2)
- triggers_store, barometric_store, correlations_store (Phase 1.3-1.4)

See ../../DESIGN.md §2 for schemas and §6 for phase rollout.
"""

from .routine_store import RoutineStore
from .supplement_store import SupplementStore
from .symptom_store import SymptomStore

__all__ = ["RoutineStore", "SupplementStore", "SymptomStore"]
