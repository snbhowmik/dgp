"""D2C Consumer agents: personas, ordering cadence, subscriptions, churn, and NPS responses."""

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from dgp.models import CustomerRow, NpsResponseRow, Channel
from dgp.fulfillment.allocator import UnfulfilledOrderIntent


PERSONA_SEGMENTS = [
    "Fitness / Biohacker",
    "Ethical Flexitarian",
    "Gourmet Foodie",
    "Curious Early Adopter",
]


@dataclass
class SimulatedCustomer:
    customer_id: str
    region_id: str
    acquired_date: date
    acquisition_campaign_type: Optional[str]
    persona_segment: str
    is_subscriber: bool
    last_order_date: date
    reorder_interval_days: int
    churned_date: Optional[date] = None
    preferred_sku_id: str = ""
    satisfaction_index: float = 1.0  # Degrades upon stockout/delay, recovers on good fulfillment


class ConsumerAgentManager:
    """Manages the population of D2C consumers, lifecycle transitions, orders, and survey feedback."""

    def __init__(self, d2c_repeat_rate: float, subscriber_fraction: float, rng: random.Random):
        self.d2c_repeat_rate = d2c_repeat_rate
        self.subscriber_fraction = subscriber_fraction
        self.rng = rng
        self.customers: Dict[str, SimulatedCustomer] = {}
        self.customer_counter = 1000

    def onboard_new_customer(
        self,
        region_id: str,
        acquired_date: date,
        acquisition_campaign_type: Optional[str],
        eligible_skus: List[str],
    ) -> SimulatedCustomer:
        """Create a new D2C customer upon conversion or organic acquisition."""
        self.customer_counter += 1
        cid = f"CUST-{self.customer_counter:06d}"
        persona = self.rng.choice(PERSONA_SEGMENTS)
        is_sub = self.rng.random() < self.subscriber_fraction

        # Preferred SKU from eligible SKUs for this region/channel
        pref_sku = self.rng.choice(eligible_skus) if eligible_skus else "SKU-CHK-500G"

        # Reorder cycle (e.g. 14, 21, 28, or 35 days)
        reorder_cycle = self.rng.choice([14, 21, 28, 35])

        cust = SimulatedCustomer(
            customer_id=cid,
            region_id=region_id,
            acquired_date=acquired_date,
            acquisition_campaign_type=acquisition_campaign_type,
            persona_segment=persona,
            is_subscriber=is_sub,
            last_order_date=acquired_date,
            reorder_interval_days=reorder_cycle,
            churned_date=None,
            preferred_sku_id=pref_sku,
            satisfaction_index=1.0,
        )
        self.customers[cid] = cust
        return cust

    def generate_daily_orders(
        self,
        current_date: date,
        eligible_skus_by_region: Dict[str, List[str]],
        sku_prices: Dict[str, float],
        sku_pack_sizes: Dict[str, float],
        sku_product_lines: Dict[str, str],
        order_counter_start: int,
    ) -> Tuple[List[UnfulfilledOrderIntent], int]:
        """Generate orders for existing active customers due to reorder on current_date."""
        order_intents: List[UnfulfilledOrderIntent] = []
        counter = order_counter_start

        for cid, cust in list(self.customers.items()):
            if cust.churned_date is not None:
                continue

            # Check churn rule: inactivity > 90 days and satisfaction low
            days_inactive = (current_date - cust.last_order_date).days
            if days_inactive > 90:
                # Churned
                cust.churned_date = cust.last_order_date + timedelta(days=90)
                continue

            # Determine if ordering today
            is_due = False
            if cust.is_subscriber:
                # Fixed cadence
                if (current_date - cust.last_order_date).days >= cust.reorder_interval_days:
                    is_due = True
            else:
                # Stochastic repeat ordering
                if (current_date - cust.last_order_date).days >= cust.reorder_interval_days:
                    prob = self.d2c_repeat_rate * cust.satisfaction_index * 0.15
                    if self.rng.random() < prob:
                        is_due = True

            if is_due:
                # Verify SKU eligibility
                el_skus = eligible_skus_by_region.get(cust.region_id, [])
                if not el_skus:
                    continue

                sku_id = cust.preferred_sku_id if cust.preferred_sku_id in el_skus else self.rng.choice(el_skus)
                pack_size = sku_pack_sizes.get(sku_id, 0.5)
                # D2C basket: 1 to 3 packs
                packs = self.rng.choices([1, 2, 3], weights=[0.60, 0.30, 0.10])[0]
                qty_kg = round(packs * pack_size, 4)
                price_per_kg = sku_prices.get(sku_id, 800.0)

                counter += 1
                order_id = f"ORD-D2C-{current_date.strftime('%y%m%d')}-{counter:05d}"
                order_intents.append(
                    UnfulfilledOrderIntent(
                        order_id=order_id,
                        order_date=current_date,
                        channel=Channel.D2C,
                        region_id=cust.region_id,
                        sku_id=sku_id,
                        product_line=sku_product_lines.get(sku_id, "cultivated_chicken"),
                        customer_id=cid,
                        account_id=None,
                        requested_qty_kg=qty_kg,
                        unit_price_inr=price_per_kg,
                        promised_lead_days=self.rng.choice([1, 2]),
                        priority=1,
                    )
                )
                cust.last_order_date = current_date

        return order_intents, counter

    def record_fulfillment_experience(
        self,
        customer_id: str,
        status: str,
        delayed: bool,
    ) -> Optional[NpsResponseRow]:
        """Update customer satisfaction based on order outcome and occasionally sample NPS."""
        cust = self.customers.get(customer_id)
        if not cust:
            return None

        # Adjust satisfaction
        if status == "fulfilled":
            if delayed:
                cust.satisfaction_index = max(0.6, cust.satisfaction_index - 0.1)
                score_draw = self.rng.choices([6, 7, 8, 9], weights=[0.2, 0.3, 0.3, 0.2])[0]
            else:
                cust.satisfaction_index = min(1.2, cust.satisfaction_index + 0.05)
                score_draw = self.rng.choices([8, 9, 10], weights=[0.15, 0.40, 0.45])[0]
        elif status == "partial":
            cust.satisfaction_index = max(0.4, cust.satisfaction_index - 0.25)
            score_draw = self.rng.choices([4, 5, 6, 7], weights=[0.3, 0.3, 0.25, 0.15])[0]
        elif status == "waitlisted":
            cust.satisfaction_index = max(0.3, cust.satisfaction_index - 0.35)
            score_draw = self.rng.choices([2, 3, 4, 5], weights=[0.3, 0.3, 0.25, 0.15])[0]
        else:  # cancelled_stockout
            cust.satisfaction_index = max(0.1, cust.satisfaction_index - 0.5)
            score_draw = self.rng.choices([0, 1, 2, 3], weights=[0.4, 0.3, 0.2, 0.1])[0]

        # Mild NPS response rate: 5% to 8% of customers respond to post-delivery survey
        if self.rng.random() < 0.07:
            return NpsResponseRow(
                response_date=cust.last_order_date.isoformat(),
                channel=Channel.D2C.value,
                region_id=cust.region_id,
                customer_or_account_id=customer_id,
                score=score_draw,
            )
        return None

    def export_customer_rows(self) -> List[CustomerRow]:
        """Export all registered customers to contract rows."""
        rows = []
        for cust in self.customers.values():
            rows.append(
                CustomerRow(
                    customer_id=cust.customer_id,
                    region_id=cust.region_id,
                    acquired_date=cust.acquired_date.isoformat(),
                    acquisition_campaign_type=cust.acquisition_campaign_type,
                    persona_segment=cust.persona_segment,
                    churned_date=cust.churned_date.isoformat() if cust.churned_date else None,
                    is_subscriber=cust.is_subscriber,
                )
            )
        return rows
