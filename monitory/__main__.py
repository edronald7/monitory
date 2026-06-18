import argparse
import select
import sys
import termios
import time
import tty

from rich.console import Console
from rich.live import Live

from .metrics import MetricsCollector
from .ui import build_layout


class RawKeyReader:
    def __enter__(self):
        if not sys.stdin.isatty():
            self._enabled = False
            return self
        self._enabled = True
        self._fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        return self

    def __exit__(self, *exc):
        if self._enabled:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)

    def quit_requested(self):
        if not self._enabled:
            return False
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            return False
        ch = sys.stdin.read(1)
        return ch.lower() == "q"


def parse_args():
    parser = argparse.ArgumentParser(
        prog="monitory",
        description="Terminal system resource monitor, no GUI.",
    )
    parser.add_argument(
        "-n", "--interval", type=float, default=1.5,
        help="seconds between refreshes (default: 1.5)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    console = Console()
    collector = MetricsCollector()

    try:
        with RawKeyReader() as keys:
            with Live(console=console, screen=True, auto_refresh=False) as live:
                while True:
                    snapshot = collector.collect()
                    width, height = console.size
                    layout = build_layout(snapshot, width, height, args.interval)
                    live.update(layout, refresh=True)

                    deadline = time.time() + args.interval
                    while time.time() < deadline:
                        if keys.quit_requested():
                            return
                        time.sleep(0.05)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
