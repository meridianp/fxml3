from fxml4_data_collector.collectors.base_collector import BaseCollector


class PolygonCollector(BaseCollector):
    """
    Collector implementation for fetching data from the Polygon API.
    """

    def __init__(self, storage, api_key: str):
        super().__init__(storage)
        self.api_key = api_key

    async def collect(self):
        """
        Fetch data from the Polygon API.
        """
        # TODO: implement API call logic using httpx
        return {}