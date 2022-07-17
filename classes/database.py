import pymongo
import motor.motor_asyncio
import warnings
import logging
from classes import Configuration
from typing import Union

__all__ = "MongoDB",


class MongoDB:
    def __init__(self, configuration_file: Configuration):
        self.configuration_file = configuration_file

        assert self.validate()

        self.client = self.start_asynchronous()
        logging.info("classes.database.MongoDB: Finished connecting to provided DB via motor. Database is ready!")

    def validate(self):
        logging.info("classes.database.MongoDB: Starting validation of database configuration")
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
        logging.info("classes.database.MongoDB: Finished validation of database configuration")
        return True

    def start_asynchronous(self):
        logging.info("classes.database.MongoDB: Trying to connect to provided DB via motor")
        return motor.motor_asyncio.AsyncIOMotorClient(host=self.configuration_file["DATABASE"]["connectionString"],
                                                      username=self.configuration_file["DATABASE"]["username"],
                                                      password=self.configuration_file["DATABASE"]["password"],
                                                      authSource=self.configuration_file["DATABASE"]["databaseName"])

    async def find_one(self, database: Union[str, motor.motor_asyncio.AsyncIOMotorDatabase],
                       collection: Union[str, pymongo.collection.Collection],
                       query: dict):
        logging.info(f"classes.database.MongoDB: find_one called for db: {database}, "
                     f"collection: {collection}, query: {query}")
        async with await self.client.start_session():
            if type(database) is str:
                database = self.client.get_database(database)
            if type(collection) is str:
                collection = database.get_collection(collection)
            assert database.validate_collection(collection)
            document = await collection.find_one(query)
            return document
