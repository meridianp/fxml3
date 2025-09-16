const mockMarketData = {
  'EUR/USD': {
    price: 1.0500,
    bid: 1.0499,
    ask: 1.0501,
    volume: 1000000,
    timestamp: new Date()
  },
  'GBP/USD': {
    price: 1.2500,
    bid: 1.2499,
    ask: 1.2501,
    volume: 800000,
    timestamp: new Date()
  },
  'USD/JPY': {
    price: 110.50,
    bid: 110.49,
    ask: 110.51,
    volume: 1200000,
    timestamp: new Date()
  }
};

const mockPositions = [
  {
    symbol: 'EUR/USD',
    quantity: 100000,
    entryPrice: 1.0450,
    currentPrice: 1.0500,
    unrealizedPnL: 500
  },
  {
    symbol: 'GBP/USD',
    quantity: -50000,
    entryPrice: 1.2550,
    currentPrice: 1.2500,
    unrealizedPnL: 250
  }
];

module.exports = {
  mockMarketData,
  mockPositions
};
