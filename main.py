import logging
import datetime
import discord
from classes import Configuration, Log, MongoDB, Bot

CONFIGURATION_FILENAME = "bot.config"
GLOBAL_CONFIG_FILE = Configuration(filename=CONFIGURATION_FILENAME)
GLOBAL_LOG_FILE = Log(configuration_file=GLOBAL_CONFIG_FILE)

logging.basicConfig(filename=f"{GLOBAL_LOG_FILE}",
                    level=f"{GLOBAL_CONFIG_FILE['LOGGING']['loggingLevel']}")

logging.info(f"Starting a new run at {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

DATABASE_CONNECTION = MongoDB(configuration_file=GLOBAL_CONFIG_FILE)
assert DATABASE_CONNECTION.test()

intents = discord.Intents.default()
bot = Bot(configuration=GLOBAL_CONFIG_FILE, database_connection=DATABASE_CONNECTION, intents=intents)
bot.run()
