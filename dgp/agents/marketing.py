"""Simulated marketing team agent: closed-loop adjustments, budget reallocation, and campaign planning."""

import random
from datetime import date
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
        # Current daily spend target by (region_id, channel, campaign_type)
        self.current_targets: Dict[Tuple[str, str, str], float] = {}

        for camp in campaign_configs:
            for r_id in region_ids:
                self.current_targets[(r_id, camp.channel, camp.campaign_type)] = camp.base_weekly_spend_inr / 7.0

    def closed_loop_weekly_review(
        self,
        recent_cpa_by_campaign: Dict[Tuple[str, str, str], float],
        stockout_rates_by_region: Dict[str, float],
    ):
        """
        Closed loop behavior:
        1. Throttle budgets in regions experiencing high stockout rates (don't waste marketing dollars on out-of-stock items).
        2. Shift budget toward campaigns with lower CPA and higher lead quality.
        """
        for (r_id, ch, c_type), target in list(self.current_targets.items()):
            stockout_rate = stockout_rates_by_region.get(r_id, 0.0)
            
            # If stockout is severe (>20%), cut budget by 10-25%
            if stockout_rate > 0.20:
                adjustment = max(0.60, 1.0 - stockout_rate * 0.5)
                self.current_targets[(r_id, ch, c_type)] = target * adjustment
            elif stockout_rate < 0.05:
                # Capacity is healthy; if campaign CPA is strong, gradually scale up budget (+3-8%)
                cpa = recent_cpa_by_campaign.get((r_id, ch, c_type), 500.0)
                if cpa < 400.0:
                    self.current_targets[(r_id, ch, c_type)] = min(target * 1.08, target * 2.0)
                elif cpa > 1200.0:
                    # Expensive CAC; trim budget slightly
                    self.current_targets[(r_id, ch, c_type)] = max(target * 0.92, target * 0.4)

    def get_daily_spend_targets(self) -> Dict[Tuple[str, str, str], float]:
        return dict(self.current_targets)
