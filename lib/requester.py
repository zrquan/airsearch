import aiohttp
from urllib import parse
from random import choice

from yarl import URL

from lib.response import Response


class Requester:
    def __init__(
            self,
            url: str,
            limit: int,
            proxy: str,
            timeout: int = 5,
            redirect: bool = False
    ) -> None:
        self.base_url = url
        self.proxy = proxy if proxy else ''
        self.redirect = redirect
        self.limit = limit
        self.timeout = aiohttp.ClientTimeout(connect=timeout)
        self.random_agents = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
            "Accept-Language": "*",
            "Accept-Encoding": "*",
            "Cache-Control": "max-age=0",
        }
        self.session = None

    def init_session(self) -> None:
        connector = aiohttp.TCPConnector(limit=self.limit, ttl_dns_cache=300)
        self.session = aiohttp.ClientSession(connector=connector)

    def set_header(self, header: str, value: str) -> None:
        self.headers[header] = value

    def set_random_agents(self, agents: list) -> None:
        self.random_agents = list(set(agents))

    async def get(self, path: str) -> Response:
        url = URL(parse.urljoin(self.base_url, path), encoded=('%' in path))
        if self.random_agents:
            self.set_header('User-Agent', choice(self.random_agents))
        async with self.session.get(
                url, headers=self.headers, proxy=self.proxy, timeout=self.timeout, allow_redirects=self.redirect
        ) as resp:
            return Response(resp.url, resp.status, resp.reason, resp.headers, await resp.content.read())

    async def close(self) -> None:
        await self.session.close()
