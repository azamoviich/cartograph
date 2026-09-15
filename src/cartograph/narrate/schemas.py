"""Structured LLM output schemas.

The core anti-hallucination mechanism lives in these shapes, not in a
regex pass afterwards: a "dependency claim" is a structured
{target_cluster, reason} pair rather than free prose, so the model
cannot narrate a relationship without naming the specific cluster it
claims a relationship with — and that name is checked against the real
graph edges after the fact. Free text is only allowed where nothing
downstream depends on it being grounded (the overview summary).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FileNote(BaseModel):
    """L0 output: one sentence, only requested for high-centrality files with no docstring."""

    module: str
    one_liner: str = Field(max_length=240)


class DependencyClaim(BaseModel):
    """A claim that this cluster relates to another named cluster, for a stated reason."""

    target_cluster: str
    reason: str = Field(max_length=200)


class ClusterSummary(BaseModel):
    """L1 output: one cluster's role, grounded against its real graph neighbors."""

    cluster: str
    role: str = Field(max_length=600)
    provides_to: list[DependencyClaim] = Field(default_factory=list)
    depends_on: list[DependencyClaim] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class RepoOverview(BaseModel):
    """L2 output: the whole-repo summary, built only from L1 summaries and graph facts.

    Entry points are deliberately not an LLM field — they're a
    deterministic graph fact (in-degree-0 clusters) attached separately
    in the final report rather than asked of the model.
    """

    summary: str = Field(max_length=1200)
    key_subsystems: list[str] = Field(default_factory=list)
    notable_risks: list[str] = Field(default_factory=list)
