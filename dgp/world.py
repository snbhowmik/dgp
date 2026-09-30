"""World simulation orchestrator."""

import random
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dgp.calendar import IndianCalendar, get_all_mondays, get_monday_of_week
from dgp.config import WorldConfig
from dgp.models import (
    RegionRow,
    SkuRow,
    ProductMatrixRow,
    OrderRow,
    CapacityBatchRow,
    CapacityPlanRow,
    ComanContractRow,
    ComanActivityRow,
    B2BAccountRow,
    MarketingDailyRow,
    MarketingPlanRow,
    CustomerRow,
    NpsResponseRow,
    Channel,
)
from dgp.production.bioreactor import BioreactorSimulator
from dgp.production.coman import ComanSimulator
from dgp.fulfillment.inventory import PerishableInventoryManager
from dgp.fulfillment.allocator import OrderAllocator, UnfulfilledOrderIntent
from dgp.funnel.marketing_engine import MarketingEngine
from dgp.funnel.organic import OrganicDemandEngine
from dgp.agents.consumer import ConsumerAgentManager
from dgp.agents.b2b import B2BAgentManager
from dgp.agents.marketing import MarketingTeamAgent
from dgp.agents.ops import OperationsTeamAgent


class WorldSimulator:
    """Orchestrates the entire DGP simulation for a given WorldConfig and random seed."""

    def __init__(self, config: WorldConfig, seed: int):
        self.config = config
        self.seed = seed
        self.rng = random.Random(seed)

    def run_simulation(
        self,
        extension_weeks: int = 0,
    ) -> Tuple[Dict[str, List[Any]], str, str, str]:
        """
        Run the simulation.
        extension_weeks: if > 0, continues the simulation for additional weeks (e.g. for drop2).
        Returns:
            tables: dict mapping filename to list of row objects
            history_start: ISO date string
            history_end: ISO date string
            plan_end: ISO date string
        """
        total_history_weeks = self.config.history_weeks + extension_weeks
        start_d = date.fromisoformat(self.config.start_date)
        history_end_d = start_d + timedelta(weeks=total_history_weeks) - timedelta(days=1)
        plan_end_d = start_d + timedelta(weeks=total_history_weeks + self.config.plan_weeks_ahead) - timedelta(days=1)

        # 1. Base static rows: Regions & SKUs
        region_rows = [
            RegionRow(
                region_id=r.region_id,
                region_name=r.region_name,
                tier=r.tier,
                cold_chain_available=r.cold_chain_available,
            )
            for r in self.config.regions
        ]

        sku_rows = [
            SkuRow(
                sku_id=s.sku_id,
                product_line=s.product_line,
                pack_size_kg=s.pack_size_kg,
                status=s.status,
                expected_launch_date=s.expected_launch_date,
                shelf_life_days=s.shelf_life_days,
                unit_cost_inr_per_kg=s.unit_cost_inr_per_kg,
                list_price_d2c_inr_per_kg=s.list_price_d2c_inr_per_kg,
            )
            for s in self.config.skus
        ]

        # Region & SKU lookup maps
        sku_map = {s.sku_id: s for s in self.config.skus}
        sku_pack_sizes = {s.sku_id: s.pack_size_kg for s in self.config.skus}
        sku_prices = {s.sku_id: s.list_price_d2c_inr_per_kg for s in self.config.skus}
        sku_shelf_lives = {s.sku_id: s.shelf_life_days for s in self.config.skus}
        sku_product_lines = {s.sku_id: s.product_line for s in self.config.skus}
        region_weights = {r.region_id: r.market_weight for r in self.config.regions}
        region_ids = [r.region_id for r in self.config.regions]

        # 2. Product Matrix
        product_matrix_rows: List[ProductMatrixRow] = []
        for rule in self.config.product_matrix_rules:
            # Expand region if ALL, METRO_ONLY, COLD_CHAIN_ONLY
            if rule.region_id == "ALL":
                target_rids = region_ids
            elif rule.region_id == "METRO_ONLY":
                target_rids = [r.region_id for r in self.config.regions if r.tier == "metro"]
            elif rule.region_id == "COLD_CHAIN_ONLY":
                target_rids = [r.region_id for r in self.config.regions if r.cold_chain_available]
            else:
                target_rids = [rule.region_id]

            for rid in target_rids:
                product_matrix_rows.append(
                    ProductMatrixRow(
                        sku_id=rule.sku_id,
                        channel=rule.channel,
                        region_id=rid,
                        eligible_from=rule.eligible_from,
                        eligible_to=rule.eligible_to,
                    )
                )

        # 3. Subsystem initializations
        bioreactor_sim = BioreactorSimulator(self.config.facilities, self.rng)
        coman_sim = ComanSimulator(self.config.coman_contracts, self.rng)
        coman_contract_rows = coman_sim.get_contract_rows()

        inventory_mgr = PerishableInventoryManager()
        allocator = OrderAllocator(inventory_mgr, self.rng)

        marketing_engine = MarketingEngine(self.config.marketing_campaigns, region_ids, self.rng)
        marketing_team = MarketingTeamAgent(self.config.marketing_campaigns, region_ids, self.rng)
        organic_engine = OrganicDemandEngine(self.config.wom_strength, self.rng)

        consumer_mgr = ConsumerAgentManager(
            d2c_repeat_rate=self.config.d2c_repeat_rate,
            subscriber_fraction=self.config.d2c_subscriber_fraction,
            rng=self.rng,
        )

        b2b_mgr = B2BAgentManager(
            templates=self.config.b2b_accounts,
            start_date=start_d,
            history_weeks=total_history_weeks,
            rng=self.rng,
        )

        ops_agent = OperationsTeamAgent(
            facilities=self.config.facilities,
            coman_configs=self.config.coman_contracts,
            coman_sim=coman_sim,
            coman_activation_threshold=self.config.coman_activation_threshold,
        )

        # Seed initial customers for warm start
        for r_id in region_ids:
            for _ in range(self.rng.randint(15, 35)):
                init_date = start_d - timedelta(days=self.rng.randint(5, 60))
                el_skus = [
                    pm.sku_id
                    for pm in product_matrix_rows
                    if pm.channel == "D2C" and pm.region_id == r_id and pm.eligible_from <= start_d.isoformat()
                ]
                consumer_mgr.onboard_new_customer(
                    region_id=r_id,
                    acquired_date=init_date,
                    acquisition_campaign_type=None,
                    eligible_skus=el_skus,
                )

        # Output collections
        capacity_batch_rows: List[CapacityBatchRow] = []
        coman_activity_rows: List[ComanActivityRow] = []
        marketing_daily_rows: List[MarketingDailyRow] = []
        order_rows: List[OrderRow] = []
        nps_rows: List[NpsResponseRow] = []

        # Initial commissioning batches completed on start_d to seed starting inventory
        for fac in self.config.facilities:
            batch_id = f"BAT-{fac.facility_id}-INIT-0001"
            init_yield = fac.planned_yield_per_batch_kg
            capacity_batch_rows.append(
                CapacityBatchRow(
                    batch_id=batch_id,
                    start_date=(start_d - timedelta(days=fac.cycle_days)).isoformat(),
                    end_date=start_d.isoformat(),
                    facility_id=fac.facility_id,
                    product_line=fac.product_line,
                    planned_yield_kg=init_yield,
                    actual_yield_kg=init_yield,
                    outcome="success",
                )
            )
            inventory_mgr.add_lot(
                product_line=fac.product_line,
                qty_kg=init_yield,
                creation_date=start_d,
                shelf_life_days=21,
            )

        # Tracking state
        stockouts_by_region: Dict[str, int] = {r: 0 for r in region_ids}
        orders_by_region: Dict[str, int] = {r: 0 for r in region_ids}
        recent_cpa: Dict[Tuple[str, str, str], float] = {}
        order_counter = 1000

        # Timeline generation
        all_mondays_history = get_all_mondays(start_d, history_end_d)
        all_mondays_full = get_all_mondays(start_d, plan_end_d)

        # Capacity Plan & Marketing Plan (history + 13 weeks forward)
        capacity_plan_rows = bioreactor_sim.generate_capacity_plan(all_mondays_full)
        marketing_plan_rows = marketing_engine.generate_marketing_plan(all_mondays_full, region_weights)

        planned_spend_map: Dict[Tuple[str, str, str, str], float] = {
            (mp.week_start, mp.region_id, mp.channel, mp.campaign_type): mp.planned_spend_inr
            for mp in marketing_plan_rows
        }
        weekly_spend_acc: Dict[Tuple[str, str, str], float] = {}
        weekly_conv_acc: Dict[Tuple[str, str, str], int] = {}

        # Run day-by-day simulation through history
        curr_d = start_d
        week_idx = 0

        while curr_d <= history_end_d:
            is_monday = curr_d.weekday() == 0
            if is_monday:
                week_idx += 1

                # 1. Ops Planning & Co-man scheduling
                # Project weekly demand based on active B2B commitments and current D2C run-rate
                proj_demand: Dict[str, float] = {}
                for pl in ALLOWED_PRODUCT_LINES_LIST:
                    proj_demand[pl] = 1200.0 * (1.0 + self.config.demand_growth_rate_annual * (week_idx / 52.0))
                
                curr_inv: Dict[str, float] = {
                    pl: inventory_mgr.get_available_kg(pl, curr_d) for pl in ALLOWED_PRODUCT_LINES_LIST
                }
                ops_agent.plan_weekly_operations(curr_d, proj_demand, curr_inv)

                # 2. Process incoming co-man deliveries
                new_coman_act, delivered_coman = coman_sim.process_week(curr_d)
                coman_activity_rows.extend(new_coman_act)
                for pl, del_kg in delivered_coman.items():
                    if del_kg > 0:
                        inventory_mgr.add_lot(
                            product_line=pl,
                            qty_kg=del_kg,
                            creation_date=curr_d,
                            shelf_life_days=21,
                        )

                # 3. Simulate weekly in-house bioreactor batches
                # Check shocks affecting production
                shock_fail_mult = 1.0
                for s in self.config.shocks:
                    if s.event_type == "supply_disruption" and s.start_week <= week_idx < s.start_week + s.duration_weeks:
                        shock_fail_mult *= s.impact_factor

                new_batches, completed_batches = bioreactor_sim.simulate_week_batches(curr_d, shock_fail_mult)
                capacity_batch_rows.extend(new_batches)
                for cb in completed_batches:
                    if cb.actual_yield_kg > 0:
                        inventory_mgr.add_lot(
                            product_line=cb.product_line,
                            qty_kg=cb.actual_yield_kg,
                            creation_date=cb.end_date,
                            shelf_life_days=21,
                        )

                # 4. Marketing closed-loop review
                if weekly_spend_acc:
                    recent_cpa = {
                        k: (sp / max(1, weekly_conv_acc.get(k, 0)))
                        for k, sp in weekly_spend_acc.items()
                    }
                    weekly_spend_acc = {}
                    weekly_conv_acc = {}
                else:
                    recent_cpa = {}

                stockout_rates = {
                    r: (stockouts_by_region[r] / max(1, orders_by_region[r])) for r in region_ids
                }
                marketing_team.closed_loop_weekly_review(recent_cpa, stockout_rates)
                stockouts_by_region = {r: 0 for r in region_ids}
                orders_by_region = {r: 0 for r in region_ids}

            # -------------------------------------------------------------
            # DAILY EXECUTION LOOP
            # -------------------------------------------------------------

            # Check shock multipliers for today
            demand_surge_mult = 1.0
            viral_wom_mult = 1.0
            for s in self.config.shocks:
                if s.start_week <= week_idx < s.start_week + s.duration_weeks:
                    if s.event_type == "demand_surge":
                        demand_surge_mult *= s.impact_factor
                    elif s.event_type == "viral_wom":
                        viral_wom_mult *= s.impact_factor

            # Indian Calendar Seasonality factor
            seasonality = IndianCalendar.get_seasonality_factor(
                curr_d, region_tier="metro", base_sensitivity=self.config.seasonality_sensitivity
            )

            # Growth factor over time
            growth = (1.0 + self.config.demand_growth_rate_annual * ((curr_d - start_d).days / 365.25))

            # 1. Marketing Funnel Simulation
            curr_monday_iso = get_monday_of_week(curr_d).isoformat()
            daily_planned = {
                (r, camp.channel, camp.campaign_type): (
                    planned_spend_map.get((curr_monday_iso, r, camp.channel, camp.campaign_type), camp.base_weekly_spend_inr) / 7.0
                )
                for camp in self.config.marketing_campaigns
                for r in region_ids
            }

            mktg_out = marketing_engine.simulate_daily(
                current_date=curr_d,
                daily_planned_spend=daily_planned,
                tactical_multipliers=marketing_team.tactical_multipliers,
                growth_multiplier=growth * seasonality * demand_surge_mult,
            )
            marketing_daily_rows.extend(mktg_out.csv_rows)

            for mrow in mktg_out.csv_rows:
                k = (mrow.region_id, mrow.channel, mrow.campaign_type)
                weekly_spend_acc[k] = weekly_spend_acc.get(k, 0.0) + mrow.spend_inr
                weekly_conv_acc[k] = weekly_conv_acc.get(k, 0) + mrow.conversions

            # Active eligible SKUs for D2C today by region
            curr_iso = curr_d.isoformat()
            eligible_d2c_skus: Dict[str, List[str]] = {}
            for r_id in region_ids:
                eligible_d2c_skus[r_id] = [
                    pm.sku_id
                    for pm in product_matrix_rows
                    if pm.channel == "D2C"
                    and pm.region_id == r_id
                    and pm.eligible_from <= curr_iso
                    and (pm.eligible_to is None or pm.eligible_to == "" or pm.eligible_to >= curr_iso)
                ]

            # 2. Onboard new customers from marketing conversions
            for reg, camp_type, camp_id, acq_date_str in mktg_out.d2c_new_conversions:
                el_skus = eligible_d2c_skus.get(reg, [])
                if el_skus:
                    new_cust = consumer_mgr.onboard_new_customer(
                        region_id=reg,
                        acquired_date=curr_d,
                        acquisition_campaign_type=camp_type,
                        eligible_skus=el_skus,
                    )

            # 3. Organic demand & viral WOM acquisitions
            active_cust_counts = {
                r: sum(1 for c in consumer_mgr.customers.values() if c.region_id == r and c.churned_date is None)
                for r in region_ids
            }
            organic_acqs = organic_engine.simulate_daily_organic(
                current_date=curr_d,
                active_customer_count_by_region=active_cust_counts,
                viral_boost_multiplier=viral_wom_mult,
            )
            for org in organic_acqs:
                el_skus = eligible_d2c_skus.get(org.region_id, [])
                if el_skus:
                    consumer_mgr.onboard_new_customer(
                        region_id=org.region_id,
                        acquired_date=curr_d,
                        acquisition_campaign_type=None,  # Null for organic/WOM
                        eligible_skus=el_skus,
                    )

            # 4. Generate Order Intents for today
            daily_intents: List[UnfulfilledOrderIntent] = []

            # (a) B2B wholesale orders if Monday (or scheduled midweek batch)
            if is_monday:
                b2b_intents, order_counter = b2b_mgr.generate_orders_for_week(
                    monday=curr_d,
                    sku_pack_sizes=sku_pack_sizes,
                    sku_product_lines=sku_product_lines,
                    order_counter_start=order_counter,
                )
                daily_intents.extend(b2b_intents)

            # (b) D2C repeat & subscriber orders
            d2c_intents, order_counter = consumer_mgr.generate_daily_orders(
                current_date=curr_d,
                eligible_skus_by_region=eligible_d2c_skus,
                sku_prices=sku_prices,
                sku_pack_sizes=sku_pack_sizes,
                sku_product_lines=sku_product_lines,
                order_counter_start=order_counter,
            )
            daily_intents.extend(d2c_intents)

            # 5. Order Allocation under Capacity Ceiling
            if daily_intents:
                fulfilled_orders = allocator.allocate_orders(
                    intents=daily_intents,
                    current_date=curr_d,
                    sku_pack_sizes=sku_pack_sizes,
                )
                order_rows.extend(fulfilled_orders)

                # Process feedback & NPS
                for ord_row in fulfilled_orders:
                    orders_by_region[ord_row.region_id] = orders_by_region.get(ord_row.region_id, 0) + 1
                    if ord_row.status in ("partial", "waitlisted", "cancelled_stockout"):
                        stockouts_by_region[ord_row.region_id] = stockouts_by_region.get(ord_row.region_id, 0) + 1

                    if ord_row.channel == Channel.D2C.value and ord_row.customer_id:
                        is_delayed = bool(ord_row.delivered_date and ord_row.delivered_date > ord_row.promised_date)
                        nps_resp = consumer_mgr.record_fulfillment_experience(
                            customer_id=ord_row.customer_id,
                            status=ord_row.status,
                            delayed=is_delayed,
                        )
                        if nps_resp:
                            nps_rows.append(nps_resp)
                    elif ord_row.channel == Channel.B2B.value and ord_row.account_id:
                        req_q = float(ord_row.requested_qty_kg)
                        ful_q = float(ord_row.fulfilled_qty_kg)
                        ratio = ful_q / max(1e-4, req_q)
                        nps_resp = b2b_mgr.record_fulfillment_experience(
                            account_id=ord_row.account_id,
                            fulfilled_ratio=ratio,
                            current_date=curr_d,
                        )
                        if nps_resp:
                            nps_rows.append(nps_resp)

            # 6. Inventory Expiry / Spoilage
            inventory_mgr.expire_spoilage(curr_d)

            # Advance to next day
            curr_d += timedelta(days=1)

        # Final export rows
        b2b_account_rows = b2b_mgr.export_account_rows()
        customer_rows = consumer_mgr.export_customer_rows()

        tables = {
            "regions.csv": region_rows,
            "skus.csv": sku_rows,
            "product_matrix.csv": product_matrix_rows,
            "orders.csv": order_rows,
            "capacity_batches.csv": capacity_batch_rows,
            "capacity_plan.csv": capacity_plan_rows,
            "coman_contracts.csv": coman_contract_rows,
            "coman_activity.csv": coman_activity_rows,
            "b2b_accounts.csv": b2b_account_rows,
            "marketing_daily.csv": marketing_daily_rows,
            "marketing_plan.csv": marketing_plan_rows,
            "customers.csv": customer_rows,
            "nps_responses.csv": nps_rows,
        }

        return tables, start_d.isoformat(), history_end_d.isoformat(), plan_end_d.isoformat()


ALLOWED_PRODUCT_LINES_LIST = ["cultivated_chicken", "mycelium", "seaweed", "microbial"]
