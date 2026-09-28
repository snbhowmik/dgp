"""Marketing funnel simulation: spend, daily performance, conversions, and platform attribution."""

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Tuple
from dgp.config import MarketingChannelConfig
from dgp.models import MarketingDailyRow, MarketingPlanRow, Channel, CampaignType


@dataclass
class DailyMarketingOutput:
    csv_rows: List[MarketingDailyRow]
    d2c_new_conversions: List[Tuple[str, str, str, str]]  # (region_id, campaign_type, campaign_id, date)
    b2b_leads: List[Tuple[str, str, str, str]]  # (region_id, campaign_type, campaign_id, date)


class MarketingEngine:
    """Simulates daily ad-platform auctions, impressions, clicks, visitors, leads, and conversions."""

    def __init__(
        self,
        campaigns: List[MarketingChannelConfig],
        region_ids: List[str],
        rng: random.Random,
    ):
        self.campaigns = campaigns
        self.region_ids = region_ids
        self.rng = rng
        self.campaign_counter = 100

    def generate_marketing_plan(
        self,
        all_mondays: List[date],
        region_weights: Dict[str, float],
    ) -> List[MarketingPlanRow]:
        """Generate weekly marketing plan across regions and campaign types for history + forward horizon."""
        plan_rows: List[MarketingPlanRow] = []

        for monday in all_mondays:
            # Indian festive bump (e.g., Q4 Oct-Dec)
            month = monday.month
            seasonal_spend_boost = 1.25 if month in [10, 11, 12] else (0.90 if month in [6, 7] else 1.0)

            for camp in self.campaigns:
                for r_id in self.region_ids:
                    w = region_weights.get(r_id, 1.0)
                    planned = camp.base_weekly_spend_inr * w * seasonal_spend_boost
                    plan_rows.append(
                        MarketingPlanRow(
                            week_start=monday.isoformat(),
                            region_id=r_id,
                            channel=camp.channel,
                            campaign_type=camp.campaign_type,
                            planned_spend_inr=round(planned, 2),
                        )
                    )
        return plan_rows

    def simulate_daily(
        self,
        current_date: date,
        daily_planned_spend: Dict[Tuple[str, str, str], float],
        stockout_penalty_by_region: Dict[str, float],
        growth_multiplier: float = 1.0,
        avg_order_value: float = 850.0,
    ) -> DailyMarketingOutput:
        """
        Simulate one day of marketing across active campaigns and regions.
        daily_planned_spend is keyed by (region_id, channel, campaign_type).
        """
        csv_rows: List[MarketingDailyRow] = []
        d2c_conversions: List[Tuple[str, str, str, str]] = []
        b2b_leads: List[Tuple[str, str, str, str]] = []

        is_weekend = current_date.weekday() >= 5

        for camp in self.campaigns:
            for r_id in self.region_ids:
                key = (r_id, camp.channel, camp.campaign_type)
                base_daily = daily_planned_spend.get(key, camp.base_weekly_spend_inr / 7.0)

                # Day of week variation: D2C spends slightly more on weekends, B2B spends on weekdays
                if camp.channel == "D2C":
                    dow_mult = 1.20 if is_weekend else 0.92
                else:
                    dow_mult = 0.50 if is_weekend else 1.20

                # Marketing team closed loop response: throttle spend in regions experiencing persistent stockouts
                stockout_suppression = max(0.40, 1.0 - 0.5 * stockout_penalty_by_region.get(r_id, 0.0))
                
                # Actual spend fluctuates slightly around daily plan (+/- 5%)
                spend_jitter = self.rng.uniform(0.95, 1.05)
                spend_inr = round(base_daily * dow_mult * stockout_suppression * spend_jitter, 2)

                if spend_inr < 5.0:
                    # Mild real-world messiness: zero spend day
                    spend_inr = 0.0
                    impressions = 0
                    clicks = 0
                    unique_visitors = 0
                    bounces = 0
                    leads = 0
                    qualified_leads = 0
                    conversions = 0
                    attributed_revenue_inr = 0.0
                else:
                    # Impressions derived from CPM
                    cpm = self.rng.uniform(180.0, 320.0) if camp.campaign_type == "social" else self.rng.uniform(250.0, 450.0)
                    impressions = max(1, int((spend_inr / cpm) * 1000))

                    # Clicks derived from CPC or CTR
                    cpc = max(5.0, camp.cost_per_click_inr * self.rng.uniform(0.9, 1.15))
                    clicks = max(1, int(spend_inr / cpc))

                    # Ensure clicks <= impressions
                    clicks = min(clicks, impressions)

                    # Unique visitors (click to visitor conversion, factoring bot traffic / drop-off)
                    visitor_rate = min(0.95, max(0.60, camp.click_to_visitor_rate * self.rng.uniform(0.95, 1.05)))
                    unique_visitors = max(1, int(clicks * visitor_rate))
                    unique_visitors = min(unique_visitors, clicks)

                    # Bounces (strictly <= unique_visitors)
                    bounce_rate = min(0.85, max(0.15, camp.bounce_rate * self.rng.uniform(0.90, 1.10)))
                    bounces = int(unique_visitors * bounce_rate)
                    bounces = min(bounces, unique_visitors)

                    # Engaged visitors available for leads
                    engaged_visitors = unique_visitors - bounces

                    # Leads (strictly <= engaged_visitors = unique_visitors - bounces)
                    lead_rate = min(0.60, camp.lead_conversion_rate * growth_multiplier * self.rng.uniform(0.85, 1.15))
                    leads = int(engaged_visitors * lead_rate)
                    leads = min(leads, engaged_visitors)

                    # Qualified leads (strictly <= leads)
                    ql_rate = min(0.95, camp.qualified_lead_rate * self.rng.uniform(0.90, 1.10))
                    qualified_leads = int(leads * ql_rate)
                    qualified_leads = min(qualified_leads, leads)

                    # Conversions (strictly <= leads, typically a subset of qualified leads)
                    conv_rate = min(0.80, camp.sale_conversion_rate * self.rng.uniform(0.85, 1.15))
                    conversions = int(qualified_leads * conv_rate)
                    conversions = min(conversions, qualified_leads)

                    # Attributed revenue (platform reported, with standard attribution model window & overlap)
                    # Platform claims credit for conversions * average order value * inflation factor
                    attributed_revenue_inr = round(
                        conversions * avg_order_value * camp.attribution_inflation * self.rng.uniform(0.90, 1.15), 2
                    )

                csv_rows.append(
                    MarketingDailyRow(
                        date=current_date.isoformat(),
                        region_id=r_id,
                        channel=camp.channel,
                        campaign_type=camp.campaign_type,
                        campaign_id=camp.campaign_id,
                        spend_inr=spend_inr,
                        impressions=impressions,
                        clicks=clicks,
                        unique_visitors=unique_visitors,
                        bounces=bounces,
                        leads=leads,
                        qualified_leads=qualified_leads,
                        conversions=conversions,
                        attributed_revenue_inr=attributed_revenue_inr,
                    )
                )

                if conversions > 0:
                    if camp.channel == "D2C":
                        for _ in range(conversions):
                            d2c_conversions.append((r_id, camp.campaign_type, camp.campaign_id, current_date.isoformat()))
                    else:
                        for _ in range(conversions):
                            b2b_leads.append((r_id, camp.campaign_type, camp.campaign_id, current_date.isoformat()))

        return DailyMarketingOutput(
            csv_rows=csv_rows,
            d2c_new_conversions=d2c_conversions,
            b2b_leads=b2b_leads,
        )
