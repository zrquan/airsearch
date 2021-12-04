import asyncio
import random
from urllib import parse

from lib.response import Response


def rand_string(length: int) -> str:
    seq = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join([random.choice(seq) for _ in range(length)])


class Inspector(object):
    def __init__(self, requester, calibration=None):
        self.requester = requester
        self.calibration = calibration
        self.response = None
        self.location = None
        self.hash = None
        self.setup()

    def setup(self):
        loop = asyncio.get_event_loop()
        first_path = self.calibration if self.calibration else rand_string(8)
        first_response = loop.run_until_complete(self.requester.get(first_path))
        self.response = first_response

        if self.response.status == 404:
            # Using the response status code is enough :-}
            return
        if self.response.redirect:
            self.location = parse.urlparse(self.response.redirect).path

        self.hash = hash(first_response)

    def scan(self, response: Response) -> bool:
        if self.response.status == response.status == 404:
            return False
        if self.response.status != response.status:
            return True

        if response.redirect and self.location == parse.urlparse(response.redirect).path:
            return False

        if self.hash and hash(response) == self.hash:
            return False

        return True
