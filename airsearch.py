import argparse
import aiohttp
import asyncio
import signal
from urllib import parse
from sys import stdout
from typing import Iterator
from aiohttp.client_exceptions import *

import warnings
warnings.simplefilter("ignore")


class Fuzzer:
    def __init__(self, req, printer, dict, show_codes, hide_codes, recursive=False) -> None:
        self.req = req
        self.out = printer
        self.dict = dict
        self.show = show_codes
        self.hide = hide_codes
        self.recursive = recursive

        self.running = asyncio.Event()
        self.directories = asyncio.Queue()
        self.dict_cursor = 0
        self.tasks = set()

    async def check_path(self, path):
        await self.running.wait()

        task = asyncio.ensure_future(self.req.get(path))
        task.add_done_callback(self.handle_result)
        task.add_done_callback(self.tasks.remove)
        self.tasks.add(task)

    def handle_result(self, result):
        try:
            resp = result.result()
            if resp.status == 200:
                self.add_directory(resp.url.path)
            elif 'Location' in resp.headers.keys():
                location = parse.urlparse(resp.headers['Location'])
                if location.hostname in self.req.base_url:
                    self.add_directory(location.path)

            if len(self.show) > 0:
                if int(resp) in self.show:
                    self.out.print_status_report(resp)
            else:
                if int(resp) not in self.hide:
                    self.out.print_status_report(resp)
        except ServerDisconnectedError as e:
            # self.out.print_error('ServerDisconnectedError', e.message)
            pass
        except ClientOSError or ClientConnectorError as e:
            self.out.print_error(e.__class__.__name__, e.strerror)
        except InvalidURL as e:
            self.out.print_error('InvalidURL', e.url)
        except ServerTimeoutError:
            pass

    def add_directory(self, path):
        if self.recursive == False:
            return False
        if path.endswith('/') and path != '/':
            if self.current_dir == '':
                self.directories.put_nowait(path)
            else:
                self.directories.put_nowait(self.current_dir + path)
            return True
        else:
            return False

    def pause(self):
        self.running.clear()

    def resume(self):
        self.running.set()

    async def start(self) -> None:
        self.resume()
        self.directories.put_nowait('')
        cursor = self.dict_cursor

        while self.directories.qsize() > 0:
            self.current_dir = self.directories.get_nowait()
            if len(self.current_dir) > 0:
                self.out.print_info(f'\nCurrent directory: {self.current_dir}')

            while cursor < len(self.dict):
                entry = self.dict[cursor]
                asyncio.ensure_future(
                    self.check_path(self.current_dir + entry))
                cursor += 1

            await asyncio.sleep(1)
            while self.tasks:
                await asyncio.sleep(1)

            cursor = 0

        await self.req.session.close()


class Controller():
    def __init__(self, args, printer) -> None:
        self._parse_args(args)
        self.loop = asyncio.get_event_loop()
        self.printer = printer

        try:
            requester = Requester(
                self.url, self.cookie, self.ua, self.concurrency, self.proxy, self.timeout, self.redirect)
            self.fuzzer = Fuzzer(requester, self.printer, self.fuzz_dict,
                                 self.show, self.hide, self.recursive)
            self.print_config()

            t = asyncio.ensure_future(self.fuzzer.start())
            self.loop.add_signal_handler(
                signal.SIGINT, self.handle_interrupt)
            self.loop.run_until_complete(t)
        except RuntimeError as why:
            print(why)

    def _parse_args(self, args):
        self.url = args.url
        if not self.url.startswith('http'):
            self.url = 'http://' + self.url

        self.show = []
        self.hide = [404]
        if args.status != None:
            for s in args.status.split(','):
                if s.startswith('0'):
                    self.hide.append(int(s[1:]))
                else:
                    self.show.append(int(s))

        try:
            exts = ''
            if args.extensions != None:
                exts = args.extensions.split(',')
            self.fuzz_dict = self.init_dict(args.wordlist, exts)
        except FileNotFoundError:
            self.printer.print_error(
                'FileNotFoundError', 'The wordlist file does not exists.')
            exit(0)

        self.extensions = args.extensions or ''

        if args.proxy is not None and not args.proxy.startswith('http'):
            self.proxy = f'http://{args.proxy}'
        else:
            self.proxy = args.proxy

        self.concurrency = args.t
        self.timeout = args.timeout
        self.cookie = args.cookie or ''
        self.ua = args.ua or ''
        self.redirect = args.redirect
        self.recursive = args.recursive

    def init_dict(self, fpath, extensions) -> Iterator[str]:
        """读取字典文件到内存，返回迭代器"""
        dict = set()
        with open(fpath) as dict_file:
            for line in dict_file.readlines():
                if '%EXT%' in line and len(extensions) > 0:
                    dict.update([line.replace('%EXT%', e).rstrip()
                                 for e in extensions])
                else:
                    dict.add(line.rstrip())
        return list(dict)

    def print_config(self) -> None:
        config_str = f'''
        Target: {self.url}
        Wordlist Size: {len(self.fuzz_dict)}
        Show Status: {self.show}
        Hide Status: {self.hide}
        '''
        self.printer.print_info(config_str)

    def handle_interrupt(self) -> None:
        fuzzer = self.fuzzer
        fuzzer.pause()
        try:
            while True:
                self.printer.print_inline(
                    f'Unfinished tasks: {len(fuzzer.tasks)}\n[q]uit / [c]ontinue: ')

                option = input()
                if option.lower() == 'q':
                    exit(0)
                elif option.lower() == 'c':
                    fuzzer.resume()
                    return
                else:
                    continue
        except KeyboardInterrupt or SystemExit:
            # 由controller退出程序，关闭session等资源
            raise KeyboardInterrupt


class Requester():
    def __init__(self, url, cookie, ua, limit, proxy, timeout=10, redirect=False) -> None:
        self.base_url = url
        self.proxy = proxy
        self.redirect = redirect
        self.timeout = aiohttp.ClientTimeout(connect=timeout)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
            "Accept-Language": "*",
            "Accept-Encoding": "*",
            "Cache-Control": "max-age=0",
        }
        if cookie != None:
            self.set_header('Cookie', cookie)
        if ua != None:
            self.set_header('User-Agent', ua)

        cli_connector = aiohttp.TCPConnector(limit=limit, ttl_dns_cache=300)
        self.session = aiohttp.ClientSession(
            connector=cli_connector, headers=self.headers)

    def set_header(self, header, value) -> None:
        self.headers[header] = value

    async def get(self, path):
        url = parse.urljoin(self.base_url, path)
        async with self.session.get(url, proxy=self.proxy, timeout=self.timeout, allow_redirects=self.redirect) as resp:
            return Response(resp.url, resp.status, resp.reason, resp.headers, await resp.content.read())


class Response():
    def __init__(self, url, status, reason, headers, body):
        self.url = url
        self.status = status
        self.reason = reason
        self.headers = headers
        self.body = body

    def __str__(self):
        return self.body

    def __int__(self):
        return self.status

    def __eq__(self, other):
        return self.status == other.status and self.body == other.body

    def __len__(self):
        return len(self.body)

    def __hash__(self):
        return hash(self.body)


class Printer():
    RED = '\033[91m{}\033[0;0m'
    GREEN = '\033[92m{}\033[0;0m'
    YELLOW = '\033[93m{}\033[0;0m'
    BLUE = '\033[94m{}\033[0;0m'
    MAGENTA = '\033[95m{}\033[0;0m'

    def __init__(self) -> None:
        self.last_inline = False

    def print_inline(self, string):
        """行内打印，即先清空当前行再进行更新"""
        stdout.write('\033[1K')
        stdout.write('\033[0G')
        stdout.write(string)
        stdout.flush()
        self.last_inline = True

    def print_newline(self, string):
        if self.last_inline == True:
            stdout.write('\033[1K')
            stdout.write('\033[0G')
        stdout.write(string + '\n')
        stdout.flush()
        self.last_inline = False

    def print_status_report(self, resp):
        if len(resp) < 1024:
            length = f'{len(resp)}B'
        else:
            length = f'{len(resp)/1024:.1f}KB'
        message = f'[{resp.status}] -- {length:<6} -- {resp.url.path}'
        if 200 <= resp.status < 300:
            message = self.GREEN.format(message)
        elif 300 <= resp.status < 400:
            message = self.BLUE.format(
                message) + ' => ' + resp.headers['Location']
        elif 500 <= resp.status:
            message = self.YELLOW.format(message)

        self.print_newline(message)

    def print_error(self, type, detail):
        message = self.RED.format(f'[{type}] -- {detail}')
        self.print_newline(message)

    def print_info(self, message):
        self.print_newline(self.MAGENTA.format(message))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help='target url')
    parser.add_argument('-w', '--wordlist', required=True,
                        help='wordlist path')
    parser.add_argument('-t', type=int, default=100,
                        help='maximum number of concurrent connections, default is 100')
    parser.add_argument(
        '-s', '--status', help='show status codes, or exclude status codes starting with 0\nExample: -s 0404,0403')
    parser.add_argument('-p', '--proxy', help='http proxy')
    parser.add_argument('-e', '--extensions', help='file extensions')
    parser.add_argument('-r', '--recursive',
                        action='store_true', help='recursive mode')
    parser.add_argument('--redirect', action='store_true',
                        help='allow redirect')
    parser.add_argument('--ua', help='User-Agent')
    parser.add_argument('--cookie', help='set request cookie')
    parser.add_argument('--timeout', type=int, help='timeout')
    args = parser.parse_args()

    Controller(args, Printer())
