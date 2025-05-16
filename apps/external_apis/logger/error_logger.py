from logging import Logger


class ErrorLoggerHandler:
    def __init__(self, logger: Logger):
        self.logger = logger
        self.logger.setLevel('DEBUG')

    def log_error(self, error: Exception):
        self.logger.error(error)
