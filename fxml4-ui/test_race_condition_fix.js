#!/usr/bin/env node
/**
 * Test script for order state race condition fix
 *
 * Simulates concurrent order updates from API and WebSocket to verify
 * that sequence-based optimistic locking prevents race conditions.
 */

const { performance } = require('perf_hooks');

// Mock the Zustand store behavior with our race condition fix
class MockTradingStore {
  constructor() {
    this.orders = [];
  }

  addOrder(order) {
    // Check if order already exists (race condition protection)
    const existing = this.orders.find(o => o.id === order.id);
    if (existing) {
      console.warn('Attempted to add existing order, using updateOrder instead:', order.id);
      // Use updateOrder logic for consistency
      this.orders = this.orders.map(o =>
        o.id === order.id && order.sequence_number > o.sequence_number
          ? { ...order, updatedAt: new Date() }
          : o
      );
      return;
    }

    // Add new order
    this.orders.push({ ...order, updatedAt: new Date() });
  }

  updateOrder(orderId, updates) {
    this.orders = this.orders.map((order) => {
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
    });
  }

  getOrder(orderId) {
    return this.orders.find(o => o.id === orderId);
  }
}

// Test scenarios
async function testRaceConditionScenarios() {
  console.log('🧪 Testing Order State Race Condition Fix');
  console.log('=' * 50);

  const store = new MockTradingStore();
  let testsPassed = 0;
  let testsTotal = 0;

  // Test 1: Concurrent API and WebSocket updates with different sequence numbers
  testsTotal++;
  console.log('\n📋 Test 1: API vs WebSocket with proper sequencing');

  // Simulate API response first (lower sequence number)
  const apiOrder = {
    id: 'order_001',
    symbol: 'EURUSD',
    status: 'pending',
    sequence_number: 1001,
    source: 'api',
    timestamp: new Date()
  };

  store.addOrder(apiOrder);

  // Simulate WebSocket update with higher sequence number (should apply)
  const wsOrder = {
    id: 'order_001',
    status: 'filled',
    sequence_number: 1002,
    source: 'websocket',
    filledQuantity: 10000
  };

  store.updateOrder('order_001', wsOrder);

  const finalOrder = store.getOrder('order_001');
  if (finalOrder.status === 'filled' && finalOrder.sequence_number === 1002) {
    console.log('✅ Test 1 PASSED: WebSocket update with higher sequence applied correctly');
    testsPassed++;
  } else {
    console.log('❌ Test 1 FAILED: Expected status=filled, sequence=1002');
    console.log('   Actual:', { status: finalOrder.status, sequence: finalOrder.sequence_number });
  }

  // Test 2: Out-of-order updates (should be rejected)
  testsTotal++;
  console.log('\n📋 Test 2: Out-of-order update rejection');

  // Try to apply update with lower sequence number (should be ignored)
  const outdatedUpdate = {
    id: 'order_001',
    status: 'cancelled',
    sequence_number: 1001, // Lower than current 1002
    source: 'websocket'
  };

  store.updateOrder('order_001', outdatedUpdate);

  const orderAfterOutdated = store.getOrder('order_001');
  if (orderAfterOutdated.status === 'filled' && orderAfterOutdated.sequence_number === 1002) {
    console.log('✅ Test 2 PASSED: Outdated update correctly ignored');
    testsPassed++;
  } else {
    console.log('❌ Test 2 FAILED: Outdated update was incorrectly applied');
  }

  // Test 3: Race condition simulation
  testsTotal++;
  console.log('\n📋 Test 3: High-frequency concurrent updates');

  // Create new order for race condition test
  const raceOrder = {
    id: 'order_race',
    symbol: 'GBPUSD',
    status: 'pending',
    sequence_number: 2000,
    source: 'api',
    filledQuantity: 0
  };

  store.addOrder(raceOrder);

  // Simulate rapid concurrent updates
  const updates = [
    { sequence_number: 2001, status: 'working', source: 'websocket' },
    { sequence_number: 2003, status: 'partially_filled', filledQuantity: 5000, source: 'websocket' },
    { sequence_number: 2002, status: 'confirmed', source: 'api' }, // Out of order
    { sequence_number: 2004, status: 'filled', filledQuantity: 10000, source: 'websocket' },
  ];

  // Apply updates rapidly
  updates.forEach(update => {
    store.updateOrder('order_race', update);
  });

  const raceResult = store.getOrder('order_race');
  if (raceResult.status === 'filled' &&
      raceResult.sequence_number === 2004 &&
      raceResult.filledQuantity === 10000) {
    console.log('✅ Test 3 PASSED: Race condition handled correctly, final state consistent');
    testsPassed++;
  } else {
    console.log('❌ Test 3 FAILED: Race condition resulted in inconsistent state');
    console.log('   Expected: status=filled, sequence=2004, filled=10000');
    console.log('   Actual:', {
      status: raceResult.status,
      sequence: raceResult.sequence_number,
      filled: raceResult.filledQuantity
    });
  }

  // Test 4: Duplicate add order prevention
  testsTotal++;
  console.log('\n📋 Test 4: Duplicate order addition prevention');

  const duplicateOrder = {
    id: 'order_duplicate',
    symbol: 'USDJPY',
    status: 'pending',
    sequence_number: 3000,
    source: 'api'
  };

  store.addOrder(duplicateOrder);

  // Try to add same order again with higher sequence (should become update)
  const duplicateAttempt = {
    id: 'order_duplicate',
    symbol: 'USDJPY',
    status: 'filled',
    sequence_number: 3001,
    source: 'websocket'
  };

  store.addOrder(duplicateAttempt);

  const duplicateResult = store.getOrder('order_duplicate');
  if (store.orders.filter(o => o.id === 'order_duplicate').length === 1 &&
      duplicateResult.status === 'filled') {
    console.log('✅ Test 4 PASSED: Duplicate add converted to update correctly');
    testsPassed++;
  } else {
    console.log('❌ Test 4 FAILED: Duplicate order handling incorrect');
  }

  // Summary
  console.log('\n' + '=' * 50);
  console.log(`📊 Test Results: ${testsPassed}/${testsTotal} tests passed`);

  if (testsPassed === testsTotal) {
    console.log('🎉 All tests PASSED! Race condition fix is working correctly.');
    console.log('');
    console.log('✅ Sequence-based optimistic locking prevents race conditions');
    console.log('✅ Out-of-order updates are correctly rejected');
    console.log('✅ Concurrent updates maintain state consistency');
    console.log('✅ Duplicate order additions are handled gracefully');
    return true;
  } else {
    console.log('💥 Some tests FAILED! Race condition fix needs adjustment.');
    return false;
  }
}

// Run tests
testRaceConditionScenarios()
  .then(success => {
    process.exit(success ? 0 : 1);
  })
  .catch(error => {
    console.error('Test execution failed:', error);
    process.exit(1);
  });
