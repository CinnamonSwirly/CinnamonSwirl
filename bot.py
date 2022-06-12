import logging, os
from dotenv import dotenv_values

configFileValues = dotenv_values("bot.config")

logging.basicConfig(filename=configFileValues["logfilename"])