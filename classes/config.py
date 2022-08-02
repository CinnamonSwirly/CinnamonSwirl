from warnings import warn as console_warning
from configparser import ConfigParser
from os import path

__all__ = "Configuration",


class Configuration(ConfigParser):
    def __init__(self, filename: str):
        """
        Creates a configparser object from the filename provided. If no file actually exists by the name given,
        one will be created
        :param filename: The name of the file containing configuration data.
        """
        super().__init__()
        self.filename = filename

        try:
            assert path.exists(f"{filename}")
        except AssertionError:
            console_warning(f"No {filename} file found. Generating a default one instead.", Warning)
            self.fallback()

        try:
            self.read(filename)
        except MemoryError:
            raise MemoryError("Insufficient memory to import configuration file. The program cannot continue.")

    def fallback(self, category: str = None, item: str = None):
        """
        Sets part or all of the configuration to default during runtime. Will create a default config file if both
        keywords are None
        :exception SyntaxError Occurs if you specify item but don't specify category
        :keyword category Specify a string if you wish to set all values in the specified category to default
        :keyword item Specify a string if you wish to set a specific item to default. Requires category to be string
        :type category: str
        :type item: str
        """
        default_config = {
            "LOGGING": {
                "loggingLevel": "DEBUG"
            },
            "DATABASE": {
                "connectionString": "mongodb://localhost:27017/",
                "databaseName": "CinnamonSwirl",
                "username": "",
                "password": ""
            },
            "DISCORD": {
                "clientID": "",
                "token": ""
            }
        }
        if category is None and item is not None:
            raise SyntaxError("classes.config.Configuration.fallback must be either called with nothing, "
                              "called with only a category or called with both a category and item.")

        if category is None and item is None:
            for key in default_config.keys():
                for subkey in default_config[key].keys():
                    self[key] = {}
                    self[key][subkey] = default_config[key][subkey]
                    with open(file=self.filename, mode="w") as file:
                        self.write(file)

        if category is not None and item is None:
            assert category in default_config.keys()
            self[category] = {}
            for subkey in default_config[category].keys():
                self[category][subkey] = default_config[category][subkey]

        if category is not None and item is not None:
            assert category in default_config.keys()
            assert item in default_config[category].keys()
            self[category][item] = default_config[category][item]
