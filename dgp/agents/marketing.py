"""Simulated marketing team agent: closed-loop adjustments, budget reallocation, and campaign planning."""

import random
from typing import Dict, List, Tuple
from dgp.config import MarketingChannelConfig


class MarketingTeamAgent:
    """Simulates realistic marketing executive decision making."""

    def __init__(
        self,
        campaign_configs: List[MarketingChannelConfig],
        region_ids: List[str],
        rng: random.Random,
    ):
        self.campaign_configs = campaign_configs
        self.region_ids = region_ids
        self.rng = rng
        # Tactical multipliers around planned spend: bounded between 0.75 and 1.25
        self.tactical_multipliers: Dict[Tuple[str, str, str], float] = {
            (r_id, camp.channel, camp.campaign_type): 1.0
            for camp in campaign_configs
            for r_id in region_ids
        }

    def closed_loop_weekly_review(
        self,
        recent_cpa_by_campaign: Dict[Tuple[str, str, str], float],
        stockout_rates_by_region: Dict[str, float],
    ):
        """
        Closed loop behavior:
        1. In regions with persistent stockouts, temporarily reduce spend by 10-25%
           (multiplier ~0.75-0.90) to avoid spending marketing budget on unfulfillable demand.
        2. In regions with healthy inventory, shift budget slightly toward high-efficiency campaigns.
        3. Realized spend is always anchored to planned spend and never collapses or decays to zero.
        """
        for (r_id, ch, c_type), current_mult in list(self.tactical_multipliers.items()):
            stockout_rate = stockout_rates_by_region.get(r_id, 0.0)

            if stockout_rate > 0.15:
                target_mult = max(0.75, 1.0 - stockout_rate * 0.4)
            elif stockout_rate < 0.05:
                cpa = recent_cpa_by_campaign.get((r_id, ch, c_type), 500.0)
                if cpa < 380.0:
                    target_mult = min(1.25, current_mult + 0.05)
                elif cpa > 850.0:
                    target_mult = max(0.85, current_mult - 0.05)
                else:
                    target_mult = 1.0
            else:
                target_mult = 1.0

            # Smooth exponential moving average update
            self.tactical_multipliers[(r_id, ch, c_type)] = round(
                0.70 * current_mult + 0.30 * target_mult, 3
            )

    def get_spend_multiplier(self, region_id: str, channel: str, campaign_type: str) -> float:
        """Return tactical multiplier for the specified campaign and region."""
        return self.tactical_multipliers.get((region_id, channel, campaign_type), 1.0)
