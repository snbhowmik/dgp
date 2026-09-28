"""Simulated operations team agent: capacity balancing, co-man scheduling, and lead time management."""

from datetime import date, timedelta
from typing import Dict, List, Optional
from dgp.config import ComanConfig, FacilityConfig
from dgp.production.coman import ComanSimulator


class OperationsTeamAgent:
    """Plans bioreactor schedules and activates co-manufacturing ahead of lead times."""

    def __init__(
        self,
        facilities: List[FacilityConfig],
        coman_configs: List[ComanConfig],
        coman_sim: ComanSimulator,
        coman_activation_threshold: float = 0.85,
    ):
        self.facilities = facilities
        self.coman_configs = coman_configs
        self.coman_sim = coman_sim
        self.activation_threshold = coman_activation_threshold

    def plan_weekly_operations(
        self,
        current_monday: date,
        projected_weekly_demand_kg: Dict[str, float],
        current_available_inventory_kg: Dict[str, float],
    ):
        """
        Evaluate projected demand across product lines.
        If in-house capacity cannot cover demand + buffer, schedule co-manufacturing
        to arrive after the partner's required lead time.
        """
        # Calculate nominal in-house capacity per week
        in_house_cap: Dict[str, float] = {}
        for fac in self.facilities:
            weekly_yield = fac.nominal_batches_per_week * fac.planned_yield_per_batch_kg * (1.0 - fac.failure_rate)
            in_house_cap[fac.product_line] = in_house_cap.get(fac.product_line, 0.0) + weekly_yield

        for c_cfg in self.coman_configs:
            pl = c_cfg.product_line
            # Check availability date
            avail_date = date.fromisoformat(c_cfg.available_from)
            if current_monday < avail_date:
                continue

            proj_demand = projected_weekly_demand_kg.get(pl, 0.0)
            nominal_cap = in_house_cap.get(pl, 0.0)
            avail_inv = current_available_inventory_kg.get(pl, 0.0)

            # Demand pressure
            gap = (proj_demand * 1.15) - (nominal_cap + avail_inv * 0.5)

            if gap > c_cfg.min_commit_kg_per_week * 0.5:
                # Schedule co-man order to arrive lead_time_weeks from now
                target_monday = current_monday + timedelta(weeks=c_cfg.lead_time_weeks)
                req_kg = max(c_cfg.min_commit_kg_per_week, min(c_cfg.max_kg_per_week, gap))
                self.coman_sim.schedule_order(c_cfg.coman_id, target_monday, req_kg)
