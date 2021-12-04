import asyncio
from typing import Callable
from urllib import parse
import functools

from lib.requester import Requester
from lib.inspector import Inspector
from lib.response import Response
from lib.dictionary import Dictionary


class Fuzzer:
    def __init__(
            self,
            requester: Requester,
            fuzz_dict: Dictionary,
            match_callback: Callable[[Response, str], None],
            not_found_callback: Callable[[str], None],
            error_callback: Callable[[str, str], None],
            exclude_response: str = None
    ) -> None:

        self.requester = requester
        self.fuzz_dict = fuzz_dict
        self.match_callback = match_callback
        self.not_found_callback = not_found_callback
        self.error_callback = error_callback
        self.current_dir = ''

        self.job_num = 0
        self.running = asyncio.Event()
        self.inspector = Inspector(requester, exclude_response)

    def set_current_dir(self, directory: str) -> None:
        self.current_dir = directory

    async def start(self, base_path: str = None) -> None:
        self.fuzz_dict.reset()
        if base_path:
            self.set_current_dir(base_path)

        for entry in self.fuzz_dict:
            self.job_num += 1
            asyncio.create_task(self.search(entry))

        # 等待所有任务完成
        while self.job_num > 0:
            await asyncio.sleep(1)

    async def search(self, entry: str) -> None:
        await self.running.wait()

        path = parse.urljoin(self.current_dir, entry)
        task = asyncio.create_task(self.requester.get(path))
        task.add_done_callback(
            functools.partial(self.handle_resp, entry))

    def pause(self) -> None:
        self.running.clear()

    def resume(self) -> None:
        self.running.set()

    def handle_resp(self, entry: str, result: asyncio.Task) -> None:
        """
        处理任务结果，根据情况调用 callback
        @param entry: 当前任务对应的字典项
        @param result: 任务结果
        """
        self.job_num -= 1
        try:
            resp = result.result()
            status = self.inspector.scan(resp)

            if status:
                self.match_callback(resp, entry)
            else:
                self.not_found_callback(entry)
        except Exception as e:
            self.error_callback(entry, e.__class__.__name__)
