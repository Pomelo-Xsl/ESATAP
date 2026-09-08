from __future__ import annotations

import shlex
from dataclasses import dataclass

from app.schemas.tasks import DEFAULT_QD_SCAN_DEPTHS, FioParameters


PROFILES = {
    "seq_read_128k": ("read", "128k", None), "seq_write_128k": ("write", "128k", None),
    "rand_read_4k": ("randread", "4k", None), "rand_write_4k": ("randwrite", "4k", None),
    "randrw_70_30": ("randrw", "4k", 70), "randrw_50_50": ("randrw", "4k", 50),
    "qd_scan": ("randread", "4k", None), "stress_rand_write": ("randwrite", "4k", None),
    "stress_seq_write": ("write", "128k", None),
}
DESTRUCTIVE_TYPES = {"seq_write_128k", "rand_write_4k", "randrw_70_30", "randrw_50_50", "stress_rand_write", "stress_seq_write"}
DESTRUCTIVE_RW = {"write", "trim", "randwrite", "randtrim", "rw", "readwrite", "randrw", "trimwrite"}

OPTION_MAP = {
    "iodepth_batch": "iodepth_batch",
    "iodepth_batch_complete_min": "iodepth_batch_complete_min",
    "iodepth_batch_complete_max": "iodepth_batch_complete_max",
    "iodepth_low": "iodepth_low",
    "ramp_time_seconds": "ramp_time",
    "start_delay_seconds": "startdelay",
    "loops": "loops",
    "number_ios": "number_ios",
    "io_size": "io_size",
    "offset": "offset",
    "offset_increment": "offset_increment",
    "io_submit_mode": "io_submit_mode",
    "rw_sequencer": "rw_sequencer",
    "invalidate": "invalidate",
    "refill_buffers": "refill_buffers",
    "scramble_buffers": "scramble_buffers",
    "zero_buffers": "zero_buffers",
    "buffer_pattern": "buffer_pattern",
    "buffer_compress_percentage": "buffer_compress_percentage",
    "dedupe_percentage": "dedupe_percentage",
    "rwmixread": "rwmixread",
    "rwmixcycle": "rwmixcycle",
    "percentage_random": "percentage_random",
    "random_distribution": "random_distribution",
    "random_generator": "random_generator",
    "randseed": "randseed",
    "randrepeat": "randrepeat",
    "allrandrepeat": "allrandrepeat",
    "norandommap": "norandommap",
    "softrandommap": "softrandommap",
    "rate": "rate",
    "rate_min": "rate_min",
    "rate_iops": "rate_iops",
    "rate_iops_min": "rate_iops_min",
    "rate_process": "rate_process",
    "rate_cycle_ms": "ratecycle",
    "thinktime_us": "thinktime",
    "thinktime_spin_us": "thinktime_spin",
    "thinktime_blocks": "thinktime_blocks",
    "latency_target_us": "latency_target",
    "latency_window_us": "latency_window",
    "latency_percentile": "latency_percentile",
    "latency_run": "latency_run",
    "fsync": "fsync",
    "fdatasync": "fdatasync",
    "end_fsync": "end_fsync",
    "sync_file_range": "sync_file_range",
    "verify": "verify",
    "do_verify": "do_verify",
    "verify_fatal": "verify_fatal",
    "verify_dump": "verify_dump",
    "verify_pattern": "verify_pattern",
    "verify_interval": "verify_interval",
    "trim_percentage": "trim_percentage",
    "trim_verify_zero": "trim_verify_zero",
    "trim_backlog": "trim_backlog",
    "trim_backlog_batch": "trim_backlog_batch",
    "cpus_allowed": "cpus_allowed",
    "cpus_allowed_policy": "cpus_allowed_policy",
    "numa_cpu_nodes": "numa_cpu_nodes",
    "numa_mem_policy": "numa_mem_policy",
    "thread": "thread",
    "nice": "nice",
    "prio_class": "prioclass",
    "prio": "prio",
    "hipri": "hipri",
    "fixedbufs": "fixedbufs",
    "registerfiles": "registerfiles",
    "sqthread_poll": "sqthread_poll",
    "sqthread_poll_cpu": "sqthread_poll_cpu",
    "cmdprio_percentage": "cmdprio_percentage",
    "cmdprio_class": "cmdprio_class",
    "cmdprio": "cmdprio",
    "serialize_overlap": "serialize_overlap",
    "atomic": "atomic",
    "nowait": "nowait",
    "steadystate": "steadystate",
    "steadystate_duration_seconds": "steadystate_duration",
    "steadystate_ramp_time_seconds": "steadystate_ramp_time",
    "zonemode": "zonemode",
    "zonesize": "zonesize",
    "zonerange": "zonerange",
    "zoneskip": "zoneskip",
    "zonecapacity": "zonecapacity",
    "max_open_zones": "max_open_zones",
    "job_max_open_zones": "job_max_open_zones",
    "read_beyond_wp": "read_beyond_wp",
    "unified_rw_reporting": "unified_rw_reporting",
    "log_hist_msec": "log_hist_msec",
    "log_hist_coarseness": "log_hist_coarseness",
    "log_max_value": "log_max_value",
    "log_offset": "log_offset",
    "log_compression": "log_compression",
}

COMMAND_GROUPS = [
    ("任务与目标", {"name", "filename", "size", "io_size", "offset", "offset_increment"}),
    ("I/O 模式", {"ioengine", "io_submit_mode", "rw", "rw_sequencer", "bs", "bsrange", "bssplit", "direct"}),
    ("队列与并发", {"iodepth", "iodepth_batch", "iodepth_batch_complete_min", "iodepth_batch_complete_max", "iodepth_low", "numjobs"}),
    ("运行控制", {"time_based", "runtime", "ramp_time", "startdelay", "loops", "number_ios", "thinktime", "thinktime_spin", "thinktime_blocks"}),
    ("负载与速率", {"rwmixread", "rwmixcycle", "percentage_random", "random_distribution", "random_generator", "randseed", "randrepeat", "allrandrepeat", "norandommap", "softrandommap", "rate", "rate_min", "rate_iops", "rate_iops_min", "rate_process", "ratecycle", "latency_target", "latency_window", "latency_percentile", "latency_run"}),
    ("数据、校验与 TRIM", {"invalidate", "refill_buffers", "scramble_buffers", "zero_buffers", "buffer_pattern", "buffer_compress_percentage", "dedupe_percentage", "fsync", "fdatasync", "end_fsync", "sync_file_range", "verify", "do_verify", "verify_fatal", "verify_dump", "verify_pattern", "verify_interval", "trim_percentage", "trim_verify_zero", "trim_backlog", "trim_backlog_batch"}),
    ("CPU、NUMA 与引擎", {"cpus_allowed", "cpus_allowed_policy", "numa_cpu_nodes", "numa_mem_policy", "thread", "nice", "prioclass", "prio", "hipri", "fixedbufs", "registerfiles", "sqthread_poll", "sqthread_poll_cpu", "cmdprio_percentage", "cmdprio_class", "cmdprio", "serialize_overlap", "atomic", "nowait", "steadystate", "steadystate_duration", "steadystate_ramp_time", "zonemode", "zonesize", "zonerange", "zoneskip", "zonecapacity", "max_open_zones", "job_max_open_zones", "read_beyond_wp"}),
    ("统计与输出", {"group_reporting", "output-format", "lat_percentiles", "percentile_list", "log_avg_msec", "log_hist_msec", "log_hist_coarseness", "log_max_value", "log_offset", "log_compression", "unified_rw_reporting", "write_iops_log", "write_bw_log", "write_lat_log", "output"}),
]


def is_destructive(test_type: str, parameters: FioParameters) -> bool:
    return (test_type in DESTRUCTIVE_TYPES or parameters.precondition or parameters.rw in DESTRUCTIVE_RW
            or bool(parameters.trim_percentage))


def build_execution_plan(test_type: str, parameters: FioParameters) -> list[tuple[str, str, int]]:
    qds = (parameters.queue_depths or DEFAULT_QD_SCAN_DEPTHS) if test_type == "qd_scan" else [parameters.queue_depth]
    plan: list[tuple[str, str, int]] = []
    if parameters.precondition:
        plan.append(("precondition", "stress_seq_write", parameters.queue_depth))
    plan.extend((f"qd_{qd}" if len(qds) > 1 else "run", test_type, qd) for qd in qds)
    return plan


def parameters_for_phase(parameters: FioParameters, phase: str) -> FioParameters:
    if phase == "precondition":
        return parameters.model_copy(update={"size": "100%", "rw": "write"})
    return parameters


def format_command_preview(argv: list[str]) -> dict[str, object]:
    buckets = {label: [] for label, _ in COMMAND_GROUPS}
    other: list[str] = []
    for argument in argv[1:]:
        option = argument[2:].split("=", 1)[0] if argument.startswith("--") else ""
        matched = False
        for label, option_names in COMMAND_GROUPS:
            if option in option_names:
                buckets[label].append(shlex.join([argument]))
                matched = True
                break
        if not matched:
            other.append(shlex.join([argument]))
    groups = [{"label": label, "arguments": buckets[label]} for label, _ in COMMAND_GROUPS if buckets[label]]
    if other:
        groups.append({"label": "其他参数", "arguments": other})
    ordered_arguments = [argument for group in groups for argument in group["arguments"]]
    lines = [shlex.join([argv[0]])] + ordered_arguments
    multiline = " \\\n  ".join(lines)
    return {"groups": groups, "multiline_command": multiline}


@dataclass
class FioCommandBuilder:
    fio_binary: str = "fio"

    def build(self, device: str, test_type: str, params: FioParameters, output_file: str, log_prefix: str, queue_depth: int | None = None) -> list[str]:
        if test_type not in PROFILES:
            raise ValueError("不支持的测试类型")
        profile_rw, default_bs, profile_readmix = PROFILES[test_type]
        rw = params.rw or profile_rw
        args = [
            self.fio_binary, f"--name={test_type}", f"--filename={device}", f"--ioengine={params.io_engine}",
            f"--direct={int(params.direct)}", f"--time_based={int(params.time_based)}",
            f"--group_reporting={int(params.group_reporting)}", "--output-format=json+",
            f"--lat_percentiles={int(params.latency_percentiles)}", f"--percentile_list={params.percentile_list}",
            f"--log_avg_msec={params.log_avg_msec}", f"--rw={rw}",
            f"--iodepth={queue_depth or params.queue_depth}",
            f"--numjobs={params.num_jobs}", f"--runtime={params.runtime_seconds}", f"--size={params.size}",
            f"--write_iops_log={log_prefix}", f"--write_bw_log={log_prefix}", f"--write_lat_log={log_prefix}",
            f"--output={output_file}",
        ]
        if params.block_size_range:
            args.append(f"--bsrange={params.block_size_range}")
        elif params.block_size_split:
            args.append(f"--bssplit={params.block_size_split}")
        else:
            args.append(f"--bs={params.block_size or default_bs}")
        if params.rwmixread is None and profile_readmix is not None and rw in {"rw", "readwrite", "randrw"}:
            args.append(f"--rwmixread={profile_readmix}")
        for attribute, option in OPTION_MAP.items():
            value = getattr(params, attribute)
            if value is not None:
                args.append(f"--{option}={int(value) if isinstance(value, bool) else value}")
        return args
