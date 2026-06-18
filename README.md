# monitory

> System monitoring by console

A terminal system resource monitor, no GUI — in the spirit of `htop`, with panels
for CPU, memory, disk, network and temperatures. The layout adapts to the
available terminal size in real time, and works the same from a plain terminal
or inside `tmux`.

It's a custom TUI built with [`rich`](https://github.com/Textualize/rich) and
[`psutil`](https://github.com/giampaolo/psutil), with no dependency on any
external monitoring tool.

## Metrics

- **CPU**: total usage, per-core usage, load average.
- **Memory**: RAM and swap (usage and percentage), plus a small breakdown of
  RAM usage by process group: **System**, **Docker**, **Py+JVM** (Python and
  Java processes combined).
- **Disk**: usage per mount point (excluding `/boot` and `/boot/efi`).
- **Network**: up/down rates per interface — only interfaces that are up and
  have actually carried traffic are shown.
- **Temperatures**: sensors available via `hwmon`, grouped under short,
  recognizable names (`CPU`, `SSD`, `Chipset`, `WiFi`, `GPU`, `Battery`,
  `System`) instead of raw, distro-specific sensor labels.

## Adaptive layout

The program recalculates the layout on every refresh based on the terminal's
actual width and height. CPU, Memory and Disk are shown whenever there is
room for them; Network and Temperatures are only added if there's still
space left over (Network takes priority if there's only room for one):

| Terminal size                                  | Layout                                                                    |
|--------------------------------------------------|------------------------------------------------------------------------------|
| Width ≥ 110 columns                               | 3 columns: CPU \| Memory \| Disk, with Network/Temperatures below if there's room |
| Width < 110 with enough height                    | CPU, Memory and Disk stacked in a single column, Network/Temperatures below if there's room |
| Very small terminal (not enough room for the above) | Compact "Summary" panel (CPU/RAM/Disk/Net/Temp in 4 lines)                |

Resizing the window or the `tmux` pane while the program is running
recalculates the layout automatically on the next refresh — no restart needed.

## Installation

Requirements: Linux + Python 3.9 or newer (with the `venv` module available).

```bash
git clone <repo-url> monitory
cd monitory
./install.sh
```

The `install.sh` script:

1. Checks that you have Python 3.9+.
2. Creates a project-local virtual environment in `.venv/` (doesn't touch
   system packages).
3. Installs the dependencies (`rich`, `psutil`).
4. Creates a `monitory` symlink in `~/.local/bin/`, ready to use like any
   other system command.
5. Warns you if `~/.local/bin` isn't in your `PATH` and tells you how to add it.

To uninstall:

```bash
./install.sh --uninstall
```

This removes the virtual environment and the symlink, without touching
anything else on your system.

## Usage

Run from any terminal or inside a `tmux` session:

```bash
monitory
```

### Options

```bash
monitory -n 2        # refresh every 2 seconds (default: 1.5)
monitory --help      # see all options
```

### Quit

- `q`
- `Ctrl+C`

## Project structure

```
monitory/
├── install.sh                  # installer: venv + dependencies + global command
├── pyproject.toml              # metadata + monitory command entry point
└── monitory/
    ├── __main__.py              # main loop: rich Live, keyboard handling, interval
    ├── metrics.py                # metric collection via psutil (CPU, RAM, disk, network, temp, processes)
    └── ui.py                     # rich layout construction and adaptive-sizing logic
```

## Notes

- Temperatures are read directly from `/sys/class/hwmon` via `psutil`; it does
  not require `lm-sensors` to be installed. If the hardware exposes no
  sensors, the panel is simply skipped.
- The loopback interface (`lo`) is always excluded from the network panel.
- Mount points of type `tmpfs`, `overlay`, `proc`, etc., as well as `/boot`
  and `/boot/efi`, are excluded from the disk panel.
- Built for Linux (sensor reads via `hwmon`, keyboard handling via
  `termios`/`tty`).

## Contributing

Pull requests welcome: new panels (GPU, battery, containers), color themes,
support for more distros/sensors, whatever you've got. The code is small and
split into `metrics.py` (data collection) and `ui.py` (presentation), so
adding a new panel is mostly a matter of adding one function to each file.
