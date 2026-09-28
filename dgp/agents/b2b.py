"""B2B wholesale account agents: contracting, weekly order generation, status transitions, and NPS."""

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from dgp.config import B2BAccountTemplate
from dgp.models import B2BAccountRow, NpsResponseRow, Channel
from dgp.fulfillment.allocator import UnfulfilledOrderIntent


@dataclass
class SimulatedB2BAccount:
    account_id: str
    account_type: str
    primary_region_id: str
    regions_served: List[str]
    outlets_count: int
    onboarded_date: Optional[date]
    contract_start: Optional[date]
    contract_end: Optional[date]
    committed_kg_per_month: Optional[float]
    contract_price_inr_per_kg: Optional[float]
    shortfall_penalty_inr_per_kg: Optional[float]
    requested_start_date: Optional[date]
    requested_kg_per_month: Optional[float]
    status_at_end: str
    preferred_sku_id: str
    churn_date: Optional[date] = None
    pause_start_date: Optional[date] = None
    pause_end_date: Optional[date] = None
    satisfaction_index: float = 1.0


class B2BAgentManager:
    """Manages B2B accounts, contract lifecycles, and commercial order patterns."""

    def __init__(
        self,
        templates: List[B2BAccountTemplate],
        start_date: date,
        history_weeks: int,
        rng: random.Random,
    ):
        self.rng = rng
        self.accounts: Dict[str, SimulatedB2BAccount] = {}
        self.history_end_date = start_date + timedelta(weeks=history_weeks)

        for tmpl in templates:
            onboard_date = start_date + timedelta(weeks=tmpl.onboard_week_offset)
            
            if tmpl.status_at_end == "pipeline":
                # Account is still in contract negotiation at end of history
                req_start = self.history_end_date + timedelta(weeks=self.rng.randint(2, 8))
                acc = SimulatedB2BAccount(
                    account_id=tmpl.account_id,
                    account_type=tmpl.account_type,
                    primary_region_id=tmpl.region_id,
                    regions_served=tmpl.regions_served,
                    outlets_count=tmpl.outlets_count,
                    onboarded_date=None,
                    contract_start=None,
                    contract_end=None,
                    committed_kg_per_month=None,
                    contract_price_inr_per_kg=None,
                    shortfall_penalty_inr_per_kg=None,
                    requested_start_date=req_start,
                    requested_kg_per_month=tmpl.committed_kg_per_month,
                    status_at_end="pipeline",
                    preferred_sku_id="SKU-CHK-1KG",
                )
            else:
                contract_start = onboard_date
                contract_end = contract_start + timedelta(weeks=tmpl.contract_duration_weeks)

                churn_d = None
                if tmpl.churn_week_offset:
                    churn_d = start_date + timedelta(weeks=tmpl.churn_week_offset)

                pause_s = None
                pause_e = None
                if tmpl.pause_week_start and tmpl.pause_week_end:
                    pause_s = start_date + timedelta(weeks=tmpl.pause_week_start)
                    pause_e = start_date + timedelta(weeks=tmpl.pause_week_end)

                acc = SimulatedB2BAccount(
                    account_id=tmpl.account_id,
                    account_type=tmpl.account_type,
                    primary_region_id=tmpl.region_id,
                    regions_served=tmpl.regions_served,
                    outlets_count=tmpl.outlets_count,
                    onboarded_date=onboard_date,
                    contract_start=contract_start,
                    contract_end=contract_end,
                    committed_kg_per_month=tmpl.committed_kg_per_month,
                    contract_price_inr_per_kg=tmpl.contract_price_inr_per_kg,
                    shortfall_penalty_inr_per_kg=tmpl.shortfall_penalty_inr_per_kg,
                    requested_start_date=None,
                    requested_kg_per_month=None,
                    status_at_end=tmpl.status_at_end,
                    preferred_sku_id="SKU-CHK-1KG",
                    churn_date=churn_d,
                    pause_start_date=pause_s,
                    pause_end_date=pause_e,
                )
            self.accounts[tmpl.account_id] = acc

    def generate_orders_for_week(
        self,
        monday: date,
        sku_pack_sizes: Dict[str, float],
        sku_product_lines: Dict[str, str],
        order_counter_start: int,
    ) -> Tuple[List[UnfulfilledOrderIntent], int]:
        """Generate weekly wholesale orders for active contracts."""
        order_intents: List[UnfulfilledOrderIntent] = []
        counter = order_counter_start

        for acc in self.accounts.values():
            # Check if active on this monday
            if acc.status_at_end == "pipeline":
                continue
            if not acc.onboarded_date or monday < acc.onboarded_date:
                continue
            if acc.churn_date and monday >= acc.churn_date:
                continue
            if acc.pause_start_date and acc.pause_end_date:
                if acc.pause_start_date <= monday <= acc.pause_end_date:
                    continue
            if acc.contract_end and monday > acc.contract_end and acc.status_at_end == "churned":
                continue

            # Nominal weekly quantity = committed_monthly / 4.33
            nominal_weekly = (acc.committed_kg_per_month or 500.0) / 4.33
            
            # Orders fluctuate around commitment (+/- 15%)
            variation = self.rng.uniform(0.85, 1.15)
            requested_qty = round(nominal_weekly * variation, 2)

            # High volume accounts may place 2 orders per week (Mon and Thu), smaller accounts 1 order (Mon)
            if requested_qty > 300.0:
                splits = [
                    (monday, round(requested_qty * 0.55, 2)),
                    (monday + timedelta(days=3), round(requested_qty * 0.45, 2)),
                ]
            else:
                splits = [(monday, requested_qty)]

            for o_date, o_qty in splits:
                counter += 1
                order_id = f"ORD-B2B-{o_date.strftime('%y%m%d')}-{counter:05d}"
                sku_id = acc.preferred_sku_id
                
                # Multi-region distribution: choose among regions_served
                serving_region = self.rng.choice(acc.regions_served) if acc.regions_served else acc.primary_region_id

                order_intents.append(
                    UnfulfilledOrderIntent(
                        order_id=order_id,
                        order_date=o_date,
                        channel=Channel.B2B,
                        region_id=serving_region,
                        sku_id=sku_id,
                        product_line=sku_product_lines.get(sku_id, "cultivated_chicken"),
                        customer_id=None,
                        account_id=acc.account_id,
                        requested_qty_kg=o_qty,
                        unit_price_inr=acc.contract_price_inr_per_kg or 700.0,
                        promised_lead_days=1,
                        priority=0,  # Highest priority to avoid shortfall penalty
                    )
                )

        return order_intents, counter

    def record_fulfillment_experience(
        self,
        account_id: str,
        fulfilled_ratio: float,
        current_date: date,
    ) -> Optional[NpsResponseRow]:
        """Record quarterly NPS or feedback after deliveries for B2B accounts."""
        acc = self.accounts.get(account_id)
        if not acc:
            return None

        # Adjust satisfaction
        if fulfilled_ratio >= 0.99:
            acc.satisfaction_index = min(1.2, acc.satisfaction_index + 0.05)
            score = self.rng.choices([8, 9, 10], weights=[0.2, 0.4, 0.4])[0]
        elif fulfilled_ratio >= 0.75:
            acc.satisfaction_index = max(0.5, acc.satisfaction_index - 0.15)
            score = self.rng.choices([5, 6, 7], weights=[0.3, 0.4, 0.3])[0]
        else:
            acc.satisfaction_index = max(0.2, acc.satisfaction_index - 0.4)
            score = self.rng.choices([1, 2, 3, 4], weights=[0.4, 0.3, 0.2, 0.1])[0]

        # B2B NPS responses are sparse (e.g., quarterly or 10% chance per order)
        if self.rng.random() < 0.10:
            return NpsResponseRow(
                response_date=current_date.isoformat(),
                channel=Channel.B2B.value,
                region_id=acc.primary_region_id,
                customer_or_account_id=acc.account_id,
                score=score,
            )
        return None

    def export_account_rows(self) -> List[B2BAccountRow]:
        """Export all B2B accounts to contract rows."""
        rows = []
        for acc in self.accounts.values():
            rows.append(
                B2BAccountRow(
                    account_id=acc.account_id,
                    account_type=acc.account_type,
                    region_id=acc.primary_region_id,
                    regions_served="|".join(acc.regions_served),
                    outlets_count=acc.outlets_count,
                    status=acc.status_at_end,
                    onboarded_date=acc.onboarded_date.isoformat() if acc.onboarded_date else None,
                    contract_start=acc.contract_start.isoformat() if acc.contract_start else None,
                    contract_end=acc.contract_end.isoformat() if acc.contract_end else None,
                    committed_kg_per_month=acc.committed_kg_per_month,
                    contract_price_inr_per_kg=acc.contract_price_inr_per_kg,
                    shortfall_penalty_inr_per_kg=acc.shortfall_penalty_inr_per_kg,
                    requested_start_date=acc.requested_start_date.isoformat() if acc.requested_start_date else None,
                    requested_kg_per_month=acc.requested_kg_per_month,
                )
            )
        return rows
