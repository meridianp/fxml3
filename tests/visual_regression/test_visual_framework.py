"""
Visual Regression Testing Framework for FXML4-UI

This module provides comprehensive visual regression testing for FXML4-UI components
using screenshot comparison, pixel diffing, and perceptual similarity metrics.

Visual Testing Features:
- Component screenshot capture
- Pixel-by-pixel comparison
- Perceptual difference detection
- Cross-browser testing support
- Responsive design validation
- Dark/light theme testing
- Animation and transition handling
- Baseline management and updates

Components Tested:
- Trading dashboard layouts
- Chart visualizations
- Order entry forms
- Portfolio views
- Risk management panels
- Market data grids
- Alert notifications
- Navigation menus
"""

import asyncio
import base64
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageChops, ImageFilter

# Optional imports with graceful fallback
try:
    from playwright.async_api import Browser, BrowserContext, Page, async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from skimage import color
    from skimage.metrics import structural_similarity as ssim

    SCIKIT_IMAGE_AVAILABLE = True
except ImportError:
    SCIKIT_IMAGE_AVAILABLE = False

logger = logging.getLogger(__name__)


class ComparisonMode(Enum):
    """Visual comparison modes."""

    PIXEL_PERFECT = "pixel_perfect"  # Exact pixel matching
    PERCEPTUAL = "perceptual"  # Human perception-based
    STRUCTURAL = "structural"  # SSIM-based comparison
    THRESHOLD = "threshold"  # Allows minor differences
    LAYOUT = "layout"  # Focus on layout/structure


class TestStatus(Enum):
    """Visual test status."""

    PASS = "pass"
    FAIL = "fail"
    NEW = "new"  # No baseline exists
    UPDATED = "updated"  # Baseline was updated
    SKIPPED = "skipped"


class DeviceProfile(Enum):
    """Device profiles for responsive testing."""

    DESKTOP_1920 = ("desktop_1920", 1920, 1080)
    DESKTOP_1440 = ("desktop_1440", 1440, 900)
    LAPTOP = ("laptop", 1366, 768)
    TABLET = ("tablet", 768, 1024)
    MOBILE = ("mobile", 375, 812)
    MOBILE_LANDSCAPE = ("mobile_landscape", 812, 375)

    def __init__(self, name: str, width: int, height: int):
        self.device_name = name
        self.width = width
        self.height = height


@dataclass
class VisualTestCase:
    """Visual regression test case definition."""

    name: str
    component: str
    url: str
    selector: Optional[str] = None  # CSS selector for component
    viewport: DeviceProfile = DeviceProfile.DESKTOP_1920
    theme: str = "light"
    wait_for: Optional[str] = None  # Selector to wait for
    wait_time: int = 0  # Additional wait in ms
    mask_selectors: List[str] = field(default_factory=list)  # Elements to mask
    comparison_mode: ComparisonMode = ComparisonMode.PERCEPTUAL
    threshold: float = 0.1  # Difference threshold (0-1)
    capture_full_page: bool = False

    @property
    def test_id(self) -> str:
        """Generate unique test identifier."""
        return f"{self.component}_{self.name}_{self.viewport.device_name}_{self.theme}"


@dataclass
class VisualTestResult:
    """Visual regression test result."""

    test_case: VisualTestCase
    status: TestStatus
    difference_percentage: float
    similarity_score: float
    baseline_path: Optional[Path] = None
    actual_path: Optional[Path] = None
    diff_path: Optional[Path] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def passed(self) -> bool:
        """Check if test passed."""
        return self.status == TestStatus.PASS

    @property
    def failed(self) -> bool:
        """Check if test failed."""
        return self.status == TestStatus.FAIL


class VisualRegressionTester:
    """Main visual regression testing engine."""

    def __init__(
        self,
        baseline_dir: str = "tests/visual_regression/baselines",
        output_dir: str = "tests/visual_regression/output",
        config_file: Optional[str] = None,
    ):
        self.baseline_dir = Path(baseline_dir)
        self.output_dir = Path(output_dir)
        self.actual_dir = self.output_dir / "actual"
        self.diff_dir = self.output_dir / "diff"

        # Create directories
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.actual_dir.mkdir(parents=True, exist_ok=True)
        self.diff_dir.mkdir(parents=True, exist_ok=True)

        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.test_results: List[VisualTestResult] = []

        # Load configuration if provided
        self.config = self._load_config(config_file) if config_file else {}

    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """Load test configuration from file."""
        config_path = Path(config_file)
        if config_path.exists():
            with open(config_path, "r") as f:
                return json.load(f)
        return {}

    async def setup_browser(
        self, browser_type: str = "chromium", headless: bool = True
    ):
        """Setup browser for testing."""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is required for visual regression testing")

        playwright = await async_playwright().start()

        if browser_type == "chromium":
            self.browser = await playwright.chromium.launch(headless=headless)
        elif browser_type == "firefox":
            self.browser = await playwright.firefox.launch(headless=headless)
        elif browser_type == "webkit":
            self.browser = await playwright.webkit.launch(headless=headless)
        else:
            raise ValueError(f"Unsupported browser type: {browser_type}")

    async def setup_page(self, test_case: VisualTestCase):
        """Setup page for specific test case."""
        if not self.browser:
            await self.setup_browser()

        # Create context with viewport
        self.context = await self.browser.new_context(
            viewport={
                "width": test_case.viewport.width,
                "height": test_case.viewport.height,
            },
            color_scheme=test_case.theme,
        )

        self.page = await self.context.new_page()

        # Navigate to URL
        await self.page.goto(test_case.url, wait_until="networkidle")

        # Wait for specific element if specified
        if test_case.wait_for:
            await self.page.wait_for_selector(test_case.wait_for)

        # Additional wait time
        if test_case.wait_time > 0:
            await asyncio.sleep(test_case.wait_time / 1000)

    async def capture_screenshot(self, test_case: VisualTestCase) -> bytes:
        """Capture screenshot of component or page."""
        if not self.page:
            await self.setup_page(test_case)

        # Mask dynamic elements
        for selector in test_case.mask_selectors:
            try:
                await self.page.evaluate(
                    f"""
                    document.querySelectorAll('{selector}').forEach(el => {{
                        el.style.visibility = 'hidden';
                    }});
                """
                )
            except Exception as e:
                logger.warning(f"Failed to mask element {selector}: {e}")

        # Capture screenshot
        if test_case.selector:
            # Capture specific element
            element = await self.page.query_selector(test_case.selector)
            if element:
                screenshot = await element.screenshot()
            else:
                raise ValueError(f"Element not found: {test_case.selector}")
        else:
            # Capture full page or viewport
            screenshot = await self.page.screenshot(
                full_page=test_case.capture_full_page
            )

        return screenshot

    def compare_images(
        self,
        baseline: Image.Image,
        actual: Image.Image,
        mode: ComparisonMode,
        threshold: float,
    ) -> Tuple[float, float, Optional[Image.Image]]:
        """
        Compare two images and return difference metrics.

        Returns:
            Tuple of (difference_percentage, similarity_score, diff_image)
        """
        # Ensure images are same size
        if baseline.size != actual.size:
            actual = actual.resize(baseline.size, Image.Resampling.LANCZOS)

        if mode == ComparisonMode.PIXEL_PERFECT:
            return self._pixel_perfect_comparison(baseline, actual)
        elif mode == ComparisonMode.PERCEPTUAL:
            return self._perceptual_comparison(baseline, actual, threshold)
        elif mode == ComparisonMode.STRUCTURAL:
            return self._structural_comparison(baseline, actual)
        elif mode == ComparisonMode.THRESHOLD:
            return self._threshold_comparison(baseline, actual, threshold)
        elif mode == ComparisonMode.LAYOUT:
            return self._layout_comparison(baseline, actual)
        else:
            return self._perceptual_comparison(baseline, actual, threshold)

    def _pixel_perfect_comparison(
        self, baseline: Image.Image, actual: Image.Image
    ) -> Tuple[float, float, Optional[Image.Image]]:
        """Exact pixel-by-pixel comparison."""
        diff = ImageChops.difference(baseline, actual)

        # Calculate difference percentage
        pixels = list(diff.getdata())
        total_pixels = len(pixels)
        different_pixels = sum(
            1 for p in pixels if p != (0, 0, 0, 0) and p != (0, 0, 0)
        )

        difference_percentage = (different_pixels / total_pixels) * 100
        similarity_score = 100 - difference_percentage

        # Create diff image with highlights
        diff_image = self._create_diff_image(baseline, actual, diff)

        return difference_percentage, similarity_score, diff_image

    def _perceptual_comparison(
        self, baseline: Image.Image, actual: Image.Image, threshold: float
    ) -> Tuple[float, float, Optional[Image.Image]]:
        """Perceptual comparison using human vision simulation."""
        # Convert to LAB color space for perceptual comparison
        baseline_array = np.array(baseline)
        actual_array = np.array(actual)

        # Calculate perceptual difference
        diff_array = np.abs(baseline_array.astype(float) - actual_array.astype(float))

        # Apply perceptual weighting (simplified)
        # Human vision is more sensitive to luminance than color
        if len(diff_array.shape) == 3 and diff_array.shape[2] >= 3:
            weighted_diff = (
                0.299 * diff_array[:, :, 0]
                + 0.587 * diff_array[:, :, 1]
                + 0.114 * diff_array[:, :, 2]
            )
        else:
            weighted_diff = (
                diff_array.mean(axis=2) if len(diff_array.shape) == 3 else diff_array
            )

        # Calculate metrics
        max_diff = 255.0
        normalized_diff = weighted_diff / max_diff
        difference_percentage = (normalized_diff > threshold).mean() * 100
        similarity_score = 100 - difference_percentage

        # Create diff image
        diff_image = self._create_perceptual_diff_image(
            baseline, actual, normalized_diff, threshold
        )

        return difference_percentage, similarity_score, diff_image

    def _structural_comparison(
        self, baseline: Image.Image, actual: Image.Image
    ) -> Tuple[float, float, Optional[Image.Image]]:
        """Structural similarity (SSIM) based comparison."""
        if not SCIKIT_IMAGE_AVAILABLE:
            # Fallback to perceptual comparison
            return self._perceptual_comparison(baseline, actual, 0.1)

        # Convert to grayscale for SSIM
        baseline_gray = np.array(baseline.convert("L"))
        actual_gray = np.array(actual.convert("L"))

        # Calculate SSIM
        similarity_index, diff_image_array = ssim(
            baseline_gray, actual_gray, full=True, data_range=255
        )

        similarity_score = similarity_index * 100
        difference_percentage = 100 - similarity_score

        # Create diff image
        diff_image = Image.fromarray((diff_image_array * 255).astype(np.uint8))

        return difference_percentage, similarity_score, diff_image

    def _threshold_comparison(
        self, baseline: Image.Image, actual: Image.Image, threshold: float
    ) -> Tuple[float, float, Optional[Image.Image]]:
        """Comparison allowing minor pixel differences within threshold."""
        baseline_array = np.array(baseline)
        actual_array = np.array(actual)

        # Calculate absolute difference
        diff_array = np.abs(baseline_array.astype(float) - actual_array.astype(float))

        # Apply threshold
        threshold_value = threshold * 255
        significant_diff = diff_array > threshold_value

        # Calculate metrics
        total_pixels = significant_diff.size
        different_pixels = significant_diff.sum()
        difference_percentage = (different_pixels / total_pixels) * 100
        similarity_score = 100 - difference_percentage

        # Create diff image
        diff_image = self._create_threshold_diff_image(
            baseline, actual, significant_diff
        )

        return difference_percentage, similarity_score, diff_image

    def _layout_comparison(
        self, baseline: Image.Image, actual: Image.Image
    ) -> Tuple[float, float, Optional[Image.Image]]:
        """Layout-focused comparison using edge detection."""
        # Convert to grayscale
        baseline_gray = baseline.convert("L")
        actual_gray = actual.convert("L")

        # Apply edge detection
        baseline_edges = baseline_gray.filter(ImageFilter.FIND_EDGES)
        actual_edges = actual_gray.filter(ImageFilter.FIND_EDGES)

        # Compare edges
        diff = ImageChops.difference(baseline_edges, actual_edges)

        # Calculate metrics
        pixels = list(diff.getdata())
        total_pixels = len(pixels)
        different_pixels = sum(
            1 for p in pixels if p > 20
        )  # Threshold for edge differences

        difference_percentage = (different_pixels / total_pixels) * 100
        similarity_score = 100 - difference_percentage

        # Create diff image
        diff_image = self._create_edge_diff_image(baseline, actual, diff)

        return difference_percentage, similarity_score, diff_image

    def _create_diff_image(
        self, baseline: Image.Image, actual: Image.Image, diff: Image.Image
    ) -> Image.Image:
        """Create a diff image with highlighted differences."""
        # Create composite image showing differences
        result = Image.new("RGBA", baseline.size)

        # Convert diff to RGBA if needed
        if diff.mode != "RGBA":
            diff = diff.convert("RGBA")

        # Highlight differences in red
        for x in range(baseline.width):
            for y in range(baseline.height):
                diff_pixel = diff.getpixel((x, y))
                if isinstance(diff_pixel, tuple) and len(diff_pixel) >= 3:
                    if sum(diff_pixel[:3]) > 0:  # There's a difference
                        result.putpixel(
                            (x, y), (255, 0, 0, 128)
                        )  # Semi-transparent red
                    else:
                        result.putpixel((x, y), baseline.getpixel((x, y)))
                else:
                    result.putpixel((x, y), baseline.getpixel((x, y)))

        return result

    def _create_perceptual_diff_image(
        self,
        baseline: Image.Image,
        actual: Image.Image,
        diff_array: np.ndarray,
        threshold: float,
    ) -> Image.Image:
        """Create perceptual diff image with gradient highlighting."""
        result = baseline.copy()
        overlay = Image.new("RGBA", baseline.size, (0, 0, 0, 0))

        # Create heatmap of differences
        for y in range(baseline.height):
            for x in range(baseline.width):
                diff_value = (
                    diff_array[y, x]
                    if y < diff_array.shape[0] and x < diff_array.shape[1]
                    else 0
                )

                if diff_value > threshold:
                    # Map difference to color intensity
                    intensity = min(255, int(diff_value * 255 / threshold))
                    overlay.putpixel((x, y), (255, 255 - intensity, 0, intensity))

        # Composite overlay on result
        result = Image.alpha_composite(result.convert("RGBA"), overlay)

        return result

    def _create_threshold_diff_image(
        self, baseline: Image.Image, actual: Image.Image, significant_diff: np.ndarray
    ) -> Image.Image:
        """Create threshold-based diff image."""
        result = baseline.copy()

        # Highlight significant differences
        for y in range(min(baseline.height, significant_diff.shape[0])):
            for x in range(min(baseline.width, significant_diff.shape[1])):
                if (
                    significant_diff[y, x].any()
                    if len(significant_diff.shape) > 2
                    else significant_diff[y, x]
                ):
                    # Mark difference with colored border
                    for dy in range(-1, 2):
                        for dx in range(-1, 2):
                            px = x + dx
                            py = y + dy
                            if 0 <= px < baseline.width and 0 <= py < baseline.height:
                                result.putpixel((px, py), (255, 0, 255))

        return result

    def _create_edge_diff_image(
        self, baseline: Image.Image, actual: Image.Image, edge_diff: Image.Image
    ) -> Image.Image:
        """Create edge-based diff image for layout comparison."""
        # Create composite showing layout differences
        result = Image.new("RGBA", baseline.size)

        # Blend baseline with edge differences
        for x in range(baseline.width):
            for y in range(baseline.height):
                baseline_pixel = baseline.getpixel((x, y))
                edge_value = (
                    edge_diff.getpixel((x, y))
                    if edge_diff.mode == "L"
                    else edge_diff.getpixel((x, y))[0]
                )

                if edge_value > 20:  # Significant edge difference
                    # Highlight in blue
                    result.putpixel((x, y), (0, 0, 255, 128))
                else:
                    result.putpixel((x, y), baseline_pixel)

        return result

    async def run_test(self, test_case: VisualTestCase) -> VisualTestResult:
        """Run a single visual regression test."""
        start_time = asyncio.get_event_loop().time()

        try:
            # Setup page
            await self.setup_page(test_case)

            # Capture screenshot
            screenshot_bytes = await self.capture_screenshot(test_case)

            # Save actual screenshot
            actual_path = self.actual_dir / f"{test_case.test_id}.png"
            with open(actual_path, "wb") as f:
                f.write(screenshot_bytes)

            actual_image = Image.open(actual_path)

            # Check if baseline exists
            baseline_path = self.baseline_dir / f"{test_case.test_id}.png"

            if not baseline_path.exists():
                # No baseline - save current as baseline
                baseline_path.parent.mkdir(parents=True, exist_ok=True)
                with open(baseline_path, "wb") as f:
                    f.write(screenshot_bytes)

                execution_time = (asyncio.get_event_loop().time() - start_time) * 1000

                return VisualTestResult(
                    test_case=test_case,
                    status=TestStatus.NEW,
                    difference_percentage=0,
                    similarity_score=100,
                    baseline_path=baseline_path,
                    actual_path=actual_path,
                    execution_time_ms=execution_time,
                )

            # Load baseline
            baseline_image = Image.open(baseline_path)

            # Compare images
            difference_percentage, similarity_score, diff_image = self.compare_images(
                baseline_image,
                actual_image,
                test_case.comparison_mode,
                test_case.threshold,
            )

            # Save diff image if there are differences
            diff_path = None
            if diff_image and difference_percentage > 0:
                diff_path = self.diff_dir / f"{test_case.test_id}.png"
                diff_image.save(diff_path)

            # Determine status
            if difference_percentage <= test_case.threshold * 100:
                status = TestStatus.PASS
            else:
                status = TestStatus.FAIL

            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000

            return VisualTestResult(
                test_case=test_case,
                status=status,
                difference_percentage=difference_percentage,
                similarity_score=similarity_score,
                baseline_path=baseline_path,
                actual_path=actual_path,
                diff_path=diff_path,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000

            return VisualTestResult(
                test_case=test_case,
                status=TestStatus.FAIL,
                difference_percentage=100,
                similarity_score=0,
                error_message=str(e),
                execution_time_ms=execution_time,
            )

    async def run_test_suite(
        self, test_cases: List[VisualTestCase]
    ) -> List[VisualTestResult]:
        """Run a suite of visual regression tests."""
        results = []

        try:
            # Setup browser once
            await self.setup_browser()

            for test_case in test_cases:
                logger.info(f"Running visual test: {test_case.test_id}")
                result = await self.run_test(test_case)
                results.append(result)
                self.test_results.append(result)

                # Log result
                if result.passed:
                    logger.info(
                        f"✅ {test_case.test_id}: PASSED (similarity: {result.similarity_score:.1f}%)"
                    )
                elif result.status == TestStatus.NEW:
                    logger.info(f"🆕 {test_case.test_id}: NEW BASELINE CREATED")
                else:
                    logger.warning(
                        f"❌ {test_case.test_id}: FAILED (difference: {result.difference_percentage:.1f}%)"
                    )

        finally:
            # Cleanup
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()

        return results

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive visual regression test report."""
        if not self.test_results:
            return {"error": "No test results available"}

        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.status == TestStatus.PASS)
        failed_tests = sum(1 for r in self.test_results if r.status == TestStatus.FAIL)
        new_tests = sum(1 for r in self.test_results if r.status == TestStatus.NEW)

        # Group by component
        component_results = {}
        for result in self.test_results:
            component = result.test_case.component
            if component not in component_results:
                component_results[component] = {"passed": 0, "failed": 0, "new": 0}

            if result.status == TestStatus.PASS:
                component_results[component]["passed"] += 1
            elif result.status == TestStatus.FAIL:
                component_results[component]["failed"] += 1
            elif result.status == TestStatus.NEW:
                component_results[component]["new"] += 1

        # Calculate average metrics
        avg_similarity = (
            sum(r.similarity_score for r in self.test_results) / total_tests
        )
        avg_execution_time = (
            sum(r.execution_time_ms for r in self.test_results) / total_tests
        )

        # Find most problematic tests
        failed_results = [r for r in self.test_results if r.status == TestStatus.FAIL]
        worst_tests = sorted(
            failed_results, key=lambda r: r.difference_percentage, reverse=True
        )[:5]

        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "new_baselines": new_tests,
                "pass_rate": (
                    (passed_tests / total_tests * 100) if total_tests > 0 else 0
                ),
                "avg_similarity": avg_similarity,
                "avg_execution_time_ms": avg_execution_time,
            },
            "component_breakdown": component_results,
            "worst_failures": [
                {
                    "test_id": r.test_case.test_id,
                    "component": r.test_case.component,
                    "difference_percentage": r.difference_percentage,
                    "diff_path": str(r.diff_path) if r.diff_path else None,
                }
                for r in worst_tests
            ],
            "recommendations": self._generate_recommendations(
                failed_tests, new_tests, avg_similarity
            ),
            "timestamp": datetime.now().isoformat(),
        }

    def _generate_recommendations(
        self, failed_count: int, new_count: int, avg_similarity: float
    ) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        if failed_count > 0:
            recommendations.append(
                f"🔴 {failed_count} visual tests failed. Review diff images and update baselines if changes are intentional."
            )

        if new_count > 0:
            recommendations.append(
                f"🆕 {new_count} new baselines created. Review to ensure they capture the correct state."
            )

        if avg_similarity < 95:
            recommendations.append(
                f"⚠️ Average similarity is {avg_similarity:.1f}%. Consider reviewing test thresholds."
            )

        if failed_count == 0 and new_count == 0:
            recommendations.append(
                "✅ All visual tests passed! UI components are visually consistent."
            )

        return recommendations


# Example test configuration
def generate_test_cases() -> List[VisualTestCase]:
    """Generate comprehensive visual test cases for FXML4-UI."""
    test_cases = []

    base_url = "http://localhost:3000"

    # Dashboard tests
    dashboard_tests = [
        VisualTestCase(
            name="main_dashboard",
            component="dashboard",
            url=f"{base_url}/dashboard",
            viewport=DeviceProfile.DESKTOP_1920,
            theme="light",
            wait_for=".dashboard-container",
            mask_selectors=[".timestamp", ".live-price"],
            comparison_mode=ComparisonMode.PERCEPTUAL,
        ),
        VisualTestCase(
            name="main_dashboard_dark",
            component="dashboard",
            url=f"{base_url}/dashboard",
            viewport=DeviceProfile.DESKTOP_1920,
            theme="dark",
            wait_for=".dashboard-container",
            mask_selectors=[".timestamp", ".live-price"],
            comparison_mode=ComparisonMode.PERCEPTUAL,
        ),
        VisualTestCase(
            name="dashboard_mobile",
            component="dashboard",
            url=f"{base_url}/dashboard",
            viewport=DeviceProfile.MOBILE,
            theme="light",
            wait_for=".dashboard-container",
            mask_selectors=[".timestamp", ".live-price"],
            comparison_mode=ComparisonMode.LAYOUT,
        ),
    ]

    # Trading panel tests
    trading_tests = [
        VisualTestCase(
            name="order_entry_form",
            component="trading",
            url=f"{base_url}/trading",
            selector=".order-entry-panel",
            viewport=DeviceProfile.DESKTOP_1920,
            theme="light",
            wait_for=".order-form",
            comparison_mode=ComparisonMode.STRUCTURAL,
        ),
        VisualTestCase(
            name="positions_grid",
            component="trading",
            url=f"{base_url}/trading",
            selector=".positions-grid",
            viewport=DeviceProfile.DESKTOP_1920,
            theme="light",
            wait_for=".grid-container",
            mask_selectors=[".position-pnl", ".position-price"],
            comparison_mode=ComparisonMode.LAYOUT,
        ),
    ]

    # Chart tests
    chart_tests = [
        VisualTestCase(
            name="price_chart",
            component="charts",
            url=f"{base_url}/charts",
            selector=".chart-container",
            viewport=DeviceProfile.DESKTOP_1920,
            theme="light",
            wait_time=2000,  # Wait for chart to render
            comparison_mode=ComparisonMode.THRESHOLD,
            threshold=0.15,  # Allow some variation in chart rendering
        ),
        VisualTestCase(
            name="chart_indicators",
            component="charts",
            url=f"{base_url}/charts?indicators=true",
            selector=".chart-container",
            viewport=DeviceProfile.DESKTOP_1920,
            theme="light",
            wait_time=2000,
            comparison_mode=ComparisonMode.THRESHOLD,
            threshold=0.2,
        ),
    ]

    # Portfolio tests
    portfolio_tests = [
        VisualTestCase(
            name="portfolio_overview",
            component="portfolio",
            url=f"{base_url}/portfolio",
            viewport=DeviceProfile.DESKTOP_1920,
            theme="light",
            wait_for=".portfolio-container",
            mask_selectors=[".balance-value", ".pnl-value"],
            comparison_mode=ComparisonMode.PERCEPTUAL,
        ),
        VisualTestCase(
            name="portfolio_tablet",
            component="portfolio",
            url=f"{base_url}/portfolio",
            viewport=DeviceProfile.TABLET,
            theme="light",
            wait_for=".portfolio-container",
            mask_selectors=[".balance-value", ".pnl-value"],
            comparison_mode=ComparisonMode.LAYOUT,
        ),
    ]

    # Risk management tests
    risk_tests = [
        VisualTestCase(
            name="risk_dashboard",
            component="risk",
            url=f"{base_url}/risk",
            viewport=DeviceProfile.DESKTOP_1920,
            theme="light",
            wait_for=".risk-metrics",
            mask_selectors=[".var-value", ".exposure-value"],
            comparison_mode=ComparisonMode.STRUCTURAL,
        )
    ]

    # Combine all test cases
    test_cases.extend(dashboard_tests)
    test_cases.extend(trading_tests)
    test_cases.extend(chart_tests)
    test_cases.extend(portfolio_tests)
    test_cases.extend(risk_tests)

    return test_cases


# Example usage
async def run_visual_regression_tests():
    """Run visual regression tests."""
    print("FXML4-UI Visual Regression Testing")
    print("=" * 50)

    # Create tester
    tester = VisualRegressionTester()

    # Generate test cases
    test_cases = generate_test_cases()

    print(f"Running {len(test_cases)} visual tests...")

    # Run tests
    results = await tester.run_test_suite(test_cases)

    # Generate report
    report = tester.generate_report()

    # Print summary
    summary = report["summary"]
    print(f"\nTest Results:")
    print(f"  Total: {summary['total_tests']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  New Baselines: {summary['new_baselines']}")
    print(f"  Pass Rate: {summary['pass_rate']:.1f}%")
    print(f"  Avg Similarity: {summary['avg_similarity']:.1f}%")

    print(f"\nRecommendations:")
    for rec in report["recommendations"]:
        print(f"  {rec}")

    return summary["pass_rate"] >= 95


if __name__ == "__main__":
    # Run example test
    success = asyncio.run(run_visual_regression_tests())
    if success:
        print("\n✅ Visual regression tests passed!")
    else:
        print("\n❌ Visual regression tests have failures.")
