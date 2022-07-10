import logging
import warnings
from os import path, makedirs
from classes import Configuration

__all__ = "Log",


class Log:
    def __init__(self, configuration_file: Configuration):
        # In case the slashes here are confusing, it merges the two so we get path\to\directory\log.file
        logging_file_path = f"{configuration_file['LOGGING']['logFileDirectory']}\\" \
                              f"{configuration_file['LOGGING']['logFileName']}"
        # TODO: There's a chance someone puts ..\..\path\to\somewhere\they\shouldn't\be

        if not path.exists(logging_file_path):
            try:
                directories_to_create = configuration_file['LOGGING']['logFileDirectory']
                makedirs(f"{directories_to_create}")
            except FileExistsError:
                pass
            except OSError:
                warnings.warn("Invalid logging file path specified in config file. Reverting to default instead.",
                              Warning)
                # TODO: Tell configuration_file to use default config

            try:
                create_logging_file = open(f"{logging_file_path}", "x")
            except OSError:
                warnings.warn(f"The OS reports {logging_file_path} doesn't exist, but when we tried to create the file,"
                              f" we were given an error. We will use a default config instead.")
                # TODO: Tell configuration_file to use default config

            assert path.exists(logging_file_path)

        self.path = logging_file_path

    def __str__(self):
        return self.path
