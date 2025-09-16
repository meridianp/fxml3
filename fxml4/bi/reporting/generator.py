"""
Custom Report Generation Engine

Provides flexible report generation capabilities with templates, parameters,
and multiple output formats for FXML4 business intelligence.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ...core.exceptions import FXML4Exception
from ...core.logger import setup_logger
from ...data_engineering.database_manager import DatabaseManager

logger = setup_logger(__name__)


@dataclass
class ReportRequest:
    """Report generation request configuration."""

    report_id: str
    template_name: str
    parameters: Dict[str, Any]
    output_formats: List[str]  # ['pdf', 'excel', 'html', 'json']
    recipients: List[str]
    schedule: Optional[str] = None  # cron expression
    priority: str = "medium"  # low, medium, high, critical
    data_sources: List[str] = None


@dataclass
class ReportMetadata:
    """Report metadata and execution information."""

    report_id: str
    template_name: str
    generated_at: datetime
    generation_time_ms: float
    data_freshness: datetime
    row_count: int
    file_size_bytes: int
    output_formats: List[str]
    parameters_used: Dict[str, Any]
    data_quality_score: float


@dataclass
class ReportSection:
    """Individual report section."""

    section_id: str
    title: str
    section_type: str  # table, chart, text, metrics, summary
    data: Any
    metadata: Dict[str, Any]
    formatting: Dict[str, Any]


class ReportGenerator:
    """
    Advanced Report Generation Engine.

    Provides flexible report generation with templates, parameters,
    multiple output formats, and automated distribution.
    """

    def __init__(self, db_manager: DatabaseManager):
        """Initialize report generator."""
        self.db = db_manager
        self.logger = setup_logger(__name__)

        # Report templates
        self.templates = {}
        self.template_cache = {}

        # Report history
        self.report_history = {}
        self.generation_stats = {
            "total_reports": 0,
            "total_generation_time": 0.0,
            "success_count": 0,
            "error_count": 0,
        }

        # Data sources
        self.data_sources = {}

        # Output directory
        self.output_dir = Path("reports/generated")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def initialize_templates(self) -> None:
        """Initialize standard report templates."""
        try:
            self.logger.info("Initializing report templates...")

            # Executive Summary Template
            self.templates["executive_summary"] = {
                "name": "Executive Summary Report",
                "description": "High-level portfolio and trading performance summary",
                "sections": [
                    {
                        "id": "overview",
                        "title": "Portfolio Overview",
                        "type": "metrics",
                    },
                    {
                        "id": "performance",
                        "title": "Performance Summary",
                        "type": "chart",
                    },
                    {"id": "risk", "title": "Risk Metrics", "type": "table"},
                    {"id": "positions", "title": "Current Positions", "type": "table"},
                    {"id": "insights", "title": "Key Insights", "type": "text"},
                ],
                "parameters": {
                    "date_range": {"type": "date_range", "required": True},
                    "include_predictions": {"type": "boolean", "default": True},
                    "detail_level": {
                        "type": "select",
                        "options": ["summary", "detailed"],
                        "default": "summary",
                    },
                },
            }

            # Trading Performance Template
            self.templates["trading_performance"] = {
                "name": "Trading Performance Analysis",
                "description": "Detailed trading activity and performance analysis",
                "sections": [
                    {
                        "id": "summary_metrics",
                        "title": "Performance Metrics",
                        "type": "metrics",
                    },
                    {"id": "pnl_chart", "title": "P&L Over Time", "type": "chart"},
                    {
                        "id": "trade_analysis",
                        "title": "Trade Analysis",
                        "type": "table",
                    },
                    {
                        "id": "strategy_breakdown",
                        "title": "Strategy Performance",
                        "type": "chart",
                    },
                    {
                        "id": "execution_quality",
                        "title": "Execution Quality",
                        "type": "table",
                    },
                ],
                "parameters": {
                    "date_range": {"type": "date_range", "required": True},
                    "symbols": {"type": "multi_select", "required": False},
                    "strategies": {"type": "multi_select", "required": False},
                },
            }

            # Risk Analysis Template
            self.templates["risk_analysis"] = {
                "name": "Risk Analysis Report",
                "description": "Comprehensive risk assessment and monitoring",
                "sections": [
                    {"id": "risk_summary", "title": "Risk Overview", "type": "metrics"},
                    {
                        "id": "var_analysis",
                        "title": "Value at Risk Analysis",
                        "type": "chart",
                    },
                    {
                        "id": "stress_tests",
                        "title": "Stress Test Results",
                        "type": "table",
                    },
                    {
                        "id": "correlation_matrix",
                        "title": "Correlation Analysis",
                        "type": "chart",
                    },
                    {
                        "id": "risk_attribution",
                        "title": "Risk Attribution",
                        "type": "table",
                    },
                ],
                "parameters": {
                    "confidence_level": {
                        "type": "select",
                        "options": ["95%", "99%"],
                        "default": "95%",
                    },
                    "include_stress_tests": {"type": "boolean", "default": True},
                },
            }

            # Compliance Template
            self.templates["compliance_report"] = {
                "name": "Compliance Monitoring Report",
                "description": "Regulatory compliance and surveillance report",
                "sections": [
                    {
                        "id": "compliance_overview",
                        "title": "Compliance Status",
                        "type": "metrics",
                    },
                    {
                        "id": "surveillance_alerts",
                        "title": "Surveillance Alerts",
                        "type": "table",
                    },
                    {
                        "id": "regulatory_metrics",
                        "title": "Regulatory Metrics",
                        "type": "table",
                    },
                    {
                        "id": "audit_trail",
                        "title": "Audit Trail Summary",
                        "type": "table",
                    },
                ],
                "parameters": {
                    "date_range": {"type": "date_range", "required": True},
                    "alert_severity": {
                        "type": "multi_select",
                        "options": ["low", "medium", "high", "critical"],
                    },
                },
            }

            # Custom Analysis Template
            self.templates["custom_analysis"] = {
                "name": "Custom Analysis Report",
                "description": "Flexible report with user-defined analysis",
                "sections": [],  # Populated dynamically
                "parameters": {
                    "analysis_type": {"type": "select", "required": True},
                    "date_range": {"type": "date_range", "required": True},
                    "custom_query": {"type": "text", "required": False},
                },
            }

            self.logger.info(f"Initialized {len(self.templates)} report templates")

        except Exception as e:
            self.logger.error(f"Error initializing templates: {e}")
            raise FXML4Exception(f"Template initialization failed: {e}")

    async def generate_report(self, request: ReportRequest) -> Dict[str, Any]:
        """
        Generate report based on request.

        Args:
            request: Report generation request

        Returns:
            Dict containing report data and metadata
        """
        start_time = datetime.utcnow()

        try:
            self.logger.info(f"Generating report: {request.report_id}")
            self.generation_stats["total_reports"] += 1

            # Validate template
            if request.template_name not in self.templates:
                raise FXML4Exception(f"Unknown template: {request.template_name}")

            template = self.templates[request.template_name]

            # Validate parameters
            validated_params = await self._validate_parameters(
                request.parameters, template.get("parameters", {})
            )

            # Generate report sections
            sections = []
            total_rows = 0

            for section_config in template["sections"]:
                section_data = await self._generate_section(
                    section_config, validated_params, request
                )
                sections.append(section_data)
                total_rows += section_data.metadata.get("row_count", 0)

            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.generation_stats["total_generation_time"] += execution_time

            # Create report metadata
            metadata = ReportMetadata(
                report_id=request.report_id,
                template_name=request.template_name,
                generated_at=datetime.utcnow(),
                generation_time_ms=execution_time,
                data_freshness=await self._get_data_freshness(),
                row_count=total_rows,
                file_size_bytes=0,  # Will be calculated after file generation
                output_formats=request.output_formats,
                parameters_used=validated_params,
                data_quality_score=await self._calculate_data_quality_score(),
            )

            # Create complete report
            report_data = {
                "metadata": asdict(metadata),
                "template": template,
                "sections": [asdict(section) for section in sections],
                "summary": await self._generate_report_summary(sections, metadata),
                "generated_at": datetime.utcnow().isoformat(),
            }

            # Store in history
            self.report_history[request.report_id] = {
                "request": asdict(request),
                "metadata": asdict(metadata),
                "generated_at": datetime.utcnow().isoformat(),
            }

            self.generation_stats["success_count"] += 1

            return report_data

        except Exception as e:
            self.generation_stats["error_count"] += 1
            self.logger.error(f"Error generating report {request.report_id}: {e}")
            raise FXML4Exception(f"Report generation failed: {e}")

    async def generate_executive_summary(
        self, date_range: Tuple[datetime, datetime], include_predictions: bool = True
    ) -> Dict[str, Any]:
        """Generate executive summary report."""
        try:
            request = ReportRequest(
                report_id=f"exec_summary_{int(datetime.utcnow().timestamp())}",
                template_name="executive_summary",
                parameters={
                    "date_range": date_range,
                    "include_predictions": include_predictions,
                    "detail_level": "summary",
                },
                output_formats=["html", "pdf"],
                recipients=[],
            )

            return await self.generate_report(request)

        except Exception as e:
            self.logger.error(f"Error generating executive summary: {e}")
            raise FXML4Exception(f"Executive summary generation failed: {e}")

    async def generate_trading_report(
        self,
        date_range: Tuple[datetime, datetime],
        symbols: List[str] = None,
        strategies: List[str] = None,
    ) -> Dict[str, Any]:
        """Generate trading performance report."""
        try:
            request = ReportRequest(
                report_id=f"trading_perf_{int(datetime.utcnow().timestamp())}",
                template_name="trading_performance",
                parameters={
                    "date_range": date_range,
                    "symbols": symbols or [],
                    "strategies": strategies or [],
                },
                output_formats=["excel", "html"],
                recipients=[],
            )

            return await self.generate_report(request)

        except Exception as e:
            self.logger.error(f"Error generating trading report: {e}")
            raise FXML4Exception(f"Trading report generation failed: {e}")

    async def generate_risk_report(
        self, confidence_level: str = "95%", include_stress_tests: bool = True
    ) -> Dict[str, Any]:
        """Generate risk analysis report."""
        try:
            request = ReportRequest(
                report_id=f"risk_analysis_{int(datetime.utcnow().timestamp())}",
                template_name="risk_analysis",
                parameters={
                    "confidence_level": confidence_level,
                    "include_stress_tests": include_stress_tests,
                },
                output_formats=["pdf", "html"],
                recipients=[],
            )

            return await self.generate_report(request)

        except Exception as e:
            self.logger.error(f"Error generating risk report: {e}")
            raise FXML4Exception(f"Risk report generation failed: {e}")

    async def list_available_templates(self) -> Dict[str, Any]:
        """List all available report templates."""
        return {
            template_name: {
                "name": template["name"],
                "description": template["description"],
                "parameters": template.get("parameters", {}),
                "sections": [s["title"] for s in template["sections"]],
            }
            for template_name, template in self.templates.items()
        }

    async def get_report_history(
        self, limit: int = 50, template_name: str = None
    ) -> List[Dict[str, Any]]:
        """Get report generation history."""
        try:
            history = list(self.report_history.values())

            # Filter by template if specified
            if template_name:
                history = [
                    h for h in history if h["request"]["template_name"] == template_name
                ]

            # Sort by generation time (most recent first)
            history.sort(key=lambda x: x["generated_at"], reverse=True)

            return history[:limit]

        except Exception as e:
            self.logger.error(f"Error getting report history: {e}")
            return []

    # Section Generation Methods
    async def _generate_section(
        self,
        section_config: Dict[str, Any],
        parameters: Dict[str, Any],
        request: ReportRequest,
    ) -> ReportSection:
        """Generate individual report section."""
        try:
            section_id = section_config["id"]
            section_type = section_config["type"]

            self.logger.debug(f"Generating section: {section_id} ({section_type})")

            # Route to appropriate section generator
            if section_type == "metrics":
                data = await self._generate_metrics_section(section_id, parameters)
            elif section_type == "chart":
                data = await self._generate_chart_section(section_id, parameters)
            elif section_type == "table":
                data = await self._generate_table_section(section_id, parameters)
            elif section_type == "text":
                data = await self._generate_text_section(section_id, parameters)
            elif section_type == "summary":
                data = await self._generate_summary_section(section_id, parameters)
            else:
                raise FXML4Exception(f"Unknown section type: {section_type}")

            # Calculate section metadata
            row_count = len(data) if isinstance(data, list) else 1

            return ReportSection(
                section_id=section_id,
                title=section_config["title"],
                section_type=section_type,
                data=data,
                metadata={
                    "row_count": row_count,
                    "generated_at": datetime.utcnow().isoformat(),
                    "data_source": "database",
                },
                formatting={"style": "standard", "color_scheme": "default"},
            )

        except Exception as e:
            self.logger.error(f"Error generating section {section_config['id']}: {e}")
            raise FXML4Exception(f"Section generation failed: {e}")

    async def _generate_metrics_section(
        self, section_id: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate metrics section data."""
        try:
            if section_id == "overview":
                return await self._get_portfolio_overview_metrics(parameters)
            elif section_id == "risk_summary":
                return await self._get_risk_summary_metrics(parameters)
            elif section_id == "compliance_overview":
                return await self._get_compliance_overview_metrics(parameters)
            elif section_id == "summary_metrics":
                return await self._get_trading_summary_metrics(parameters)
            else:
                # Generic metrics
                return await self._get_generic_metrics(section_id, parameters)

        except Exception as e:
            self.logger.error(f"Error generating metrics section {section_id}: {e}")
            raise

    async def _generate_chart_section(
        self, section_id: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate chart section data."""
        try:
            if section_id == "performance":
                return await self._get_performance_chart_data(parameters)
            elif section_id == "pnl_chart":
                return await self._get_pnl_chart_data(parameters)
            elif section_id == "var_analysis":
                return await self._get_var_chart_data(parameters)
            elif section_id == "strategy_breakdown":
                return await self._get_strategy_chart_data(parameters)
            elif section_id == "correlation_matrix":
                return await self._get_correlation_chart_data(parameters)
            else:
                # Generic chart
                return await self._get_generic_chart_data(section_id, parameters)

        except Exception as e:
            self.logger.error(f"Error generating chart section {section_id}: {e}")
            raise

    async def _generate_table_section(
        self, section_id: str, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate table section data."""
        try:
            if section_id == "risk":
                return await self._get_risk_table_data(parameters)
            elif section_id == "positions":
                return await self._get_positions_table_data(parameters)
            elif section_id == "trade_analysis":
                return await self._get_trades_table_data(parameters)
            elif section_id == "execution_quality":
                return await self._get_execution_table_data(parameters)
            elif section_id == "stress_tests":
                return await self._get_stress_test_table_data(parameters)
            elif section_id == "surveillance_alerts":
                return await self._get_surveillance_table_data(parameters)
            elif section_id == "regulatory_metrics":
                return await self._get_regulatory_table_data(parameters)
            elif section_id == "audit_trail":
                return await self._get_audit_table_data(parameters)
            elif section_id == "risk_attribution":
                return await self._get_risk_attribution_table_data(parameters)
            else:
                # Generic table
                return await self._get_generic_table_data(section_id, parameters)

        except Exception as e:
            self.logger.error(f"Error generating table section {section_id}: {e}")
            raise

    async def _generate_text_section(
        self, section_id: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate text section data."""
        try:
            if section_id == "insights":
                return await self._get_key_insights(parameters)
            else:
                # Generic text
                return {
                    "content": f"Text content for section: {section_id}",
                    "word_count": 50,
                    "key_points": ["Point 1", "Point 2", "Point 3"],
                }

        except Exception as e:
            self.logger.error(f"Error generating text section {section_id}: {e}")
            raise

    async def _generate_summary_section(
        self, section_id: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate summary section data."""
        try:
            return {
                "executive_summary": "Portfolio performance summary for the reporting period.",
                "key_highlights": [
                    "Strong performance in EUR/USD trading",
                    "Risk metrics within acceptable ranges",
                    "Successful execution of trading strategies",
                ],
                "recommendations": [
                    "Continue current strategy allocation",
                    "Monitor correlation risks",
                    "Consider position size adjustments",
                ],
            }

        except Exception as e:
            self.logger.error(f"Error generating summary section {section_id}: {e}")
            raise

    # Data Retrieval Methods
    async def _get_portfolio_overview_metrics(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get portfolio overview metrics."""
        try:
            date_range = parameters.get("date_range")
            start_date, end_date = (
                date_range
                if date_range
                else (datetime.utcnow() - timedelta(days=30), datetime.utcnow())
            )

            # Portfolio performance query
            performance_query = """
            SELECT
                SUM(pnl) as total_pnl,
                COUNT(*) as total_trades,
                COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
                AVG(pnl) as avg_pnl
            FROM trades
            WHERE created_at BETWEEN %s AND %s
            """

            performance_data = await self.db.fetch_one(
                performance_query, (start_date, end_date)
            )

            # Current positions
            positions_query = """
            SELECT
                COUNT(*) as active_positions,
                SUM(current_value) as portfolio_value,
                SUM(unrealized_pnl) as unrealized_pnl
            FROM positions
            WHERE status = 'active'
            """

            positions_data = await self.db.fetch_one(positions_query)

            # Calculate metrics
            win_rate = (
                performance_data.get("winning_trades", 0)
                / max(performance_data.get("total_trades", 1), 1)
            ) * 100

            return {
                "total_pnl": float(performance_data.get("total_pnl", 0)),
                "portfolio_value": float(positions_data.get("portfolio_value", 0)),
                "unrealized_pnl": float(positions_data.get("unrealized_pnl", 0)),
                "active_positions": int(positions_data.get("active_positions", 0)),
                "total_trades": int(performance_data.get("total_trades", 0)),
                "win_rate": win_rate,
                "avg_trade_pnl": float(performance_data.get("avg_pnl", 0)),
            }

        except Exception as e:
            self.logger.error(f"Error getting portfolio overview metrics: {e}")
            return {}

    async def _get_risk_summary_metrics(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get risk summary metrics."""
        try:
            # Risk metrics query
            risk_query = """
            SELECT
                portfolio_var,
                expected_shortfall,
                max_drawdown,
                current_drawdown,
                sharpe_ratio,
                volatility
            FROM risk_metrics
            WHERE date = CURRENT_DATE
            ORDER BY created_at DESC
            LIMIT 1
            """

            risk_data = await self.db.fetch_one(risk_query)

            return {
                "portfolio_var": float(risk_data.get("portfolio_var", 0)),
                "expected_shortfall": float(risk_data.get("expected_shortfall", 0)),
                "max_drawdown": float(risk_data.get("max_drawdown", 0)),
                "current_drawdown": float(risk_data.get("current_drawdown", 0)),
                "sharpe_ratio": float(risk_data.get("sharpe_ratio", 0)),
                "volatility": float(risk_data.get("volatility", 0)),
                "risk_level": (
                    "Medium"
                    if float(risk_data.get("portfolio_var", 0)) < 0.02
                    else "High"
                ),
            }

        except Exception as e:
            self.logger.error(f"Error getting risk summary metrics: {e}")
            return {}

    async def _get_performance_chart_data(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get performance chart data."""
        try:
            date_range = parameters.get("date_range")
            start_date, end_date = (
                date_range
                if date_range
                else (datetime.utcnow() - timedelta(days=30), datetime.utcnow())
            )

            # Daily P&L chart data
            pnl_query = """
            SELECT
                DATE(created_at) as date,
                SUM(pnl) as daily_pnl
            FROM trades
            WHERE created_at BETWEEN %s AND %s
            GROUP BY DATE(created_at)
            ORDER BY date
            """

            pnl_data = await self.db.fetch_all(pnl_query, (start_date, end_date))

            # Calculate cumulative P&L
            cumulative_pnl = 0
            chart_data = []

            for row in pnl_data:
                cumulative_pnl += float(row["daily_pnl"])
                chart_data.append(
                    {
                        "date": (
                            row["date"].isoformat()
                            if hasattr(row["date"], "isoformat")
                            else str(row["date"])
                        ),
                        "daily_pnl": float(row["daily_pnl"]),
                        "cumulative_pnl": cumulative_pnl,
                    }
                )

            return {
                "chart_type": "line",
                "data": chart_data,
                "x_axis": "date",
                "y_axis": ["daily_pnl", "cumulative_pnl"],
                "title": "Performance Over Time",
            }

        except Exception as e:
            self.logger.error(f"Error getting performance chart data: {e}")
            return {"chart_type": "line", "data": [], "error": str(e)}

    async def _get_positions_table_data(
        self, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get current positions table data."""
        try:
            positions_query = """
            SELECT
                symbol,
                quantity,
                entry_price,
                current_price,
                current_value,
                unrealized_pnl,
                created_at
            FROM positions
            WHERE status = 'active'
            ORDER BY ABS(current_value) DESC
            """

            positions_data = await self.db.fetch_all(positions_query)

            return [
                {
                    "symbol": row["symbol"],
                    "quantity": float(row["quantity"]),
                    "entry_price": float(row["entry_price"]),
                    "current_price": float(row["current_price"]),
                    "current_value": float(row["current_value"]),
                    "unrealized_pnl": float(row["unrealized_pnl"]),
                    "pnl_percentage": (
                        float(row["unrealized_pnl"])
                        / max(abs(float(row["current_value"])), 1)
                    )
                    * 100,
                    "days_held": (datetime.utcnow() - row["created_at"]).days,
                }
                for row in positions_data
            ]

        except Exception as e:
            self.logger.error(f"Error getting positions table data: {e}")
            return []

    async def _get_trades_table_data(
        self, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get trades table data."""
        try:
            date_range = parameters.get("date_range")
            start_date, end_date = (
                date_range
                if date_range
                else (datetime.utcnow() - timedelta(days=7), datetime.utcnow())
            )

            trades_query = """
            SELECT
                trade_id,
                symbol,
                strategy,
                entry_time,
                exit_time,
                quantity,
                entry_price,
                exit_price,
                pnl,
                commission,
                duration_minutes
            FROM trades
            WHERE created_at BETWEEN %s AND %s
            ORDER BY entry_time DESC
            LIMIT 100
            """

            trades_data = await self.db.fetch_all(trades_query, (start_date, end_date))

            return [
                {
                    "trade_id": row["trade_id"],
                    "symbol": row["symbol"],
                    "strategy": row["strategy"],
                    "entry_time": (
                        row["entry_time"].isoformat() if row["entry_time"] else None
                    ),
                    "exit_time": (
                        row["exit_time"].isoformat() if row["exit_time"] else None
                    ),
                    "quantity": float(row["quantity"]),
                    "entry_price": float(row["entry_price"]),
                    "exit_price": (
                        float(row["exit_price"]) if row["exit_price"] else None
                    ),
                    "pnl": float(row["pnl"]),
                    "commission": float(row["commission"]),
                    "duration_hours": (
                        float(row["duration_minutes"]) / 60
                        if row["duration_minutes"]
                        else None
                    ),
                    "outcome": "Win" if float(row["pnl"]) > 0 else "Loss",
                }
                for row in trades_data
            ]

        except Exception as e:
            self.logger.error(f"Error getting trades table data: {e}")
            return []

    # Helper Methods
    async def _validate_parameters(
        self, provided_params: Dict[str, Any], template_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate and normalize report parameters."""
        validated = {}

        for param_name, param_config in template_params.items():
            param_type = param_config.get("type")
            required = param_config.get("required", False)
            default = param_config.get("default")

            if param_name in provided_params:
                value = provided_params[param_name]

                # Type validation
                if (
                    param_type == "date_range"
                    and isinstance(value, (list, tuple))
                    and len(value) == 2
                ):
                    validated[param_name] = value
                elif param_type == "boolean":
                    validated[param_name] = bool(value)
                elif param_type == "select" and value in param_config.get(
                    "options", []
                ):
                    validated[param_name] = value
                elif param_type == "multi_select" and isinstance(value, list):
                    validated[param_name] = value
                else:
                    validated[param_name] = value

            elif required:
                raise FXML4Exception(f"Required parameter missing: {param_name}")
            elif default is not None:
                validated[param_name] = default

        return validated

    async def _get_data_freshness(self) -> datetime:
        """Get data freshness timestamp."""
        try:
            query = """
            SELECT MAX(created_at) as latest_data
            FROM trades
            """
            result = await self.db.fetch_one(query)
            return result.get("latest_data", datetime.utcnow())
        except Exception:
            return datetime.utcnow()

    async def _calculate_data_quality_score(self) -> float:
        """Calculate data quality score."""
        try:
            # Mock data quality calculation
            return np.random.uniform(0.85, 0.98)
        except Exception:
            return 0.9

    async def _generate_report_summary(
        self, sections: List[ReportSection], metadata: ReportMetadata
    ) -> Dict[str, Any]:
        """Generate report summary."""
        return {
            "total_sections": len(sections),
            "total_data_points": sum(s.metadata.get("row_count", 0) for s in sections),
            "generation_time_ms": metadata.generation_time_ms,
            "data_quality_score": metadata.data_quality_score,
            "key_findings": [
                "Portfolio performance within expected ranges",
                "Risk metrics indicate moderate risk level",
                "Trading activity consistent with strategy",
            ],
        }

    # Mock data methods for remaining sections
    async def _get_compliance_overview_metrics(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "compliance_score": 95.5,
            "active_alerts": 3,
            "resolved_alerts": 12,
            "surveillance_coverage": 100.0,
        }

    async def _get_trading_summary_metrics(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "total_trades": 156,
            "winning_trades": 89,
            "win_rate": 57.1,
            "avg_trade_duration": 4.5,
            "best_trade": 245.50,
            "worst_trade": -89.20,
        }

    async def _get_generic_metrics(
        self, section_id: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"metric_1": 100.0, "metric_2": 85.5, "metric_3": 92.3}

    async def _get_pnl_chart_data(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        return {"chart_type": "bar", "data": [], "title": "P&L Analysis"}

    async def _get_var_chart_data(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        return {"chart_type": "line", "data": [], "title": "Value at Risk"}

    async def _get_strategy_chart_data(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"chart_type": "pie", "data": [], "title": "Strategy Performance"}

    async def _get_correlation_chart_data(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"chart_type": "heatmap", "data": [], "title": "Correlation Matrix"}

    async def _get_generic_chart_data(
        self, section_id: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"chart_type": "line", "data": [], "title": f"Chart: {section_id}"}

    async def _get_risk_table_data(
        self, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        return [
            {"metric": "VaR", "value": 0.025},
            {"metric": "Max Drawdown", "value": 0.08},
        ]

    async def _get_execution_table_data(
        self, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        return [
            {"metric": "Avg Slippage", "value": 0.0005},
            {"metric": "Fill Rate", "value": 99.8},
        ]

    async def _get_stress_test_table_data(
        self, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        return [
            {"scenario": "Market Crash", "impact": -0.15},
            {"scenario": "Volatility Spike", "impact": -0.08},
        ]

    async def _get_surveillance_table_data(
        self, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        return [{"alert_type": "Unusual Volume", "count": 2, "severity": "Medium"}]

    async def _get_regulatory_table_data(
        self, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        return [
            {
                "regulation": "MiFID II",
                "status": "Compliant",
                "last_check": datetime.utcnow().isoformat(),
            }
        ]

    async def _get_audit_table_data(
        self, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        return [
            {
                "action": "Trade Execution",
                "timestamp": datetime.utcnow().isoformat(),
                "user": "system",
            }
        ]

    async def _get_risk_attribution_table_data(
        self, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        return [{"symbol": "EUR/USD", "contribution": 0.45, "percentage": 45.0}]

    async def _get_generic_table_data(
        self, section_id: str, parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        return [{"column_1": "value_1", "column_2": "value_2"}]

    async def _get_key_insights(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "content": "Key insights from the analysis period reveal strong performance trends.",
            "insights": [
                "Trading performance exceeded benchmarks",
                "Risk metrics remained within target ranges",
                "Strategy diversification is working effectively",
            ],
            "recommendations": [
                "Continue current strategy allocation",
                "Monitor emerging market trends",
                "Consider position size optimization",
            ],
        }

    def get_generation_statistics(self) -> Dict[str, Any]:
        """Get report generation statistics."""
        avg_generation_time = self.generation_stats["total_generation_time"] / max(
            self.generation_stats["total_reports"], 1
        )

        success_rate = (
            self.generation_stats["success_count"]
            / max(self.generation_stats["total_reports"], 1)
        ) * 100

        return {
            "total_reports_generated": self.generation_stats["total_reports"],
            "successful_generations": self.generation_stats["success_count"],
            "failed_generations": self.generation_stats["error_count"],
            "success_rate_percentage": success_rate,
            "average_generation_time_ms": avg_generation_time,
            "available_templates": len(self.templates),
            "reports_in_history": len(self.report_history),
        }
