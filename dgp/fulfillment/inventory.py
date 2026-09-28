"""Perishable inventory lot tracking with FEFO (First-Expired, First-Out) and spoilage."""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional


@dataclass
class InventoryLot:
    lot_id: str
    product_line: str
    creation_date: date
    expiry_date: date
    initial_kg: float
    remaining_kg: float


class PerishableInventoryManager:
    """Tracks inventory lots by product line, enforces shelf life, and deducts via FEFO."""

    def __init__(self):
        self.lots: Dict[str, List[InventoryLot]] = {}
        self.lot_counter = 1000
        self.spoilage_log: List[dict] = []

    def add_lot(
        self,
        product_line: str,
        qty_kg: float,
        creation_date: date,
        shelf_life_days: int,
    ) -> InventoryLot:
        """Add newly produced or delivered batch to inventory."""
        self.lot_counter += 1
        import datetime
        expiry_date = creation_date + datetime.timedelta(days=shelf_life_days)
        lot = InventoryLot(
            lot_id=f"LOT-{self.lot_counter:05d}",
            product_line=product_line,
            creation_date=creation_date,
            expiry_date=expiry_date,
            initial_kg=qty_kg,
            remaining_kg=qty_kg,
        )
        if product_line not in self.lots:
            self.lots[product_line] = []
        self.lots[product_line].append(lot)
        return lot

    def expire_spoilage(self, current_date: date) -> float:
        """Remove and record expired lots. Returns total kg spoiled on this date."""
        total_spoiled_kg = 0.0
        for pl, lot_list in self.lots.items():
            active_lots = []
            for lot in lot_list:
                if lot.remaining_kg <= 1e-4:
                    continue
                if lot.expiry_date < current_date:
                    # Expired and spoiled
                    total_spoiled_kg += lot.remaining_kg
                    self.spoilage_log.append({
                        "date": current_date.isoformat(),
                        "product_line": pl,
                        "lot_id": lot.lot_id,
                        "spoiled_kg": lot.remaining_kg,
                    })
                    lot.remaining_kg = 0.0
                else:
                    active_lots.append(lot)
            self.lots[pl] = active_lots
        return total_spoiled_kg

    def get_available_kg(self, product_line: str, current_date: date) -> float:
        """Return total unexpired available kg for product line."""
        self.expire_spoilage(current_date)
        lots = self.lots.get(product_line, [])
        return sum(lot.remaining_kg for lot in lots if lot.expiry_date >= current_date and lot.remaining_kg > 0)

    def deduct(self, product_line: str, requested_kg: float, current_date: date) -> float:
        """
        Deduct requested_kg using FEFO (earliest expiry first).
        Returns actual fulfilled kg.
        """
        self.expire_spoilage(current_date)
        lots = self.lots.get(product_line, [])
        # Sort by expiry_date ascending (FEFO)
        lots.sort(key=lambda l: l.expiry_date)

        fulfilled_kg = 0.0
        remaining_needed = requested_kg

        for lot in lots:
            if remaining_needed <= 1e-4:
                break
            if lot.expiry_date < current_date or lot.remaining_kg <= 1e-4:
                continue

            available = lot.remaining_kg
            take = min(available, remaining_needed)
            lot.remaining_kg -= take
            remaining_needed -= take
            fulfilled_kg += take

        return round(fulfilled_kg, 4)
