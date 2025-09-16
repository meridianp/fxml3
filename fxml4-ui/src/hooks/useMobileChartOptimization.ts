/**
 * Mobile Chart Optimization Hook
 *
 * Provides performance optimizations for chart rendering on mobile devices
 * including adaptive refresh rates, touch gesture handling, and memory management
 */

'use client';

import { useEffect, useState, useCallback, useRef, useMemo } from 'react';

interface MobileChartConfig {
  enableReducedRefreshRate?: boolean;
  enableTouchOptimization?: boolean;
  enableMemoryOptimization?: boolean;
  maxDataPoints?: number;
  throttleMs?: number;
}

interface MobileOptimization {
  isMobile: boolean;
  isLowEndDevice: boolean;
  shouldReduceAnimations: boolean;
  optimizedRefreshRate: number;
  maxDataPoints: number;
  throttleMs: number;
  handleTouchStart: (e: TouchEvent) => void;
  handleTouchMove: (e: TouchEvent) => void;
  handleTouchEnd: (e: TouchEvent) => void;
  cleanup: () => void;
}

const defaultConfig: Required<MobileChartConfig> = {
  enableReducedRefreshRate: true,
  enableTouchOptimization: true,
  enableMemoryOptimization: true,
  maxDataPoints: 500,
  throttleMs: 100
};

export function useMobileChartOptimization(
  config: MobileChartConfig = {}
): MobileOptimization {
  const fullConfig = { ...defaultConfig, ...config };
  const [isMobile, setIsMobile] = useState(false);
  const [isLowEndDevice, setIsLowEndDevice] = useState(false);
  const [shouldReduceAnimations, setShouldReduceAnimations] = useState(false);

  const touchStartRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const lastTouchMoveRef = useRef<number>(0);

  // Detect mobile and device capabilities
  useEffect(() => {
    const checkMobileAndCapabilities = () => {
      // Mobile detection
      const userAgent = navigator.userAgent.toLowerCase();
      const mobileKeywords = ['android', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone'];
      const isMobileDevice = mobileKeywords.some(keyword => userAgent.includes(keyword)) ||
                            window.innerWidth <= 768;

      // Device capability detection
      const hardwareConcurrency = navigator.hardwareConcurrency || 4;
      const deviceMemory = (navigator as any).deviceMemory || 4;
      const connection = (navigator as any).connection;

      const isLowEnd = hardwareConcurrency < 4 ||
                      deviceMemory < 4 ||
                      (connection && (connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g'));

      // Animation preference detection
      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      setIsMobile(isMobileDevice);
      setIsLowEndDevice(isLowEnd);
      setShouldReduceAnimations(prefersReducedMotion || isLowEnd);
    };

    checkMobileAndCapabilities();

    // Listen for orientation changes
    const handleOrientationChange = () => {
      setTimeout(checkMobileAndCapabilities, 100);
    };

    window.addEventListener('orientationchange', handleOrientationChange);
    window.addEventListener('resize', checkMobileAndCapabilities);

    return () => {
      window.removeEventListener('orientationchange', handleOrientationChange);
      window.removeEventListener('resize', checkMobileAndCapabilities);
    };
  }, []);

  // Touch gesture handling
  const handleTouchStart = useCallback((e: TouchEvent) => {
    if (!fullConfig.enableTouchOptimization) return;

    const touch = e.touches[0];
    touchStartRef.current = {
      x: touch.clientX,
      y: touch.clientY,
      time: Date.now()
    };
  }, [fullConfig.enableTouchOptimization]);

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (!fullConfig.enableTouchOptimization) return;

    const now = Date.now();
    if (now - lastTouchMoveRef.current < fullConfig.throttleMs) {
      return;
    }
    lastTouchMoveRef.current = now;

    // Prevent default scrolling on chart area
    if (e.target && (e.target as Element).closest('.chart-container')) {
      e.preventDefault();
    }
  }, [fullConfig.enableTouchOptimization, fullConfig.throttleMs]);

  const handleTouchEnd = useCallback((e: TouchEvent) => {
    if (!fullConfig.enableTouchOptimization) return;

    touchStartRef.current = null;
  }, [fullConfig.enableTouchOptimization]);

  // Calculate optimized refresh rate
  const optimizedRefreshRate = useMemo(() => {
    if (!fullConfig.enableReducedRefreshRate) return 60;

    if (isLowEndDevice) return 20;
    if (isMobile) return 30;
    return 60;
  }, [isMobile, isLowEndDevice, fullConfig.enableReducedRefreshRate]);

  // Calculate optimized max data points
  const maxDataPoints = useMemo(() => {
    if (!fullConfig.enableMemoryOptimization) return fullConfig.maxDataPoints;

    if (isLowEndDevice) return Math.min(200, fullConfig.maxDataPoints);
    if (isMobile) return Math.min(350, fullConfig.maxDataPoints);
    return fullConfig.maxDataPoints;
  }, [isMobile, isLowEndDevice, fullConfig.maxDataPoints, fullConfig.enableMemoryOptimization]);

  // Calculate throttle time
  const throttleMs = useMemo(() => {
    if (isLowEndDevice) return Math.max(200, fullConfig.throttleMs);
    if (isMobile) return Math.max(100, fullConfig.throttleMs);
    return fullConfig.throttleMs;
  }, [isMobile, isLowEndDevice, fullConfig.throttleMs]);

  // Cleanup function
  const cleanup = useCallback(() => {
    touchStartRef.current = null;
    lastTouchMoveRef.current = 0;
  }, []);

  return {
    isMobile,
    isLowEndDevice,
    shouldReduceAnimations,
    optimizedRefreshRate,
    maxDataPoints,
    throttleMs,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd,
    cleanup
  };
}

// Helper hook for chart container optimization
export function useChartContainer() {
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setContainerSize({ width, height });
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => resizeObserver.disconnect();
  }, []);

  return { containerRef, containerSize };
}

// Hook for data sampling on mobile devices
export function useMobileDataSampling<T>(
  data: T[],
  maxPoints: number = 500
): T[] {
  return useMemo(() => {
    if (data.length <= maxPoints) return data;

    // Use systematic sampling to maintain data distribution
    const step = data.length / maxPoints;
    const sampledData: T[] = [];

    for (let i = 0; i < data.length; i += step) {
      sampledData.push(data[Math.floor(i)]);
    }

    // Always include the last data point
    if (sampledData[sampledData.length - 1] !== data[data.length - 1]) {
      sampledData[sampledData.length - 1] = data[data.length - 1];
    }

    return sampledData;
  }, [data, maxPoints]);
}
