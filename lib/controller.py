import asyncio
from queue import Queue
from urllib import parse
import signal

from aiohttp.client_exceptions import ClientConnectionError

from lib.fuzzer import Fuzzer
from lib.response import Response
from lib.requester import Requester
from lib.option import Option
from lib.output import Output


class Controller:
    def __init__(self, option: Option, output: Output) -> None:
        self.out = output

        self.targets = option.targets
        self.include_status = option.include_status
        self.exclude_status = option.exclude_status
        self.exclude_sizes = option.exclude_sizes
        self.exclude_texts = option.exclude_texts
        self.fuzz_dict = option.wordlist

        self.proxy = option.proxy
        self.limit = option.limit
        self.timeout = option.timeout
        self.headers = option.headers
        self.redirect = option.redirect
        self.recursive = option.recursive
        self.max_depth = option.max_depth
        self.exclude_response = option.exclude_response

        self.use_random_agents = option.use_random_agents
        if self.use_random_agents:
            self.random_agents = option.random_agents

        self.directories = Queue()
        self.current_dir = ''
        if len(option.subdirs) > 0:
            for subdir in option.subdirs:
                self.directories.put_nowait(subdir)

        self.current_fuzzer = None
        self.loop = asyncio.get_event_loop()
        self.loop.add_signal_handler(signal.SIGINT, self.handle_interrupt)
        self.start()

    def start(self) -> None:
        for target in self.targets:
            self.out.print_target(target)
            requester = Requester(
                target,
                self.limit,
                self.proxy,
                self.timeout,
                self.redirect
            )
            # 如果指定了子目录，就忽略根目录
            if self.directories.qsize() == 0:
                self.directories.put_nowait('/')

            for name, value in self.headers.items():
                requester.set_header(name, value)

            if self.use_random_agents:
                requester.set_random_agents(self.random_agents)

            requester.init_session()

            try:
                # Test request to see if server is up
                self.loop.run_until_complete(requester.get(''))
            except ClientConnectionError:
                print(f'{target} is not up')
                continue

            fuzzer = self.current_fuzzer = Fuzzer(
                requester,
                self.fuzz_dict,
                self.match_callback,
                self.not_found_callback,
                self.error_callback,
                self.exclude_response
            )
            fuzzer.resume()
            while not self.directories.empty():
                self.current_dir = self.directories.get_nowait()
                self.out.init_task(self.current_dir)
                self.loop.run_until_complete(fuzzer.start(self.current_dir))
                self.out.finish()

            self.loop.run_until_complete(requester.close())

    def match_callback(self, resp: Response, entry: str) -> None:
        if not self.valid(resp):
            self.out.step()
            return

        if self.recursive:
            if resp.redirect:
                self.add_redirect_directory(entry, resp.redirect)
            else:
                self.add_directory(entry)

        self.out.print_result(resp, parse.urljoin(self.current_dir, entry.lstrip('/')))

    def not_found_callback(self, entry: str) -> None:
        # self.out.progress.print(f'Not Found: {entry}')
        self.out.step()

    def error_callback(self, entry: str, err: str) -> None:
        # self.out.progress.print(f'[red]{err}: {entry}')
        self.out.record_error(err)

    def add_directory(self, path: str) -> bool:
        # 是否将路径视为目录，取决于字典
        if not path.endswith('/'):
            return False

        dirs = []
        for d in path.split('/'):
            if d != '':
                dirs.append(d)
        for i in range(1, len(dirs) + 1):
            directory = self.current_dir + '/'.join(dirs[:i]) + '/'
            if self.max_depth and directory.lstrip('/').count('/') > self.max_depth:
                break
            self.directories.put_nowait(directory)
        return True

    def add_redirect_directory(self, path: str, redirect: str) -> bool:
        # 如果是 dir -> dir/ 这种跳转情况，将 dir/ 加入队列
        base_path = parse.urljoin(self.current_dir, path)
        redirect_path = parse.urlparse(redirect).path

        if redirect_path.strip('/') == base_path.strip('/'):
            return self.add_directory(path + '/')

        return False

    def valid(self, resp: Response) -> bool:
        # 根据命令选项过滤结果
        if resp.status in self.exclude_status:
            return False
        if self.include_status and resp.status not in self.include_status:
            return False
        if self.exclude_sizes and resp.size in self.exclude_sizes:
            return False
        if self.exclude_texts:
            for exclude_text in self.exclude_texts:
                if exclude_text in str(resp):
                    return False

        return True

    def handle_interrupt(self) -> None:
        self.current_fuzzer.pause()
        try:
            while True:
                self.out.progress.print(f'Fuzzer paused, you can choose \[q]uit or \[c]ontinue', style='dim red')
                option = input()
                if option.lower() == 'q':
                    self.out.finish(interrupt=True)
                    exit(0)
                elif option.lower() == 'c':
                    self.current_fuzzer.resume()
                    return
                else:
                    continue
        except KeyboardInterrupt or SystemExit:
            raise KeyboardInterrupt
