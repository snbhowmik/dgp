"""Co-manufacturing partners, contracting, lead times, and weekly activity."""

import random
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple
from dgp.config import ComanConfig
from dgp.models import ComanActivityRow, ComanContractRow


@dataclass
class ComanOrder:
    coman_id: str
    target_week_start: date
    requested_kg: float


class ComanSimulator:
    """Manages co-manufacturing contracts and weekly order/delivery execution."""

    def __init__(self, configs: List[ComanConfig], rng: random.Random):
        self.configs = configs
        self.rng = rng
        self.active_until: Dict[str, date] = {}
        self.pending_orders: List[ComanOrder] = []

    def get_contract_rows(self) -> List[ComanContractRow]:
        """Return contract definitions."""
        rows = []
        for c in self.configs:
            rows.append(
                ComanContractRow(
                    coman_id=c.coman_id,
                    product_line=c.product_line,
                    available_from=c.available_from,
                    lead_time_weeks=c.lead_time_weeks,
                    min_commit_kg_per_week=c.min_commit_kg_per_week,
                    max_kg_per_week=c.max_kg_per_week,
                    unit_cost_inr_per_kg=c.unit_cost_inr_per_kg,
                    min_active_weeks=c.min_active_weeks,
                )
            )
        return rows

    def schedule_order(
        self,
        coman_id: str,
        target_week_start: date,
        requested_kg: float,
    ):
        """Schedule an order to arrive on target_week_start."""
        self.pending_orders.append(
            ComanOrder(
                coman_id=coman_id,
                target_week_start=target_week_start,
                requested_kg=requested_kg,
            )
        )

    def process_week(
        self,
        current_monday: date,
    ) -> Tuple[List[ComanActivityRow], Dict[str, float]]:
        """
        Process orders arriving on current_monday.
        Returns:
            activity_rows: CSV rows for coman_activity.csv
            delivered_by_product_line: dict of product_line -> delivered kg
        """
        activity_rows: List[ComanActivityRow] = []
        delivered_by_pl: Dict[str, float] = {}

        # Find orders matching current_monday
        cfg_map = {c.coman_id: c for c in self.configs}
        
        # Check active coman orders for this week
        todays_orders = [o for o in self.pending_orders if o.target_week_start == current_monday]
        
        for order in todays_orders:
            cfg = cfg_map.get(order.coman_id)
            if not cfg:
                continue

            # Requested kg clamped by contract bounds
            req_kg = max(cfg.min_commit_kg_per_week, min(cfg.max_kg_per_week, order.requested_kg))

            # Delivery realization (subject to partner reliability)
            delivered_ratio = self.rng.uniform(0.92, 1.02) if self.rng.random() < cfg.reliability else self.rng.uniform(0.60, 0.85)
            delivered_kg = round(req_kg * delivered_ratio, 2)

            activity_rows.append(
                ComanActivityRow(
                    coman_id=cfg.coman_id,
                    week_start=current_monday.isoformat(),
                    requested_kg=req_kg,
                    delivered_kg=delivered_kg,
                )
            )

            delivered_by_pl[cfg.product_line] = delivered_by_pl.get(cfg.product_line, 0.0) + delivered_kg

        return activity_rows, delivered_by_pl
