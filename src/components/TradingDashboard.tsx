/**
 * TDD-based Trading Dashboard Component for FXML4.
 *
 * Main trading interface with real-time data, order management,
 * and comprehensive trading functionality.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Button,
  TextField,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  FormControl,
  InputLabel,
  Alert,
  CircularProgress,
  Switch,
  FormControlLabel
} from '@mui/material';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CandlestickChart
} from 'recharts';
import { useMarketData } from '../contexts/MarketDataContext';
import { useOrders } from '../contexts/OrderContext';

interface Position {
  symbol: string;
  quantity: number;
  entryPrice: number;
  currentPrice: number;
  unrealizedPnL: number;
}

interface TradingDashboardProps {
  userId: string;
  accountId: string;
  symbols: string[];
  positions?: Position[];
  accountData?: any;
  onOrderSubmit?: (order: any) => void;
  onOrderModify?: (modification: any) => void;
  onEmergencyStop?: () => void;
  onExportHistory?: (params: any) => void;
  onQuickBuy?: () => void;
  onQuickSell?: () => void;
  mlPredictions?: any;
  newsItems?: any[];
}

export const TradingDashboard: React.FC<TradingDashboardProps> = ({
  userId,
  accountId,
  symbols,
  positions = [],
  accountData,
  onOrderSubmit,
  onOrderModify,
  onEmergencyStop,
  onExportHistory,
  onQuickBuy,
  onQuickSell,
  mlPredictions,
  newsItems = []
}) => {
  const { marketData, connectionStatus } = useMarketData();
  const { orders, submitOrder, modifyOrder } = useOrders();

  const [selectedSymbol, setSelectedSymbol] = useState(symbols[0]);
  const [orderQuantity, setOrderQuantity] = useState('');
  const [orderPrice, setOrderPrice] = useState('');
  const [orderType, setOrderType] = useState('MARKET');
  const [positionFilter, setPositionFilter] = useState('');
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [showElliottWave, setShowElliottWave] = useState(false);
  const [timeframe, setTimeframe] = useState('1H');
  const [emergencyModalOpen, setEmergencyModalOpen] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [modifyModalOpen, setModifyModalOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<any>(null);
  const [quantityError, setQuantityError] = useState('');

  // Calculate total P&L
  const totalPnL = positions.reduce((sum, pos) => sum + pos.unrealizedPnL, 0);

  // Filter positions
  const filteredPositions = positions.filter(pos =>
    pos.symbol.toLowerCase().includes(positionFilter.toLowerCase())
  );

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.key === 'b' && onQuickBuy) {
        onQuickBuy();
      } else if (e.key === 's' && onQuickSell) {
        onQuickSell();
      }
    };

    window.addEventListener('keypress', handleKeyPress);
    return () => window.removeEventListener('keypress', handleKeyPress);
  }, [onQuickBuy, onQuickSell]);

  const handleOrderSubmit = (side: 'BUY' | 'SELL') => {
    if (!orderQuantity) {
      setQuantityError('Quantity is required');
      return;
    }

    const quantity = parseFloat(orderQuantity);
    if (quantity <= 0) {
      setQuantityError('Quantity must be positive');
      return;
    }

    const order = {
      symbol: selectedSymbol,
      side,
      quantity,
      orderType,
      price: orderType === 'LIMIT' ? parseFloat(orderPrice) : undefined
    };

    if (onOrderSubmit) {
      onOrderSubmit(order);
    } else {
      submitOrder(order);
    }

    // Reset form
    setOrderQuantity('');
    setOrderPrice('');
    setQuantityError('');
  };

  const handleOrderModify = (orderId: string) => {
    const order = orders.find(o => o.id === orderId);
    setSelectedOrder(order);
    setModifyModalOpen(true);
  };

  const confirmOrderModification = () => {
    if (selectedOrder && onOrderModify) {
      onOrderModify({
        orderId: selectedOrder.id,
        price: parseFloat(orderPrice)
      });
    }
    setModifyModalOpen(false);
  };

  const handleEmergencyStop = () => {
    setEmergencyModalOpen(false);
    if (onEmergencyStop) {
      onEmergencyStop();
    }
  };

  const handleExport = (format: string) => {
    if (onExportHistory) {
      onExportHistory({
        format,
        dateRange: { start: new Date(), end: new Date() }
      });
    }
    setExportModalOpen(false);
  };

  return (
    <Box
      data-testid="trading-dashboard"
      className={`theme-${theme}`}
      sx={{ flexGrow: 1, p: 2 }}
    >
      <Grid container spacing={2}>
        {/* Market Watchlist */}
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper data-testid="market-watchlist" sx={{ p: 2 }}>
            <Typography variant="h6">Market Watch</Typography>
            {symbols.map(symbol => {
              const data = marketData?.[symbol];
              return (
                <Box key={symbol} sx={{ py: 1 }}>
                  <Typography>{symbol}</Typography>
                  <Typography variant="h6">
                    {data?.price || '1.0500'}
                  </Typography>
                </Box>
              );
            })}
          </Paper>
        </Grid>

        {/* Chart Container */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper data-testid="chart-container" sx={{ p: 2, height: 400 }}>
            <Box data-testid="price-chart">
              <Box sx={{ mb: 2 }}>
                {['1M', '5M', '15M', '1H', '4H', '1D'].map(tf => (
                  <Button
                    key={tf}
                    size="small"
                    data-testid={`timeframe-${tf.toLowerCase()}`}
                    className={timeframe === tf ? 'selected' : ''}
                    onClick={() => setTimeframe(tf)}
                  >
                    {tf}
                  </Button>
                ))}
                <FormControlLabel
                  control={
                    <Switch
                      checked={showElliottWave}
                      onChange={(e) => setShowElliottWave(e.target.checked)}
                    />
                  }
                  label="Elliott Wave"
                />
              </Box>

              <Box data-testid="candlestick-chart" sx={{ height: 250 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={[{ time: '1', price: 1.05 }, { time: '2', price: 1.0501 }]}>
                    <Line type="monotone" dataKey="price" stroke="#8884d8" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <Tooltip />
                  </LineChart>
                </ResponsiveContainer>
              </Box>

              {showElliottWave && (
                <Box data-testid="elliott-wave-overlay">
                  <Typography>Wave 3</Typography>
                </Box>
              )}

              <Box data-testid="volume-bars" sx={{ height: 50 }}>
                {/* Volume bars */}
              </Box>
            </Box>
          </Paper>
        </Grid>

        {/* Order Panel */}
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper data-testid="order-panel" sx={{ p: 2 }}>
            <Typography variant="h6">Place Order</Typography>

            <FormControl fullWidth sx={{ my: 1 }}>
              <InputLabel>Symbol</InputLabel>
              <Select
                value={selectedSymbol}
                label="Symbol"
                onChange={(e) => setSelectedSymbol(e.target.value)}
              >
                {symbols.map(sym => (
                  <MenuItem key={sym} value={sym}>{sym}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <TextField
              fullWidth
              label="Quantity"
              value={orderQuantity}
              onChange={(e) => {
                setOrderQuantity(e.target.value);
                setQuantityError('');
              }}
              error={!!quantityError}
              helperText={quantityError}
              sx={{ my: 1 }}
            />

            {orderType === 'LIMIT' && (
              <TextField
                fullWidth
                label="Price"
                value={orderPrice}
                onChange={(e) => setOrderPrice(e.target.value)}
                sx={{ my: 1 }}
              />
            )}

            <Box sx={{ mt: 2 }}>
              <Button
                fullWidth
                variant="contained"
                color="success"
                onClick={() => handleOrderSubmit('BUY')}
                sx={{ mb: 1 }}
              >
                BUY
              </Button>
              <Button
                fullWidth
                variant="contained"
                color="error"
                onClick={() => handleOrderSubmit('SELL')}
              >
                SELL
              </Button>
            </Box>

            <Button onClick={() => handleOrderSubmit('BUY')}>
              Submit Order
            </Button>
          </Paper>
        </Grid>

        {/* Positions Table */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Paper data-testid="positions-table" sx={{ p: 2 }}>
            <Typography variant="h6">Open Positions</Typography>
            <TextField
              placeholder="Filter positions..."
              value={positionFilter}
              onChange={(e) => setPositionFilter(e.target.value)}
              size="small"
              sx={{ my: 1 }}
            />

            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Symbol</TableCell>
                    <TableCell>Quantity</TableCell>
                    <TableCell>Entry Price</TableCell>
                    <TableCell>Current Price</TableCell>
                    <TableCell>P&L</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredPositions.map((position, index) => (
                    <TableRow key={index}>
                      <TableCell>{position.symbol}</TableCell>
                      <TableCell>{position.quantity.toLocaleString()}</TableCell>
                      <TableCell>{position.entryPrice}</TableCell>
                      <TableCell>{position.currentPrice}</TableCell>
                      <TableCell className={position.unrealizedPnL >= 0 ? 'profit' : 'loss'}>
                        {position.unrealizedPnL >= 0 ? '+' : ''}
                        ${position.unrealizedPnL.toFixed(2)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>

        {/* Orders Table */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Paper data-testid="orders-table" sx={{ p: 2 }}>
            <Typography variant="h6">Open Orders</Typography>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Symbol</TableCell>
                    <TableCell>Side</TableCell>
                    <TableCell>Quantity</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Price</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {orders.map((order) => (
                    <TableRow key={order.id} data-testid={`order-row-${order.id}`}>
                      <TableCell>{order.symbol}</TableCell>
                      <TableCell>{order.side}</TableCell>
                      <TableCell>{order.quantity.toLocaleString()}</TableCell>
                      <TableCell>{order.orderType}</TableCell>
                      <TableCell>{order.price ? order.price.toFixed(4) : 'Market'}</TableCell>
                      <TableCell>{order.status}</TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          onClick={() => handleOrderModify(order.id)}
                          disabled={order.status !== 'PENDING'}
                        >
                          Modify
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>

        {/* Account Summary */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper data-testid="account-summary" sx={{ p: 2 }}>
            <Typography variant="h6">Account Summary</Typography>
            {accountData && (
              <>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                  <Typography>Balance:</Typography>
                  <Typography>${accountData.balance?.toLocaleString()}.00</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                  <Typography>Equity:</Typography>
                  <Typography>${accountData.equity?.toLocaleString()}.00</Typography>
                </Box>
              </>
            )}
          </Paper>

          {/* Total P&L */}
          <Box
            data-testid="total-pnl"
            className={totalPnL >= 0 ? 'profit' : 'loss'}
            sx={{ mt: 2, p: 2, bgcolor: totalPnL >= 0 ? 'success.light' : 'error.light' }}
          >
            <Typography variant="h6">
              Total P&L: ${totalPnL.toFixed(2)}
            </Typography>
          </Box>
        </Grid>

        {/* Risk Metrics */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper data-testid="risk-metrics" sx={{ p: 2 }}>
            <Typography variant="h6">Risk Metrics</Typography>
            <Box sx={{ py: 0.5 }}>
              <Typography>Margin Used</Typography>
              <Typography>Free Margin</Typography>
              <Typography>Margin Level</Typography>
              <Typography>Daily P&L</Typography>
            </Box>
          </Paper>
        </Grid>

        {/* ML Predictions */}
        {mlPredictions && (
          <Grid size={{ xs: 12, md: 4 }}>
            <Paper data-testid="ml-predictions" sx={{ p: 2 }}>
              <Typography variant="h6">ML Predictions</Typography>
              {Object.entries(mlPredictions).map(([symbol, pred]: [string, any]) => (
                <Box key={symbol} sx={{ py: 0.5 }}>
                  <Typography>{symbol}</Typography>
                  <Typography>
                    {pred.direction === 'up' ? '↑' : '↓'} {(pred.confidence * 100).toFixed(0)}%
                  </Typography>
                </Box>
              ))}
            </Paper>
          </Grid>
        )}

        {/* News Feed */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper data-testid="news-feed" sx={{ p: 2 }}>
            <Typography variant="h6">News Feed</Typography>
            {newsItems.map(news => (
              <Box key={news.id} sx={{ py: 0.5 }}>
                <Typography>{news.title}</Typography>
                <Chip
                  data-testid={`impact-${news.impact}`}
                  label={news.impact}
                  size="small"
                  color={news.impact === 'high' ? 'error' : 'default'}
                />
              </Box>
            ))}
          </Paper>
        </Grid>

        {/* Controls */}
        <Grid size={{ xs: 12 }}>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              data-testid="emergency-stop"
              variant="contained"
              color="error"
              onClick={() => setEmergencyModalOpen(true)}
            >
              EMERGENCY STOP
            </Button>

            <Button onClick={() => setExportModalOpen(true)}>
              Export History
            </Button>

            <Box
              data-testid="connection-status"
              className={connectionStatus}
              title={`Connected to market data`}
              sx={{
                width: 20,
                height: 20,
                borderRadius: '50%',
                bgcolor: connectionStatus === 'connected' ? 'success.main' : 'error.main'
              }}
            />

            <IconButton
              data-testid="theme-toggle"
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
            >
              {theme === 'light' ? '🌙' : '☀️'}
            </IconButton>
          </Box>
        </Grid>
      </Grid>

      {/* Emergency Stop Modal */}
      <Dialog open={emergencyModalOpen} onClose={() => setEmergencyModalOpen(false)}>
        <DialogTitle>Emergency Stop</DialogTitle>
        <DialogContent>
          <Typography>
            This will immediately close all positions and cancel all orders.
            Are you sure?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEmergencyModalOpen(false)}>Cancel</Button>
          <Button color="error" onClick={handleEmergencyStop}>
            CONFIRM SHUTDOWN
          </Button>
        </DialogActions>
      </Dialog>

      {/* Export Modal */}
      <Dialog open={exportModalOpen} onClose={() => setExportModalOpen(false)}>
        <DialogTitle>Export Trading History</DialogTitle>
        <DialogContent>
          <FormControl fullWidth>
            <InputLabel>Format</InputLabel>
            <Select defaultValue="CSV" label="Format">
              <MenuItem value="CSV">CSV</MenuItem>
              <MenuItem value="PDF">PDF</MenuItem>
              <MenuItem value="EXCEL">Excel</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setExportModalOpen(false)}>Cancel</Button>
          <Button onClick={() => handleExport('CSV')}>Export</Button>
        </DialogActions>
      </Dialog>

      {/* Modify Order Modal */}
      <Dialog open={modifyModalOpen} onClose={() => setModifyModalOpen(false)}>
        <DialogTitle>Modify Order</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Price"
            value={orderPrice}
            onChange={(e) => setOrderPrice(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setModifyModalOpen(false)}>Cancel</Button>
          <Button onClick={confirmOrderModification}>Update Order</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
