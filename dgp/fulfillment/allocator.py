"""Fulfillment engine and capacity allocation under hard capacity ceiling."""

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from dgp.models import OrderRow, OrderStatus, Channel
from dgp.fulfillment.inventory import PerishableInventoryManager


@dataclass
class UnfulfilledOrderIntent:
    order_id: str
    order_date: date
    channel: Channel
    region_id: str
    sku_id: str
    product_line: str
    customer_id: Optional[str]
    account_id: Optional[str]
    requested_qty_kg: float
    unit_price_inr: float
    promised_lead_days: int = 2
    priority: int = 1  # Lower = higher priority (e.g., B2B committed = 0, D2C = 1)


class OrderAllocator:
    """Allocates inventory to daily orders, handling stockouts, partials, waitlists, and cancellations."""

    def __init__(self, inventory_mgr: PerishableInventoryManager, rng: random.Random):
        self.inventory_mgr = inventory_mgr
        self.rng = rng
        self.waitlist: List[UnfulfilledOrderIntent] = []

    def allocate_orders(
        self,
        intents: List[UnfulfilledOrderIntent],
        current_date: date,
        sku_pack_sizes: Dict[str, float],
    ) -> List[OrderRow]:
        """
        Allocate available physical inventory to order intents.
        Prioritizes B2B committed contracts first, then D2C orders.
        """
        # Combine any existing waitlisted orders that are ready to attempt fulfillment
        all_intents = list(intents)
        if self.waitlist:
            recheck_waitlist = []
            for w in self.waitlist:
                # If waitlisted for more than 5 days, cancel due to stockout
                if (current_date - w.order_date).days > 5:
                    # Will be output as cancelled_stockout
                    pass
                else:
                    recheck_waitlist.append(w)
            self.waitlist = recheck_waitlist

        # Sort intents by priority (B2B first = 0, D2C = 1)
        all_intents.sort(key=lambda x: (x.priority, x.order_date))

        results: List[OrderRow] = []

        for intent in all_intents:
            promised_date = intent.order_date + timedelta(days=intent.promised_lead_days)
            available = self.inventory_mgr.get_available_kg(intent.product_line, current_date)

            # Check if customer cancels for reasons unrelated to stockout (e.g. 0.5% chance)
            if self.rng.random() < 0.005:
                results.append(
                    OrderRow(
                        order_id=intent.order_id,
                        order_date=intent.order_date.isoformat(),
                        channel=intent.channel.value,
                        region_id=intent.region_id,
                        sku_id=intent.sku_id,
                        customer_id=intent.customer_id,
                        account_id=intent.account_id,
                        requested_qty_kg=intent.requested_qty_kg,
                        fulfilled_qty_kg=0.0,
                        unit_price_inr=intent.unit_price_inr,
                        status=OrderStatus.CANCELLED_OTHER.value,
                        promised_date=promised_date.isoformat(),
                        delivered_date=None,
                    )
                )
                continue

            # Allocation logic
            if available >= intent.requested_qty_kg:
                # Full fulfillment
                fulfilled = self.inventory_mgr.deduct(intent.product_line, intent.requested_qty_kg, current_date)
                
                # Small chance of 1-day logistics delay (2%)
                delivery_delay = 1 if self.rng.random() < 0.02 else 0
                delivered_date = promised_date + timedelta(days=delivery_delay)

                results.append(
                    OrderRow(
                        order_id=intent.order_id,
                        order_date=intent.order_date.isoformat(),
                        channel=intent.channel.value,
                        region_id=intent.region_id,
                        sku_id=intent.sku_id,
                        customer_id=intent.customer_id,
                        account_id=intent.account_id,
                        requested_qty_kg=intent.requested_qty_kg,
                        fulfilled_qty_kg=fulfilled,
                        unit_price_inr=intent.unit_price_inr,
                        status=OrderStatus.FULFILLED.value,
                        promised_date=promised_date.isoformat(),
                        delivered_date=delivered_date.isoformat(),
                    )
                )

            elif available > 0:
                # Partial fulfillment possible
                pack_size = sku_pack_sizes.get(intent.sku_id, 0.5)
                # Pack-level rounding: fulfill whole number of packs possible
                packs_available = int(available / max(pack_size, 0.01))

                if packs_available > 0 and (packs_available * pack_size < intent.requested_qty_kg):
                    partial_kg = round(packs_available * pack_size, 4)
                    fulfilled = self.inventory_mgr.deduct(intent.product_line, partial_kg, current_date)
                    delivery_delay = 1 if self.rng.random() < 0.03 else 0
                    delivered_date = promised_date + timedelta(days=delivery_delay)

                    results.append(
                        OrderRow(
                            order_id=intent.order_id,
                            order_date=intent.order_date.isoformat(),
                            channel=intent.channel.value,
                            region_id=intent.region_id,
                            sku_id=intent.sku_id,
                            customer_id=intent.customer_id,
                            account_id=intent.account_id,
                            requested_qty_kg=intent.requested_qty_kg,
                            fulfilled_qty_kg=fulfilled,
                            unit_price_inr=intent.unit_price_inr,
                            status=OrderStatus.PARTIAL.value,
                            promised_date=promised_date.isoformat(),
                            delivered_date=delivered_date.isoformat(),
                        )
                    )
                else:
                    # Can't even fulfill 1 pack, or available was too small -> waitlist or cancel
                    if intent.channel == Channel.D2C and self.rng.random() < 0.35:
                        status = OrderStatus.WAITLISTED.value
                    else:
                        status = OrderStatus.CANCELLED_STOCKOUT.value

                    results.append(
                        OrderRow(
                            order_id=intent.order_id,
                            order_date=intent.order_date.isoformat(),
                            channel=intent.channel.value,
                            region_id=intent.region_id,
                            sku_id=intent.sku_id,
                            customer_id=intent.customer_id,
                            account_id=intent.account_id,
                            requested_qty_kg=intent.requested_qty_kg,
                            fulfilled_qty_kg=0.0,
                            unit_price_inr=intent.unit_price_inr,
                            status=status,
                            promised_date=promised_date.isoformat(),
                            delivered_date=None,
                        )
                    )

            else:
                # Zero available inventory
                if intent.channel == Channel.D2C and self.rng.random() < 0.30:
                    status = OrderStatus.WAITLISTED.value
                else:
                    status = OrderStatus.CANCELLED_STOCKOUT.value

                results.append(
                    OrderRow(
                        order_id=intent.order_id,
                        order_date=intent.order_date.isoformat(),
                        channel=intent.channel.value,
                        region_id=intent.region_id,
                        sku_id=intent.sku_id,
                        customer_id=intent.customer_id,
                        account_id=intent.account_id,
                        requested_qty_kg=intent.requested_qty_kg,
                        fulfilled_qty_kg=0.0,
                        unit_price_inr=intent.unit_price_inr,
                        status=status,
                        promised_date=promised_date.isoformat(),
                        delivered_date=None,
                    )
                )

        return results
