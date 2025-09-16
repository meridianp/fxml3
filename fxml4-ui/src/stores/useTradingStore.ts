import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export type OrderSide = 'buy' | 'sell';
export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit';
export type OrderStatus = 'pending' | 'filled' | 'partially_filled' | 'cancelled' | 'rejected';
export type PositionSide = 'long' | 'short';

export interface Order {
  id: string;
  symbol: string;
  side: OrderSide;
  type: OrderType;
  quantity: number;
  price?: number;
  stopPrice?: number;
  status: OrderStatus;
  filledQuantity: number;
  averageFillPrice?: number;
  timestamp: Date;
  updatedAt: Date;
  stopLoss?: number;
  takeProfit?: number;
  timeInForce?: 'GTC' | 'IOC' | 'FOK' | 'DAY';
  // Optimistic locking for race condition prevention
  sequence_number: number;
  source: 'api' | 'websocket' | 'manual';
}

export interface Position {
  id: string;
  symbol: string;
  side: PositionSide;
  quantity: number;
  averagePrice: number;
  currentPrice: number;
  unrealizedPnL: number;
  realizedPnL: number;
  timestamp: Date;
  updatedAt: Date;
  stopLoss?: number;
  takeProfit?: number;
}

export interface AccountInfo {
  balance: number;
  equity: number;
  marginUsed: number;
  availableMargin: number;
  marginLevel: number;
  totalRealizedPnL: number;
  totalUnrealizedPnL: number;
  currency: string;
}

export interface TradingState {
  // Account
  accountInfo: AccountInfo | null;

  // Orders
  orders: Order[];
  orderHistory: Order[];

  // Positions
  positions: Position[];
  closedPositions: Position[];

  // Order form state
  selectedSymbol: string;
  orderType: OrderType;
  orderSide: OrderSide;
  quantity: number;
  price: number | null;
  stopPrice: number | null;
  stopLoss: number | null;
  takeProfit: number | null;
  timeInForce: 'GTC' | 'IOC' | 'FOK' | 'DAY';

  // UI state
  showAdvancedOptions: boolean;
  selectedOrderId: string | null;
  selectedPositionId: string | null;

  // Loading states
  placingOrder: boolean;
  closingPosition: boolean;
  cancellingOrder: boolean;
}

interface TradingActions {
  // Account actions
  updateAccountInfo: (accountInfo: AccountInfo) => void;

  // Order actions
  addOrder: (order: Order) => void;
  updateOrder: (orderId: string, updates: Partial<Order>) => void;
  removeOrder: (orderId: string) => void;
  moveOrderToHistory: (orderId: string) => void;

  // Position actions
  addPosition: (position: Position) => void;
  updatePosition: (positionId: string, updates: Partial<Position>) => void;
  removePosition: (positionId: string) => void;
  movePositionToClosed: (positionId: string) => void;

  // Order form actions
  setSelectedSymbol: (symbol: string) => void;
  setOrderType: (type: OrderType) => void;
  setOrderSide: (side: OrderSide) => void;
  setQuantity: (quantity: number) => void;
  setPrice: (price: number | null) => void;
  setStopPrice: (stopPrice: number | null) => void;
  setStopLoss: (stopLoss: number | null) => void;
  setTakeProfit: (takeProfit: number | null) => void;
  setTimeInForce: (timeInForce: TradingState['timeInForce']) => void;
  resetOrderForm: () => void;

  // UI actions
  toggleAdvancedOptions: () => void;
  setSelectedOrderId: (orderId: string | null) => void;
  setSelectedPositionId: (positionId: string | null) => void;

  // Loading actions
  setPlacingOrder: (placing: boolean) => void;
  setClosingPosition: (closing: boolean) => void;
  setCancellingOrder: (cancelling: boolean) => void;

  // Utilities
  getOrder: (orderId: string) => Order | undefined;
  getPosition: (positionId: string) => Position | undefined;
  getPositionBySymbol: (symbol: string) => Position | undefined;
  getTotalPnL: () => number;
  getMarginUsage: () => number;
  canPlaceOrder: (quantity: number, price?: number) => boolean;

  // Reset
  reset: () => void;
}

const initialOrderFormState = {
  selectedSymbol: 'EURUSD',
  orderType: 'market' as OrderType,
  orderSide: 'buy' as OrderSide,
  quantity: 10000,
  price: null,
  stopPrice: null,
  stopLoss: null,
  takeProfit: null,
  timeInForce: 'GTC' as const,
};

const initialState: TradingState = {
  accountInfo: null,
  orders: [],
  orderHistory: [],
  positions: [],
  closedPositions: [],
  ...initialOrderFormState,
  showAdvancedOptions: false,
  selectedOrderId: null,
  selectedPositionId: null,
  placingOrder: false,
  closingPosition: false,
  cancellingOrder: false,
};

export const useTradingStore = create<TradingState & TradingActions>()(
  devtools(
    (set, get) => ({
      ...initialState,

      // Account actions
      updateAccountInfo: (accountInfo) => {
        set({ accountInfo }, false, 'updateAccountInfo');
      },

      // Order actions
      addOrder: (order) => {
        set(
          (state) => {
            // Check if order already exists (race condition protection)
            const existing = state.orders.find(o => o.id === order.id);
            if (existing) {
              console.warn('Attempted to add existing order, using updateOrder instead:', order.id);
              // Use updateOrder logic for consistency
              return {
                orders: state.orders.map(o =>
                  o.id === order.id && order.sequence_number > o.sequence_number
                    ? { ...order, updatedAt: new Date() }
                    : o
                )
              };
            }

            // Add new order
            return {
              orders: [...state.orders, { ...order, updatedAt: new Date() }]
            };
          },
          false,
          'addOrder'
        );
      },

      updateOrder: (orderId, updates) => {
        set(
          (state) => ({
            orders: state.orders.map((order) => {
              if (order.id !== orderId) return order;

              // Sequence number conflict resolution
              if (updates.sequence_number && updates.sequence_number <= order.sequence_number) {
                console.warn(
                  `Ignored order update with stale sequence number. Current: ${order.sequence_number}, Update: ${updates.sequence_number}`,
                  { orderId, currentSource: order.source, updateSource: updates.source }
                );
                return order;
              }

              // Apply update
              return { ...order, ...updates, updatedAt: new Date() };
            }),
          }),
          false,
          'updateOrder'
        );
      },

      removeOrder: (orderId) => {
        set(
          (state) => ({
            orders: state.orders.filter((order) => order.id !== orderId),
          }),
          false,
          'removeOrder'
        );
      },

      moveOrderToHistory: (orderId) => {
        set(
          (state) => {
            const order = state.orders.find((o) => o.id === orderId);
            if (!order) return state;

            return {
              orders: state.orders.filter((o) => o.id !== orderId),
              orderHistory: [...state.orderHistory, order],
            };
          },
          false,
          'moveOrderToHistory'
        );
      },

      // Position actions
      addPosition: (position) => {
        set(
          (state) => ({ positions: [...state.positions, position] }),
          false,
          'addPosition'
        );
      },

      updatePosition: (positionId, updates) => {
        set(
          (state) => ({
            positions: state.positions.map((position) =>
              position.id === positionId
                ? { ...position, ...updates, updatedAt: new Date() }
                : position
            ),
          }),
          false,
          'updatePosition'
        );
      },

      removePosition: (positionId) => {
        set(
          (state) => ({
            positions: state.positions.filter((position) => position.id !== positionId),
          }),
          false,
          'removePosition'
        );
      },

      movePositionToClosed: (positionId) => {
        set(
          (state) => {
            const position = state.positions.find((p) => p.id === positionId);
            if (!position) return state;

            return {
              positions: state.positions.filter((p) => p.id !== positionId),
              closedPositions: [...state.closedPositions, position],
            };
          },
          false,
          'movePositionToClosed'
        );
      },

      // Order form actions
      setSelectedSymbol: (symbol) => {
        set({ selectedSymbol: symbol }, false, 'setSelectedSymbol');
      },

      setOrderType: (type) => {
        set(
          (state) => ({
            orderType: type,
            // Clear price fields if switching to market order
            price: type === 'market' ? null : state.price,
            stopPrice: type !== 'stop' && type !== 'stop_limit' ? null : state.stopPrice,
          }),
          false,
          'setOrderType'
        );
      },

      setOrderSide: (side) => {
        set({ orderSide: side }, false, 'setOrderSide');
      },

      setQuantity: (quantity) => {
        set({ quantity: Math.max(0, quantity) }, false, 'setQuantity');
      },

      setPrice: (price) => {
        set({ price: price && price > 0 ? price : null }, false, 'setPrice');
      },

      setStopPrice: (stopPrice) => {
        set(
          { stopPrice: stopPrice && stopPrice > 0 ? stopPrice : null },
          false,
          'setStopPrice'
        );
      },

      setStopLoss: (stopLoss) => {
        set(
          { stopLoss: stopLoss && stopLoss > 0 ? stopLoss : null },
          false,
          'setStopLoss'
        );
      },

      setTakeProfit: (takeProfit) => {
        set(
          { takeProfit: takeProfit && takeProfit > 0 ? takeProfit : null },
          false,
          'setTakeProfit'
        );
      },

      setTimeInForce: (timeInForce) => {
        set({ timeInForce }, false, 'setTimeInForce');
      },

      resetOrderForm: () => {
        set(
          {
            ...initialOrderFormState,
            showAdvancedOptions: false,
          },
          false,
          'resetOrderForm'
        );
      },

      // UI actions
      toggleAdvancedOptions: () => {
        set(
          (state) => ({ showAdvancedOptions: !state.showAdvancedOptions }),
          false,
          'toggleAdvancedOptions'
        );
      },

      setSelectedOrderId: (orderId) => {
        set({ selectedOrderId: orderId }, false, 'setSelectedOrderId');
      },

      setSelectedPositionId: (positionId) => {
        set({ selectedPositionId: positionId }, false, 'setSelectedPositionId');
      },

      // Loading actions
      setPlacingOrder: (placing) => {
        set({ placingOrder: placing }, false, 'setPlacingOrder');
      },

      setClosingPosition: (closing) => {
        set({ closingPosition: closing }, false, 'setClosingPosition');
      },

      setCancellingOrder: (cancelling) => {
        set({ cancellingOrder: cancelling }, false, 'setCancellingOrder');
      },

      // Utilities
      getOrder: (orderId) => {
        return get().orders.find((order) => order.id === orderId);
      },

      getPosition: (positionId) => {
        return get().positions.find((position) => position.id === positionId);
      },

      getPositionBySymbol: (symbol) => {
        return get().positions.find((position) => position.symbol === symbol);
      },

      getTotalPnL: () => {
        const state = get();
        const unrealizedPnL = state.positions.reduce((sum, pos) => sum + pos.unrealizedPnL, 0);
        const realizedPnL = state.accountInfo?.totalRealizedPnL || 0;
        return unrealizedPnL + realizedPnL;
      },

      getMarginUsage: () => {
        const accountInfo = get().accountInfo;
        if (!accountInfo || accountInfo.equity === 0) return 0;
        return (accountInfo.marginUsed / accountInfo.equity) * 100;
      },

      canPlaceOrder: (quantity, price) => {
        const state = get();
        const accountInfo = state.accountInfo;

        if (!accountInfo || quantity <= 0) return false;

        // Simple margin check - in reality this would be more complex
        const estimatedMargin = quantity * (price || 1) * 0.01; // 1% margin requirement

        return estimatedMargin <= accountInfo.availableMargin;
      },

      // Reset
      reset: () => {
        set(initialState, false, 'reset');
      },
    }),
    {
      name: 'trading-store',
    }
  )
);
