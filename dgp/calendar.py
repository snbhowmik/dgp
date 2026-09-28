"""Calendar utilities, week boundaries, and Indian seasonality and festival cycles."""

from datetime import date, timedelta
from typing import Dict, List, Tuple


def get_monday_of_week(d: date) -> date:
    """Return the Monday of the week containing date d."""
    return d - timedelta(days=d.weekday())


def date_range(start_date: date, end_date: date):
    """Generate dates from start_date to end_date (inclusive)."""
    curr = start_date
    while curr <= end_date:
        yield curr
        curr += timedelta(days=1)


def get_all_mondays(start_date: date, end_date: date) -> List[date]:
    """Return all Mondays in the date range."""
    first_monday = get_monday_of_week(start_date)
    mondays = []
    curr = first_monday
    while curr <= end_date:
        if curr >= start_date:
            mondays.append(curr)
        curr += timedelta(days=7)
    return mondays


class IndianCalendar:
    """Provides Indian calendar factors, seasonality multipliers, and festival impacts."""

    # Approximate festival date anchors per year (Gregorian dates)
    # Diwali, Dussehra, Navratri (Autumn), Eid al-Fitr, Holi, New Year
    FESTIVAL_ANCHORS = {
        2022: {
            "holi": date(2022, 3, 18),
            "eid": date(2022, 5, 3),
            "shravan_start": date(2022, 7, 14),
            "shravan_end": date(2022, 8, 12),
            "navratri_start": date(2022, 9, 26),
            "navratri_end": date(2022, 10, 5),
            "dussehra": date(2022, 10, 5),
            "diwali": date(2022, 10, 24),
            "winter_holiday_start": date(2022, 12, 20),
            "winter_holiday_end": date(2023, 1, 2),
        },
        2023: {
            "holi": date(2023, 3, 8),
            "eid": date(2023, 4, 22),
            "shravan_start": date(2023, 7, 4),
            "shravan_end": date(2023, 8, 31),  # Adhik maas year
            "navratri_start": date(2023, 10, 15),
            "navratri_end": date(2023, 10, 24),
            "dussehra": date(2023, 10, 24),
            "diwali": date(2023, 11, 12),
            "winter_holiday_start": date(2023, 12, 20),
            "winter_holiday_end": date(2024, 1, 2),
        },
        2024: {
            "holi": date(2024, 3, 25),
            "eid": date(2024, 4, 11),
            "shravan_start": date(2024, 7, 22),
            "shravan_end": date(2024, 8, 19),
            "navratri_start": date(2024, 10, 3),
            "navratri_end": date(2024, 10, 12),
            "dussehra": date(2024, 10, 12),
            "diwali": date(2024, 11, 1),
            "winter_holiday_start": date(2024, 12, 20),
            "winter_holiday_end": date(2025, 1, 2),
        },
        2025: {
            "holi": date(2025, 3, 14),
            "eid": date(2025, 3, 31),
            "shravan_start": date(2025, 7, 11),
            "shravan_end": date(2025, 8, 9),
            "navratri_start": date(2025, 9, 22),
            "navratri_end": date(2025, 10, 2),
            "dussehra": date(2025, 10, 2),
            "diwali": date(2025, 10, 20),
            "winter_holiday_start": date(2025, 12, 20),
            "winter_holiday_end": date(2026, 1, 2),
        },
        2026: {
            "holi": date(2026, 3, 4),
            "eid": date(2026, 3, 20),
            "shravan_start": date(2026, 7, 29),
            "shravan_end": date(2026, 8, 27),
            "navratri_start": date(2026, 10, 11),
            "navratri_end": date(2026, 10, 20),
            "dussehra": date(2026, 10, 20),
            "diwali": date(2026, 11, 8),
            "winter_holiday_start": date(2026, 12, 20),
            "winter_holiday_end": date(2027, 1, 2),
        },
    }

    @classmethod
    def get_seasonality_factor(cls, d: date, region_tier: str, base_sensitivity: float = 1.0) -> float:
        """
        Calculate seasonal demand multiplier for food/alternative protein.
        Includes monthly baseline, summer heatwave impact, festival peaks and fasting dips.
        """
        # Baseline annual smooth wave (peak in winter dining Nov-Feb, dip in summer May-July)
        day_of_year = d.timetuple().tm_yday
        import math
        # Annual cycle peaked around mid December (day ~350)
        annual_cycle = 1.0 + 0.12 * math.cos(2 * math.pi * (day_of_year - 350) / 365.25)

        # Festival modifiers
        fest_mod = 1.0
        events = cls.FESTIVAL_ANCHORS.get(d.year, {})

        # Navratri: fasting dip for general meat, curiosity/substitute peak for alt-protein early adopters
        # In Indian metros/tier 1, restaurant footfalls shift, B2B wholesale can dip slightly or pivot
        if "navratri_start" in events and "navratri_end" in events:
            if events["navratri_start"] <= d <= events["navratri_end"]:
                fest_mod *= 0.82  # temporary fasting dip

        # Shravan season: mild dip across North/West regions
        if "shravan_start" in events and "shravan_end" in events:
            if events["shravan_start"] <= d <= events["shravan_end"]:
                fest_mod *= 0.90

        # Post-Diwali / Diwali week: celebration surge
        if "diwali" in events:
            diwali_day = events["diwali"]
            diff = (d - diwali_day).days
            if -3 <= diff <= 7:
                fest_mod *= 1.30

        # Winter wedding and holiday party season (late Dec - early Jan)
        if "winter_holiday_start" in events and "winter_holiday_end" in events:
            if events["winter_holiday_start"] <= d <= events["winter_holiday_end"]:
                fest_mod *= 1.25

        # Holi: spring festive bump
        if "holi" in events:
            diff = abs((d - events["holi"]).days)
            if diff <= 2:
                fest_mod *= 1.15

        # Blend with base_sensitivity
        multiplier = 1.0 + (annual_cycle * fest_mod - 1.0) * base_sensitivity
        return max(0.4, multiplier)

    @classmethod
    def get_day_of_week_factor(cls, d: date, channel: str) -> float:
        """Day of week multipliers. D2C peaks on weekends; B2B orders peak Mon-Wed."""
        weekday = d.weekday()  # 0 = Monday, 6 = Sunday
        if channel == "D2C":
            # Friday evening to Sunday has higher e-commerce grocery ordering
            factors = [0.85, 0.85, 0.90, 0.95, 1.15, 1.25, 1.05]
            return factors[weekday]
        else:
            # B2B orders placed Mon-Thu for kitchen prep
            factors = [1.35, 1.25, 1.15, 1.10, 0.85, 0.70, 0.60]
            return factors[weekday]
