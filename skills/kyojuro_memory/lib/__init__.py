"""kyojuro_memory.lib — Implementation modules for the kyojuro_memory skill.

Phase 1.1 implements the persistence layer (stores). Future phases will add:
- extractors  (Phase 1.2): LLM-based info extraction from user messages
- summarizer  (Phase 1.2): conversation summary
- nudges      (Phase 1.3): proactive notifications (supplement reminder, barometric, routine)
- analysis    (Phase 1.4): correlation detection between supplements / symptoms / routines

See ../DESIGN.md §3 for the full component layout.
"""

__version__ = "0.1.0-mvp-stores"
