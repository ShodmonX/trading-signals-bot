from app.main import main
from app.logger import configure_logs
import asyncio
import logging


if __name__ == "__main__":
    configure_logs()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot ishdan to'xtadi!")
    except Exception as e:
        logging.exception(e)