/**
 * Professional Equity Curve Chart
 *
 * Interactive equity curve visualization using lightweight-charts
 * Shows portfolio performance over time with drawdown visualization
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, IChartApi, ISeriesApi } from 'lightweight-charts';

interface EquityPoint {
  timestamp: string;
  equity: number;
  drawdown_pct: number;
}

interface EquityCurveChartProps {
  data: EquityPoint[];
  initialCapital: number;
  finalCapital: number;
  className?: string;
}

export default function EquityCurveChart({
  data,
  initialCapital,
  finalCapital,
  className = ''
}: EquityCurveChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const equitySeriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const drawdownSeriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const [showDrawdown, setShowDrawdown] = useState(false);

  useEffect(() => {
    if (!chartContainerRef.current || !data.length) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#9CA3AF',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: '#374151' },
        horzLines: { color: '#374151' },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          width: 1,
          color: '#6B7280',
          style: 2,
        },
        horzLine: {
          width: 1,
          color: '#6B7280',
          style: 2,
        },
      },
      rightPriceScale: {
        borderColor: '#374151',
        textColor: '#9CA3AF',
      },
      timeScale: {
        borderColor: '#374151',
        textColor: '#9CA3AF',
        timeVisible: true,
      },
      watermark: {
        visible: true,
        fontSize: 24,
        color: '#1F2937',
        text: 'FXML4 Performance',
      },
    });

    chartRef.current = chart;

    // Create equity series
    const equitySeries = chart.addAreaSeries({
      lineColor: '#10B981',
      topColor: 'rgba(16, 185, 129, 0.3)',
      bottomColor: 'rgba(16, 185, 129, 0.05)',
      lineWidth: 2,
      priceFormat: {
        type: 'price',
        precision: 2,
        minMove: 0.01,
      },
      title: 'Portfolio Equity',
    });

    equitySeriesRef.current = equitySeries;

    // Create drawdown series (initially hidden)
    const drawdownSeries = chart.addAreaSeries({
      lineColor: '#EF4444',
      topColor: 'rgba(239, 68, 68, 0.05)',
      bottomColor: 'rgba(239, 68, 68, 0.3)',
      lineWidth: 2,
      priceFormat: {
        type: 'percent',
        precision: 2,
      },
      title: 'Drawdown',
      visible: false,
    });

    drawdownSeriesRef.current = drawdownSeries;

    // Process and set data
    const equityData = data.map(point => ({
      time: Math.floor(new Date(point.timestamp).getTime() / 1000),
      value: point.equity,
    }));

    const drawdownData = data.map(point => ({
      time: Math.floor(new Date(point.timestamp).getTime() / 1000),
      value: Math.abs(point.drawdown_pct),
    }));

    equitySeries.setData(equityData);
    drawdownSeries.setData(drawdownData);

    // Fit content
    chart.timeScale().fitContent();

    // Resize handler
    const handleResize = () => {
      if (chartContainerRef.current && chart) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chart) {
        chart.remove();
      }
    };
  }, [data]);

  const toggleDrawdown = () => {
    if (drawdownSeriesRef.current) {
      const newVisibility = !showDrawdown;
      drawdownSeriesRef.current.applyOptions({ visible: newVisibility });
      setShowDrawdown(newVisibility);
    }
  };

  const totalReturn = ((finalCapital - initialCapital) / initialCapital) * 100;
  const totalReturnColor = totalReturn >= 0 ? 'text-green-400' : 'text-red-400';

  return (
    <div className={`relative ${className}`}>
      {/* Chart Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Equity Curve</h3>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-gray-400">
              Initial: <span className="text-white font-medium">${initialCapital.toLocaleString()}</span>
            </span>
            <span className="text-gray-400">
              Final: <span className="text-white font-medium">${finalCapital.toLocaleString()}</span>
            </span>
            <span className="text-gray-400">
              Return: <span className={`font-medium ${totalReturnColor}`}>{totalReturn.toFixed(2)}%</span>
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={toggleDrawdown}
            className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
              showDrawdown
                ? 'bg-red-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {showDrawdown ? 'Hide' : 'Show'} Drawdown
          </button>
        </div>
      </div>

      {/* Chart Container */}
      <div
        ref={chartContainerRef}
        className="bg-gray-800/50 rounded-lg border border-gray-600"
        style={{ height: '400px', width: '100%' }}
      />

      {/* Legend */}
      <div className="flex items-center gap-6 mt-3 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-green-500 rounded-sm"></div>
          <span className="text-gray-400">Portfolio Equity</span>
        </div>
        {showDrawdown && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-red-500 rounded-sm"></div>
            <span className="text-gray-400">Drawdown %</span>
          </div>
        )}
      </div>

      {/* Chart Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
        <div className="bg-gray-800/50 rounded p-3">
          <div className="text-xs text-gray-400">Data Points</div>
          <div className="text-lg font-medium text-white">{data.length.toLocaleString()}</div>
        </div>
        <div className="bg-gray-800/50 rounded p-3">
          <div className="text-xs text-gray-400">Peak Equity</div>
          <div className="text-lg font-medium text-green-400">
            ${Math.max(...data.map(d => d.equity)).toLocaleString()}
          </div>
        </div>
        <div className="bg-gray-800/50 rounded p-3">
          <div className="text-xs text-gray-400">Max Drawdown</div>
          <div className="text-lg font-medium text-red-400">
            {Math.min(...data.map(d => d.drawdown_pct)).toFixed(2)}%
          </div>
        </div>
        <div className="bg-gray-800/50 rounded p-3">
          <div className="text-xs text-gray-400">Duration</div>
          <div className="text-lg font-medium text-white">
            {Math.floor((new Date(data[data.length - 1]?.timestamp).getTime() - new Date(data[0]?.timestamp).getTime()) / (1000 * 60 * 60 * 24))} days
          </div>
        </div>
      </div>
    </div>
  );
}
