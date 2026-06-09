"""Pipeline state management subpackage.

Provides JSON checkpoint files per stage so the agentic pipeline can be
resumed from any completed stage without re-running earlier ones.
"""

from .state import PipelineState, StageStatus, StageName

__all__ = ["PipelineState", "StageStatus", "StageName"]
