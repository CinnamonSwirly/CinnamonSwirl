import pymongo
import motor.motor_asyncio
import warnings
import logging
from classes import Configuration
from typing import Union, Optional, Literal

__all__ = "MongoDB",


class MongoDB:
    def __init__(self, configuration_file: Configuration):
        self.configuration_file = configuration_file

        assert self._validate()

        self.client = self._start_asynchronous()
        logging.info("classes.database.MongoDB: Finished connecting to provided DB via motor. Database is ready!")

    def _validate(self) -> bool:
        logging.info("classes.database.MongoDB: Starting validation of database configuration")
        logging.debug(f"classes.database.MongoDB: Read configuration_file.configuration as: "
                      f"{self.configuration_file.configuration}")
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

    def _start_asynchronous(self) -> motor.motor_asyncio.AsyncIOMotorClient:
        logging.info("classes.database.MongoDB: Trying to connect to provided DB via motor")
        return motor.motor_asyncio.AsyncIOMotorClient(host=self.configuration_file["DATABASE"]["connectionString"],
                                                      username=self.configuration_file["DATABASE"]["username"],
                                                      password=self.configuration_file["DATABASE"]["password"],
                                                      authSource=self.configuration_file["DATABASE"]["databaseName"])

    def test(self) -> bool:
        logging.info("classes.database.MongoDB: Testing connection to database")
        loop = self.client.get_io_loop()
        query = {"result": "Success!"}
        item = loop.run_until_complete(self.find_one(database='CinnamonSwirl', collection='test', query=query))
        if item['result'] == "Success!":
            logging.info("classes.database.MongoDB: Test OK")
            return True
        else:
            logging.error("classes.database.MongoDB: Test failed when looking for 'result' in collection 'test' under"
                          "database 'CinnamonSwirl'. Expected 'Success!'")
            return False

    async def find_one(self, database: Union[str, motor.motor_asyncio.AsyncIOMotorDatabase],
                       collection: Union[str, pymongo.collection.Collection],
                       query: dict) -> dict:
        logging.info(f"classes.database.MongoDB: find_one called for db: {database}, "
                     f"collection: {collection}, query: {query}")
        async with await self.client.start_session():
            if type(database) is str:
                database = self.client.get_database(database)
            if type(collection) is str:
                collection = database.get_collection(collection)
            assert database.validate_collection(collection)
            document = await collection.find_one(filter=query)
            return document

    async def find_many(self, database: Union[str, motor.motor_asyncio.AsyncIOMotorDatabase],
                        collection: Union[str, pymongo.collection.Collection],
                        query: dict, length: int, sort_by: Optional[str],
                        sort_direction: Optional[Literal[1, -1]]) -> list:
        logging.info(f"classes.database.MongoDB: find_many called for db: {database}, "
                     f"collection: {collection}, query: {query}")
        async with await self.client.start_session():
            if type(database) is str:
                database = self.client.get_database(database)
            if type(collection) is str:
                collection = database.get_collection(collection)
            assert database.validate_collection(collection)
            cursor = collection.find(filter=query)
            if sort_by and sort_direction:
                logging.debug(f"classes.database.MongoDB: find_many has sorting enabled. "
                              f"{sort_by} by {sort_direction}")
                assert sort_by in ('_id', 'recipient', 'message', 'time')
                cursor.sort(key_or_list=sort_by, direction=sort_direction)
            # Pycharm thinks collection and cursor could be a str. We catch that above and change it.
            # noinspection PyUnresolvedReferences
            result = await cursor.to_list(length=length)
            logging.debug(f"classes.database.MongoDB: Found {len(result)} result(s).")
            return result

    async def insert_one(self, database: Union[str, motor.motor_asyncio.AsyncIOMotorDatabase],
                         collection: Union[str, pymongo.collection.Collection],
                         query: dict) -> Union[int, None]:
        logging.info(f"classes.database.MongoDB: insert_one called for db: {database}, "
                     f"collection: {collection}, query: {query}")
        async with await self.client.start_session():
            if type(database) is str:
                database = self.client.get_database(database)
            if type(collection) is str:
                collection = database.get_collection(collection)
            assert database.validate_collection(collection)
            result = await collection.insert_one(query)
            if result.inserted_id:
                return result.inserted_id
            else:
                return None
