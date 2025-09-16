/**
 * Performance Optimization Hooks
 *
 * Custom hooks for implementing performance optimizations
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useRouter } from 'next/router';

// Hook for virtualized lists with performance optimization
export function useVirtualizedList<T>(
  items: T[],
  options: {
    itemHeight: number;
    containerHeight: number;
    overscan?: number;
    enableSmoothing?: boolean;
  }
) {
  const { itemHeight, containerHeight, overscan = 5, enableSmoothing = true } = options;
  const [scrollTop, setScrollTop] = useState(0);
  const [isScrolling, setIsScrolling] = useState(false);
  const scrollTimeoutRef = useRef<NodeJS.Timeout>();

  const visibleRange = useMemo(() => {
    const visibleItemCount = Math.ceil(containerHeight / itemHeight);
    const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const endIndex = Math.min(items.length, startIndex + visibleItemCount + overscan * 2);

    return { startIndex, endIndex, visibleItemCount };
  }, [scrollTop, itemHeight, containerHeight, overscan, items.length]);

  const visibleItems = useMemo(() => {
    return items.slice(visibleRange.startIndex, visibleRange.endIndex).map((item, index) => ({
      item,
      index: visibleRange.startIndex + index,
      style: {
        position: 'absolute' as const,
        top: (visibleRange.startIndex + index) * itemHeight,
        height: itemHeight,
        width: '100%'
      }
    }));
  }, [items, visibleRange, itemHeight]);

  const handleScroll = useCallback((event: React.UIEvent<HTMLDivElement>) => {
    const newScrollTop = event.currentTarget.scrollTop;

    if (enableSmoothing) {
      // Smooth scrolling with throttling
      requestAnimationFrame(() => {
        setScrollTop(newScrollTop);
      });
    } else {
      setScrollTop(newScrollTop);
    }

    setIsScrolling(true);

    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }

    scrollTimeoutRef.current = setTimeout(() => {
      setIsScrolling(false);
    }, 150);
  }, [enableSmoothing]);

  const containerProps = {
    style: {
      height: containerHeight,
      overflow: 'auto' as const,
      position: 'relative' as const
    },
    onScroll: handleScroll
  };

  const innerProps = {
    style: {
      height: items.length * itemHeight,
      position: 'relative' as const
    }
  };

  return {
    visibleItems,
    containerProps,
    innerProps,
    isScrolling,
    totalHeight: items.length * itemHeight,
    scrollTop
  };
}

// Hook for debounced search with performance optimization
export function useOptimizedSearch<T>(
  items: T[],
  searchFields: (keyof T)[],
  options: {
    debounceMs?: number;
    minSearchLength?: number;
    maxResults?: number;
    enableHighlighting?: boolean;
  } = {}
) {
  const {
    debounceMs = 300,
    minSearchLength = 2,
    maxResults = 100,
    enableHighlighting = false
  } = options;

  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const searchTimeoutRef = useRef<NodeJS.Timeout>();

  // Debounce search term
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    setIsSearching(true);

    searchTimeoutRef.current = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setIsSearching(false);
    }, debounceMs);

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchTerm, debounceMs]);

  // Memoized search results
  const searchResults = useMemo(() => {
    if (!debouncedSearchTerm || debouncedSearchTerm.length < minSearchLength) {
      return items;
    }

    const lowercaseSearch = debouncedSearchTerm.toLowerCase();

    const filtered = items.filter(item => {
      return searchFields.some(field => {
        const value = item[field];
        if (typeof value === 'string') {
          return value.toLowerCase().includes(lowercaseSearch);
        }
        if (typeof value === 'number') {
          return value.toString().includes(lowercaseSearch);
        }
        return false;
      });
    }).slice(0, maxResults);

    return filtered;
  }, [items, debouncedSearchTerm, searchFields, minSearchLength, maxResults]);

  // Highlight function for search results
  const highlightText = useCallback((text: string, highlight: string) => {
    if (!enableHighlighting || !highlight) return text;

    const parts = text.split(new RegExp(`(${highlight})`, 'gi'));
    return parts.map((part, index) =>
      part.toLowerCase() === highlight.toLowerCase() ? (
        <mark key={index} className="bg-yellow-200">{part}</mark>
      ) : part
    );
  }, [enableHighlighting]);

  return {
    searchTerm,
    setSearchTerm,
    searchResults,
    isSearching,
    highlightText,
    hasResults: searchResults.length > 0,
    resultCount: searchResults.length
  };
}

// Hook for memoized expensive calculations
export function useMemoizedCalculation<T>(
  calculateFn: () => T,
  dependencies: any[],
  options: {
    enableCaching?: boolean;
    cacheKey?: string;
    ttl?: number;
  } = {}
) {
  const { enableCaching = true, cacheKey, ttl = 5 * 60 * 1000 } = options; // 5 minutes default TTL
  const cacheRef = useRef<Map<string, { value: T; timestamp: number }>>(new Map());

  const result = useMemo(() => {
    if (enableCaching && cacheKey) {
      const cached = cacheRef.current.get(cacheKey);
      const now = Date.now();

      if (cached && (now - cached.timestamp) < ttl) {
        return cached.value;
      }
    }

    const calculatedValue = calculateFn();

    if (enableCaching && cacheKey) {
      cacheRef.current.set(cacheKey, {
        value: calculatedValue,
        timestamp: Date.now()
      });
    }

    return calculatedValue;
  }, dependencies);

  const clearCache = useCallback(() => {
    if (cacheKey) {
      cacheRef.current.delete(cacheKey);
    } else {
      cacheRef.current.clear();
    }
  }, [cacheKey]);

  return { result, clearCache };
}

// Hook for optimized API calls with caching and deduplication
export function useOptimizedAPI<T>(
  url: string,
  options: {
    enabled?: boolean;
    refetchInterval?: number;
    staleTime?: number;
    cacheTime?: number;
    dedupe?: boolean;
  } = {}
) {
  const {
    enabled = true,
    refetchInterval,
    staleTime = 5 * 60 * 1000, // 5 minutes
    cacheTime = 10 * 60 * 1000, // 10 minutes
    dedupe = true
  } = options;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const cacheRef = useRef<Map<string, {
    data: T;
    timestamp: number;
    promise?: Promise<T>;
  }>>(new Map());

  const intervalRef = useRef<NodeJS.Timeout>();

  const fetchData = useCallback(async (): Promise<T> => {
    const now = Date.now();

    // Check cache first
    const cached = cacheRef.current.get(url);
    if (cached && (now - cached.timestamp) < staleTime) {
      return cached.data;
    }

    // Deduplicate concurrent requests
    if (dedupe && cached?.promise) {
      return cached.promise;
    }

    setLoading(true);
    setError(null);

    const fetchPromise = fetch(url)
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
      })
      .then((result: T) => {
        cacheRef.current.set(url, {
          data: result,
          timestamp: now,
        });
        setData(result);
        setLoading(false);
        return result;
      })
      .catch(err => {
        setError(err);
        setLoading(false);
        throw err;
      });

    if (dedupe) {
      cacheRef.current.set(url, {
        data: cached?.data || null as any,
        timestamp: cached?.timestamp || 0,
        promise: fetchPromise
      });
    }

    return fetchPromise;
  }, [url, staleTime, dedupe]);

  // Initial fetch
  useEffect(() => {
    if (enabled) {
      fetchData().catch(() => {
        // Error already handled in fetchData
      });
    }
  }, [enabled, fetchData]);

  // Refetch interval
  useEffect(() => {
    if (enabled && refetchInterval) {
      intervalRef.current = setInterval(() => {
        fetchData().catch(() => {
          // Error already handled in fetchData
        });
      }, refetchInterval);

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    }
  }, [enabled, refetchInterval, fetchData]);

  // Cache cleanup
  useEffect(() => {
    const cleanup = () => {
      const now = Date.now();
      for (const [key, value] of cacheRef.current.entries()) {
        if (now - value.timestamp > cacheTime) {
          cacheRef.current.delete(key);
        }
      }
    };

    const cleanupInterval = setInterval(cleanup, cacheTime);
    return () => clearInterval(cleanupInterval);
  }, [cacheTime]);

  const refetch = useCallback(() => {
    cacheRef.current.delete(url);
    return fetchData();
  }, [url, fetchData]);

  return {
    data,
    loading,
    error,
    refetch,
    isStale: data && cacheRef.current.get(url) &&
             Date.now() - cacheRef.current.get(url)!.timestamp > staleTime
  };
}

// Hook for route-based code splitting with preloading
export function useRoutePreloading() {
  const router = useRouter();
  const preloadedRoutes = useRef<Set<string>>(new Set());

  const preloadRoute = useCallback(async (route: string) => {
    if (preloadedRoutes.current.has(route)) {
      return;
    }

    try {
      await router.prefetch(route);
      preloadedRoutes.current.add(route);
      console.log(`🎯 Preloaded route: ${route}`);
    } catch (error) {
      console.error(`Failed to preload route ${route}:`, error);
    }
  }, [router]);

  // Preload routes on hover/focus
  const createPreloadHandlers = useCallback((route: string, delay: number = 0) => ({
    onMouseEnter: () => {
      setTimeout(() => preloadRoute(route), delay);
    },
    onFocus: () => {
      setTimeout(() => preloadRoute(route), delay);
    }
  }), [preloadRoute]);

  // Preload critical routes
  const preloadCriticalRoutes = useCallback((routes: string[]) => {
    routes.forEach(route => preloadRoute(route));
  }, [preloadRoute]);

  return {
    preloadRoute,
    createPreloadHandlers,
    preloadCriticalRoutes,
    preloadedRoutes: Array.from(preloadedRoutes.current)
  };
}

// Hook for optimized image loading
export function useOptimizedImage(
  src: string,
  options: {
    lazy?: boolean;
    placeholder?: string;
    quality?: number;
    sizes?: string;
    priority?: boolean;
  } = {}
) {
  const {
    lazy = true,
    placeholder,
    quality = 75,
    sizes,
    priority = false
  } = options;

  const [imageState, setImageState] = useState<{
    src: string;
    loading: boolean;
    error: boolean;
    loaded: boolean;
  }>({
    src: placeholder || '',
    loading: false,
    error: false,
    loaded: false
  });

  const imageRef = useRef<HTMLImageElement>();
  const observerRef = useRef<IntersectionObserver>();

  // Intersection observer for lazy loading
  useEffect(() => {
    if (!lazy || priority) {
      loadImage();
      return;
    }

    observerRef.current = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          loadImage();
          observerRef.current?.disconnect();
        }
      },
      { threshold: 0.1 }
    );

    if (imageRef.current) {
      observerRef.current.observe(imageRef.current);
    }

    return () => {
      observerRef.current?.disconnect();
    };
  }, [lazy, priority, src]);

  const loadImage = useCallback(() => {
    if (imageState.loaded || imageState.loading) return;

    setImageState(prev => ({ ...prev, loading: true, error: false }));

    const img = new Image();

    img.onload = () => {
      setImageState({
        src: src,
        loading: false,
        error: false,
        loaded: true
      });
    };

    img.onerror = () => {
      setImageState(prev => ({
        ...prev,
        loading: false,
        error: true
      }));
    };

    // Optimize image URL with quality and size parameters
    let optimizedSrc = src;
    if (src.includes('?')) {
      optimizedSrc += `&q=${quality}`;
    } else {
      optimizedSrc += `?q=${quality}`;
    }

    img.src = optimizedSrc;
  }, [src, quality, imageState.loaded, imageState.loading]);

  return {
    ...imageState,
    imageRef,
    imageProps: {
      ref: imageRef,
      src: imageState.src,
      loading: lazy && !priority ? 'lazy' : 'eager',
      sizes,
      onLoad: () => {
        if (!imageState.loaded) {
          setImageState(prev => ({ ...prev, loaded: true, loading: false }));
        }
      },
      onError: () => {
        setImageState(prev => ({ ...prev, error: true, loading: false }));
      }
    }
  };
}

// Hook for performance budget monitoring
export function usePerformanceBudget(
  budgets: {
    bundleSize?: number;
    loadTime?: number;
    renderTime?: number;
    memoryUsage?: number;
  }
) {
  const [budgetStatus, setBudgetStatus] = useState<{
    [key: string]: {
      current: number;
      budget: number;
      status: 'good' | 'warning' | 'exceeded';
      percentage: number;
    };
  }>({});

  const checkBudgets = useCallback(() => {
    const status: typeof budgetStatus = {};

    // Check bundle size budget
    if (budgets.bundleSize && typeof window !== 'undefined') {
      const resources = performance.getEntriesByType('resource');
      const totalSize = resources.reduce((total, resource) => {
        return total + (resource.transferSize || 0);
      }, 0);

      const percentage = (totalSize / budgets.bundleSize) * 100;
      status.bundleSize = {
        current: totalSize,
        budget: budgets.bundleSize,
        status: percentage > 100 ? 'exceeded' : percentage > 80 ? 'warning' : 'good',
        percentage
      };
    }

    // Check load time budget
    if (budgets.loadTime && typeof window !== 'undefined') {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
      const loadTime = navigation ? navigation.loadEventEnd - navigation.navigationStart : 0;

      const percentage = (loadTime / budgets.loadTime) * 100;
      status.loadTime = {
        current: loadTime,
        budget: budgets.loadTime,
        status: percentage > 100 ? 'exceeded' : percentage > 80 ? 'warning' : 'good',
        percentage
      };
    }

    setBudgetStatus(status);
  }, [budgets]);

  useEffect(() => {
    checkBudgets();

    // Check budgets periodically
    const interval = setInterval(checkBudgets, 10000);
    return () => clearInterval(interval);
  }, [checkBudgets]);

  return {
    budgetStatus,
    checkBudgets,
    overallStatus: Object.values(budgetStatus).some(b => b.status === 'exceeded') ? 'exceeded' :
                  Object.values(budgetStatus).some(b => b.status === 'warning') ? 'warning' : 'good'
  };
}
