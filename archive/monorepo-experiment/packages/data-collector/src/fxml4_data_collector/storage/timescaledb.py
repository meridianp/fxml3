class TimescaleDBStorage:
    """
    Storage adapter for persisting data to TimescaleDB.
    """

    def __init__(self, dsn: str):
        self.dsn = dsn

    async def save(self, data):
        """
        Persist the collected data to TimescaleDB.
        """
        # TODO: implement save logic using asyncpg
        pass