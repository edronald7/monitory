import datetime

from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .metrics import human_bytes, human_rate

BAR_WIDTH = 20


def _color_for_percent(percent):
    if percent < 60:
        return "green"
    if percent < 85:
        return "yellow"
    return "red"


def bar(percent, width=BAR_WIDTH, suffix=""):
    percent = max(0.0, min(100.0, percent))
    filled = int(round(width * percent / 100))
    color = _color_for_percent(percent)
    text = Text()
    text.append("█" * filled, style=color)
    text.append("░" * (width - filled), style="grey35")
    text.append(f" {percent:5.1f}%")
    if suffix:
        text.append(suffix, style="dim")
    return text


SLOGAN = "System monitoring by console"


def header_renderable(snapshot, width):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    load = snapshot["cpu"]["load"]
    left = Text(f" {snapshot['hostname']} ", style="bold black on cyan")
    if width >= 90:
        left.append(f" {SLOGAN} ", style="dim italic")
    mid = Text(f"uptime {snapshot['uptime']}  load {load[0]:.2f} {load[1]:.2f} {load[2]:.2f}", style="bold white")
    right = Text(now, style="bold white")
    table = Table.grid(expand=True)
    table.add_column(justify="left")
    table.add_column(justify="center", ratio=1)
    table.add_column(justify="right")
    table.add_row(left, mid, right)
    return table


def footer_renderable(interval):
    return Text(f" q: quit  |  Ctrl+C: quit  |  refresh: {interval}s ", style="dim")


def _cpu_core_rows(n_cores, panel_width):
    compact_text = panel_width < 38
    if compact_text:
        cols = max(1, panel_width // 9)
    else:
        cols = 2
    rows = -(-n_cores // cols)
    return compact_text, cols, rows


def cpu_panel(snapshot, panel_width=40):
    cpu = snapshot["cpu"]
    cores = cpu["per_core"]
    compact_text, cols, _ = _cpu_core_rows(len(cores), panel_width)

    grid = Table.grid(expand=True, padding=(0, 1))
    for _ in range(cols):
        grid.add_column(ratio=1)

    if compact_text:
        cells = []
        for i, pct in enumerate(cores):
            color = _color_for_percent(pct)
            cells.append(Text(f"C{i:<2}:", style="dim") + Text(f"{pct:3.0f}%", style=color))
    else:
        cells = []
        for i, pct in enumerate(cores):
            line = Table.grid(expand=True)
            line.add_column(width=5)
            line.add_column(ratio=1)
            line.add_row(Text(f"c{i:<2}", style="dim"), bar(pct, width=5))
            cells.append(line)

    for i in range(0, len(cells), cols):
        row = cells[i:i + cols]
        row += [Text("")] * (cols - len(row))
        grid.add_row(*row)

    title = f"CPU {cpu['overall']:5.1f}%"
    overall_width = max(8, min(20, panel_width - 12))
    body = Table.grid(expand=True)
    body.add_column()
    body.add_row(bar(cpu["overall"], width=overall_width))
    body.add_row(grid)
    return Panel(body, title=title, border_style="blue")


PROCESS_GROUPS = ("System", "Docker", "Py+JVM")


def classify_process(name, user):
    n = name.lower()
    if "docker" in n or "containerd" in n or n in ("runc", "dockerd"):
        return "Docker"
    if "python" in n or "java" in n:
        return "Py+JVM"
    return "System"


def _process_groups_table(snapshot, panel_width):
    totals = {g: 0.0 for g in PROCESS_GROUPS}
    counts = {g: 0 for g in PROCESS_GROUPS}
    for p in snapshot["processes"]:
        group = classify_process(p["name"], p["user"])
        totals[group] += p["mem"]
        counts[group] += 1

    bar_w = 10 if panel_width >= 40 else 4
    order = sorted(PROCESS_GROUPS, key=lambda g: totals[g], reverse=True)
    table = Table(expand=True, box=None, padding=(0, 1), show_edge=False)
    table.add_column("Group", no_wrap=True)
    table.add_column("RAM", ratio=1, no_wrap=True, overflow="crop")
    table.add_column("Proc.", justify="right", width=5)
    for group in order:
        table.add_row(group, bar(totals[group], width=bar_w), str(counts[group]))
    return table


def memory_panel(snapshot, panel_width=40):
    mem = snapshot["memory"]
    show_suffix = panel_width >= 38
    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(width=5)
    grid.add_column(ratio=1, no_wrap=True, overflow="crop")
    ram_suffix = f" {human_bytes(mem['used'])}/{human_bytes(mem['total'])}" if show_suffix else ""
    grid.add_row("RAM", bar(mem["percent"], width=10, suffix=ram_suffix))
    if mem["swap_total"] > 0:
        swap_suffix = f" {human_bytes(mem['swap_used'])}/{human_bytes(mem['swap_total'])}" if show_suffix else ""
        grid.add_row("Swap", bar(mem["swap_percent"], width=10, suffix=swap_suffix))

    body = Table.grid(expand=True)
    body.add_column()
    body.add_row(grid)
    body.add_row(_process_groups_table(snapshot, panel_width))
    return Panel(body, title="Memory", border_style="magenta")


def memory_panel_height(snapshot):
    mem = snapshot["memory"]
    lines = 1  # RAM
    if mem["swap_total"] > 0:
        lines += 1
    lines += 1  # group table header
    lines += len(PROCESS_GROUPS)
    return lines + 2  # borders/title


def disk_panel(snapshot, max_rows=None):
    disks = snapshot["disks"]
    table = Table(expand=True, box=None, padding=(0, 1))
    table.add_column("Mnt", overflow="ellipsis", no_wrap=True, ratio=2)
    table.add_column("Usage", ratio=2)
    table.add_column("Size", justify="right", ratio=1)
    rows = disks if max_rows is None else disks[:max_rows]
    for d in rows:
        table.add_row(d["mountpoint"], bar(d["percent"], width=14), human_bytes(d["total"]))
    if not rows:
        table.add_row("no disks", "", "")
    return Panel(table, title="Disk", border_style="green")


def network_panel(snapshot, max_rows=None):
    ifaces = snapshot["network"]
    table = Table(expand=True, box=None, padding=(0, 1))
    table.add_column("Interface", no_wrap=True)
    table.add_column("↓", justify="right")
    table.add_column("↑", justify="right")
    rows = ifaces if max_rows is None else ifaces[:max_rows]
    for it in rows:
        table.add_row(it["name"], human_rate(it["recv_rate"]), human_rate(it["sent_rate"]))
    return Panel(table, title="Network", border_style="yellow")


def temperature_panel(snapshot, max_rows=None):
    temps = snapshot["temperatures"]
    table = Table(expand=True, box=None, padding=(0, 1))
    table.add_column("Sensor", no_wrap=True, overflow="ellipsis")
    table.add_column("Temp", justify="right")
    rows = temps if max_rows is None else temps[:max_rows]
    for t in rows:
        c = t["current"]
        color = "green" if c < 60 else ("yellow" if c < 80 else "red")
        table.add_row(t["label"], Text(f"{c:.0f}°C", style=color))
    return Panel(table, title="Temperatures", border_style="red")


def compact_stats_renderable(snapshot):
    cpu = snapshot["cpu"]
    mem = snapshot["memory"]
    disks = snapshot["disks"]
    disk_pct = max((d["percent"] for d in disks), default=0.0)
    temps = snapshot["temperatures"]
    max_temp = max((t["current"] for t in temps), default=None)
    net = snapshot["network"]
    total_down = sum(i["recv_rate"] for i in net)
    total_up = sum(i["sent_rate"] for i in net)

    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(width=5)
    grid.add_column(ratio=1)
    grid.add_row("CPU", bar(cpu["overall"], width=16))
    grid.add_row("RAM", bar(mem["percent"], width=16))
    grid.add_row("DISK", bar(disk_pct, width=16))
    extra = f"Net ↓{human_rate(total_down)} ↑{human_rate(total_up)}"
    if max_temp is not None:
        extra += f"   Temp max {max_temp:.0f}°C"
    grid.add_row("", Text(extra, style="dim"))
    return Panel(grid, title="Summary", border_style="cyan")


def _panel_height(n_rows, min_h=4, max_h=10, overhead=3):
    return max(min_h, min(max_h, n_rows + overhead))


def build_layout(snapshot, width, height, interval):
    root = Layout()
    root.split_column(
        Layout(name="header", size=1),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=1),
    )
    root["header"].update(header_renderable(snapshot, width))
    root["footer"].update(footer_renderable(interval))

    n_cores = len(snapshot["cpu"]["per_core"])
    n_disks = len(snapshot["disks"])
    n_net = len(snapshot["network"])
    n_temp = len(snapshot["temperatures"])
    overhead = 2  # header + footer

    wide_mode = width >= 110
    col_width = max(20, (width // 3 - 4) if wide_mode else (width - 4))
    _, _, core_rows = _cpu_core_rows(n_cores, col_width)
    cpu_h = core_rows + 3

    mem_h = memory_panel_height(snapshot)
    disk_h = _panel_height(n_disks, min_h=4, max_h=8)

    core_h = max(cpu_h, mem_h, disk_h) if wide_mode else (cpu_h + mem_h + disk_h)
    core_fits = (overhead + core_h) <= height

    if not core_fits:
        top_size = min(8, max(height - overhead, 3))
        root["body"].split_column(
            Layout(name="top", size=top_size),
            Layout(name="filler", ratio=1),
        )
        root["body"]["top"].update(compact_stats_renderable(snapshot))
        root["body"]["filler"].update(Text(""))
        return root

    remaining = height - overhead - core_h
    net_h = _panel_height(n_net, min_h=4, max_h=7) if n_net > 0 else 0
    temp_h = _panel_height(n_temp, min_h=4, max_h=7) if n_temp > 0 else 0
    extra_row_mode = width >= 90

    show_net = show_temp = False
    extra_h = 0
    if net_h and temp_h:
        needed_both = max(net_h, temp_h) if extra_row_mode else (net_h + temp_h)
        if needed_both <= remaining:
            show_net = show_temp = True
            extra_h = needed_both
    if not (show_net and show_temp):
        if net_h and net_h <= remaining:
            show_net = True
            extra_h = net_h
        elif temp_h and temp_h <= remaining:
            show_temp = True
            extra_h = temp_h

    sections = [Layout(name="core", size=core_h)]
    if extra_h:
        sections.append(Layout(name="extra", size=extra_h))
    sections.append(Layout(name="filler", ratio=1))
    root["body"].split_column(*sections)

    core = root["body"]["core"]
    if wide_mode:
        core.split_row(
            Layout(name="c1", ratio=1),
            Layout(name="c2", ratio=1),
            Layout(name="c3", ratio=1),
        )
        core["c1"].update(cpu_panel(snapshot, col_width))
        core["c2"].update(memory_panel(snapshot, col_width))
        core["c3"].update(disk_panel(snapshot))
    else:
        core.split_column(
            Layout(name="cpu", size=cpu_h),
            Layout(name="mem", size=mem_h),
            Layout(name="disk", size=disk_h),
        )
        core["cpu"].update(cpu_panel(snapshot, col_width))
        core["mem"].update(memory_panel(snapshot, col_width))
        core["disk"].update(disk_panel(snapshot))

    if extra_h:
        extra = root["body"]["extra"]
        if show_net and show_temp:
            if extra_row_mode:
                extra.split_row(Layout(name="net", ratio=1), Layout(name="temp", ratio=1))
            else:
                extra.split_column(Layout(name="net", size=net_h), Layout(name="temp", size=temp_h))
            extra["net"].update(network_panel(snapshot))
            extra["temp"].update(temperature_panel(snapshot))
        elif show_net:
            extra.update(network_panel(snapshot))
        elif show_temp:
            extra.update(temperature_panel(snapshot))

    root["body"]["filler"].update(Text(""))
    return root
