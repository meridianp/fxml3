/**
 * Trading Store
 *
 * Manages trading state including orders, positions, and account data
 */

import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type { Order, Position, Account, TradingSignal } from '@/types';

interface TradingState {
  // Account data
  account: Account | null;

  // Trading data
  orders: Order[];
  positions: Position[];
  signals: TradingSignal[];

  // UI state
  isLoadingOrders: boolean;
  isLoadingPositions: boolean;
  isLoadingAccount: boolean;
  selectedOrder: Order | null;
  selectedPosition: Position | null;

  // Real-time updates
  lastOrderUpdate: number;
  lastPositionUpdate: number;
  lastAccountUpdate: number;

  // Actions
  setAccount: (account: Account) => void;
  updateAccount: (updates: Partial<Account>) => void;

  setOrders: (orders: Order[]) => void;
  addOrder: (order: Order) => void;
  updateOrder: (order: Order) => void;
  removeOrder: (orderId: string) => void;
  setLoadingOrders: (loading: boolean) => void;
  selectOrder: (order: Order | null) => void;

  setPositions: (positions: Position[]) => void;
  addPosition: (position: Position) => void;
  updatePosition: (position: Position) => void;
  removePosition: (positionId: string) => void;
  setLoadingPositions: (loading: boolean) => void;
  selectPosition: (position: Position | null) => void;

  setSignals: (signals: TradingSignal[]) => void;
  addSignal: (signal: TradingSignal) => void;

  setLoadingAccount: (loading: boolean) => void;
  clearTradingData: () => void;

  // Computed values
  getTotalPnL: () => number;
  getMarginUsed: () => number;
  getMarginAvailable: () => number;
  getPositionsBySymbol: (symbol: string) => Position[];
  getOrdersBySymbol: (symbol: string) => Order[];
  getActiveOrdersCount: () => number;
  getOpenPositionsCount: () => number;
}

export const useTradingStore = create<TradingState>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    account: null,
    orders: [],
    positions: [],
    signals: [],
    isLoadingOrders: false,
    isLoadingPositions: false,
    isLoadingAccount: false,
    selectedOrder: null,
    selectedPosition: null,
    lastOrderUpdate: 0,
    lastPositionUpdate: 0,
    lastAccountUpdate: 0,

    // Account actions
    setAccount: (account: Account) => set({
      account,
      lastAccountUpdate: Date.now()
    }),

    updateAccount: (updates: Partial<Account>) => {
      set(state => ({
        account: state.account ? { ...state.account, ...updates } : null,
        lastAccountUpdate: Date.now()
      }));
    },

    // Order actions
    setOrders: (orders: Order[]) => set({
      orders: orders.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
      lastOrderUpdate: Date.now()
    }),

    addOrder: (order: Order) => {
      set(state => ({
        orders: [order, ...state.orders].sort((a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        ),
        lastOrderUpdate: Date.now()
      }));

      // Trigger order notification
      if (typeof window !== 'undefined') {
        const event = new CustomEvent('orderUpdate', {
          detail: { type: 'new', order }
        });
        window.dispatchEvent(event);
      }
    },

    updateOrder: (updatedOrder: Order) => {
      set(state => ({
        orders: state.orders.map(order =>
          order.id === updatedOrder.id ? updatedOrder : order
        ),
        selectedOrder: state.selectedOrder?.id === updatedOrder.id ? updatedOrder : state.selectedOrder,
        lastOrderUpdate: Date.now()
      }));

      // Trigger order notification
      if (typeof window !== 'undefined') {
        const event = new CustomEvent('orderUpdate', {
          detail: { type: 'update', order: updatedOrder }
        });
        window.dispatchEvent(event);
      }
    },

    removeOrder: (orderId: string) => {
      set(state => ({
        orders: state.orders.filter(order => order.id !== orderId),
        selectedOrder: state.selectedOrder?.id === orderId ? null : state.selectedOrder,
        lastOrderUpdate: Date.now()
      }));
    },

    setLoadingOrders: (loading: boolean) => set({ isLoadingOrders: loading }),
    selectOrder: (order: Order | null) => set({ selectedOrder: order }),

    // Position actions
    setPositions: (positions: Position[]) => set({
      positions: positions.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
      lastPositionUpdate: Date.now()
    }),

    addPosition: (position: Position) => {
      set(state => ({
        positions: [position, ...state.positions].sort((a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        ),
        lastPositionUpdate: Date.now()
      }));

      // Trigger position notification
      if (typeof window !== 'undefined') {
        const event = new CustomEvent('positionUpdate', {
          detail: { type: 'new', position }
        });
        window.dispatchEvent(event);
      }
    },

    updatePosition: (updatedPosition: Position) => {
      set(state => ({
        positions: state.positions.map(position =>
          position.id === updatedPosition.id ? updatedPosition : position
        ),
        selectedPosition: state.selectedPosition?.id === updatedPosition.id ? updatedPosition : state.selectedPosition,
        lastPositionUpdate: Date.now()
      }));

      // Trigger position notification
      if (typeof window !== 'undefined') {
        const event = new CustomEvent('positionUpdate', {
          detail: { type: 'update', position: updatedPosition }
        });
        window.dispatchEvent(event);
      }
    },

    removePosition: (positionId: string) => {
      set(state => ({
        positions: state.positions.filter(position => position.id !== positionId),
        selectedPosition: state.selectedPosition?.id === positionId ? null : state.selectedPosition,
        lastPositionUpdate: Date.now()
      }));
    },

    setLoadingPositions: (loading: boolean) => set({ isLoadingPositions: loading }),
    selectPosition: (position: Position | null) => set({ selectedPosition: position }),

    // Signal actions
    setSignals: (signals: TradingSignal[]) => set({
      signals: signals.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    }),

    addSignal: (signal: TradingSignal) => {
      set(state => ({
        signals: [signal, ...state.signals]
          .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
          .slice(0, 100) // Keep only the most recent 100 signals
      }));

      // Trigger signal notification
      if (typeof window !== 'undefined') {
        const event = new CustomEvent('signalUpdate', {
          detail: { signal }
        });
        window.dispatchEvent(event);
      }
    },

    setLoadingAccount: (loading: boolean) => set({ isLoadingAccount: loading }),

    clearTradingData: () => set({
      orders: [],
      positions: [],
      signals: [],
      selectedOrder: null,
      selectedPosition: null,
      lastOrderUpdate: 0,
      lastPositionUpdate: 0,
      lastAccountUpdate: 0
    }),

    // Computed values
    getTotalPnL: () => {
      const { positions, account } = get();
      const unrealizedPnL = positions.reduce((sum, pos) => sum + pos.unrealized_pnl, 0);
      const realizedPnL = account?.realized_pnl || 0;
      return unrealizedPnL + realizedPnL;
    },

    getMarginUsed: () => {
      const { account } = get();
      return account?.margin_used || 0;
    },

    getMarginAvailable: () => {
      const { account } = get();
      return account?.margin_available || 0;
    },

    getPositionsBySymbol: (symbol: string) => {
      return get().positions.filter(pos => pos.symbol === symbol);
    },

    getOrdersBySymbol: (symbol: string) => {
      return get().orders.filter(order => order.symbol === symbol);
    },

    getActiveOrdersCount: () => {
      return get().orders.filter(order =>
        order.status === 'pending' || order.status === 'partially_filled'
      ).length;
    },

    getOpenPositionsCount: () => {
      return get().positions.length;
    }
  }))
);
