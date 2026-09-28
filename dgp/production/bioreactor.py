"""In-house bioreactor batch production simulation."""

import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Tuple
from dgp.models import CapacityBatchRow, CapacityPlanRow, BatchOutcome
from dgp.config import FacilityConfig


@dataclass
class CompletedBatch:
    batch_id: str
    facility_id: str
    product_line: str
    start_date: date
    end_date: date
    planned_yield_kg: float
    actual_yield_kg: float
    outcome: BatchOutcome


class BioreactorSimulator:
    """Simulates facility scheduling, batch runs, yields, and failure modes."""

    def __init__(self, facilities: List[FacilityConfig], rng: random.Random):
        self.facilities = facilities
        self.rng = rng
        self.batch_counter = 1000

    def generate_capacity_plan(
        self,
        week_mondays: List[date],
    ) -> List[CapacityPlanRow]:
        """Generate weekly capacity plans for history + forward horizon."""
        plan_rows = []
        for monday in week_mondays:
            for fac in self.facilities:
                plan_rows.append(
                    CapacityPlanRow(
                        week_start=monday.isoformat(),
                        facility_id=fac.facility_id,
                        product_line=fac.product_line,
                        planned_batches=fac.nominal_batches_per_week,
                        planned_yield_per_batch_kg=fac.planned_yield_per_batch_kg,
                    )
                )
        return plan_rows

    def simulate_week_batches(
        self,
        monday: date,
        shock_failure_multiplier: float = 1.0,
    ) -> Tuple[List[CapacityBatchRow], List[CompletedBatch]]:
        """Simulate discrete batches completing during the week starting on monday."""
        csv_rows: List[CapacityBatchRow] = []
        completed_batches: List[CompletedBatch] = []

        for fac in self.facilities:
            # Batches scheduled during this week
            num_batches = fac.nominal_batches_per_week
            # Batch completion staggered across the week
            for b in range(num_batches):
                self.batch_counter += 1
                batch_id = f"BAT-{fac.facility_id}-{monday.strftime('%y%W')}-{self.batch_counter:04d}"
                
                # Stagger batch start and end dates within the week/preceding cycle
                day_offset = int((b / max(1, num_batches)) * 5)
                end_date = monday + timedelta(days=day_offset + 1)
                start_date = end_date - timedelta(days=fac.cycle_days)

                planned_yield = fac.planned_yield_per_batch_kg

                # Determine outcome
                effective_fail_rate = min(0.60, fac.failure_rate * shock_failure_multiplier)
                effective_partial_rate = min(0.60, fac.partial_rate * shock_failure_multiplier)
                
                r = self.rng.random()
                if r < effective_fail_rate:
                    outcome = BatchOutcome.FAILED
                    actual_yield = 0.0
                elif r < effective_fail_rate + effective_partial_rate:
                    outcome = BatchOutcome.PARTIAL
                    partial_frac = self.rng.uniform(0.35, 0.75)
                    actual_yield = round(planned_yield * partial_frac, 2)
                else:
                    outcome = BatchOutcome.SUCCESS
                    # Gaussian noise around planned yield
                    noise = self.rng.gauss(0.0, fac.yield_std_pct)
                    actual_yield = round(planned_yield * max(0.80, min(1.20, 1.0 + noise)), 2)

                completed_batches.append(
                    CompletedBatch(
                        batch_id=batch_id,
                        facility_id=fac.facility_id,
                        product_line=fac.product_line,
                        start_date=start_date,
                        end_date=end_date,
                        planned_yield_kg=planned_yield,
                        actual_yield_kg=actual_yield,
                        outcome=outcome,
                    )
                )

                csv_rows.append(
                    CapacityBatchRow(
                        batch_id=batch_id,
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                        facility_id=fac.facility_id,
                        product_line=fac.product_line,
                        planned_yield_kg=planned_yield,
                        actual_yield_kg=actual_yield,
                        outcome=outcome.value,
                    )
                )

        return csv_rows, completed_batches
