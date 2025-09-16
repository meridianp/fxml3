import abc


class BaseCollector(abc.ABC):
    """
    Abstract base class for data collectors.
    """

    def __init__(self, storage):
        self.storage = storage

    @abc.abstractmethod
    async def collect(self):
        """
        Fetch data from a source.
        """
        pass

    async def collect_and_store(self):
        """
        Collect data and store it using the provided storage backend.
        """
        data = await self.collect()
        await self.storage.save(data)