import logging
import datetime
from classes import Configuration, Log

CONFIGURATION_FILENAME = "bot.config"
GLOBAL_CONFIG_FILE = Configuration(filename=CONFIGURATION_FILENAME)
GLOBAL_LOG_FILE = Log(configuration_file=GLOBAL_CONFIG_FILE)

logging.basicConfig(filename=f"{GLOBAL_LOG_FILE}",
                    level=f"{GLOBAL_CONFIG_FILE['LOGGING']['loggingLevel']}")

logging.debug(f"Starting a new run at {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
