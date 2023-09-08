from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters
from telegram.error import NetworkError
import asyncio
import logging
import signal

from bot.loader import loop, bot, db, rabbit
from bot.handlers import start_command, button, help_command, unknown, status_command, unsubscribe_command, subscribe_command
from bot import monitor

MAX_RETRIES = 15  # maximum number bot of connection retries
RETRY_DELAY = 5  # delay (in seconds) between retries

# Set up logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Instantiate application scheduler
app_monitor = monitor.ApplicationMonitor(db=db, rabbit=rabbit)


async def shutdown():
    logger.info("Shutting down scheduler...")
    app_monitor.stop()
    # Stop bot
    logger.info("Shutting down bot...")
    await bot.updater.stop()
    await bot.stop()
    await bot.shutdown()
    # Terminate rabbit & db connections
    logger.info("Shutting down rabbit...")
    await rabbit.close()
    logger.info("Shutting down db...")
    await db.close()
    logger.info("Done.")


async def main():
    # Connect to postgres
    await db.connect()
    # Connect to rabbit
    await rabbit.connect()

    # Install signal handlers for SIGINT and SIGTERM
    signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(shutdown()))
    signal.signal(signal.SIGTERM, lambda s, f: asyncio.create_task(shutdown()))

    # Register command and message handlers
    bot.add_handler(CommandHandler("start", start_command, has_args=False))
    bot.add_handler(CallbackQueryHandler(button))
    bot.add_handler(CommandHandler("status", status_command, has_args=False))
    bot.add_handler(CommandHandler("subscribe", subscribe_command))
    bot.add_handler(CommandHandler("unsubscribe", unsubscribe_command, has_args=False))
    bot.add_handler(CommandHandler("help", help_command, has_args=False))
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    bot.add_handler(unknown_handler)

    # Run the bot
    logger.info("Starting telegram bot")
    for retry in range(1, MAX_RETRIES + 1):
        try:
            await bot.initialize()
            await bot.updater.start_polling()
            await bot.start()
            break
        except NetworkError as e:
            if retry < MAX_RETRIES:
                logger.error(f"Failed to start bot due to network error: {e}")
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries reached. Could not start telegram bot")
                raise

    # Run RabbitMQ consumer
    await rabbit.consume_messages()

    # Start ApplicationMonitor
    await asyncio.sleep(15)  # wait some time before running scheduler
    await app_monitor.start()

    logger.info("Main loop has exited")


if __name__ == "__main__":
    loop.run_until_complete(main())
