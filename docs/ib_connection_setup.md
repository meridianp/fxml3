# Interactive Brokers TWS API Connection Setup

This guide explains how to set up Interactive Brokers Trader Workstation (TWS) for API connections with FXML4.

## Prerequisites

1. An Interactive Brokers account (regular or paper trading)
2. TWS (Trader Workstation) installed on your computer
3. Python environment with ibapi package installed

## TWS Configuration Steps

1. **Start TWS (Trader Workstation)**
   - Launch the TWS application
   - Log in to your account (regular or paper trading)

2. **Configure API Settings**
   - Go to Edit -> Global Configuration -> API -> Settings
   - Check "Enable ActiveX and Socket Clients"
   - Set Socket Port to 7497 (for paper trading) or 7496 (for live trading)
   - Check "Allow connections from localhost only" if you're testing on the same machine
   - Optionally, you can increase "Max. connections" if needed (default is fine for testing)
   - Optionally, uncheck "Read-Only API" if you need to place orders via API

3. **Configure API Precautions (Optional)**
   - In the same API settings window, go to the "Precautions" tab
   - Adjust any security settings according to your needs
   - For testing, you might want to disable some confirmations to make automation easier

4. **Save Settings**
   - Click "Apply" and then "OK" to save your changes

## Testing the Connection

Once TWS is properly configured, you can test the API connection using our test script:

```bash
python scripts/test_ib_connection.py --symbol GBPUSD
```

You can also specify different parameters:

```bash
python scripts/test_ib_connection.py --host 127.0.0.1 --port 7497 --client-id 1 --symbol EURUSD
```

### Troubleshooting Connection Issues

If you encounter connection problems:

1. **Verify TWS is Running**
   - Make sure TWS is open and you're logged in

2. **Check Port Settings**
   - Confirm the port in your code matches the port in TWS settings

3. **Check Client ID**
   - Try different client IDs if the one you're using is already occupied

4. **API Permissions**
   - Ensure your account has API permissions enabled

5. **Firewall Issues**
   - Check if your firewall is blocking the connection

6. **TWS Timeout**
   - TWS has an auto-logout feature. If it's been idle for too long, you may need to log in again

## Connection Properties

| Parameter | Paper Trading | Live Trading |
|-----------|--------------|--------------|
| Host      | 127.0.0.1    | 127.0.0.1    |
| Port      | 7497         | 7496         |
| Client ID | Any unique number | Any unique number |

## Next Steps

After successfully connecting to TWS API, you can:

1. Retrieve market data for specific symbols
2. Query account information
3. Place and manage orders
4. Monitor positions and P&L

For more information, refer to the [Interactive Brokers API Documentation](https://interactivebrokers.github.io/tws-api/).
