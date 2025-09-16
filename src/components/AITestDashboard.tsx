/**
 * AI Test Analysis Dashboard
 *
 * Provides visual insights, predictive intelligence, and actionable
 * recommendations for test optimization with strict audit trails
 * and human-in-the-loop validation for financial systems.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  Button,
  Alert,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Warning,
  CheckCircle,
  Speed,
  Security,
  Analytics,
  Visibility,
  ThumbUp,
  ThumbDown,
  History,
  SmartToy
} from '@mui/icons-material';

import { aiTestAnalyzer, TestAnalysisInsight, TestExecution, AuditTrailEntry } from '../ai-testing/AITestAnalyzer';
import { aiTestDataGenerator, AIGeneratedScenario } from '../ai-testing/AITestDataGenerator';

interface DashboardState {
  insights: TestAnalysisInsight[];
  statistics: any;
  scenarios: AIGeneratedScenario[];
  auditLog: AuditTrailEntry[];
  loading: boolean;
  error: string | null;
  aiEnabled: boolean;
  lastRefresh: number;
}

interface InsightCardProps {
  insight: TestAnalysisInsight;
  onApprove: (approved: boolean, notes?: string) => void;
}

const InsightCard: React.FC<InsightCardProps> = ({ insight, onApprove }) => {
  const [approvalDialog, setApprovalDialog] = useState(false);
  const [notes, setNotes] = useState('');

  const getSeverityColor = (severity: string): 'error' | 'warning' | 'info' | 'success' => {
    switch (severity) {
      case 'critical': return 'error';
      case 'high': return 'error';
      case 'medium': return 'warning';
      case 'low': return 'info';
      default: return 'info';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'performance': return <Speed />;
      case 'reliability': return <Security />;
      case 'coverage': return <Analytics />;
      case 'optimization': return <TrendingUp />;
      default: return <SmartToy />;
    }
  };

  const handleApproval = (approved: boolean) => {
    onApprove(approved, notes);
    setApprovalDialog(false);
    setNotes('');
  };

  return (
    <>
      <Card
        elevation={2}
        sx={{
          mb: 2,
          border: insight.severity === 'critical' ? '2px solid #f44336' :
                 insight.severity === 'high' ? '2px solid #ff9800' : 'none',
          opacity: insight.humanReviewed ? 0.7 : 1
        }}
      >
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="flex-start">
            <Box display="flex" alignItems="center" gap={1} mb={1}>
              {getTypeIcon(insight.type)}
              <Typography variant="h6" component="div">
                {insight.title}
              </Typography>
              <Chip
                label={insight.severity.toUpperCase()}
                color={getSeverityColor(insight.severity)}
                size="small"
              />
            </Box>
            <Box display="flex" gap={1}>
              <Chip
                label={`${insight.confidence}% confidence`}
                size="small"
                variant="outlined"
              />
              {!insight.humanReviewed && (
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => setApprovalDialog(true)}
                  startIcon={<Visibility />}
                >
                  Review
                </Button>
              )}
            </Box>
          </Box>

          <Typography variant="body2" color="text.secondary" mb={2}>
            {insight.description}
          </Typography>

          <Alert severity="info" sx={{ mb: 2 }}>
            <strong>Recommendation:</strong> {insight.recommendation}
          </Alert>

          <Box display="flex" gap={1} mb={2}>
            <Chip label={insight.type} size="small" />
            <Chip label={`${insight.affectedTests.length} tests`} size="small" />
            <Chip label={insight.impact} size="small" variant="outlined" />
          </Box>

          {insight.humanReviewed && (
            <Box display="flex" alignItems="center" gap={1}>
              {insight.humanApproved ? (
                <CheckCircle color="success" />
              ) : (
                <Warning color="warning" />
              )}
              <Typography variant="caption" color="text.secondary">
                {insight.humanApproved ? 'Approved' : 'Rejected'} by human reviewer
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>

      <Dialog open={approvalDialog} onClose={() => setApprovalDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>Review AI Insight</DialogTitle>
        <DialogContent>
          <Typography variant="h6" mb={2}>{insight.title}</Typography>
          <Typography variant="body2" mb={2}>{insight.description}</Typography>

          <Alert severity="info" sx={{ mb: 2 }}>
            <strong>AI Recommendation:</strong> {insight.recommendation}
          </Alert>

          <Typography variant="subtitle2" mb={1}>Affected Tests:</Typography>
          <Box mb={2}>
            {insight.affectedTests.map((test, index) => (
              <Chip key={index} label={test} size="small" sx={{ mr: 1, mb: 1 }} />
            ))}
          </Box>

          <Typography variant="subtitle2" mb={1}>
            AI Confidence: {insight.confidence}% | Impact: {insight.impact}
          </Typography>

          <Box mt={2}>
            <Typography variant="subtitle2" mb={1}>Review Notes:</Typography>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add your review notes here..."
              style={{ width: '100%', minHeight: '100px', padding: '8px' }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setApprovalDialog(false)}>Cancel</Button>
          <Button
            onClick={() => handleApproval(false)}
            color="error"
            startIcon={<ThumbDown />}
          >
            Reject
          </Button>
          <Button
            onClick={() => handleApproval(true)}
            color="success"
            startIcon={<ThumbUp />}
          >
            Approve
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

const AITestDashboard: React.FC = () => {
  const [state, setState] = useState<DashboardState>({
    insights: [],
    statistics: {},
    scenarios: [],
    auditLog: [],
    loading: true,
    error: null,
    aiEnabled: true,
    lastRefresh: Date.now()
  });

  const [selectedTab, setSelectedTab] = useState<'insights' | 'scenarios' | 'audit'>('insights');

  const refreshData = useCallback(async () => {
    try {
      setState(prev => ({ ...prev, loading: true, error: null }));

      // Get AI insights and statistics
      const insights = aiTestAnalyzer.getInsights({ minConfidence: 60 });
      const statistics = aiTestAnalyzer.getTestStatistics();
      const auditLog = aiTestAnalyzer.getAuditLog(50);

      // Generate some AI scenarios for demonstration
      const scenarios = [
        aiTestDataGenerator.generateTradingScenario({ complexity: 5, riskLevel: 'medium' }),
        aiTestDataGenerator.generateTradingScenario({ complexity: 7, riskLevel: 'high' }),
        aiTestDataGenerator.generateTradingScenario({ complexity: 3, riskLevel: 'low' })
      ];

      setState(prev => ({
        ...prev,
        insights,
        statistics,
        scenarios,
        auditLog,
        loading: false,
        lastRefresh: Date.now()
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'An error occurred'
      }));
    }
  }, []);

  useEffect(() => {
    refreshData();

    // Auto-refresh every 30 seconds
    const interval = setInterval(refreshData, 30000);
    return () => clearInterval(interval);
  }, [refreshData]);

  const handleInsightApproval = (insightIndex: number, approved: boolean, notes?: string) => {
    try {
      aiTestAnalyzer.approveInsight(insightIndex, approved, 'dashboard_user', notes);
      refreshData(); // Refresh to show updated state
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to process approval'
      }));
    }
  };

  const handleAIToggle = (enabled: boolean) => {
    setState(prev => ({ ...prev, aiEnabled: enabled }));
    // In a real implementation, this would configure the AI analyzer
  };

  const getInsightSummary = () => {
    const { insights } = state;
    return {
      total: insights.length,
      critical: insights.filter(i => i.severity === 'critical').length,
      high: insights.filter(i => i.severity === 'high').length,
      approved: insights.filter(i => i.humanApproved).length,
      pending: insights.filter(i => !i.humanReviewed).length
    };
  };

  const renderStatisticsCards = () => {
    const { statistics } = state;
    const summary = getInsightSummary();

    return (
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1}>
                <Analytics color="primary" />
                <Typography variant="h6">Test Executions</Typography>
              </Box>
              <Typography variant="h4">{statistics.totalExecutions || 0}</Typography>
              <Typography variant="body2" color="text.secondary">
                {((statistics.passRate || 0) * 100).toFixed(1)}% pass rate
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1}>
                <Speed color="info" />
                <Typography variant="h6">Avg Duration</Typography>
              </Box>
              <Typography variant="h4">{(statistics.averageDuration || 0).toFixed(0)}ms</Typography>
              <Typography variant="body2" color="text.secondary">
                Per test execution
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1}>
                <SmartToy color="secondary" />
                <Typography variant="h6">AI Insights</Typography>
              </Box>
              <Typography variant="h4">{summary.total}</Typography>
              <Typography variant="body2" color="text.secondary">
                {summary.pending} pending review
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1}>
                <Security color="warning" />
                <Typography variant="h6">Issues Found</Typography>
              </Box>
              <Typography variant="h4" color={summary.critical + summary.high > 0 ? 'error' : 'success'}>
                {summary.critical + summary.high}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Critical & high severity
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    );
  };

  if (state.loading) {
    return (
      <Box p={3}>
        <Typography variant="h4" mb={2}>AI Test Analysis Dashboard</Typography>
        <LinearProgress />
        <Typography mt={2}>Loading AI insights...</Typography>
      </Box>
    );
  }

  if (state.error) {
    return (
      <Box p={3}>
        <Alert severity="error" action={
          <Button color="inherit" size="small" onClick={refreshData}>
            Retry
          </Button>
        }>
          {state.error}
        </Alert>
      </Box>
    );
  }

  return (
    <Box p={3}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">🤖 AI Test Analysis Dashboard</Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <FormControlLabel
            control={
              <Switch
                checked={state.aiEnabled}
                onChange={(e) => handleAIToggle(e.target.checked)}
              />
            }
            label="AI Analysis Enabled"
          />
          <Button variant="outlined" onClick={refreshData} startIcon={<History />}>
            Refresh
          </Button>
        </Box>
      </Box>

      {/* Statistics Overview */}
      {renderStatisticsCards()}

      {/* Navigation Tabs */}
      <Box mb={3}>
        <Button
          variant={selectedTab === 'insights' ? 'contained' : 'outlined'}
          onClick={() => setSelectedTab('insights')}
          sx={{ mr: 1 }}
        >
          AI Insights ({state.insights.length})
        </Button>
        <Button
          variant={selectedTab === 'scenarios' ? 'contained' : 'outlined'}
          onClick={() => setSelectedTab('scenarios')}
          sx={{ mr: 1 }}
        >
          Test Scenarios ({state.scenarios.length})
        </Button>
        <Button
          variant={selectedTab === 'audit' ? 'contained' : 'outlined'}
          onClick={() => setSelectedTab('audit')}
        >
          Audit Trail ({state.auditLog.length})
        </Button>
      </Box>

      {/* Content Sections */}
      {selectedTab === 'insights' && (
        <Box>
          {state.insights.length === 0 ? (
            <Alert severity="info">
              No AI insights available. Run some tests to generate analysis data.
            </Alert>
          ) : (
            <Box>
              <Typography variant="h5" mb={2}>
                AI-Generated Insights & Recommendations
              </Typography>
              {state.insights.map((insight, index) => (
                <InsightCard
                  key={index}
                  insight={insight}
                  onApprove={(approved, notes) => handleInsightApproval(index, approved, notes)}
                />
              ))}
            </Box>
          )}
        </Box>
      )}

      {selectedTab === 'scenarios' && (
        <Box>
          <Typography variant="h5" mb={2}>AI-Generated Test Scenarios</Typography>
          <Grid container spacing={2}>
            {state.scenarios.map((scenario, index) => (
              <Grid item xs={12} md={6} key={index}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" mb={1}>{scenario.name}</Typography>
                    <Typography variant="body2" mb={2}>{scenario.description}</Typography>

                    <Box display="flex" gap={1} mb={2}>
                      <Chip label={scenario.riskLevel} size="small" color={
                        scenario.riskLevel === 'extreme' ? 'error' :
                        scenario.riskLevel === 'high' ? 'warning' : 'default'
                      } />
                      <Chip label={`Complexity ${scenario.complexity}/10`} size="small" />
                      <Chip label={scenario.expectedOutcome} size="small" variant="outlined" />
                    </Box>

                    <Typography variant="body2" color="text.secondary">
                      Market Condition: {scenario.marketCondition.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Duration: {scenario.duration} minutes | Timeframe: {scenario.timeframe}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      AI Confidence: {scenario.aiConfidence}%
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {selectedTab === 'audit' && (
        <Box>
          <Typography variant="h5" mb={2}>Audit Trail</Typography>
          <Card>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Timestamp</TableCell>
                  <TableCell>Action</TableCell>
                  <TableCell>Details</TableCell>
                  <TableCell>User</TableCell>
                  <TableCell>AI Confidence</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {state.auditLog.map((entry, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      {new Date(entry.timestamp).toLocaleString()}
                    </TableCell>
                    <TableCell>{entry.action}</TableCell>
                    <TableCell>
                      {typeof entry.details === 'object' ?
                        JSON.stringify(entry.details, null, 2).substring(0, 100) + '...' :
                        entry.details
                      }
                    </TableCell>
                    <TableCell>{entry.user || 'System'}</TableCell>
                    <TableCell>
                      {entry.aiConfidence ? `${entry.aiConfidence}%` : 'N/A'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </Box>
      )}

      {/* Footer */}
      <Box mt={4} pt={2} borderTop="1px solid #eee">
        <Typography variant="caption" color="text.secondary">
          Last refreshed: {new Date(state.lastRefresh).toLocaleString()} |
          AI Analysis Framework v1.0 |
          Financial Trading System Compliance Enabled
        </Typography>
      </Box>
    </Box>
  );
};

export default AITestDashboard;
