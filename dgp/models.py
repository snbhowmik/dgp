"""Data contract models, enumerations, and row definitions for Contract v1.0.0."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


class Tier(str, Enum):
    METRO = "metro"
    TIER1 = "tier1"
    TIER2 = "tier2"


class ProductLine(str, Enum):
    CULTIVATED_CHICKEN = "cultivated_chicken"
    MYCELIUM = "mycelium"
    SEAWEED = "seaweed"
    MICROBIAL = "microbial"


class SkuStatus(str, Enum):
    RND = "rnd"
    PILOT = "pilot"
    PRODUCTION = "production"
    RETIRED = "retired"


class Channel(str, Enum):
    D2C = "D2C"
    B2B = "B2B"


class OrderStatus(str, Enum):
    FULFILLED = "fulfilled"
    PARTIAL = "partial"
    WAITLISTED = "waitlisted"
    CANCELLED_STOCKOUT = "cancelled_stockout"
    CANCELLED_OTHER = "cancelled_other"


class BatchOutcome(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class B2BAccountType(str, Enum):
    RESTAURANT = "restaurant"
    QSR_CHAIN = "qsr_chain"
    HOTEL = "hotel"
    CATERER = "caterer"
    DISTRIBUTOR = "distributor"
    OTHER = "other"


class B2BAccountStatus(str, Enum):
    ACTIVE = "active"
    PIPELINE = "pipeline"
    CHURNED = "churned"
    PAUSED = "paused"


class CampaignType(str, Enum):
    PPC = "ppc"
    NATIVE = "native"
    SOCIAL = "social"
    INFLUENCER = "influencer"
    EMAIL = "email"
    TRADE = "trade"


# -------------------------------------------------------------------------
# Row Dataclasses matching Contract v1.0.0
# -------------------------------------------------------------------------

@dataclass
class RegionRow:
    region_id: str
    region_name: str
    tier: str
    cold_chain_available: bool

    def to_csv_dict(self) -> dict:
        return {
            "region_id": self.region_id,
            "region_name": self.region_name,
            "tier": self.tier,
            "cold_chain_available": "true" if self.cold_chain_available else "false",
        }


@dataclass
class SkuRow:
    sku_id: str
    product_line: str
    pack_size_kg: float
    status: str
    expected_launch_date: Optional[str]
    shelf_life_days: int
    unit_cost_inr_per_kg: float
    list_price_d2c_inr_per_kg: float

    def to_csv_dict(self) -> dict:
        return {
            "sku_id": self.sku_id,
            "product_line": self.product_line,
            "pack_size_kg": f"{self.pack_size_kg:.4f}".rstrip("0").rstrip("."),
            "status": self.status,
            "expected_launch_date": self.expected_launch_date or "",
            "shelf_life_days": str(self.shelf_life_days),
            "unit_cost_inr_per_kg": f"{self.unit_cost_inr_per_kg:.2f}",
            "list_price_d2c_inr_per_kg": f"{self.list_price_d2c_inr_per_kg:.2f}",
        }


@dataclass
class ProductMatrixRow:
    sku_id: str
    channel: str
    region_id: str
    eligible_from: str
    eligible_to: Optional[str]

    def to_csv_dict(self) -> dict:
        return {
            "sku_id": self.sku_id,
            "channel": self.channel,
            "region_id": self.region_id,
            "eligible_from": self.eligible_from,
            "eligible_to": self.eligible_to or "",
        }


@dataclass
class OrderRow:
    order_id: str
    order_date: str
    channel: str
    region_id: str
    sku_id: str
    customer_id: Optional[str]
    account_id: Optional[str]
    requested_qty_kg: float
    fulfilled_qty_kg: float
    unit_price_inr: float
    status: str
    promised_date: str
    delivered_date: Optional[str]

    def to_csv_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "order_date": self.order_date,
            "channel": self.channel,
            "region_id": self.region_id,
            "sku_id": self.sku_id,
            "customer_id": self.customer_id or "",
            "account_id": self.account_id or "",
            "requested_qty_kg": f"{self.requested_qty_kg:.4f}".rstrip("0").rstrip("."),
            "fulfilled_qty_kg": f"{self.fulfilled_qty_kg:.4f}".rstrip("0").rstrip("."),
            "unit_price_inr": f"{self.unit_price_inr:.2f}",
            "status": self.status,
            "promised_date": self.promised_date,
            "delivered_date": self.delivered_date or "",
        }


@dataclass
class CapacityBatchRow:
    batch_id: str
    start_date: str
    end_date: str
    facility_id: str
    product_line: str
    planned_yield_kg: float
    actual_yield_kg: float
    outcome: str

    def to_csv_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "facility_id": self.facility_id,
            "product_line": self.product_line,
            "planned_yield_kg": f"{self.planned_yield_kg:.2f}",
            "actual_yield_kg": f"{self.actual_yield_kg:.2f}",
            "outcome": self.outcome,
        }


@dataclass
class CapacityPlanRow:
    week_start: str
    facility_id: str
    product_line: str
    planned_batches: int
    planned_yield_per_batch_kg: float

    def to_csv_dict(self) -> dict:
        return {
            "week_start": self.week_start,
            "facility_id": self.facility_id,
            "product_line": self.product_line,
            "planned_batches": str(self.planned_batches),
            "planned_yield_per_batch_kg": f"{self.planned_yield_per_batch_kg:.2f}",
        }


@dataclass
class ComanContractRow:
    coman_id: str
    product_line: str
    available_from: str
    lead_time_weeks: int
    min_commit_kg_per_week: float
    max_kg_per_week: float
    unit_cost_inr_per_kg: float
    min_active_weeks: int

    def to_csv_dict(self) -> dict:
        return {
            "coman_id": self.coman_id,
            "product_line": self.product_line,
            "available_from": self.available_from,
            "lead_time_weeks": str(self.lead_time_weeks),
            "min_commit_kg_per_week": f"{self.min_commit_kg_per_week:.2f}",
            "max_kg_per_week": f"{self.max_kg_per_week:.2f}",
            "unit_cost_inr_per_kg": f"{self.unit_cost_inr_per_kg:.2f}",
            "min_active_weeks": str(self.min_active_weeks),
        }


@dataclass
class ComanActivityRow:
    coman_id: str
    week_start: str
    requested_kg: float
    delivered_kg: float

    def to_csv_dict(self) -> dict:
        return {
            "coman_id": self.coman_id,
            "week_start": self.week_start,
            "requested_kg": f"{self.requested_kg:.2f}",
            "delivered_kg": f"{self.delivered_kg:.2f}",
        }


@dataclass
class B2BAccountRow:
    account_id: str
    account_type: str
    region_id: str
    regions_served: str
    outlets_count: int
    status: str
    onboarded_date: Optional[str]
    contract_start: Optional[str]
    contract_end: Optional[str]
    committed_kg_per_month: Optional[float]
    contract_price_inr_per_kg: Optional[float]
    shortfall_penalty_inr_per_kg: Optional[float]
    requested_start_date: Optional[str]
    requested_kg_per_month: Optional[float]

    def to_csv_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "account_type": self.account_type,
            "region_id": self.region_id,
            "regions_served": self.regions_served,
            "outlets_count": str(self.outlets_count),
            "status": self.status,
            "onboarded_date": self.onboarded_date or "",
            "contract_start": self.contract_start or "",
            "contract_end": self.contract_end or "",
            "committed_kg_per_month": f"{self.committed_kg_per_month:.2f}" if self.committed_kg_per_month is not None else "",
            "contract_price_inr_per_kg": f"{self.contract_price_inr_per_kg:.2f}" if self.contract_price_inr_per_kg is not None else "",
            "shortfall_penalty_inr_per_kg": f"{self.shortfall_penalty_inr_per_kg:.2f}" if self.shortfall_penalty_inr_per_kg is not None else "",
            "requested_start_date": self.requested_start_date or "",
            "requested_kg_per_month": f"{self.requested_kg_per_month:.2f}" if self.requested_kg_per_month is not None else "",
        }


@dataclass
class MarketingDailyRow:
    date: str
    region_id: str
    channel: str
    campaign_type: str
    campaign_id: str
    spend_inr: float
    impressions: int
    clicks: int
    unique_visitors: int
    bounces: int
    leads: int
    qualified_leads: int
    conversions: int
    attributed_revenue_inr: float

    def to_csv_dict(self) -> dict:
        return {
            "date": self.date,
            "region_id": self.region_id,
            "channel": self.channel,
            "campaign_type": self.campaign_type,
            "campaign_id": self.campaign_id,
            "spend_inr": f"{self.spend_inr:.2f}",
            "impressions": str(self.impressions),
            "clicks": str(self.clicks),
            "unique_visitors": str(self.unique_visitors),
            "bounces": str(self.bounces),
            "leads": str(self.leads),
            "qualified_leads": str(self.qualified_leads),
            "conversions": str(self.conversions),
            "attributed_revenue_inr": f"{self.attributed_revenue_inr:.2f}",
        }


@dataclass
class MarketingPlanRow:
    week_start: str
    region_id: str
    channel: str
    campaign_type: str
    planned_spend_inr: float

    def to_csv_dict(self) -> dict:
        return {
            "week_start": self.week_start,
            "region_id": self.region_id,
            "channel": self.channel,
            "campaign_type": self.campaign_type,
            "planned_spend_inr": f"{self.planned_spend_inr:.2f}",
        }


@dataclass
class CustomerRow:
    customer_id: str
    region_id: str
    acquired_date: str
    acquisition_campaign_type: Optional[str]
    persona_segment: str
    churned_date: Optional[str]
    is_subscriber: bool

    def to_csv_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "region_id": self.region_id,
            "acquired_date": self.acquired_date,
            "acquisition_campaign_type": self.acquisition_campaign_type or "",
            "persona_segment": self.persona_segment,
            "churned_date": self.churned_date or "",
            "is_subscriber": "true" if self.is_subscriber else "false",
        }


@dataclass
class NpsResponseRow:
    response_date: str
    channel: str
    region_id: str
    customer_or_account_id: str
    score: int

    def to_csv_dict(self) -> dict:
        return {
            "response_date": self.response_date,
            "channel": self.channel,
            "region_id": self.region_id,
            "customer_or_account_id": self.customer_or_account_id,
            "score": str(self.score),
        }
