from urllib.parse import quote


class Dictionary:
    def __init__(self, path: str, extensions: list) -> None:
        self.path = path
        self._index = 0
        self._extensions = extensions
        self._ext_holder = '%EXT%'

        self.build(path, extensions)

    @property
    def last_index(self):
        """最近一个已迭代项的位置"""
        return self._index - 1

    def _safe_quote(self, string) -> str:
        """对中文或其他非ASCII字符编码"""
        return quote(string, safe="!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")

    def build(self, path, ext):
        dict = set()
        with open(path) as dict_file:
            for line in dict_file.readlines():
                if self._ext_holder in line and len(ext) > 0:
                    # 替换后缀
                    for e in ext:
                        _ = line.replace(self._ext_holder, e).rstrip()
                        dict.add(self._safe_quote(_))
                else:
                    _ = line.rstrip()
                    dict.add(self._safe_quote(_))

        self._words = tuple(dict)

    def reset(self):
        self._index = 0

    def __len__(self):
        return len(self._words)

    def __iter__(self):
        return self

    def __next__(self):
        if self._index < len(self):
            self._index += 1
            return self._words[self._index - 1]

        raise StopIteration()
