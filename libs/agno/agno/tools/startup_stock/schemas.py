"""Structured output schemas for startup stock agents."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class InvestorOwnership(BaseModel):
    investor_name: str
    wallet_address: str
    shares: float
    ownership_pct: float
    status: str = "pending"


class DilutionImpact(BaseModel):
    scenario_name: str
    new_shares: float
    option_pool_increase: float = 0.0
    post_money_total: float
    investors: List[InvestorOwnership]


class VestingSummary(BaseModel):
    beneficiary: str
    total_shares: float
    vested_shares: float
    releasable_shares: float
    revoked: bool = False


class EquityIntelligenceReport(BaseModel):
    """Structured report for equity intelligence agents."""

    summary: str = Field(description="Executive summary of cap table health")
    token_symbol: str = Field(description="Token ticker symbol")
    total_investors: int
    total_shares: float
    sync_health: str = Field(description="Overall sync status: healthy, pending, or drifted")
    pending_sync_count: int = 0
    drift_count: int = 0
    vesting_schedules: List[VestingSummary] = Field(default_factory=list)
    dilution_scenarios: List[DilutionImpact] = Field(default_factory=list)
    public_comparisons: List[str] = Field(
        default_factory=list,
        description="Public market comparisons from finance tools",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Actionable recommendations for founders",
    )


class PipelineStatus(BaseModel):
    """End-to-end pipeline checkpoint status."""

    step: str
    status: str
    detail: Optional[str] = None
