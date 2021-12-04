class Response:
    def __init__(
            self,
            url: str,
            status: int,
            reason: str,
            headers: dict,
            body: bytes
    ) -> None:
        self.url = url
        self.status = status
        self.reason = reason
        self.headers = headers
        self.body = body

    @property
    def redirect(self):
        return self.headers.get('location')

    @property
    def size(self):
        """
        响应包 body 的长度
        @return: 带单位的长度
        """
        base = 1024
        num = len(self.body)
        for x in ['B', 'KB', 'MB', 'GB']:
            if base > num > -base:
                return '%.0f%s' % (num, x)
            num /= base
        return '%.0f%s' % (num, 'TB')

    def __str__(self):
        return bytes.decode(self.body)

    def __int__(self):
        return self.status

    def __eq__(self, other):
        return self.status == other.status and self.body == other.body

    def __len__(self):
        return len(self.body)

    def __hash__(self):
        return hash(self.body)
