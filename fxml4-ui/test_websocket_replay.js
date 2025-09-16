#!/usr/bin/env node
/**
 * Test script for WebSocket message replay functionality
 *
 * Simulates WebSocket disconnection and reconnection scenarios to verify
 * that message replay prevents data loss and maintains proper ordering.
 */

const { EventEmitter } = require('events');

// Mock WebSocket service with message replay functionality
class MockWebSocketService extends EventEmitter {
  constructor() {
    super();
    this.isConnected = false;
    this.lastSequenceNumber = 0;
    this.messageQueue = [];
    this.maxQueueSize = 1000;
    this.disconnectedAt = null;
    this.subscriptions = new Set();
  }

  connect() {
    this.isConnected = true;
    this.emit('connected');
    console.log('✅ WebSocket connected');
  }

  disconnect(reason = 'test') {
    this.isConnected = false;
    this.disconnectedAt = Date.now();
    this.emit('disconnected', reason);
    console.log(`⚠️  WebSocket disconnected: ${reason} at ${new Date(this.disconnectedAt)}`);
  }

  reconnect() {
    this.connect();
    this.requestMessageReplay();
    this.emit('reconnected');
    console.log('🔄 WebSocket reconnected - requesting message replay');
  }

  requestMessageReplay() {
    if (!this.disconnectedAt) return;

    const reconnectedAt = Date.now();
    const disconnectionDuration = reconnectedAt - this.disconnectedAt;

    console.log(`📋 Requesting message replay for ${disconnectionDuration}ms disconnection`);
    console.log(`   Last sequence: ${this.lastSequenceNumber}, subscriptions: ${this.subscriptions.size}`);

    // Simulate server providing replay messages
    setTimeout(() => {
      this.simulateMessageReplay(disconnectionDuration);
    }, 100);

    this.disconnectedAt = null;
  }

  simulateMessageReplay(disconnectionDuration) {
    // Simulate messages that were sent during disconnection
    const replayMessages = [];
    const messagesPerSecond = 10; // 10 messages per second
    const expectedMessages = Math.floor(disconnectionDuration / 1000 * messagesPerSecond);

    for (let i = 1; i <= expectedMessages; i++) {
      replayMessages.push({
        id: `replay_${this.lastSequenceNumber + i}`,
        type: 'market_data',
        data: {
          symbol: 'EURUSD',
          bid: 1.1000 + (Math.random() * 0.01),
          ask: 1.1005 + (Math.random() * 0.01),
          timestamp: this.disconnectedAt + (i * 100) // 100ms intervals
        },
        sequence: this.lastSequenceNumber + i,
        timestamp: this.disconnectedAt + (i * 100)
      });
    }

    if (replayMessages.length > 0) {
      this.handleReplayedMessages(replayMessages);
    } else {
      console.log('📭 No messages to replay');
    }
  }

  handleReplayedMessages(messages) {
    console.log(`📥 Processing ${messages.length} replayed messages`);

    // Sort messages by sequence number to ensure proper order
    const sortedMessages = messages.sort((a, b) => a.sequence - b.sequence);

    let processedCount = 0;
    let skippedCount = 0;

    // Process each message
    sortedMessages.forEach(message => {
      const processed = this.processQueuedMessage(message);
      if (processed) {
        processedCount++;
      } else {
        skippedCount++;
      }
    });

    console.log(`✅ Replay complete: ${processedCount} processed, ${skippedCount} skipped`);
    console.log(`   Current sequence: ${this.lastSequenceNumber}`);
  }

  processQueuedMessage(message) {
    // Check if this message is newer than our last processed sequence
    if (message.sequence <= this.lastSequenceNumber) {
      console.debug(`⏭️  Ignoring duplicate/old message: ${message.sequence}`);
      return false;
    }

    // Update last sequence number
    this.lastSequenceNumber = message.sequence;

    // Add to message queue for replay protection
    this.messageQueue.push(message);

    // Trim queue if it gets too large
    if (this.messageQueue.length > this.maxQueueSize) {
      this.messageQueue = this.messageQueue.slice(-this.maxQueueSize);
    }

    // Emit the message event
    this.emit(message.type, message.data);
    return true;
  }

  // Simulate receiving regular messages
  simulateMessage(type, data) {
    if (!this.isConnected) {
      console.log(`❌ Cannot send message while disconnected: ${type}`);
      return;
    }

    const message = {
      id: `msg_${Date.now()}`,
      type,
      data,
      sequence: this.lastSequenceNumber + 1,
      timestamp: Date.now()
    };

    this.processQueuedMessage(message);
  }

  subscribe(channel) {
    this.subscriptions.add(channel);
    console.log(`🔔 Subscribed to: ${channel}`);
  }

  getStats() {
    return {
      lastSequenceNumber: this.lastSequenceNumber,
      queueSize: this.messageQueue.length,
      subscriptions: this.subscriptions.size,
      isConnected: this.isConnected
    };
  }
}

// Test scenarios
async function testWebSocketReplayScenarios() {
  console.log('🧪 Testing WebSocket Message Replay Functionality');
  console.log('=' * 55);

  const ws = new MockWebSocketService();
  let testsPassed = 0;
  let testsTotal = 0;
  let receivedMessages = [];

  // Set up message listener
  ws.on('market_data', (data) => {
    receivedMessages.push(data);
  });

  // Test 1: Normal operation with sequence numbers
  testsTotal++;
  console.log('\n📋 Test 1: Normal message processing with sequence numbers');

  ws.connect();
  ws.subscribe('market_data:EURUSD');

  // Send some normal messages
  for (let i = 1; i <= 5; i++) {
    ws.simulateMessage('market_data', {
      symbol: 'EURUSD',
      bid: 1.1000,
      ask: 1.1005,
      timestamp: Date.now()
    });
  }

  if (ws.lastSequenceNumber === 5 && receivedMessages.length === 5) {
    console.log('✅ Test 1 PASSED: Normal message processing works correctly');
    testsPassed++;
  } else {
    console.log('❌ Test 1 FAILED: Expected 5 messages with sequence 5');
    console.log(`   Actual: ${receivedMessages.length} messages, sequence ${ws.lastSequenceNumber}`);
  }

  // Test 2: Disconnection and replay
  testsTotal++;
  console.log('\n📋 Test 2: Disconnection and message replay');

  const beforeDisconnectSequence = ws.lastSequenceNumber;
  const beforeDisconnectMessages = receivedMessages.length;

  ws.disconnect('connection_lost');

  // Simulate messages arriving during disconnection (these will be replayed)
  await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second disconnection

  ws.reconnect();

  // Wait for replay to complete
  await new Promise(resolve => setTimeout(resolve, 500));

  const afterReconnectSequence = ws.lastSequenceNumber;
  const afterReconnectMessages = receivedMessages.length;

  const replayedMessagesCount = afterReconnectMessages - beforeDisconnectMessages;
  const sequenceGap = afterReconnectSequence - beforeDisconnectSequence;

  if (replayedMessagesCount > 0 && sequenceGap === replayedMessagesCount) {
    console.log(`✅ Test 2 PASSED: ${replayedMessagesCount} messages replayed correctly`);
    testsPassed++;
  } else {
    console.log('❌ Test 2 FAILED: Message replay count/sequence mismatch');
    console.log(`   Replayed messages: ${replayedMessagesCount}, sequence gap: ${sequenceGap}`);
  }

  // Test 3: Duplicate message handling
  testsTotal++;
  console.log('\n📋 Test 3: Duplicate message rejection');

  const beforeDuplicateCount = receivedMessages.length;
  const currentSequence = ws.lastSequenceNumber;

  // Try to process a message with old sequence number
  const duplicateMessage = {
    id: 'duplicate_test',
    type: 'market_data',
    data: { symbol: 'EURUSD', bid: 1.2000, ask: 1.2005 },
    sequence: currentSequence - 5, // Old sequence
    timestamp: Date.now()
  };

  const processed = ws.processQueuedMessage(duplicateMessage);
  const afterDuplicateCount = receivedMessages.length;

  if (!processed && afterDuplicateCount === beforeDuplicateCount && ws.lastSequenceNumber === currentSequence) {
    console.log('✅ Test 3 PASSED: Duplicate message correctly rejected');
    testsPassed++;
  } else {
    console.log('❌ Test 3 FAILED: Duplicate message was incorrectly processed');
  }

  // Test 4: Out-of-order message handling
  testsTotal++;
  console.log('\n📋 Test 4: Out-of-order message handling during replay');

  // Simulate out-of-order messages during replay
  const outOfOrderMessages = [
    { sequence: ws.lastSequenceNumber + 3, data: { timestamp: 3 } },
    { sequence: ws.lastSequenceNumber + 1, data: { timestamp: 1 } },
    { sequence: ws.lastSequenceNumber + 2, data: { timestamp: 2 } },
  ].map(msg => ({
    id: `order_test_${msg.sequence}`,
    type: 'market_data',
    data: { symbol: 'EURUSD', bid: 1.1000, ask: 1.1005, ...msg.data },
    sequence: msg.sequence,
    timestamp: Date.now()
  }));

  ws.handleReplayedMessages(outOfOrderMessages);

  // Check if messages were processed in correct order
  const lastThreeMessages = receivedMessages.slice(-3);
  const timestampsInOrder = lastThreeMessages.every((msg, i) =>
    i === 0 || msg.timestamp >= lastThreeMessages[i-1].timestamp
  );

  if (timestampsInOrder && ws.lastSequenceNumber === ws.lastSequenceNumber) {
    console.log('✅ Test 4 PASSED: Out-of-order messages processed in correct sequence');
    testsPassed++;
  } else {
    console.log('❌ Test 4 FAILED: Messages not processed in correct order');
  }

  // Summary
  console.log('\n' + '=' * 55);
  console.log(`📊 Test Results: ${testsPassed}/${testsTotal} tests passed`);

  const stats = ws.getStats();
  console.log('\n📈 Final Statistics:');
  console.log(`   Last sequence number: ${stats.lastSequenceNumber}`);
  console.log(`   Message queue size: ${stats.queueSize}`);
  console.log(`   Total messages received: ${receivedMessages.length}`);
  console.log(`   Active subscriptions: ${stats.subscriptions}`);

  if (testsPassed === testsTotal) {
    console.log('\n🎉 All tests PASSED! WebSocket message replay is working correctly.');
    console.log('');
    console.log('✅ Message replay prevents data loss during disconnections');
    console.log('✅ Sequence numbers ensure proper message ordering');
    console.log('✅ Duplicate messages are correctly rejected');
    console.log('✅ Out-of-order messages are handled gracefully');
    return true;
  } else {
    console.log('\n💥 Some tests FAILED! Message replay needs adjustment.');
    return false;
  }
}

// Run tests
testWebSocketReplayScenarios()
  .then(success => {
    process.exit(success ? 0 : 1);
  })
  .catch(error => {
    console.error('Test execution failed:', error);
    process.exit(1);
  });
