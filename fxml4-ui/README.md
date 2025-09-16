# FXML4 Trading Platform - Frontend

Professional forex trading platform frontend built with Next.js, React 18, and TypeScript. Provides real-time trading interface with ML-powered signals, comprehensive backtesting, and advanced data management capabilities.

## 🚀 Features

### Core Trading Interface
- **Real-time Market Data**: Live price feeds with WebSocket streaming
- **Order Management**: Professional order entry, modification, and tracking
- **Position Monitoring**: Real-time P&L, margin, and risk metrics
- **Signal Integration**: ML-generated trading signals with confidence indicators

### Data Management
- **Market Data Hub**: Real-time and historical data visualization
- **Data Quality Monitoring**: Feed health, latency, and completeness tracking
- **Multi-Broker Integration**: Unified data aggregation from multiple sources

### ML Training Studio
- **Visual Model Builder**: Drag-and-drop model configuration
- **Training Progress**: Real-time monitoring with live performance charts
- **Model Comparison**: Side-by-side performance analysis
- **One-Click Deployment**: Seamless model deployment to production

### Backtesting Laboratory
- **Strategy Builder**: Visual strategy configuration and testing
- **Performance Analytics**: Comprehensive risk-adjusted metrics
- **Walk-Forward Analysis**: Robust out-of-sample validation
- **Optimization Engine**: Parameter optimization with Monte Carlo simulation

## 🛠️ Technology Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript 5.3+
- **Styling**: Tailwind CSS 3.4 with custom trading theme
- **UI Components**: Headless UI + Custom components
- **Charts**: Lightweight Charts (TradingView) + Recharts
- **State Management**: Zustand
- **API Client**: Axios with retry logic
- **Real-time Data**: Socket.IO client
- **Data Fetching**: TanStack Query (React Query)
- **Forms**: React Hook Form + Zod validation
- **Icons**: Heroicons + Lucide React
- **Animations**: Framer Motion

## 📦 Installation

### Prerequisites
- Node.js 18+
- npm 9+ or yarn 3+
- FXML4 Backend API running

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd fxml4-ui

# Install dependencies
npm install
# or
yarn install

# Copy environment configuration
cp .env.example .env.local

# Configure environment variables
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

### Development
```bash
# Start development server
npm run dev
# or
yarn dev

# Open browser
open http://localhost:3000
```

### Build for Production
```bash
# Build for production
npm run build

# Start production server
npm run start

# Or export static files
npm run export
```

## 🏗️ Project Structure

```
fxml4-ui/
├── src/
│   ├── components/           # Reusable UI components
│   │   ├── layout/          # Layout components
│   │   ├── common/          # Shared components
│   │   ├── charts/          # Trading charts
│   │   ├── data/            # Data management UI
│   │   ├── trading/         # Trading interface
│   │   ├── training/        # ML training UI
│   │   └── backtesting/     # Backtesting UI
│   ├── pages/               # Next.js pages
│   │   ├── data/            # Data management pages
│   │   ├── trading/         # Trading pages
│   │   ├── training/        # ML training pages
│   │   └── backtesting/     # Backtesting pages
│   ├── hooks/               # Custom React hooks
│   ├── services/            # API and WebSocket services
│   ├── stores/              # State management
│   ├── types/               # TypeScript definitions
│   ├── utils/               # Utility functions
│   ├── config/              # Configuration constants
│   └── styles/              # Global styles
├── public/                  # Static assets
├── docs/                    # Documentation
└── tests/                   # Test files
```

## 🔧 Configuration

### Environment Variables
```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws

# Feature Flags
NEXT_PUBLIC_ENABLE_LIVE_TRADING=true
NEXT_PUBLIC_ENABLE_ML_TRAINING=true
NEXT_PUBLIC_ENABLE_BACKTESTING=true

# Analytics (optional)
NEXT_PUBLIC_GA_TRACKING_ID=
NEXT_PUBLIC_SENTRY_DSN=
```

### Trading Configuration
Core trading parameters are configured in `src/config/constants.ts`:
- Supported currency pairs
- Default timeframes
- Order types and limits
- Chart settings
- Refresh intervals

## 📊 Key Components

### Real-Time Charts
```typescript
import { TradingChart } from '@/components/charts/TradingChart';

<TradingChart
  symbol="EURUSD"
  timeframe="1h"
  indicators={['sma', 'rsi']}
  onOrderPlace={handleOrderPlace}
/>
```

### Market Data Grid
```typescript
import { MarketDataGrid } from '@/components/data/MarketDataGrid';

<MarketDataGrid
  symbols={['EURUSD', 'GBPUSD', 'USDJPY']}
  onSymbolSelect={handleSymbolSelect}
  realTime={true}
/>
```

### Trading Console
```typescript
import { TradingConsole } from '@/components/trading/TradingConsole';

<TradingConsole
  account={account}
  positions={positions}
  orders={orders}
  onOrderSubmit={handleOrderSubmit}
/>
```

## 🔌 API Integration

The frontend integrates with the FXML4 backend API through:

### REST API Client
```typescript
import { apiClient } from '@/services/api';

// Market data
const candles = await apiClient.getMarketData('EURUSD', '1h');

// Trading operations
const order = await apiClient.placeOrder({
  symbol: 'EURUSD',
  side: 'buy',
  quantity: 100000,
  type: 'market'
});
```

### WebSocket Streaming
```typescript
import { wsService } from '@/services/websocket';

// Real-time market data
wsService.on('market_data', (data) => {
  updatePriceDisplay(data);
});

// Order updates
wsService.on('order_update', (order) => {
  updateOrderStatus(order);
});
```

## 🧪 Testing

```bash
# Run unit tests
npm run test

# Run tests in watch mode
npm run test:watch

# Run integration tests
npm run test:integration

# Generate coverage report
npm run test:coverage
```

## 🚀 Deployment

### Docker Deployment
```bash
# Build Docker image
docker build -t fxml4-ui:latest .

# Run container
docker run -p 3000:3000 fxml4-ui:latest
```

### Production Optimization
- Static asset optimization with Next.js Image
- Bundle analysis and code splitting
- Service Worker for offline capabilities
- CDN integration for global performance

## 🔐 Security

### Frontend Security Features
- Content Security Policy (CSP) headers
- XSS protection with sanitized inputs
- Secure authentication with JWT tokens
- Rate limiting for API calls
- Input validation with Zod schemas

### Trading Security
- Order confirmation dialogs
- Position size limits
- Risk management alerts
- Session timeout handling
- Audit logging for all trading actions

## 📱 Responsive Design

The interface is optimized for:
- **Desktop**: Full featured trading workstation
- **Tablet**: Streamlined interface for monitoring
- **Mobile**: Essential trading functions and alerts

## 🎨 Theming

Supports both light and dark themes with:
- Automatic system preference detection
- Manual theme switching
- Trading-specific color schemes
- High contrast mode for accessibility

## 🔧 Development Tools

### Code Quality
```bash
# Linting
npm run lint
npm run lint:fix

# Type checking
npm run type-check

# Code formatting
npm run format
npm run format:check
```

### Storybook (Component Development)
```bash
# Start Storybook
npm run storybook

# Build Storybook
npm run build-storybook
```

## 📈 Performance

### Optimization Features
- Server-side rendering (SSR) for critical pages
- Static generation for documentation
- Image optimization with Next.js
- Bundle splitting and lazy loading
- Virtual scrolling for large datasets
- WebSocket connection pooling

### Performance Targets
- First Contentful Paint: < 1.5s
- Largest Contentful Paint: < 2.5s
- Time to Interactive: < 3.5s
- Chart rendering: < 100ms
- Real-time updates: < 50ms latency

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow TypeScript strict mode
- Write comprehensive tests
- Use semantic commit messages
- Update documentation for new features
- Follow the established component patterns

## 📄 License

This project is proprietary software. All rights reserved.

## 🆘 Support

- Documentation: [docs/](./docs/)
- API Reference: http://localhost:8000/docs
- Issues: Create GitHub issues for bugs and feature requests
