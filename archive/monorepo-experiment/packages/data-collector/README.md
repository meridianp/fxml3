# fxml4 Data Collector

The `fxml4-data-collector` package provides a framework for collecting and storing data from various sources to TimescaleDB. It includes:

- **Collectors**: Abstract base and concrete implementations for fetching data.
- **Storage**: Adapters for persisting collected data (e.g., TimescaleDB).

## Structure

- `src/fxml4_data_collector/collectors` - Collector classes handle data retrieval.
- `src/fxml4_data_collector/storage` - Storage adapters for persisting data.

## Usage

1. Install the package:

   ```bash
   poetry add ./packages/data-collector
   ```

2. Implement or configure your collector and storage settings.

3. Run your collection workflow, for example:

   ```python
   from fxml4_data_collector.collectors.polygon_collector import PolygonCollector
   from fxml4_data_collector.storage.timescaledb import TimescaleDBStorage

   async def main():
       storage = TimescaleDBStorage(dsn="postgresql://user:pass@localhost/db")
       collector = PolygonCollector(storage=storage, api_key="YOUR_API_KEY")
       await collector.collect_and_store()

   import asyncio
   asyncio.run(main())
   ```

## Testing

Run tests with:

```bash
pytest tests
```