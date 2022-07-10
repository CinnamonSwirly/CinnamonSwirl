import configparser
import warnings
from os import path

__all__ = "Configuration",


class Configuration:
    def __init__(self, filename: str):
        self.filename = filename
        self.configuration = configparser.ConfigParser()

        try:
            assert path.exists(f"{filename}")
        except AssertionError:
            warnings.warn(f"No {filename} file found. Generating a default one instead.", Warning)
            self.fallback(everything=True)

        try:
            self.configuration.read(filename)
        except MemoryError:
            raise MemoryError("Insufficient memory to import configuration file. The program cannot continue.")

        try:
            assert 'LOGGING' in self.configuration
        except AssertionError:
            warnings.warn(f"No LOGGING section in {filename} file. Generating a default one instead.",
                          Warning)
            self.fallback(category='LOGGING')

        for key in ['logFileDirectory', 'logFileName', 'loggingLevel']:
            try:
                assert key in self.configuration['LOGGING']
            except AssertionError:
                warnings.warn(f"No {key} line found in {filename} file. Going with the default instead.",
                              Warning)
                self.fallback(category='LOGGING', item=key)

        try:
            assert self.configuration['LOGGING']['loggingLevel'] in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        except AssertionError:
            warnings.warn("Invalid logging level specified in config file. Reverting to WARNING instead.", Warning)
            self.fallback(category='LOGGING', item='loggingLevel')

    def __getitem__(self, item):
        return self.configuration[item]

    def fallback(self, category: str = None, item: str = None, everything: bool = False):
        default_config = {
            "LOGGING": {
                "logFileDirectory": "logs",
                "logFileName": "cinnamonswirl.log",
                "loggingLevel": "DEBUG"
            }
        }
        # TODO: Can this be made a bit cleaner?
        if everything:
            for key in default_config.keys():
                self.configuration[key] = {}
                for subkey in default_config[key]:
                    self.configuration[key][subkey] = default_config[key][subkey]
            with open(file=self.filename, mode="w") as file:
                self.configuration.write(file)
            return
        else:
            assert category in default_config.keys()
            if item is None:
                self.configuration[category] = {}
                for key in default_config[category].keys():
                    self.configuration[category][key] = default_config[category][key]
                with open(file=self.filename, mode="w") as file:
                    self.configuration.write(file)
                return

            assert item in default_config[category].keys()
            self.configuration[category][item] = default_config[category][item]
