"""World configuration models and loader."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class RegionConfig:
    region_id: str
    region_name: str
    tier: str  # metro, tier1, tier2
    cold_chain_available: bool
    market_weight: float = 1.0


@dataclass
class SkuConfig:
    sku_id: str
    product_line: str
    pack_size_kg: float
    status: str  # rnd, pilot, production, retired
    expected_launch_date: Optional[str]
    shelf_life_days: int
    unit_cost_inr_per_kg: float
    list_price_d2c_inr_per_kg: float


@dataclass
class ProductMatrixRule:
    sku_id: str
    channel: str
    region_id: str  # or 'ALL', 'METRO_ONLY', 'COLD_CHAIN_ONLY'
    eligible_from: str
    eligible_to: Optional[str] = None


@dataclass
class FacilityConfig:
    facility_id: str
    product_line: str
    nominal_batches_per_week: int
    planned_yield_per_batch_kg: float
    cycle_days: int = 7
    failure_rate: float = 0.04
    partial_rate: float = 0.08
    yield_std_pct: float = 0.07


@dataclass
class ComanConfig:
    coman_id: str
    product_line: str
    available_from: str
    lead_time_weeks: int
    min_commit_kg_per_week: float
    max_kg_per_week: float
    unit_cost_inr_per_kg: float
    min_active_weeks: int
    reliability: float = 0.96


@dataclass
class MarketingChannelConfig:
    channel: str  # D2C or B2B
    campaign_type: str  # ppc, native, social, influencer, email, trade
    campaign_id: str
    base_weekly_spend_inr: float
    cost_per_click_inr: float
    click_to_visitor_rate: float = 0.85
    bounce_rate: float = 0.35
    lead_conversion_rate: float = 0.12
    qualified_lead_rate: float = 0.65
    sale_conversion_rate: float = 0.35
    attribution_inflation: float = 1.25  # Platform reported attribution multiplier


@dataclass
class B2BAccountTemplate:
    account_id: str
    account_type: str  # restaurant, qsr_chain, hotel, caterer, distributor, other
    region_id: str
    regions_served: List[str]
    outlets_count: int
    onboard_week_offset: int  # week when account joins
    contract_duration_weeks: int
    committed_kg_per_month: float
    contract_price_inr_per_kg: float
    shortfall_penalty_inr_per_kg: float
    status_at_end: str = "active"  # active, pipeline, churned, paused
    churn_week_offset: Optional[int] = None
    pause_week_start: Optional[int] = None
    pause_week_end: Optional[int] = None


@dataclass
class ShockEvent:
    name: str
    start_week: int
    duration_weeks: int
    event_type: str  # 'demand_surge', 'supply_disruption', 'viral_wom', 'pilot_launch', 'cold_chain_failure'
    impact_factor: float
    target_regions: Optional[List[str]] = None
    target_skus: Optional[List[str]] = None
    description: str = ""


@dataclass
class WorldConfig:
    world_name: str
    description: str
    history_weeks: int
    start_date: str  # YYYY-MM-DD (must be Monday)
    plan_weeks_ahead: int = 13
    
    # Dynamics parameters
    demand_growth_rate_annual: float = 0.15
    seasonality_sensitivity: float = 1.0
    wom_strength: float = 0.05
    d2c_repeat_rate: float = 0.40
    d2c_subscriber_fraction: float = 0.10
    ops_capacity_buffer: float = 1.15
    coman_activation_threshold: float = 0.85  # Capacity utilization triggering co-man
    marketing_responsiveness: float = 1.0
    nps_baseline: float = 8.5
    
    # Entities
    regions: List[RegionConfig] = field(default_factory=list)
    skus: List[SkuConfig] = field(default_factory=list)
    product_matrix_rules: List[ProductMatrixRule] = field(default_factory=list)
    facilities: List[FacilityConfig] = field(default_factory=list)
    coman_contracts: List[ComanConfig] = field(default_factory=list)
    marketing_campaigns: List[MarketingChannelConfig] = field(default_factory=list)
    b2b_accounts: List[B2BAccountTemplate] = field(default_factory=list)
    shocks: List[ShockEvent] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldConfig":
        regions = [RegionConfig(**r) for r in data.get("regions", [])]
        skus = [SkuConfig(**s) for s in data.get("skus", [])]
        matrix = [ProductMatrixRule(**m) for m in data.get("product_matrix_rules", [])]
        facilities = [FacilityConfig(**f) for f in data.get("facilities", [])]
        coman = [ComanConfig(**c) for c in data.get("coman_contracts", [])]
        mktg = [MarketingChannelConfig(**m) for m in data.get("marketing_campaigns", [])]
        b2b = [B2BAccountTemplate(**b) for b in data.get("b2b_accounts", [])]
        shocks = [ShockEvent(**s) for s in data.get("shocks", [])]

        return cls(
            world_name=data["world_name"],
            description=data.get("description", ""),
            history_weeks=data["history_weeks"],
            start_date=data["start_date"],
            plan_weeks_ahead=data.get("plan_weeks_ahead", 13),
            demand_growth_rate_annual=data.get("demand_growth_rate_annual", 0.15),
            seasonality_sensitivity=data.get("seasonality_sensitivity", 1.0),
            wom_strength=data.get("wom_strength", 0.05),
            d2c_repeat_rate=data.get("d2c_repeat_rate", 0.40),
            d2c_subscriber_fraction=data.get("d2c_subscriber_fraction", 0.10),
            ops_capacity_buffer=data.get("ops_capacity_buffer", 1.15),
            coman_activation_threshold=data.get("coman_activation_threshold", 0.85),
            marketing_responsiveness=data.get("marketing_responsiveness", 1.0),
            nps_baseline=data.get("nps_baseline", 8.5),
            regions=regions,
            skus=skus,
            product_matrix_rules=matrix,
            facilities=facilities,
            coman_contracts=coman,
            marketing_campaigns=mktg,
            b2b_accounts=b2b,
            shocks=shocks,
        )

    @classmethod
    def load_yaml(cls, path: str) -> "WorldConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
