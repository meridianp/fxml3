const React = require('react');

// Mock Recharts components
const ResponsiveContainer = ({ children }) => React.createElement('div', {}, children);
const LineChart = ({ children }) => React.createElement('div', { 'data-testid': 'line-chart' }, children);
const Line = () => React.createElement('div', {});
const AreaChart = ({ children }) => React.createElement('div', {}, children);
const Area = () => React.createElement('div', {});
const BarChart = ({ children }) => React.createElement('div', {}, children);
const Bar = () => React.createElement('div', {});
const XAxis = () => React.createElement('div', {});
const YAxis = () => React.createElement('div', {});
const CartesianGrid = () => React.createElement('div', {});
const Tooltip = () => React.createElement('div', {});
const Legend = () => React.createElement('div', {});
const CandlestickChart = ({ children }) => React.createElement('div', {}, children);

module.exports = {
  ResponsiveContainer,
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
  CandlestickChart
};
