import warnings
from os import path, makedirs, getcwd
from classes import Configuration

__all__ = "Log",


class Log:
    def __init__(self, configuration_file: Configuration):
        """
        Validates configuration settings around logging, ensures the "logs" directory exists, creates it if it doesn't
        :param configuration_file:
        :return filepath for log file. Intended for use with Logging.basicConfig.
        """
        try:
            assert 'LOGGING' in configuration_file.configuration
        except AssertionError:
            warnings.warn(f"No LOGGING section in {configuration_file.filename} file. "
                          f"Generating a default one instead.",
                          Warning)
            configuration_file.fallback(category='LOGGING')

        for key in ['loggingLevel']:
            try:
                assert key in configuration_file.configuration['LOGGING']
            except AssertionError:
                warnings.warn(f"No {key} line found in {configuration_file.filename} file. "
                              f"Going with the default instead.",
                              Warning)
                configuration_file.fallback(category='LOGGING', item=key)

        try:
            assert configuration_file.configuration['LOGGING']['loggingLevel'] in \
                   ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        except AssertionError:
            warnings.warn("Invalid logging level specified in config file. Reverting to WARNING instead.", Warning)
            configuration_file.fallback(category='LOGGING', item='loggingLevel')

        current_path = getcwd()
        logging_file_path = current_path + "\\logs\\cinnamonswirl.log"

        try:
            assert path.exists(logging_file_path)
        except AssertionError:
            try:
                directories_to_create, tail = logging_file_path.split("\\cinnamonswirl.log")
                makedirs(f"{directories_to_create}")
                open(f"{logging_file_path}", "x")
            except OSError:
                warnings.warn(f"Unable to create {logging_file_path}, verify you have permissions and/or disk space.",
                              Warning)
                raise

        self.path = logging_file_path

    def __str__(self):
        return self.path
