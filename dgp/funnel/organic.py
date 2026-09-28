"""Organic demand dynamics: Word-of-mouth (WOM), crowdsourced content, and viral surges."""

import random
from dataclasses import dataclass
from datetime import date
from typing import List, Tuple


@dataclass
class OrganicAcquisition:
    region_id: str
    date: date
    is_viral: bool = False


class OrganicDemandEngine:
    """Simulates organic word-of-mouth customer generation and viral spikes."""

    def __init__(self, wom_strength: float, rng: random.Random):
        self.wom_strength = wom_strength
        self.rng = rng

    def simulate_daily_organic(
        self,
        current_date: date,
        active_customer_count_by_region: dict,
        viral_boost_multiplier: float = 1.0,
    ) -> List[OrganicAcquisition]:
        """Generate organic D2C customer acquisitions for current_date."""
        acquisitions: List[OrganicAcquisition] = []

        for region_id, count in active_customer_count_by_region.items():
            # Expected organic acquisition is proportional to active satisfied customer base
            # e.g., 1 out of 500 active customers refers a friend every month (0.00007 per day)
            lambda_daily = max(0.05, count * 0.00015 * self.wom_strength * viral_boost_multiplier)
            
            # Draw Poisson / Binomial approximation
            num_acquisitions = 0
            # Simple Poisson sampling
            l = lambda_daily
            k = 0
            p = 1.0
            import math
            exp_l = math.exp(-min(50.0, l))
            while True:
                k += 1
                p *= self.rng.random()
                if p <= exp_l:
                    num_acquisitions = k - 1
                    break
                if k > 100:
                    num_acquisitions = int(l)
                    break

            for _ in range(num_acquisitions):
                acquisitions.append(
                    OrganicAcquisition(
                        region_id=region_id,
                        date=current_date,
                        is_viral=viral_boost_multiplier > 1.5,
                    )
                )

        return acquisitions
