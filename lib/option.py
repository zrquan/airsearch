from argparse import ArgumentParser, Namespace

from lib.dictionary import Dictionary
from os import path
from ipaddress import ip_network, ip_address


class Option:
    def __init__(self, script_path: str) -> None:
        self.script_path = script_path
        self.default_max_depth = 3
        self.default_conn_limit = 100
        self.default_extensions = ['html']

        option = self.parse_arguments()

        try:
            self.targets = self.parse_targets(option.targets)
        except ValueError:
            self.targets = self.parse_targets_file(option.targets)

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
                hn, hv = h.split(': ')
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
        if raw_target.startswith('http'):
            targets.extend([target for target in raw_target.split(',') if target != ''])
        elif 0 < int(raw_target[:raw_target.index('.')]) < 255:
            if '/' in raw_target:
                targets.extend(['http://' + str(_) for _ in ip_network(raw_target, strict=False).hosts()])
            elif '-' in raw_target:
                start, end = (ip_address(ip) for ip in raw_target.split('-'))
                while start <= end:
                    targets.append('http://' + str(start))
                    start += 1
        return targets

    @staticmethod
    def parse_targets_file(raw_target: str) -> list:
        targets = list()
        try:
            with open(raw_target) as target_file:
                for item in target_file.readlines():
                    if not item.startswith('http'):
                        item = 'http://' + item
                    targets.append(item.rstrip())
        except FileNotFoundError:
            print('file not found, or url doesn\'t start with schema')
            exit(0)
        return targets

    def parse_arguments(self) -> Namespace:
        parser = ArgumentParser()

        parser.add_argument('targets', help='target address, support string, file and CIDR format')
        parser.add_argument('-w', '--wordlist', default=path.join(self.script_path, 'resources/dict.txt'),
                            help='customize wordlist, default is "resources/dict.txt"', metavar='PATH')
        parser.add_argument('-e', '--extensions', help='file extensions, separated by commas')
        parser.add_argument('--subdirs', help='specify sub-directories of the given targets, separated by commas')
        parser.add_argument('-r', '--recursive',
                            action='store_true', help='recursive mode')
        parser.add_argument('-R', '--max-depth', help='maximum recursion depth', action='store',
                            type=int, dest='max_depth', default=self.default_max_depth)

        filter_group = parser.add_argument_group("Filter options")

        filter_group.add_argument('-i', '--include-status', dest='include_status',
                                  help='include status codes, separated by commas, support ranges (Example: 200,300-399)')
        filter_group.add_argument('-x', '--exclude-status', dest='exclude_status',
                                  help='exclude status codes, separated by commas, support ranges (Example: 301,500-599)')
        filter_group.add_argument('--exclude-sizes', dest='exclude_sizes',
                                  help='exclude responses by sizes, separated by commas (Example: 123B,4KB)')
        filter_group.add_argument('--exclude-texts', dest='exclude_texts',
                                  help='exclude responses by texts, separated by commas (Example: "Not found", "Error")')
        filter_group.add_argument('--exclude-response', dest='exclude_response',
                                  help='exclude responses by response of this page', metavar='URL')

        req_group = parser.add_argument_group("Request options")

        req_group.add_argument('-H', '--header', action='append', dest='headers',
                               help='HTTP request header, support multiple flags')
        req_group.add_argument('--random-agent', dest='use_random_agents', action='store_true',
                               help='choose a random User-Agent for each request')
        req_group.add_argument('-p', '--proxy', help='HTTP proxy')
        req_group.add_argument('--limit', type=int, default=self.default_conn_limit,
                               help='maximum number of concurrent connections, default is 100')
        req_group.add_argument('--redirect', action='store_true',
                               help='follow redirection')
        req_group.add_argument('--timeout', type=int,
                               metavar='SECOND', help='request timeout')

        return parser.parse_args()
