import pymongo
import motor.motor_asyncio
import warnings
from classes import Configuration
from typing import Union

__all__ = "MongoDB",


class MongoDB:
    def __init__(self, configuration_file: Configuration):
        self.configuration_file = configuration_file

        assert self.validate()

        self.client = self.start_asynchronous()

    def validate(self):
        try:
            assert "DATABASE" in self.configuration_file.configuration
        except AssertionError:
            warnings.warn("No DATABASE section in configuration file. Reverting to default.")
            self.configuration_file.fallback(category="DATABASE")

        try:
            assert "connectionString" in self.configuration_file.configuration['DATABASE']
        except AssertionError:
            warnings.warn("No connectionString in the DATABASE section in configuration file. Reverting to default.")
            self.configuration_file.fallback(category="DATABASE", item="connectionString")

        assert "username", "password" in self.configuration_file.configuration['DATABASE']
        return True

    def start_asynchronous(self):
        return motor.motor_asyncio.AsyncIOMotorClient(host=self.configuration_file["DATABASE"]["connectionString"],
                                                      username=self.configuration_file["DATABASE"]["username"],
                                                      password=self.configuration_file["DATABASE"]["password"],
                                                      authSource=self.configuration_file["DATABASE"]["databaseName"])

    async def find_one(self, database: Union[str, motor.motor_asyncio.AsyncIOMotorDatabase],
                       collection: Union[str, pymongo.collection.Collection],
                       query: dict):
        async with await self.client.start_session():
            if type(database) is str:
                database = self.client.get_database(database)
            if type(collection) is str:
                collection = database.get_collection(collection)
            assert database.validate_collection(collection)
            document = await collection.find_one(query)
            return document
