import os
import socket
import time

import psutil


def human_bytes(n):
    for unit in ("B", "K", "M", "G", "T", "P"):
        if abs(n) < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}E"


def human_rate(bytes_per_sec):
    return f"{human_bytes(bytes_per_sec)}/s"


def human_uptime(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


_IGNORED_FS_TYPES = {"tmpfs", "devtmpfs", "squashfs", "overlay", "proc", "sysfs", "cgroup", "cgroup2"}

_TEMP_NAME_RULES = (
    (("core", "package", "tctl", "tdie", "cpu"), "CPU"),
    (("composite", "nvme", "ssd"), "SSD"),
    (("pch", "chipset"), "Chipset"),
    (("wifi", "wlan"), "WiFi"),
    (("gpu", "amdgpu", "nouveau", "radeon"), "GPU"),
    (("battery", "bat"), "Battery"),
    (("acpi", "systin", "mobo", "motherboard"), "System"),
)


def friendly_temp_name(chip, label):
    haystack = f"{chip} {label}".lower()
    for keywords, friendly in _TEMP_NAME_RULES:
        if any(k in haystack for k in keywords):
            return friendly
    return (label or chip).strip()


class MetricsCollector:
    def __init__(self):
        self.hostname = socket.gethostname()
        self.boot_time = psutil.boot_time()
        psutil.cpu_percent(percpu=True)
        self._last_net = psutil.net_io_counters(pernic=True)
        self._last_sample_time = time.time()

    def collect(self):
        now = time.time()
        elapsed = max(now - self._last_sample_time, 1e-6)

        snapshot = {
            "hostname": self.hostname,
            "uptime": human_uptime(now - self.boot_time),
            "cpu": self._collect_cpu(),
            "memory": self._collect_memory(),
            "disks": self._collect_disks(),
            "network": self._collect_network(elapsed),
            "temperatures": self._collect_temperatures(),
            "processes": self._collect_processes(),
        }

        self._last_sample_time = now
        return snapshot

    def _collect_cpu(self):
        per_core = psutil.cpu_percent(percpu=True)
        overall = sum(per_core) / len(per_core) if per_core else 0.0
        try:
            load1, load5, load15 = os.getloadavg()
        except (OSError, AttributeError):
            load1 = load5 = load15 = 0.0
        return {
            "overall": overall,
            "per_core": per_core,
            "load": (load1, load5, load15),
        }

    def _collect_memory(self):
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        return {
            "total": vm.total,
            "used": vm.used,
            "percent": vm.percent,
            "swap_total": sm.total,
            "swap_used": sm.used,
            "swap_percent": sm.percent,
        }

    def _collect_disks(self):
        disks = []
        seen_mounts = set()
        for part in psutil.disk_partitions(all=False):
            if part.fstype in _IGNORED_FS_TYPES:
                continue
            if part.mountpoint == "/boot" or part.mountpoint.startswith("/boot/"):
                continue
            if part.mountpoint in seen_mounts:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            seen_mounts.add(part.mountpoint)
            disks.append({
                "mountpoint": part.mountpoint,
                "total": usage.total,
                "used": usage.used,
                "percent": usage.percent,
            })
        disks.sort(key=lambda d: d["mountpoint"])
        return disks

    def _collect_network(self, elapsed):
        current = psutil.net_io_counters(pernic=True)
        try:
            stats = psutil.net_if_stats()
        except OSError:
            stats = {}
        interfaces = []
        for name, counters in current.items():
            if name == "lo":
                continue
            iface_stats = stats.get(name)
            if iface_stats is not None and not iface_stats.isup:
                continue
            if counters.bytes_sent == 0 and counters.bytes_recv == 0:
                continue
            prev = self._last_net.get(name)
            sent_rate = recv_rate = 0
            if prev is not None:
                sent_rate = max(counters.bytes_sent - prev.bytes_sent, 0) / elapsed
                recv_rate = max(counters.bytes_recv - prev.bytes_recv, 0) / elapsed
            interfaces.append({
                "name": name,
                "sent_rate": sent_rate,
                "recv_rate": recv_rate,
                "bytes_sent": counters.bytes_sent,
                "bytes_recv": counters.bytes_recv,
            })
        self._last_net = current
        interfaces.sort(key=lambda i: i["recv_rate"] + i["sent_rate"], reverse=True)
        return interfaces

    def _collect_temperatures(self):
        grouped = {}
        try:
            temps = psutil.sensors_temperatures()
        except AttributeError:
            temps = {}
        for chip, entries in temps.items():
            for entry in entries:
                friendly = friendly_temp_name(chip, entry.label)
                if friendly not in grouped or entry.current > grouped[friendly]:
                    grouped[friendly] = entry.current
        readings = [{"label": label, "current": value} for label, value in grouped.items()]
        readings.sort(key=lambda r: r["current"], reverse=True)
        return readings

    def _collect_processes(self):
        procs = []
        for p in psutil.process_iter(["pid", "name", "username"]):
            try:
                mem = p.memory_percent()
                info = p.info
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"] or "?",
                    "user": info["username"] or "?",
                    "mem": mem,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        procs.sort(key=lambda x: x["mem"], reverse=True)
        return procs
