from argparse import ArgumentParser, Namespace

from lib.dictionary import Dictionary
from os import path


class Option:
    def __init__(self, script_path: str) -> None:
        self.script_path = script_path
        self.default_max_depth = 3
        self.default_conn_limit = 100
        self.default_extensions = ['html']

        option = self.parse_arguments()

        self.targets = self.parse_targets(option.targets)
        self.include_status = self.parse_status_codes(option.include_status) if option.include_status else []
        self.exclude_status = self.parse_status_codes(option.exclude_status) if option.exclude_status else []

        try:
            if option.extensions:
                self.extensions = option.extensions.split(',')
                self.wordlist = Dictionary(option.wordlist, self.extensions)
            else:
                self.wordlist = Dictionary(option.wordlist, self.default_extensions)
        except FileNotFoundError:
            print('The wordlist file does not exists.')
            exit(0)

        self.use_random_agents = option.use_random_agents
        if self.use_random_agents:
            self.random_agents = []
            with open(path.join(self.script_path, 'resources/user-agents.txt')) as f:
                for line in f.readlines():
                    self.random_agents.append(line.strip())

        if option.exclude_sizes:
            self.exclude_sizes = [s.strip().upper()
                                  for s in option.exclude_sizes.split(',')]
        else:
            self.exclude_sizes = []

        if option.exclude_texts:
            self.exclude_texts = option.exclude_texts.split(',')
        else:
            self.exclude_texts = []

        self.subdirs = []
        if option.subdirs:
            for subdir in option.subdirs.split(','):
                subdir = subdir.strip()
                if not subdir.endswith('/'):
                    subdir += '/'
                self.subdirs.append(subdir)

        if option.proxy is not None and not option.proxy.startswith('http'):
            self.proxy = f'http://{option.proxy}'
        else:
            self.proxy = option.proxy

        self.limit = option.limit
        self.timeout = option.timeout

        self.headers = {}
        if option.headers:
            for h in option.headers:
                hn, hv = h.split(':')
                self.headers[hn.strip()] = hv.strip()

        self.redirect = option.redirect
        self.recursive = option.recursive
        self.max_depth = option.max_depth
        self.exclude_response = option.exclude_response

    @staticmethod
    def parse_status_codes(raw_status_codes: str) -> list:
        status_codes = []
        for status_code in raw_status_codes.split(','):
            try:
                if '-' in status_code:
                    begin, end = (int(code) for code in status_code.split('-'))
                    status_codes.extend(range(begin, end + 1))
                else:
                    status_codes.append(int(status_code.strip()))
            except ValueError:
                print("Invalid status code or status code range: {0}".format(
                    status_code))
                exit(1)
        return list(set(status_codes))

    @staticmethod
    def parse_targets(raw_target: str) -> list:
        targets = list()
        # todo: cidr
        if raw_target.startswith('http'):
            targets.append(raw_target)
        else:
            try:
                with open(raw_target) as target_file:
                    for item in target_file.readlines():
                        if not item.startswith('http'):
                            item = 'http://' + item
                        targets.append(item)
            except FileNotFoundError:
                print('file not found, or url doesn\'t start with schema')
                exit(0)
        return targets

    def parse_arguments(self) -> Namespace:
        parser = ArgumentParser()

        parser.add_argument('targets', help='target URL or list file')
        parser.add_argument('-w', '--wordlist', default=path.join(self.script_path, 'resources/dict.txt'),
                            help='wordlist path', metavar='PATH')
        parser.add_argument('-e', '--extensions', help='file extensions')
        parser.add_argument('--subdirs', help='scan sub-directories of the given URL[s] (separated by commas)')
        parser.add_argument('-r', '--recursive',
                            action='store_true', help='recursive mode')
        parser.add_argument('-R', '--max-depth', help='maximum recursion depth', action='store',
                            type=int, dest='max_depth', default=self.default_max_depth)

        # filter
        parser.add_argument('-i', '--include-status', dest='include_status',
                            help='include status codes, separated by commas, support ranges (Example: 200,300-399)')
        parser.add_argument('-x', '--exclude-status', dest='exclude_status',
                            help='exclude status codes, separated by commas, support ranges (Example: 301,500-599)')
        parser.add_argument('--exclude-sizes', dest='exclude_sizes',
                            help='exclude responses by sizes, separated by commas (Example: 123B,4KB)')
        parser.add_argument('--exclude-texts', dest='exclude_texts',
                            help='exclude responses by texts, separated by commas (Example: "Not found", "Error")')
        parser.add_argument('--exclude-response', dest='exclude_response',
                            help='exclude responses by response of this page (path as input)')

        # requester
        parser.add_argument('-H', '--header', action='append', dest='headers',
                            help='HTTP request header, support multiple flags (Example: -H "Referer: example.com" -H "Accept: */*")')
        parser.add_argument('--random-agent', dest='use_random_agents', action='store_true',
                            help='choose a random User-Agent for each request')
        parser.add_argument('-p', '--proxy', help='HTTP proxy')
        parser.add_argument('--limit', type=int, default=self.default_conn_limit, metavar='SECOND',
                            help='maximum number of concurrent connections, default is 100')
        parser.add_argument('--redirect', action='store_true',
                            help='follow redirection')
        parser.add_argument('--timeout', type=int,
                            metavar='SECOND', help='timeout of per request')

        return parser.parse_args()
