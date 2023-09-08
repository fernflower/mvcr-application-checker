"""
Read requests from the message queue, collect application status, post status update message

Ideas borrowed from https://github.com/fernflower/trvalypobytexamchecker/blob/main/src/fetcher/a2exams_fetcher.py

"""
import logging
import signal

from fetcher.config import URL, RABBIT_HOST, RABBIT_USER, RABBIT_PASSWORD
from fetcher.browser import Browser
from fetcher.messaging import Messaging
from fetcher.application_processor import ApplicationProcessor


# Set up logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def main():
    """Connect to the message queue, run fetch for the application data, post back status"""
    browser_instance = Browser()
    messaging_instance = Messaging(RABBIT_HOST, RABBIT_USER, RABBIT_PASSWORD)
    processor = ApplicationProcessor(messaging=messaging_instance, browser=browser_instance, url=URL)

    # Register the signal handlers
    signal.signal(signal.SIGINT, lambda s, f: processor.shutdown())
    signal.signal(signal.SIGTERM, lambda s, f: processor.shutdown())

    # Connect to RabbitMQ & set up
    messaging_instance.connect()
    messaging_instance.setup_queues("ApplicationFetchQueue", "StatusUpdateQueue")

    # Start processing requests
    messaging_instance.consume_messages("ApplicationFetchQueue", processor.callback)


if __name__ == "__main__":
    main()