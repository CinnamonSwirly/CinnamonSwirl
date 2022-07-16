import logging
import datetime
import pprint
from classes import Configuration, Log, MongoDB

CONFIGURATION_FILENAME = "bot.config"
GLOBAL_CONFIG_FILE = Configuration(filename=CONFIGURATION_FILENAME)
GLOBAL_LOG_FILE = Log(configuration_file=GLOBAL_CONFIG_FILE)

logging.basicConfig(filename=f"{GLOBAL_LOG_FILE}",
                    level=f"{GLOBAL_CONFIG_FILE['LOGGING']['loggingLevel']}")

logging.debug(f"Starting a new run at {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

DATABASE_CONNECTION = MongoDB(configuration_file=GLOBAL_CONFIG_FILE)

loop = DATABASE_CONNECTION.client.get_io_loop()

query = {"result": "Success!"}

item = loop.run_until_complete(DATABASE_CONNECTION.find_one(database='CinnamonSwirl', collection='test',
                                                            query=query))

pprint.pprint(item)
