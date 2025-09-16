"""
Event Classifier for FXML4 Trading System

This module provides intelligent classification of economic events based on
their potential market impact, affected currencies, and trading implications.
It helps the trading system make informed decisions about when to suspend
trading operations.

Key Features:
- Event impact level classification (Low, Medium, High, Critical)
- Currency impact mapping and cross-pair analysis
- Rule-based classification engine
- Historical impact analysis
- Custom classification rules
- Real-time impact assessment

Classification Criteria:
- Event type and historical volatility impact
- Currency and country significance
- Market session timing
- Forecast vs actual deviation analysis
"""

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .economic_calendar import EconomicEvent, EventImpact

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EventCategory(Enum):
    """Economic event categories."""

    MONETARY_POLICY = "monetary_policy"
    EMPLOYMENT = "employment"
    INFLATION = "inflation"
    GDP_GROWTH = "gdp_growth"
    MANUFACTURING = "manufacturing"
    RETAIL_CONSUMER = "retail_consumer"
    TRADE_BALANCE = "trade_balance"
    HOUSING = "housing"
    SERVICES = "services"
    CENTRAL_BANK_SPEECH = "central_bank_speech"
    GEOPOLITICAL = "geopolitical"
    OTHER = "other"


class CurrencyTier(Enum):
    """Currency importance tiers."""

    TIER_1 = 1  # USD, EUR, GBP, JPY - Major currencies
    TIER_2 = 2  # CHF, CAD, AUD, NZD - Major crosses
    TIER_3 = 3  # Other traded currencies


@dataclass
class ClassificationRule:
    """Event classification rule."""

    rule_id: str
    name: str
    event_patterns: List[str]  # Regex patterns to match event titles
    category: EventCategory
    base_impact: EventImpact
    currency_multiplier: Dict[str, float] = field(default_factory=dict)
    time_sensitivity_hours: int = 2  # Hours before/after event when impact is highest
    description: str = ""
    active: bool = True

    def matches_event(self, event: EconomicEvent) -> bool:
        """Check if rule matches the given event."""
        if not self.active:
            return False

        for pattern in self.event_patterns:
            if re.search(pattern, event.title, re.IGNORECASE):
                return True

        return False

    def calculate_impact(self, event: EconomicEvent) -> EventImpact:
        """Calculate event impact based on rule and event characteristics."""
        base_impact_score = self._impact_to_score(self.base_impact)

        # Apply currency multiplier
        currency_multiplier = self.currency_multiplier.get(event.currency, 1.0)
        adjusted_score = base_impact_score * currency_multiplier

        # Apply time-of-day multiplier (higher impact during active trading sessions)
        time_multiplier = self._calculate_time_multiplier(event)
        final_score = adjusted_score * time_multiplier

        return self._score_to_impact(final_score)

    def _impact_to_score(self, impact: EventImpact) -> float:
        """Convert impact enum to numeric score."""
        impact_scores = {
            EventImpact.LOW: 1.0,
            EventImpact.MEDIUM: 2.0,
            EventImpact.HIGH: 3.0,
            EventImpact.CRITICAL: 4.0,
        }
        return impact_scores[impact]

    def _score_to_impact(self, score: float) -> EventImpact:
        """Convert numeric score to impact enum."""
        if score >= 3.5:
            return EventImpact.CRITICAL
        elif score >= 2.5:
            return EventImpact.HIGH
        elif score >= 1.5:
            return EventImpact.MEDIUM
        else:
            return EventImpact.LOW

    def _calculate_time_multiplier(self, event: EconomicEvent) -> float:
        """Calculate time-based impact multiplier."""
        # Higher impact during major trading sessions
        hour_utc = event.date_time.hour

        # London session (8:00-16:00 UTC) and New York session (13:00-21:00 UTC)
        if (8 <= hour_utc <= 16) or (13 <= hour_utc <= 21):
            return 1.2  # 20% higher impact during active sessions
        else:
            return 0.8  # 20% lower impact during quiet hours


@dataclass
class CurrencyImpactMap:
    """Maps currencies to affected trading pairs."""

    base_currency: str
    tier: CurrencyTier
    major_pairs: Set[str] = field(default_factory=set)
    cross_pairs: Set[str] = field(default_factory=set)
    impact_radius: float = 1.0  # How far the impact spreads (0.0-1.0)

    def get_all_affected_pairs(self) -> Set[str]:
        """Get all pairs affected by this currency."""
        return self.major_pairs.union(self.cross_pairs)

    def get_impact_strength(self, pair: str) -> float:
        """Get impact strength for specific pair (0.0-1.0)."""
        if pair in self.major_pairs:
            return 1.0 * self.impact_radius
        elif pair in self.cross_pairs:
            return 0.7 * self.impact_radius
        else:
            return 0.0


class EventClassifier:
    """
    Intelligent economic event classifier.

    Analyzes economic events and classifies them by impact level,
    affected currencies, and trading implications.
    """

    def __init__(self):
        self.classification_rules: List[ClassificationRule] = []
        self.currency_maps: Dict[str, CurrencyImpactMap] = {}
        self.event_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # Initialize default rules and currency maps
        self._initialize_default_rules()
        self._initialize_currency_maps()

        logger.info(
            f"EventClassifier initialized with {len(self.classification_rules)} rules"
        )

    def _initialize_default_rules(self) -> None:
        """Initialize default classification rules."""
        # Central Bank Rate Decisions
        self.classification_rules.append(
            ClassificationRule(
                rule_id="cb_rate_decisions",
                name="Central Bank Rate Decisions",
                event_patterns=[
                    r"federal funds rate",
                    r"interest rate decision",
                    r"policy rate",
                    r"bank rate",
                    r"repo rate",
                    r"cash rate",
                    r"refi rate",
                ],
                category=EventCategory.MONETARY_POLICY,
                base_impact=EventImpact.CRITICAL,
                currency_multiplier={"USD": 1.0, "EUR": 1.0, "GBP": 1.0, "JPY": 0.9},
                time_sensitivity_hours=4,
                description="Central bank interest rate decisions",
            )
        )

        # Employment Data
        self.classification_rules.append(
            ClassificationRule(
                rule_id="employment_data",
                name="Employment Reports",
                event_patterns=[
                    r"non.?farm payrolls",
                    r"nfp",
                    r"employment change",
                    r"unemployment rate",
                    r"jobless claims",
                    r"labor force",
                    r"participation rate",
                ],
                category=EventCategory.EMPLOYMENT,
                base_impact=EventImpact.HIGH,
                currency_multiplier={"USD": 1.2, "EUR": 1.0, "GBP": 1.0},
                time_sensitivity_hours=2,
                description="Employment and labor market indicators",
            )
        )

        # Inflation Data
        self.classification_rules.append(
            ClassificationRule(
                rule_id="inflation_data",
                name="Inflation Indicators",
                event_patterns=[
                    r"consumer price index",
                    r"cpi",
                    r"producer price",
                    r"ppi",
                    r"inflation",
                    r"deflator",
                    r"core inflation",
                ],
                category=EventCategory.INFLATION,
                base_impact=EventImpact.HIGH,
                currency_multiplier={"USD": 1.1, "EUR": 1.0, "GBP": 1.0},
                time_sensitivity_hours=2,
                description="Inflation and price level indicators",
            )
        )

        # GDP and Growth
        self.classification_rules.append(
            ClassificationRule(
                rule_id="gdp_growth",
                name="GDP and Growth Indicators",
                event_patterns=[
                    r"gross domestic product",
                    r"gdp",
                    r"economic growth",
                    r"quarterly growth",
                    r"gdp annualized",
                    r"gdp preliminary",
                ],
                category=EventCategory.GDP_GROWTH,
                base_impact=EventImpact.HIGH,
                currency_multiplier={"USD": 1.0, "EUR": 0.9, "GBP": 0.9},
                time_sensitivity_hours=3,
                description="GDP and economic growth measures",
            )
        )

        # Manufacturing Data
        self.classification_rules.append(
            ClassificationRule(
                rule_id="manufacturing_data",
                name="Manufacturing Indicators",
                event_patterns=[
                    r"manufacturing pmi",
                    r"industrial production",
                    r"factory orders",
                    r"ism manufacturing",
                    r"markit pmi",
                    r"purchasing managers",
                ],
                category=EventCategory.MANUFACTURING,
                base_impact=EventImpact.MEDIUM,
                currency_multiplier={"USD": 0.9, "EUR": 0.8, "GBP": 0.8},
                time_sensitivity_hours=1,
                description="Manufacturing and industrial indicators",
            )
        )

        # Retail and Consumer Data
        self.classification_rules.append(
            ClassificationRule(
                rule_id="retail_consumer",
                name="Retail and Consumer Data",
                event_patterns=[
                    r"retail sales",
                    r"consumer confidence",
                    r"consumer spending",
                    r"consumer sentiment",
                    r"personal income",
                    r"personal spending",
                ],
                category=EventCategory.RETAIL_CONSUMER,
                base_impact=EventImpact.MEDIUM,
                currency_multiplier={"USD": 1.0, "EUR": 0.8, "GBP": 0.8},
                time_sensitivity_hours=2,
                description="Retail sales and consumer indicators",
            )
        )

        # Central Bank Speeches
        self.classification_rules.append(
            ClassificationRule(
                rule_id="cb_speeches",
                name="Central Bank Speeches",
                event_patterns=[
                    r"fed chair",
                    r"fed governor",
                    r"ecb president",
                    r"boe governor",
                    r"speaks",
                    r"testimony",
                    r"jackson hole",
                    r"fomc member",
                ],
                category=EventCategory.CENTRAL_BANK_SPEECH,
                base_impact=EventImpact.MEDIUM,
                currency_multiplier={"USD": 0.8, "EUR": 0.7, "GBP": 0.7},
                time_sensitivity_hours=1,
                description="Central bank official speeches and testimonies",
            )
        )

    def _initialize_currency_maps(self) -> None:
        """Initialize currency impact maps."""
        # USD - Tier 1
        self.currency_maps["USD"] = CurrencyImpactMap(
            base_currency="USD",
            tier=CurrencyTier.TIER_1,
            major_pairs={
                "EURUSD",
                "GBPUSD",
                "USDJPY",
                "USDCHF",
                "USDCAD",
                "AUDUSD",
                "NZDUSD",
            },
            cross_pairs={"EURJPY", "GBPJPY", "CHFJPY", "CADJPY", "AUDJPY", "NZDJPY"},
            impact_radius=1.0,
        )

        # EUR - Tier 1
        self.currency_maps["EUR"] = CurrencyImpactMap(
            base_currency="EUR",
            tier=CurrencyTier.TIER_1,
            major_pairs={
                "EURUSD",
                "EURGBP",
                "EURJPY",
                "EURCHF",
                "EURCAD",
                "EURAUD",
                "EURNZD",
            },
            cross_pairs={"GBPCHF", "CADCHF", "AUDCHF", "NZDCHF"},
            impact_radius=0.9,
        )

        # GBP - Tier 1
        self.currency_maps["GBP"] = CurrencyImpactMap(
            base_currency="GBP",
            tier=CurrencyTier.TIER_1,
            major_pairs={
                "GBPUSD",
                "EURGBP",
                "GBPJPY",
                "GBPCHF",
                "GBPCAD",
                "GBPAUD",
                "GBPNZD",
            },
            cross_pairs={"EURAUD", "EURCAD", "EURNZD"},
            impact_radius=0.8,
        )

        # JPY - Tier 1
        self.currency_maps["JPY"] = CurrencyImpactMap(
            base_currency="JPY",
            tier=CurrencyTier.TIER_1,
            major_pairs={
                "USDJPY",
                "EURJPY",
                "GBPJPY",
                "CHFJPY",
                "CADJPY",
                "AUDJPY",
                "NZDJPY",
            },
            cross_pairs={"AUDCAD", "NZDCAD", "AUDNZD"},
            impact_radius=0.7,
        )

        # CHF - Tier 2
        self.currency_maps["CHF"] = CurrencyImpactMap(
            base_currency="CHF",
            tier=CurrencyTier.TIER_2,
            major_pairs={"USDCHF", "EURCHF", "GBPCHF", "CHFJPY"},
            cross_pairs={"CADCHF", "AUDCHF", "NZDCHF"},
            impact_radius=0.6,
        )

        # CAD - Tier 2
        self.currency_maps["CAD"] = CurrencyImpactMap(
            base_currency="CAD",
            tier=CurrencyTier.TIER_2,
            major_pairs={"USDCAD", "EURCAD", "GBPCAD", "CADJPY"},
            cross_pairs={"CADCHF", "AUDCAD", "NZDCAD"},
            impact_radius=0.6,
        )

    def classify_event(
        self, event: EconomicEvent
    ) -> Tuple[EventImpact, EventCategory, Set[str]]:
        """
        Classify an economic event.

        Returns:
            Tuple of (impact_level, category, affected_pairs)
        """
        # Find matching classification rules
        matching_rules = [
            rule for rule in self.classification_rules if rule.matches_event(event)
        ]

        if not matching_rules:
            # Default classification for unmatched events
            impact = self._classify_by_default_logic(event)
            category = self._categorize_by_title(event.title)
            affected_pairs = self._get_affected_pairs(event.currency)
            return impact, category, affected_pairs

        # Use the first matching rule (rules should be ordered by specificity)
        primary_rule = matching_rules[0]
        impact = primary_rule.calculate_impact(event)
        category = primary_rule.category
        affected_pairs = self._get_affected_pairs(event.currency)

        logger.debug(
            f"Classified event '{event.title}' as {impact.value} impact, category: {category.value}"
        )

        # Record classification for future analysis
        self._record_classification(event, impact, category, primary_rule)

        return impact, category, affected_pairs

    def get_trading_suspension_recommendation(
        self, event: EconomicEvent
    ) -> Dict[str, Any]:
        """Get trading suspension recommendation for an event."""
        impact, category, affected_pairs = self.classify_event(event)

        # Determine suspension timing
        suspension_config = self._get_suspension_config(impact, category)

        # Calculate suspension windows
        pre_event_minutes = suspension_config["pre_event_minutes"]
        post_event_minutes = suspension_config["post_event_minutes"]

        suspension_start = event.date_time - timedelta(minutes=pre_event_minutes)
        suspension_end = event.date_time + timedelta(minutes=post_event_minutes)

        return {
            "event_id": event.event_id,
            "event_title": event.title,
            "event_time": event.date_time.isoformat(),
            "impact_level": impact.value,
            "category": category.value,
            "suspension_recommended": impact
            in [EventImpact.HIGH, EventImpact.CRITICAL],
            "affected_pairs": list(affected_pairs),
            "suspension_start": suspension_start.isoformat(),
            "suspension_end": suspension_end.isoformat(),
            "pre_event_minutes": pre_event_minutes,
            "post_event_minutes": post_event_minutes,
            "total_suspension_minutes": pre_event_minutes + post_event_minutes,
            "reasoning": self._get_suspension_reasoning(impact, category, event),
        }

    def _classify_by_default_logic(self, event: EconomicEvent) -> EventImpact:
        """Default classification logic for unmatched events."""
        # Simple keyword-based classification
        title_lower = event.title.lower()

        # Critical keywords
        critical_keywords = [
            "rate decision",
            "fed chair",
            "ecb president",
            "non-farm payrolls",
        ]
        if any(keyword in title_lower for keyword in critical_keywords):
            return EventImpact.CRITICAL

        # High impact keywords
        high_keywords = ["cpi", "gdp", "unemployment", "inflation", "employment"]
        if any(keyword in title_lower for keyword in high_keywords):
            return EventImpact.HIGH

        # Medium impact keywords
        medium_keywords = ["pmi", "retail sales", "industrial", "manufacturing"]
        if any(keyword in title_lower for keyword in medium_keywords):
            return EventImpact.MEDIUM

        # Default to low impact
        return EventImpact.LOW

    def _categorize_by_title(self, title: str) -> EventCategory:
        """Categorize event by title keywords."""
        title_lower = title.lower()

        category_keywords = {
            EventCategory.MONETARY_POLICY: ["rate", "policy", "fed", "ecb", "boe"],
            EventCategory.EMPLOYMENT: [
                "employment",
                "jobs",
                "unemployment",
                "payrolls",
                "jobless",
            ],
            EventCategory.INFLATION: ["cpi", "inflation", "price", "ppi"],
            EventCategory.GDP_GROWTH: ["gdp", "growth", "economic"],
            EventCategory.MANUFACTURING: [
                "manufacturing",
                "industrial",
                "factory",
                "pmi",
            ],
            EventCategory.RETAIL_CONSUMER: [
                "retail",
                "consumer",
                "spending",
                "confidence",
            ],
            EventCategory.CENTRAL_BANK_SPEECH: [
                "speaks",
                "speech",
                "testimony",
                "remarks",
            ],
        }

        for category, keywords in category_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                return category

        return EventCategory.OTHER

    def _get_affected_pairs(self, currency: str) -> Set[str]:
        """Get trading pairs affected by currency events."""
        if currency not in self.currency_maps:
            return set()

        currency_map = self.currency_maps[currency]
        return currency_map.get_all_affected_pairs()

    def _get_suspension_config(
        self, impact: EventImpact, category: EventCategory
    ) -> Dict[str, int]:
        """Get suspension timing configuration."""
        # Base suspension times by impact level
        base_config = {
            EventImpact.LOW: {"pre_event_minutes": 0, "post_event_minutes": 0},
            EventImpact.MEDIUM: {"pre_event_minutes": 5, "post_event_minutes": 10},
            EventImpact.HIGH: {"pre_event_minutes": 15, "post_event_minutes": 30},
            EventImpact.CRITICAL: {"pre_event_minutes": 30, "post_event_minutes": 60},
        }

        config = base_config[impact].copy()

        # Category-specific adjustments
        category_adjustments = {
            EventCategory.MONETARY_POLICY: {
                "pre_multiplier": 1.5,
                "post_multiplier": 2.0,
            },
            EventCategory.EMPLOYMENT: {"pre_multiplier": 1.2, "post_multiplier": 1.5},
            EventCategory.INFLATION: {"pre_multiplier": 1.2, "post_multiplier": 1.3},
            EventCategory.CENTRAL_BANK_SPEECH: {
                "pre_multiplier": 0.8,
                "post_multiplier": 0.8,
            },
        }

        if category in category_adjustments:
            adj = category_adjustments[category]
            config["pre_event_minutes"] = int(
                config["pre_event_minutes"] * adj.get("pre_multiplier", 1.0)
            )
            config["post_event_minutes"] = int(
                config["post_event_minutes"] * adj.get("post_multiplier", 1.0)
            )

        return config

    def _get_suspension_reasoning(
        self, impact: EventImpact, category: EventCategory, event: EconomicEvent
    ) -> str:
        """Generate reasoning for suspension recommendation."""
        if impact in [EventImpact.LOW, EventImpact.MEDIUM]:
            return f"Low-to-medium impact {category.value} event. Minimal trading suspension required."

        base_reason = f"High impact {category.value} event affecting {event.currency} currency pairs."

        if impact == EventImpact.CRITICAL:
            return f"{base_reason} Extended trading suspension recommended due to potential extreme volatility."
        else:
            return f"{base_reason} Standard trading suspension recommended during event period."

    def _record_classification(
        self,
        event: EconomicEvent,
        impact: EventImpact,
        category: EventCategory,
        rule: ClassificationRule,
    ) -> None:
        """Record classification for analysis."""
        classification_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_id": event.event_id,
            "event_title": event.title,
            "currency": event.currency,
            "impact": impact.value,
            "category": category.value,
            "rule_id": rule.rule_id,
            "rule_name": rule.name,
        }

        self.event_history[event.event_id].append(classification_record)

    def add_custom_rule(self, rule: ClassificationRule) -> None:
        """Add custom classification rule."""
        # Insert at beginning to give priority to custom rules
        self.classification_rules.insert(0, rule)
        logger.info(f"Added custom classification rule: {rule.name}")

    def remove_rule(self, rule_id: str) -> bool:
        """Remove classification rule."""
        for i, rule in enumerate(self.classification_rules):
            if rule.rule_id == rule_id:
                removed_rule = self.classification_rules.pop(i)
                logger.info(f"Removed classification rule: {removed_rule.name}")
                return True
        return False

    def get_classification_stats(self) -> Dict[str, Any]:
        """Get classification statistics."""
        total_classifications = sum(
            len(history) for history in self.event_history.values()
        )

        impact_counts = defaultdict(int)
        category_counts = defaultdict(int)
        currency_counts = defaultdict(int)

        for event_history in self.event_history.values():
            if event_history:  # Get latest classification for each event
                latest = event_history[-1]
                impact_counts[latest["impact"]] += 1
                category_counts[latest["category"]] += 1
                currency_counts[latest["currency"]] += 1

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_classifications": total_classifications,
            "unique_events_classified": len(self.event_history),
            "active_rules": len([r for r in self.classification_rules if r.active]),
            "total_rules": len(self.classification_rules),
            "classification_by_impact": dict(impact_counts),
            "classification_by_category": dict(category_counts),
            "classification_by_currency": dict(currency_counts),
        }
