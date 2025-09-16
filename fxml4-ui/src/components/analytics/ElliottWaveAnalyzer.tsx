/**
 * Elliott Wave Analysis Component
 *
 * AI-enhanced Elliott Wave pattern detection and analysis with LLM validation
 * Migrated from FXML3 Streamlit application with enhanced React functionality
 */

'use client';

import { useState, useEffect } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useAppStore } from '@/stores/appStore';
import {
  CursorArrowRaysIcon,
  BeakerIcon,
  CpuChipIcon,
  ChartBarIcon,
  WrenchScrewdriverIcon,
  SparklesIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';

interface WavePattern {
  id: string;
  wave_type: 'impulse' | 'corrective';
  degree: 'primary' | 'intermediate' | 'minor' | 'minute' | 'minuette';
  start_idx: number;
  end_idx: number;
  confidence: number;
  fibonacci_levels: {
    level: number;
    price: number;
    type: 'retracement' | 'extension';
  }[];
  subwaves: {
    wave_num: number;
    start_idx: number;
    end_idx: number;
    start_price: number;
    end_price: number;
    confidence: number;
  }[];
  llm_validation?: {
    validated: boolean;
    confidence: number;
    reasoning: string;
    corrections?: string;
  };
}

interface WaveAnalysisResult {
  analysis_id: string;
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  waves: WavePattern[];
  market_structure: {
    trend: 'bullish' | 'bearish' | 'sideways';
    cycle_position: 'early' | 'middle' | 'late';
    completion_probability: number;
  };
  trading_signals: {
    signal_type: 'BUY' | 'SELL' | 'HOLD';
    entry_price: number;
    stop_loss: number;
    take_profit: number[];
    confidence: number;
    reasoning: string;
  }[];
  created_at: string;
  updated_at: string;
}

interface WaveAnalysisOptions {
  include_subwaves: boolean;
  min_wave_points: number;
  confidence_threshold: number;
  enable_llm_validation: boolean;
  fibonacci_analysis: boolean;
  degree_filter: string[];
}

export default function ElliottWaveAnalyzer() {
  const [activeTab, setActiveTab] = useState('detection');
  const [symbol, setSymbol] = useState('EURUSD');
  const [timeframe, setTimeframe] = useState('1h');
  const [analysisOptions, setAnalysisOptions] = useState<WaveAnalysisOptions>({
    include_subwaves: true,
    min_wave_points: 5,
    confidence_threshold: 0.7,
    enable_llm_validation: true,
    fibonacci_analysis: true,
    degree_filter: ['primary', 'intermediate', 'minor']
  });

  const [currentAnalysis, setCurrentAnalysis] = useState<WaveAnalysisResult | null>(null);
  const [analysisHistory, setAnalysisHistory] = useState<WaveAnalysisResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);

  const { addNotification } = useAppStore();

  useEffect(() => {
    loadAnalysisHistory();
  }, []);

  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (taskId && currentAnalysis?.status === 'processing') {
      interval = setInterval(() => {
        checkAnalysisStatus();
      }, 2000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [taskId, currentAnalysis?.status]);

  const loadAnalysisHistory = async () => {
    try {
      // Simulate API call - in production this would fetch from /api/analysis/waves
      const mockHistory: WaveAnalysisResult[] = [
        {
          analysis_id: 'wave_001',
          symbol: 'EURUSD',
          timeframe: '1h',
          start_date: '2023-11-01',
          end_date: '2023-12-01',
          status: 'completed',
          progress: 100,
          waves: generateMockWaves(),
          market_structure: {
            trend: 'bullish',
            cycle_position: 'middle',
            completion_probability: 0.73
          },
          trading_signals: [
            {
              signal_type: 'BUY',
              entry_price: 1.0845,
              stop_loss: 1.0790,
              take_profit: [1.0920, 1.0985],
              confidence: 0.78,
              reasoning: 'Wave 4 correction complete, Wave 5 impulse expected'
            }
          ],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      ];

      setAnalysisHistory(mockHistory);
    } catch (error) {
      console.error('Failed to load analysis history:', error);
      addNotification({
        type: 'error',
        title: 'Load Error',
        message: 'Failed to load wave analysis history'
      });
    }
  };

  const startWaveAnalysis = async () => {
    try {
      setLoading(true);

      // Simulate API call - in production this would call /api/analysis/waves
      const mockTaskId = `task_${Date.now()}`;
      setTaskId(mockTaskId);

      const newAnalysis: WaveAnalysisResult = {
        analysis_id: `wave_${Date.now()}`,
        symbol,
        timeframe,
        start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        end_date: new Date().toISOString().split('T')[0],
        status: 'processing',
        progress: 0,
        waves: [],
        market_structure: {
          trend: 'sideways',
          cycle_position: 'early',
          completion_probability: 0
        },
        trading_signals: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };

      setCurrentAnalysis(newAnalysis);

      addNotification({
        type: 'info',
        title: 'Analysis Started',
        message: `Elliott Wave analysis started for ${symbol} ${timeframe}`
      });

      // Simulate progressive analysis
      setTimeout(() => simulateAnalysisProgress(), 1000);

    } catch (error) {
      console.error('Failed to start wave analysis:', error);
      addNotification({
        type: 'error',
        title: 'Analysis Error',
        message: 'Failed to start Elliott Wave analysis'
      });
    } finally {
      setLoading(false);
    }
  };

  const simulateAnalysisProgress = () => {
    if (!currentAnalysis) return;

    const progressSteps = [15, 35, 55, 75, 90, 100];
    let currentStep = 0;

    const progressInterval = setInterval(() => {
      if (currentStep >= progressSteps.length) {
        clearInterval(progressInterval);

        // Analysis complete
        const completedAnalysis: WaveAnalysisResult = {
          ...currentAnalysis,
          status: 'completed',
          progress: 100,
          waves: generateMockWaves(),
          market_structure: {
            trend: 'bullish',
            cycle_position: 'middle',
            completion_probability: 0.73
          },
          trading_signals: [
            {
              signal_type: 'BUY',
              entry_price: 1.0845,
              stop_loss: 1.0790,
              take_profit: [1.0920, 1.0985],
              confidence: 0.78,
              reasoning: 'Wave 4 correction complete, Wave 5 impulse expected'
            }
          ],
          updated_at: new Date().toISOString()
        };

        setCurrentAnalysis(completedAnalysis);
        setAnalysisHistory(prev => [completedAnalysis, ...prev]);
        setTaskId(null);

        addNotification({
          type: 'success',
          title: 'Analysis Complete',
          message: 'Elliott Wave analysis completed successfully'
        });

        return;
      }

      const progress = progressSteps[currentStep];
      setCurrentAnalysis(prev => prev ? {
        ...prev,
        progress,
        updated_at: new Date().toISOString()
      } : null);

      currentStep++;
    }, 1500);
  };

  const checkAnalysisStatus = async () => {
    if (!taskId || !currentAnalysis) return;

    try {
      // Simulate API call to check task status
      // In production: GET /api/tasks/{taskId}
    } catch (error) {
      console.error('Failed to check analysis status:', error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="w-5 h-5 text-green-400" />;
      case 'processing':
        return <ClockIcon className="w-5 h-5 text-blue-400" />;
      case 'failed':
        return <XCircleIcon className="w-5 h-5 text-red-400" />;
      default:
        return <ExclamationTriangleIcon className="w-5 h-5 text-yellow-400" />;
    }
  };

  const formatConfidence = (confidence: number): string => {
    return `${(confidence * 100).toFixed(1)}%`;
  };

  const getWaveColor = (waveNum: number): string => {
    const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6'];
    return colors[waveNum % colors.length];
  };

  return (
    <div className="h-full">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-700 bg-gray-900/50">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-white">Elliott Wave Analyzer</h1>
              <p className="text-gray-400">AI-enhanced Elliott Wave pattern detection and analysis</p>
            </div>

            <div className="flex items-center gap-3">
              <Button
                onClick={startWaveAnalysis}
                disabled={loading || currentAnalysis?.status === 'processing'}
                className="gap-2"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <SparklesIcon className="w-4 h-4" />
                )}
                {currentAnalysis?.status === 'processing' ? 'Analyzing...' : 'Start Analysis'}
              </Button>
            </div>
          </div>

          <TabsList className="grid w-full grid-cols-4 bg-gray-800">
            <TabsTrigger value="detection" className="gap-2">
              <CursorArrowRaysIcon className="w-4 h-4" />
              Detection
            </TabsTrigger>
            <TabsTrigger value="patterns" className="gap-2">
              <ChartBarIcon className="w-4 h-4" />
              Patterns
            </TabsTrigger>
            <TabsTrigger value="signals" className="gap-2">
              <BeakerIcon className="w-4 h-4" />
              Signals
            </TabsTrigger>
            <TabsTrigger value="history" className="gap-2">
              <ClockIcon className="w-4 h-4" />
              History
            </TabsTrigger>
          </TabsList>
        </div>

        <div className="flex-1 p-6">
          <TabsContent value="detection" className="h-full mt-0">
            <div className="space-y-6">
              {/* Analysis Configuration */}
              <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Analysis Configuration</h3>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">Symbol</label>
                      <Select value={symbol} onValueChange={setSymbol}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="EURUSD">EUR/USD</SelectItem>
                          <SelectItem value="GBPUSD">GBP/USD</SelectItem>
                          <SelectItem value="USDJPY">USD/JPY</SelectItem>
                          <SelectItem value="AUDUSD">AUD/USD</SelectItem>
                          <SelectItem value="USDCHF">USD/CHF</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">Timeframe</label>
                      <Select value={timeframe} onValueChange={setTimeframe}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="15m">15 minutes</SelectItem>
                          <SelectItem value="1h">1 hour</SelectItem>
                          <SelectItem value="4h">4 hours</SelectItem>
                          <SelectItem value="1d">Daily</SelectItem>
                          <SelectItem value="1w">Weekly</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Min Wave Points: {analysisOptions.min_wave_points}
                      </label>
                      <input
                        type="range"
                        min="3"
                        max="20"
                        value={analysisOptions.min_wave_points}
                        onChange={(e) => setAnalysisOptions(prev => ({
                          ...prev,
                          min_wave_points: parseInt(e.target.value)
                        }))}
                        className="w-full"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Confidence Threshold: {formatConfidence(analysisOptions.confidence_threshold)}
                      </label>
                      <input
                        type="range"
                        min="0.1"
                        max="0.9"
                        step="0.05"
                        value={analysisOptions.confidence_threshold}
                        onChange={(e) => setAnalysisOptions(prev => ({
                          ...prev,
                          confidence_threshold: parseFloat(e.target.value)
                        }))}
                        className="w-full"
                      />
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="space-y-3">
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={analysisOptions.include_subwaves}
                          onChange={(e) => setAnalysisOptions(prev => ({
                            ...prev,
                            include_subwaves: e.target.checked
                          }))}
                          className="rounded border-gray-600 bg-gray-800 text-blue-500"
                        />
                        <span className="text-sm text-gray-300">Include Subwaves</span>
                      </label>

                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={analysisOptions.enable_llm_validation}
                          onChange={(e) => setAnalysisOptions(prev => ({
                            ...prev,
                            enable_llm_validation: e.target.checked
                          }))}
                          className="rounded border-gray-600 bg-gray-800 text-blue-500"
                        />
                        <span className="text-sm text-gray-300">LLM Validation</span>
                      </label>

                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={analysisOptions.fibonacci_analysis}
                          onChange={(e) => setAnalysisOptions(prev => ({
                            ...prev,
                            fibonacci_analysis: e.target.checked
                          }))}
                          className="rounded border-gray-600 bg-gray-800 text-blue-500"
                        />
                        <span className="text-sm text-gray-300">Fibonacci Analysis</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              {/* Current Analysis Status */}
              {currentAnalysis && (
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-white">Current Analysis</h3>
                    <div className="flex items-center gap-2">
                      {getStatusIcon(currentAnalysis.status)}
                      <span className="text-sm text-gray-300 capitalize">{currentAnalysis.status}</span>
                    </div>
                  </div>

                  {currentAnalysis.status === 'processing' && (
                    <div className="space-y-3">
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400">Progress</span>
                        <span className="text-white">{currentAnalysis.progress}%</span>
                      </div>
                      <div className="w-full bg-gray-700 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${currentAnalysis.progress}%` }}
                        />
                      </div>
                      <div className="text-sm text-gray-400">
                        Analyzing {currentAnalysis.symbol} {currentAnalysis.timeframe} patterns...
                      </div>
                    </div>
                  )}

                  {currentAnalysis.status === 'completed' && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                      <div className="bg-gray-800/50 rounded p-3 text-center">
                        <div className="text-lg font-bold text-blue-400">
                          {currentAnalysis.waves.length}
                        </div>
                        <div className="text-sm text-gray-400">Patterns Detected</div>
                      </div>

                      <div className="bg-gray-800/50 rounded p-3 text-center">
                        <div className="text-lg font-bold text-green-400">
                          {formatConfidence(currentAnalysis.market_structure.completion_probability)}
                        </div>
                        <div className="text-sm text-gray-400">Completion Probability</div>
                      </div>

                      <div className="bg-gray-800/50 rounded p-3 text-center">
                        <div className="text-lg font-bold text-purple-400">
                          {currentAnalysis.trading_signals.length}
                        </div>
                        <div className="text-sm text-gray-400">Trading Signals</div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="patterns" className="h-full mt-0">
            <div className="space-y-6">
              {currentAnalysis?.waves.length ? (
                <div className="space-y-6">
                  {/* Market Structure Overview */}
                  <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-white mb-4">Market Structure</h3>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                      <div className="bg-gray-800/50 rounded p-4">
                        <div className="text-sm text-gray-400 mb-1">Trend Direction</div>
                        <div className={`text-xl font-bold ${
                          currentAnalysis.market_structure.trend === 'bullish' ? 'text-green-400' :
                          currentAnalysis.market_structure.trend === 'bearish' ? 'text-red-400' : 'text-gray-400'
                        }`}>
                          {currentAnalysis.market_structure.trend.toUpperCase()}
                        </div>
                      </div>

                      <div className="bg-gray-800/50 rounded p-4">
                        <div className="text-sm text-gray-400 mb-1">Cycle Position</div>
                        <div className="text-xl font-bold text-blue-400">
                          {currentAnalysis.market_structure.cycle_position.toUpperCase()}
                        </div>
                      </div>

                      <div className="bg-gray-800/50 rounded p-4">
                        <div className="text-sm text-gray-400 mb-1">Completion Probability</div>
                        <div className="text-xl font-bold text-purple-400">
                          {formatConfidence(currentAnalysis.market_structure.completion_probability)}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Wave Patterns */}
                  <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-white mb-4">Detected Wave Patterns</h3>

                    <div className="space-y-4">
                      {currentAnalysis.waves.map((wave, index) => (
                        <div key={wave.id} className="bg-gray-800/50 rounded-lg p-4">
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-3">
                              <div className={`w-4 h-4 rounded-full`} style={{ backgroundColor: getWaveColor(index) }} />
                              <span className="font-medium text-white">
                                {wave.wave_type.charAt(0).toUpperCase() + wave.wave_type.slice(1)} Wave
                              </span>
                              <span className="text-sm text-gray-400">({wave.degree})</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm text-gray-400">Confidence:</span>
                              <span className="text-sm font-medium text-white">
                                {formatConfidence(wave.confidence)}
                              </span>
                            </div>
                          </div>

                          {wave.llm_validation && (
                            <div className={`mb-3 p-3 rounded-lg border ${
                              wave.llm_validation.validated
                                ? 'border-green-500/30 bg-green-500/10'
                                : 'border-yellow-500/30 bg-yellow-500/10'
                            }`}>
                              <div className="flex items-center gap-2 mb-2">
                                <CpuChipIcon className={`w-4 h-4 ${
                                  wave.llm_validation.validated ? 'text-green-400' : 'text-yellow-400'
                                }`} />
                                <span className="text-sm font-medium text-white">
                                  LLM Validation {wave.llm_validation.validated ? 'Confirmed' : 'Flagged'}
                                </span>
                                <span className="text-xs text-gray-400">
                                  ({formatConfidence(wave.llm_validation.confidence)})
                                </span>
                              </div>
                              <div className="text-sm text-gray-300">
                                {wave.llm_validation.reasoning}
                              </div>
                              {wave.llm_validation.corrections && (
                                <div className="text-sm text-yellow-400 mt-2">
                                  Suggested: {wave.llm_validation.corrections}
                                </div>
                              )}
                            </div>
                          )}

                          {wave.subwaves.length > 0 && (
                            <div>
                              <div className="text-sm font-medium text-gray-300 mb-2">Subwaves:</div>
                              <div className="grid grid-cols-1 lg:grid-cols-5 gap-2">
                                {wave.subwaves.map((subwave) => (
                                  <div key={subwave.wave_num} className="bg-gray-700/50 rounded p-2 text-center">
                                    <div className="text-xs text-gray-400 mb-1">Wave {subwave.wave_num}</div>
                                    <div className="text-sm font-medium text-white">
                                      {subwave.start_price.toFixed(5)} → {subwave.end_price.toFixed(5)}
                                    </div>
                                    <div className="text-xs text-gray-500">
                                      {formatConfidence(subwave.confidence)}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Chart Visualization */}
                  <div className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-white mb-4">Wave Pattern Chart</h3>
                    <div className="bg-gray-800/50 rounded-lg p-6 text-center">
                      <ChartBarIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                      <p className="text-gray-400">Interactive candlestick chart with Elliott Wave overlays</p>
                      <p className="text-sm text-gray-500 mt-2">
                        Candlestick data with wave annotations, Fibonacci levels, and pattern highlights
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 text-center">
                  <CursorArrowRaysIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-white mb-2">No Patterns Detected</h3>
                  <p className="text-gray-400">Run a wave analysis to detect Elliott Wave patterns</p>
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="signals" className="h-full mt-0">
            <div className="space-y-6">
              {currentAnalysis?.trading_signals.length ? (
                <div className="space-y-4">
                  {currentAnalysis.trading_signals.map((signal, index) => (
                    <div key={index} className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className={`px-3 py-1 rounded-full text-sm font-medium ${
                            signal.signal_type === 'BUY' ? 'bg-green-500/20 text-green-400' :
                            signal.signal_type === 'SELL' ? 'bg-red-500/20 text-red-400' :
                            'bg-gray-500/20 text-gray-400'
                          }`}>
                            {signal.signal_type}
                          </div>
                          <span className="text-white font-medium">{currentAnalysis.symbol}</span>
                        </div>
                        <div className="text-sm text-gray-400">
                          Confidence: {formatConfidence(signal.confidence)}
                        </div>
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-4">
                        <div className="bg-gray-800/50 rounded p-3">
                          <div className="text-sm text-gray-400 mb-1">Entry Price</div>
                          <div className="text-lg font-bold text-white">
                            {signal.entry_price.toFixed(5)}
                          </div>
                        </div>

                        <div className="bg-gray-800/50 rounded p-3">
                          <div className="text-sm text-gray-400 mb-1">Stop Loss</div>
                          <div className="text-lg font-bold text-red-400">
                            {signal.stop_loss.toFixed(5)}
                          </div>
                        </div>

                        <div className="bg-gray-800/50 rounded p-3">
                          <div className="text-sm text-gray-400 mb-1">Take Profit 1</div>
                          <div className="text-lg font-bold text-green-400">
                            {signal.take_profit[0]?.toFixed(5) || 'N/A'}
                          </div>
                        </div>

                        <div className="bg-gray-800/50 rounded p-3">
                          <div className="text-sm text-gray-400 mb-1">Take Profit 2</div>
                          <div className="text-lg font-bold text-green-400">
                            {signal.take_profit[1]?.toFixed(5) || 'N/A'}
                          </div>
                        </div>
                      </div>

                      <div className="bg-gray-800/50 rounded-lg p-4">
                        <div className="text-sm font-medium text-gray-300 mb-2">Analysis Reasoning:</div>
                        <div className="text-sm text-gray-400">
                          {signal.reasoning}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 text-center">
                  <BeakerIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-white mb-2">No Trading Signals</h3>
                  <p className="text-gray-400">Complete a wave analysis to generate trading signals</p>
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="history" className="h-full mt-0">
            <div className="space-y-6">
              {analysisHistory.length > 0 ? (
                <div className="space-y-4">
                  {analysisHistory.map((analysis) => (
                    <div key={analysis.analysis_id} className="bg-gray-900 border border-gray-700 rounded-lg p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div>
                          <div className="flex items-center gap-3 mb-2">
                            <span className="font-medium text-white">
                              {analysis.symbol} {analysis.timeframe}
                            </span>
                            <div className="flex items-center gap-2">
                              {getStatusIcon(analysis.status)}
                              <span className="text-sm text-gray-400 capitalize">{analysis.status}</span>
                            </div>
                          </div>
                          <div className="text-sm text-gray-400">
                            {new Date(analysis.created_at).toLocaleDateString()} -
                            {new Date(analysis.updated_at).toLocaleDateString()}
                          </div>
                        </div>

                        <div className="flex items-center gap-4">
                          <div className="text-center">
                            <div className="text-lg font-bold text-blue-400">{analysis.waves.length}</div>
                            <div className="text-xs text-gray-500">Patterns</div>
                          </div>
                          <div className="text-center">
                            <div className="text-lg font-bold text-green-400">{analysis.trading_signals.length}</div>
                            <div className="text-xs text-gray-500">Signals</div>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCurrentAnalysis(analysis)}
                          >
                            View Details
                          </Button>
                        </div>
                      </div>

                      {analysis.status === 'completed' && (
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                          <div className="bg-gray-800/50 rounded p-3 text-center">
                            <div className="text-sm font-medium text-gray-300">Market Trend</div>
                            <div className={`text-lg font-bold ${
                              analysis.market_structure.trend === 'bullish' ? 'text-green-400' :
                              analysis.market_structure.trend === 'bearish' ? 'text-red-400' : 'text-gray-400'
                            }`}>
                              {analysis.market_structure.trend.toUpperCase()}
                            </div>
                          </div>

                          <div className="bg-gray-800/50 rounded p-3 text-center">
                            <div className="text-sm font-medium text-gray-300">Cycle Position</div>
                            <div className="text-lg font-bold text-blue-400">
                              {analysis.market_structure.cycle_position.toUpperCase()}
                            </div>
                          </div>

                          <div className="bg-gray-800/50 rounded p-3 text-center">
                            <div className="text-sm font-medium text-gray-300">Completion Prob.</div>
                            <div className="text-lg font-bold text-purple-400">
                              {formatConfidence(analysis.market_structure.completion_probability)}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 text-center">
                  <ClockIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-white mb-2">No Analysis History</h3>
                  <p className="text-gray-400">Your completed wave analyses will appear here</p>
                </div>
              )}
            </div>
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

// Helper function for generating mock wave data
function generateMockWaves(): WavePattern[] {
  return [
    {
      id: 'wave_impulse_1',
      wave_type: 'impulse',
      degree: 'primary',
      start_idx: 0,
      end_idx: 120,
      confidence: 0.85,
      fibonacci_levels: [
        { level: 0.382, price: 1.0823, type: 'retracement' },
        { level: 0.618, price: 1.0798, type: 'retracement' },
        { level: 1.618, price: 1.0920, type: 'extension' }
      ],
      subwaves: [
        { wave_num: 1, start_idx: 0, end_idx: 24, start_price: 1.0750, end_price: 1.0850, confidence: 0.82 },
        { wave_num: 2, start_idx: 24, end_idx: 48, start_price: 1.0850, end_price: 1.0810, confidence: 0.78 },
        { wave_num: 3, start_idx: 48, end_idx: 84, start_price: 1.0810, end_price: 1.0920, confidence: 0.91 },
        { wave_num: 4, start_idx: 84, end_idx: 108, start_price: 1.0920, end_price: 1.0880, confidence: 0.75 },
        { wave_num: 5, start_idx: 108, end_idx: 120, start_price: 1.0880, end_price: 1.0950, confidence: 0.83 }
      ],
      llm_validation: {
        validated: true,
        confidence: 0.87,
        reasoning: 'Strong impulse pattern with clear 5-wave structure. Wave 3 extension confirms bullish momentum. Fibonacci ratios align well with Elliott Wave principles.',
        corrections: undefined
      }
    },
    {
      id: 'wave_corrective_1',
      wave_type: 'corrective',
      degree: 'intermediate',
      start_idx: 120,
      end_idx: 180,
      confidence: 0.73,
      fibonacci_levels: [
        { level: 0.382, price: 1.0912, type: 'retracement' },
        { level: 0.5, price: 1.0885, type: 'retracement' },
        { level: 0.618, price: 1.0858, type: 'retracement' }
      ],
      subwaves: [
        { wave_num: 1, start_idx: 120, end_idx: 140, start_price: 1.0950, end_price: 1.0880, confidence: 0.71 },
        { wave_num: 2, start_idx: 140, end_idx: 160, start_price: 1.0880, end_price: 1.0920, confidence: 0.68 },
        { wave_num: 3, start_idx: 160, end_idx: 180, start_price: 1.0920, end_price: 1.0845, confidence: 0.79 }
      ],
      llm_validation: {
        validated: false,
        confidence: 0.65,
        reasoning: 'Pattern shows ABC correction but wave B retracement is deeper than typical. May be developing into a more complex correction.',
        corrections: 'Consider alternative count as WXY or triangle pattern'
      }
    }
  ];
}
