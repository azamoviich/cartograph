"""Drop any claim that names something outside the facts it was given.

This is the mechanical half of anti-hallucination: the schema forces a
dependency claim to name a specific cluster, and this strips any claim
naming a cluster that isn't an actual graph neighbor — regardless of how
plausible the model's stated reason sounds.
"""

from __future__ import annotations

from cartograph.narrate.schemas import ClusterSummary, RepoOverview


def enforce_cluster_citations(summary: ClusterSummary, valid_neighbors: set[str]) -> ClusterSummary:
    return summary.model_copy(
        update={
            "provides_to": [c for c in summary.provides_to if c.target_cluster in valid_neighbors],
            "depends_on": [c for c in summary.depends_on if c.target_cluster in valid_neighbors],
        }
    )


def enforce_overview_citations(overview: RepoOverview, valid_clusters: set[str]) -> RepoOverview:
    return overview.model_copy(
        update={
            "key_subsystems": [c for c in overview.key_subsystems if c in valid_clusters],
        }
    )
