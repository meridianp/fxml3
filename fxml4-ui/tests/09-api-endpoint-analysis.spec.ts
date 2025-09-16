/**
 * 🔍 API ENDPOINT MISMATCH ANALYSIS
 *
 * Simple test to capture all API requests and analyze frontend vs backend mismatches
 */

import { test, expect } from '@playwright/test';

interface ApiRequest {
  method: string;
  url: string;
  status?: number;
  timestamp: number;
}

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000';
const API_URL = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8001';

test.describe('🔍 API Endpoint Mismatch Analysis', () => {

  test('Capture all frontend API requests and analyze mismatches', async ({ page }) => {
    const apiRequests: ApiRequest[] = [];

    // Intercept all API requests
    await page.route('**/*', async (route) => {
      const request = route.request();
      const url = request.url();

      // Only track API requests to our backend
      if (url.includes(':8001')) {
        apiRequests.push({
          method: request.method(),
          url,
          timestamp: Date.now()
        });

        console.log(`🔍 API Request: ${request.method()} ${url}`);
      }

      await route.continue();
    });

    // Also track response status codes
    page.on('response', response => {
      const url = response.url();
      if (url.includes(':8001')) {
        const request = apiRequests.find(req => req.url === url && !req.status);
        if (request) {
          request.status = response.status();
          console.log(`📊 API Response: ${response.status()} ${url}`);
        }
      }
    });

    // Test each main page to capture all API calls
    const pages = ['dashboard', 'trading', 'data', 'training', 'backtesting', 'elliott-waves', 'analytics'];

    for (const pageRoute of pages) {
      console.log(`\\n🔍 Testing page: /${pageRoute}`);
      await page.goto(`${BASE_URL}/${pageRoute}`);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000); // Allow time for API calls
    }

    // Analysis of captured requests
    console.log('\\n📊 API REQUEST ANALYSIS');
    console.log('========================');

    const uniqueEndpoints = [...new Set(apiRequests.map(req => `${req.method} ${req.url.replace(API_URL, '')}`))];

    console.log(`\\n🔍 Frontend is calling ${uniqueEndpoints.length} unique API endpoints:`);
    uniqueEndpoints.forEach(endpoint => {
      console.log(`  - ${endpoint}`);
    });

    // Analyze response codes
    const responseAnalysis = apiRequests.reduce((acc, req) => {
      const status = req.status || 'No Response';
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {} as Record<string | number, number>);

    console.log('\\n📊 Response Status Analysis:');
    Object.entries(responseAnalysis).forEach(([status, count]) => {
      const emoji = status === '200' ? '✅' : status === '401' ? '🔒' : status === '404' ? '❌' : '⚠️';
      console.log(`  ${emoji} ${status}: ${count} requests`);
    });

    // Identify problematic endpoints
    const problematicRequests = apiRequests.filter(req => req.status && req.status >= 400);

    if (problematicRequests.length > 0) {
      console.log('\\n🚨 PROBLEMATIC ENDPOINTS:');
      problematicRequests.forEach(req => {
        const endpoint = req.url.replace(API_URL, '');
        console.log(`  ${req.status} ${req.method} ${endpoint}`);
      });
    }

    // Success metrics
    const totalRequests = apiRequests.length;
    const successfulRequests = apiRequests.filter(req => req.status === 200).length;
    const authRequests = apiRequests.filter(req => req.status === 401).length; // Expected for authenticated endpoints
    const notFoundRequests = apiRequests.filter(req => req.status === 404).length;

    console.log('\\n🎯 SUMMARY METRICS:');
    console.log(`Total API Requests: ${totalRequests}`);
    console.log(`Successful (200): ${successfulRequests}`);
    console.log(`Auth Required (401): ${authRequests}`);
    console.log(`Not Found (404): ${notFoundRequests}`);
    console.log(`Other Errors: ${totalRequests - successfulRequests - authRequests - notFoundRequests}`);

    if (notFoundRequests > 0) {
      console.log('\\n🚨 ACTION REQUIRED: Frontend is calling non-existent API endpoints');
    }

    if (authRequests > 0) {
      console.log('\\n🔒 NOTE: Some endpoints require authentication (expected behavior)');
    }

    // Assertions for the test
    expect(totalRequests).toBeGreaterThan(0);
    console.log('\\n✅ API endpoint analysis completed');
  });
});
