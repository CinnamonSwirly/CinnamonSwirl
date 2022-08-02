"""
CinnamonSwirl is a bot for discord using the discord.py API wrapper and motor_asyncio
Repository URL: https://github.com/CinnamonSwirly/CinnamonSwirl

This bot requires a MongoDB database. Before running, you should review the sample config file and make adjustments.
The bot was built as a learning exercise and doesn't offer extensive features or long-term support.
Licensed under the Creative Commons Zero v1 Universal license.
tl;dr: Use it for whatever, but it stays in public domain.
"""
from logging import basicConfig as loggingConfig, info
from datetime import datetime
from discord import Intents
from classes import Configuration, Log, MongoDB, Bot

CONFIGURATION_FILENAME = "bot.config"  # If you change this, be sure to rename your config file too!
GLOBAL_CONFIG_FILE = Configuration(filename=CONFIGURATION_FILENAME)
GLOBAL_LOG_FILE = Log(configuration_file=GLOBAL_CONFIG_FILE)

loggingConfig(filename=f"{GLOBAL_LOG_FILE}", level=f"{GLOBAL_CONFIG_FILE['LOGGING']['loggingLevel']}")

info(f"Starting a new instance at {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

DATABASE_CONNECTION = MongoDB(configuration_file=GLOBAL_CONFIG_FILE)
assert DATABASE_CONNECTION.test()

intents = Intents.default()
bot = Bot(configuration=GLOBAL_CONFIG_FILE, database_connection=DATABASE_CONNECTION, intents=intents)
bot.run()
