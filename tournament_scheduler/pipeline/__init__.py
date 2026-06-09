"""Pipeline state management subpackage.

Provides JSON checkpoint files per stage so the agentic pipeline can be
resumed from any completed stage without re-running earlier ones, plus
the ``TournamentUpdater`` for targeted post-generation modifications.
"""

from .state import PipelineState, StageStatus, StageName
from .tournament_updater import TournamentUpdater, UpdateResult

__all__ = ["PipelineState", "StageStatus", "StageName", "TournamentUpdater", "UpdateResult"]
