import React, { createContext, useContext, useState } from 'react';

interface Order {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  orderType: 'MARKET' | 'LIMIT';
  price?: number;
  status: 'PENDING' | 'FILLED' | 'CANCELLED';
  timestamp: Date;
}

interface OrderContextType {
  orders: Order[];
  submitOrder: (order: Omit<Order, 'id' | 'status' | 'timestamp'>) => void;
  modifyOrder: (orderId: string, updates: Partial<Order>) => void;
  cancelOrder: (orderId: string) => void;
}

const OrderContext = createContext<OrderContextType | undefined>(undefined);

export const useOrders = () => {
  const context = useContext(OrderContext);
  if (!context) {
    throw new Error('useOrders must be used within an OrderProvider');
  }
  return context;
};

interface OrderProviderProps {
  children: React.ReactNode;
  onOrderSubmit?: (order: any) => void;
}

export const OrderProvider: React.FC<OrderProviderProps> = ({ children, onOrderSubmit }) => {
  const [orders, setOrders] = useState<Order[]>([
    {
      id: '123',
      symbol: 'EUR/USD',
      side: 'BUY',
      quantity: 10000,
      orderType: 'LIMIT',
      price: 1.0500,
      status: 'PENDING',
      timestamp: new Date()
    }
  ]);

  const submitOrder = (order: Omit<Order, 'id' | 'status' | 'timestamp'>) => {
    if (onOrderSubmit) {
      onOrderSubmit(order);
    }
    const newOrder: Order = {
      ...order,
      id: Date.now().toString(),
      status: 'PENDING',
      timestamp: new Date()
    };
    setOrders(prev => [...prev, newOrder]);
  };

  const modifyOrder = (orderId: string, updates: Partial<Order>) => {
    setOrders(prev => prev.map(o => o.id === orderId ? { ...o, ...updates } : o));
  };

  const cancelOrder = (orderId: string) => {
    setOrders(prev => prev.map(o => o.id === orderId ? { ...o, status: 'CANCELLED' } : o));
  };

  return (
    <OrderContext.Provider value={{ orders, submitOrder, modifyOrder, cancelOrder }}>
      {children}
    </OrderContext.Provider>
  );
};
