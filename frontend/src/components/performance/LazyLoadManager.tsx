/**
 * Lazy Load Manager Component
 *
 * Centralized lazy loading management with performance monitoring
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useInView } from 'react-intersection-observer';

interface LazyLoadConfig {
  threshold: number;
  rootMargin: string;
  preloadDelay: number;
  retryAttempts: number;
  enablePreloading: boolean;
  performanceLogging: boolean;
}

interface LazyComponentInfo {
  id: string;
  name: string;
  loadState: 'idle' | 'loading' | 'loaded' | 'error';
  loadTime?: number;
  retryCount: number;
  priority: 'high' | 'medium' | 'low';
  preloaded: boolean;
}

interface LazyLoadManagerProps {
  config?: Partial<LazyLoadConfig>;
  children: React.ReactNode;
  onLoadStateChange?: (components: LazyComponentInfo[]) => void;
}

const defaultConfig: LazyLoadConfig = {
  threshold: 0.1,
  rootMargin: '50px',
  preloadDelay: 2000,
  retryAttempts: 3,
  enablePreloading: true,
  performanceLogging: process.env.NODE_ENV === 'development'
};

export const LazyLoadManager: React.FC<LazyLoadManagerProps> = ({
  config = {},
  children,
  onLoadStateChange
}) => {
  const finalConfig = { ...defaultConfig, ...config };
  const [components, setComponents] = useState<Map<string, LazyComponentInfo>>(new Map());
  const [performanceMetrics, setPerformanceMetrics] = useState({
    totalComponents: 0,
    loadedComponents: 0,
    failedComponents: 0,
    averageLoadTime: 0,
    totalLoadTime: 0
  });

  const preloadTimerRef = useRef<NodeJS.Timeout>();
  const observerRef = useRef<IntersectionObserver>();

  // Initialize intersection observer for lazy loading
  useEffect(() => {
    if (typeof window !== 'undefined') {
      observerRef.current = new IntersectionObserver(
        (entries) => {
          entries.forEach(entry => {
            const componentId = entry.target.getAttribute('data-lazy-id');
            if (componentId && entry.isIntersecting) {
              triggerComponentLoad(componentId);
            }
          });
        },
        {
          threshold: finalConfig.threshold,
          rootMargin: finalConfig.rootMargin
        }
      );
    }

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
      if (preloadTimerRef.current) {
        clearTimeout(preloadTimerRef.current);
      }
    };
  }, [finalConfig.threshold, finalConfig.rootMargin]);

  // Register a new lazy component
  const registerComponent = useCallback((info: Omit<LazyComponentInfo, 'loadState' | 'retryCount' | 'preloaded'>) => {
    const componentInfo: LazyComponentInfo = {
      ...info,
      loadState: 'idle',
      retryCount: 0,
      preloaded: false
    };

    setComponents(prev => {
      const next = new Map(prev);
      next.set(info.id, componentInfo);
      return next;
    });

    // Update metrics
    setPerformanceMetrics(prev => ({
      ...prev,
      totalComponents: prev.totalComponents + 1
    }));

    return componentInfo;
  }, []);

  // Update component state
  const updateComponent = useCallback((id: string, updates: Partial<LazyComponentInfo>) => {
    setComponents(prev => {
      const next = new Map(prev);
      const existing = next.get(id);
      if (existing) {
        next.set(id, { ...existing, ...updates });
      }
      return next;
    });
  }, []);

  // Trigger component loading
  const triggerComponentLoad = useCallback(async (componentId: string) => {
    const component = components.get(componentId);
    if (!component || component.loadState !== 'idle') return;

    const startTime = performance.now();

    updateComponent(componentId, { loadState: 'loading' });

    try {
      // Simulate component loading (would be actual dynamic import)
      await new Promise(resolve => setTimeout(resolve, Math.random() * 1000 + 500));

      const endTime = performance.now();
      const loadTime = endTime - startTime;

      updateComponent(componentId, {
        loadState: 'loaded',
        loadTime
      });

      // Update performance metrics
      setPerformanceMetrics(prev => ({
        ...prev,
        loadedComponents: prev.loadedComponents + 1,
        totalLoadTime: prev.totalLoadTime + loadTime,
        averageLoadTime: (prev.totalLoadTime + loadTime) / (prev.loadedComponents + 1)
      }));

      if (finalConfig.performanceLogging) {
        console.log(`🚀 Lazy loaded ${component.name} in ${loadTime.toFixed(2)}ms`);
      }

    } catch (error) {
      const component = components.get(componentId);
      if (component && component.retryCount < finalConfig.retryAttempts) {
        // Retry loading
        setTimeout(() => {
          updateComponent(componentId, {
            loadState: 'idle',
            retryCount: component.retryCount + 1
          });
          triggerComponentLoad(componentId);
        }, 1000 * Math.pow(2, component.retryCount)); // Exponential backoff
      } else {
        updateComponent(componentId, { loadState: 'error' });
        setPerformanceMetrics(prev => ({
          ...prev,
          failedComponents: prev.failedComponents + 1
        }));

        console.error(`❌ Failed to lazy load ${component?.name}:`, error);
      }
    }
  }, [components, finalConfig.retryAttempts, finalConfig.performanceLogging, updateComponent]);

  // Preload high-priority components
  const preloadComponents = useCallback(() => {
    if (!finalConfig.enablePreloading) return;

    const highPriorityComponents = Array.from(components.values())
      .filter(comp => comp.priority === 'high' && comp.loadState === 'idle' && !comp.preloaded);

    highPriorityComponents.forEach(component => {
      updateComponent(component.id, { preloaded: true });
      triggerComponentLoad(component.id);
    });

    if (finalConfig.performanceLogging && highPriorityComponents.length > 0) {
      console.log(`🎯 Preloading ${highPriorityComponents.length} high-priority components`);
    }
  }, [components, finalConfig.enablePreloading, finalConfig.performanceLogging, triggerComponentLoad, updateComponent]);

  // Schedule preloading
  useEffect(() => {
    if (finalConfig.enablePreloading) {
      preloadTimerRef.current = setTimeout(preloadComponents, finalConfig.preloadDelay);
    }
  }, [finalConfig.enablePreloading, finalConfig.preloadDelay, preloadComponents]);

  // Notify parent of load state changes
  useEffect(() => {
    if (onLoadStateChange) {
      onLoadStateChange(Array.from(components.values()));
    }
  }, [components, onLoadStateChange]);

  // Observe elements for lazy loading
  const observeElement = useCallback((element: Element, componentId: string) => {
    if (observerRef.current && element) {
      element.setAttribute('data-lazy-id', componentId);
      observerRef.current.observe(element);
    }
  }, []);

  // Unobserve elements
  const unobserveElement = useCallback((element: Element) => {
    if (observerRef.current && element) {
      observerRef.current.unobserve(element);
    }
  }, []);

  // Context value for child components
  const contextValue = {
    registerComponent,
    updateComponent,
    triggerComponentLoad,
    observeElement,
    unobserveElement,
    config: finalConfig,
    metrics: performanceMetrics,
    components: Array.from(components.values())
  };

  return (
    <LazyLoadContext.Provider value={contextValue}>
      {children}
    </LazyLoadContext.Provider>
  );
};

// Context for accessing lazy load functionality
export const LazyLoadContext = React.createContext<{
  registerComponent: (info: Omit<LazyComponentInfo, 'loadState' | 'retryCount' | 'preloaded'>) => LazyComponentInfo;
  updateComponent: (id: string, updates: Partial<LazyComponentInfo>) => void;
  triggerComponentLoad: (componentId: string) => Promise<void>;
  observeElement: (element: Element, componentId: string) => void;
  unobserveElement: (element: Element) => void;
  config: LazyLoadConfig;
  metrics: any;
  components: LazyComponentInfo[];
} | null>(null);

// Hook for using lazy load context
export const useLazyLoad = () => {
  const context = React.useContext(LazyLoadContext);
  if (!context) {
    throw new Error('useLazyLoad must be used within a LazyLoadManager');
  }
  return context;
};

// HOC for making components lazy-loadable
export function withLazyLoad<P extends object>(
  Component: React.ComponentType<P>,
  options: {
    name: string;
    priority?: 'high' | 'medium' | 'low';
    fallback?: React.ComponentType;
    errorFallback?: React.ComponentType<{ error: Error; retry: () => void }>;
  }
) {
  return React.forwardRef<any, P>((props, ref) => {
    const { registerComponent, observeElement, unobserveElement, components } = useLazyLoad();
    const [componentId] = useState(() => `lazy-${options.name}-${Math.random().toString(36).substr(2, 9)}`);
    const elementRef = useRef<HTMLDivElement>(null);

    // Register component on mount
    useEffect(() => {
      registerComponent({
        id: componentId,
        name: options.name,
        priority: options.priority || 'medium'
      });
    }, [componentId, registerComponent]);

    // Observe element for lazy loading
    useEffect(() => {
      if (elementRef.current) {
        observeElement(elementRef.current, componentId);

        return () => {
          if (elementRef.current) {
            unobserveElement(elementRef.current);
          }
        };
      }
    }, [componentId, observeElement, unobserveElement]);

    const componentState = components.find(c => c.id === componentId);

    if (!componentState) {
      return <div ref={elementRef} className="h-32 bg-gray-100 animate-pulse rounded" />;
    }

    switch (componentState.loadState) {
      case 'idle':
      case 'loading':
        if (options.fallback) {
          const FallbackComponent = options.fallback;
          return (
            <div ref={elementRef}>
              <FallbackComponent />
            </div>
          );
        }
        return <div ref={elementRef} className="h-32 bg-gray-100 animate-pulse rounded" />;

      case 'error':
        if (options.errorFallback) {
          const ErrorComponent = options.errorFallback;
          return (
            <div ref={elementRef}>
              <ErrorComponent
                error={new Error(`Failed to load ${options.name}`)}
                retry={() => {/* retry logic */}}
              />
            </div>
          );
        }
        return (
          <div ref={elementRef} className="h-32 bg-red-100 flex items-center justify-center rounded">
            <span className="text-red-600 text-sm">Failed to load {options.name}</span>
          </div>
        );

      case 'loaded':
        return (
          <div ref={elementRef}>
            <Component {...props} ref={ref} />
          </div>
        );

      default:
        return <div ref={elementRef} className="h-32 bg-gray-100 animate-pulse rounded" />;
    }
  });
}

// Lazy loading performance monitor component
export const LazyLoadMonitor: React.FC = () => {
  const { metrics, components, config } = useLazyLoad();
  const [isVisible, setIsVisible] = useState(false);

  if (process.env.NODE_ENV !== 'development') {
    return null;
  }

  return (
    <div className="fixed bottom-16 right-4 z-50">
      <div className="bg-gray-900 text-white rounded-lg shadow-lg border border-gray-700">
        <button
          onClick={() => setIsVisible(!isVisible)}
          className="w-full p-2 text-sm font-semibold flex items-center justify-between hover:bg-gray-800 rounded-lg"
        >
          <span>Lazy Load Monitor</span>
          <div className="flex items-center space-x-2">
            <span className="bg-blue-600 text-xs px-2 py-1 rounded">
              {metrics.loadedComponents}/{metrics.totalComponents}
            </span>
            <svg
              className={`w-4 h-4 transform transition-transform ${isVisible ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </button>

        {isVisible && (
          <div className="border-t border-gray-700 p-3 max-w-sm">
            <div className="grid grid-cols-2 gap-2 text-xs mb-3">
              <div>
                <span className="text-gray-400">Loaded:</span>
                <div className="font-mono">{metrics.loadedComponents}</div>
              </div>
              <div>
                <span className="text-gray-400">Failed:</span>
                <div className="font-mono text-red-400">{metrics.failedComponents}</div>
              </div>
              <div>
                <span className="text-gray-400">Avg Load:</span>
                <div className="font-mono">{metrics.averageLoadTime.toFixed(0)}ms</div>
              </div>
              <div>
                <span className="text-gray-400">Total Time:</span>
                <div className="font-mono">{metrics.totalLoadTime.toFixed(0)}ms</div>
              </div>
            </div>

            <div className="max-h-32 overflow-y-auto space-y-1">
              {components.map(component => (
                <div key={component.id} className="flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-2">
                    <div className={`w-2 h-2 rounded-full ${
                      component.loadState === 'loaded' ? 'bg-green-400' :
                      component.loadState === 'loading' ? 'bg-yellow-400' :
                      component.loadState === 'error' ? 'bg-red-400' : 'bg-gray-400'
                    }`}></div>
                    <span className="truncate max-w-[100px]">{component.name}</span>
                  </div>
                  <div className="text-gray-400">
                    {component.loadTime ? `${component.loadTime.toFixed(0)}ms` : '-'}
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-3 pt-2 border-t border-gray-700 text-xs text-gray-400">
              Config: {config.threshold}t, {config.rootMargin}m
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
