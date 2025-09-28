import logging
import sys
import os


def configure_logs(format: str ='%(asctime)s - %(levelname)s - %(message)s', level: int = logging.INFO):
    """
    Configure loggers for the bot and database connections.

    This function sets up logging to the console, a file named "bot.log", and a file named "db.log".
    Logs are formatted according to the specified format string, and the logging level is set to the specified level.
    """
    os.makedirs('logs', exist_ok=True)

    # Create a console handler and set its level and format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(format))

    # Create a file handler for the bot logs and set its level and format
    file_handler_bot = logging.FileHandler("./logs/bot.log", encoding="utf-8")
    file_handler_bot.setLevel(level)
    file_handler_bot.setFormatter(logging.Formatter(format))

    # Create a file handler for the database logs and set its level and format
    file_handler_db = logging.FileHandler("./logs/db.log", encoding="utf-8")
    file_handler_db.setLevel(level)
    file_handler_db.setFormatter(logging.Formatter(format))

    # Get the root logger and set its level and add the handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)

    # Get the aiogram logger, set its level and add the bot file handler
    aiogram_logger = logging.getLogger("aiogram")
    aiogram_logger.setLevel(level)
    aiogram_logger.addHandler(file_handler_bot)
    aiogram_logger.propagate = False

    # Get the sqlalchemy logger, set its level and add the db file handler
    sqlalchemy_logger = logging.getLogger("sqlalchemy")
    sqlalchemy_logger.setLevel(level)
    sqlalchemy_logger.addHandler(file_handler_db)
    sqlalchemy_logger.propagate = False
