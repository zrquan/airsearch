from rich import print
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
)

from lib.option import Option
from lib.response import Response


class Output:
    def __init__(self, option: Option) -> None:
        self.option = option
        self.banner = Panel.fit(
            f'''[magenta]        __   __   ___       __   __       
 /\  | |__) /__` |__   /\  |__) /  ` |__| 
/~~\ | |  \ .__/ |___ /~~\ |  \ \__, |  | 
[/magenta]
[#ffffbe]Extensions:[/#ffffbe] {option.extensions}
[#ffffbe]Wordlist size:[/#ffffbe] {len(option.wordlist)}
[#ffffbe]Connection limit:[/#ffffbe] {option.limit}''', subtitle='by 4shen0ne', subtitle_align='right')
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn('{task.fields[directory]}'),
            BarColumn(bar_width=30),
            TextColumn('[progress.percentage]{task.percentage:>3.0f}%'),
            '|',
            TextColumn('[red]error: {task.fields[error_num]}'),
        )
        self.task = None
        self.current_dir = None
        self.error_num = 0

    def show_banner(self) -> None:
        print(self.banner)

    def init_task(self, current_dir: str) -> None:
        self.current_dir = current_dir
        self.task = self.progress.add_task(
            'fuzz', directory=current_dir, error_num=self.error_num, total=len(self.option.wordlist))
        self.progress.start()

    def finish(self, interrupt: bool = False) -> None:
        if interrupt:
            self.progress.print('Interrupted by user', style='black on red')
        else:
            self.progress.print(
                f'Searching [blue]{self.current_dir}[/blue] finished, [red]{self.error_num}[/red] errors occurred')
        self.progress.update(self.task, visible=False)
        self.progress.stop()

    def print_result(self, resp: Response, path: str) -> None:
        status = resp.status
        if 200 <= status < 300:
            self.progress.print(f'[green]{status} - {resp.size} - {path}')
        elif 300 <= status < 400 and resp.redirect:
            self.progress.print(f'[blue]{status} - {resp.size} - {path}[white] --> {resp.redirect}')
        else:
            self.progress.print(f'[white]{status} - {resp.size} - {path}')
        self.progress.advance(self.task)

    def print_target(self, target: str):
        self.progress.print(f'Target: {target}\n', style='cyan')

    def step(self):
        self.progress.advance(self.task)

    def record_error(self, message: str):
        self.error_num += 1
        # self.progress.print(f'[red]{message}')
        self.progress.update(self.task, error_num=self.error_num)
        self.progress.advance(self.task)
