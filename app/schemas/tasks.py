from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.core.config import settings


TEST_TYPES = Literal[
    "seq_read_128k", "seq_write_128k", "rand_read_4k", "rand_write_4k",
    "randrw_70_30", "randrw_50_50", "qd_scan", "stress_rand_write", "stress_seq_write",
]
DEFAULT_QD_SCAN_DEPTHS = [1, 2, 4, 8, 16, 32, 64, 128, 256]


class FioParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_size: Optional[str] = None
    block_size_range: Optional[str] = None
    block_size_split: Optional[str] = None
    queue_depth: int = Field(default=32, ge=1, le=1024)
    iodepth_batch: Optional[int] = Field(default=None, ge=1, le=1024)
    iodepth_batch_complete_min: Optional[int] = Field(default=None, ge=0, le=1024)
    iodepth_batch_complete_max: Optional[int] = Field(default=None, ge=0, le=1024)
    iodepth_low: Optional[int] = Field(default=None, ge=1, le=1024)
    num_jobs: int = Field(default=1, ge=1, le=128)
    runtime_seconds: int = Field(default=60, ge=1, le=604800)
    ramp_time_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    start_delay_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    time_based: bool = True
    loops: Optional[int] = Field(default=None, ge=1, le=1_000_000)
    number_ios: Optional[int] = Field(default=None, ge=1)
    size: str = "100%"
    io_size: Optional[str] = None
    offset: Optional[str] = None
    offset_increment: Optional[str] = None
    precondition: bool = False
    queue_depths: Optional[List[int]] = None
    io_engine: Literal["io_uring", "io_uring_cmd", "libaio", "sync", "psync", "pvsync", "pvsync2", "mmap"] = "io_uring"
    io_submit_mode: Optional[Literal["inline", "offload"]] = None
    rw: Optional[Literal["read", "write", "trim", "randread", "randwrite", "randtrim", "rw", "readwrite", "randrw", "trimwrite"]] = None
    rw_sequencer: Optional[Literal["sequential", "identical"]] = None
    direct: bool = True
    invalidate: Optional[bool] = None
    refill_buffers: Optional[bool] = None
    scramble_buffers: Optional[bool] = None
    zero_buffers: Optional[bool] = None
    buffer_pattern: Optional[str] = None
    buffer_compress_percentage: Optional[int] = Field(default=None, ge=0, le=100)
    dedupe_percentage: Optional[int] = Field(default=None, ge=0, le=100)
    rwmixread: Optional[int] = Field(default=None, ge=0, le=100)
    rwmixcycle: Optional[int] = Field(default=None, ge=1)
    percentage_random: Optional[int] = Field(default=None, ge=0, le=100)
    random_distribution: Optional[str] = None
    random_generator: Optional[Literal["tausworthe", "lfsr", "tausworthe64"]] = None
    randseed: Optional[int] = Field(default=None, ge=0)
    randrepeat: Optional[bool] = None
    allrandrepeat: Optional[bool] = None
    norandommap: Optional[bool] = None
    softrandommap: Optional[bool] = None
    rate: Optional[str] = None
    rate_min: Optional[str] = None
    rate_iops: Optional[int] = Field(default=None, ge=1)
    rate_iops_min: Optional[int] = Field(default=None, ge=1)
    rate_process: Optional[Literal["linear", "poisson"]] = None
    rate_cycle_ms: Optional[int] = Field(default=None, ge=1)
    thinktime_us: Optional[int] = Field(default=None, ge=0)
    thinktime_spin_us: Optional[int] = Field(default=None, ge=0)
    thinktime_blocks: Optional[int] = Field(default=None, ge=1)
    latency_target_us: Optional[int] = Field(default=None, ge=1)
    latency_window_us: Optional[int] = Field(default=None, ge=1)
    latency_percentile: Optional[float] = Field(default=None, gt=0, le=100)
    latency_run: Optional[bool] = None
    fsync: Optional[int] = Field(default=None, ge=0)
    fdatasync: Optional[int] = Field(default=None, ge=0)
    end_fsync: Optional[bool] = None
    sync_file_range: Optional[str] = None
    verify: Optional[Literal["none", "md5", "crc32c", "crc32", "crc64", "sha1", "sha256", "sha512", "xxhash"]] = None
    do_verify: Optional[bool] = None
    verify_fatal: Optional[bool] = None
    verify_dump: Optional[bool] = None
    verify_pattern: Optional[str] = None
    verify_interval: Optional[int] = Field(default=None, ge=1)
    trim_percentage: Optional[int] = Field(default=None, ge=0, le=100)
    trim_verify_zero: Optional[bool] = None
    trim_backlog: Optional[int] = Field(default=None, ge=0)
    trim_backlog_batch: Optional[int] = Field(default=None, ge=0)
    cpus_allowed: Optional[str] = None
    cpus_allowed_policy: Optional[Literal["shared", "split"]] = None
    numactl_cpu_nodes: Optional[str] = Field(default=None, max_length=128)
    numactl_mem_nodes: Optional[str] = Field(default=None, max_length=128)
    numa_cpu_nodes: Optional[str] = None
    numa_mem_policy: Optional[str] = None
    thread: Optional[bool] = None
    nice: Optional[int] = Field(default=None, ge=-20, le=19)
    prio_class: Optional[int] = Field(default=None, ge=0, le=3)
    prio: Optional[int] = Field(default=None, ge=0, le=7)
    hipri: Optional[bool] = None
    fixedbufs: Optional[bool] = None
    registerfiles: Optional[bool] = None
    sqthread_poll: Optional[bool] = None
    sqthread_poll_cpu: Optional[int] = Field(default=None, ge=0)
    cmdprio_percentage: Optional[int] = Field(default=None, ge=0, le=100)
    cmdprio_class: Optional[int] = Field(default=None, ge=0, le=3)
    cmdprio: Optional[int] = Field(default=None, ge=0, le=7)
    serialize_overlap: Optional[bool] = None
    atomic: Optional[bool] = None
    nowait: Optional[bool] = None
    steadystate: Optional[str] = None
    steadystate_duration_seconds: Optional[int] = Field(default=None, ge=1)
    steadystate_ramp_time_seconds: Optional[int] = Field(default=None, ge=0)
    zonemode: Optional[Literal["none", "strided", "zbd"]] = None
    zonesize: Optional[str] = None
    zonerange: Optional[str] = None
    zoneskip: Optional[str] = None
    zonecapacity: Optional[str] = None
    max_open_zones: Optional[int] = Field(default=None, ge=0)
    job_max_open_zones: Optional[int] = Field(default=None, ge=0)
    read_beyond_wp: Optional[bool] = None
    group_reporting: bool = True
    unified_rw_reporting: Optional[Literal["none", "mixed", "both"]] = None
    log_avg_msec: int = Field(default=1000, ge=0, le=3_600_000)
    log_hist_msec: Optional[int] = Field(default=None, ge=0, le=3_600_000)
    log_hist_coarseness: Optional[int] = Field(default=None, ge=0, le=6)
    log_max_value: Optional[bool] = None
    log_offset: Optional[bool] = None
    log_compression: Optional[int] = Field(default=None, ge=0, le=100)
    latency_percentiles: bool = True
    percentile_list: str = "50:90:95:99:99.9:99.99"

    @field_validator("block_size")
    @classmethod
    def valid_bs(cls, value: Optional[str]):
        if value is not None and not re.fullmatch(r"[1-9]\d*[kKmMgG]?", value):
            raise ValueError("块大小格式无效，例如 4k、128k、1m")
        return value

    @field_validator("block_size_range", "block_size_split", "rate", "rate_min", "sync_file_range")
    @classmethod
    def valid_fio_expression(cls, value: Optional[str]):
        if value is not None and not re.fullmatch(r"[A-Za-z0-9_%:,.+\-/]+", value):
            raise ValueError("fio 参数表达式包含不支持的字符")
        return value

    @field_validator("size")
    @classmethod
    def valid_size(cls, value: str):
        if value != "100%" and not re.fullmatch(r"[1-9]\d*(?:[kKmMgGtT]|[kKmMgGtT]i?[bB])", value):
            raise ValueError("测试容量格式无效，例如 10G、10GiB 或 100%")
        return value

    @field_validator("io_size", "offset", "offset_increment", "zonesize", "zonerange", "zoneskip", "zonecapacity")
    @classmethod
    def valid_optional_size(cls, value: Optional[str]):
        if value is not None and not re.fullmatch(r"(?:0|[1-9]\d*(?:[kKmMgGtT]|[kKmMgGtT]i?[bB])|(?:100|[1-9]\d?)%)", value):
            raise ValueError("容量/偏移格式无效，例如 10GiB 或 20%")
        return value

    @field_validator("random_distribution")
    @classmethod
    def valid_random_distribution(cls, value: Optional[str]):
        if value is not None and not re.fullmatch(r"(?:random|zipf|pareto|normal|zoned|zoned_abs)(?::[0-9.,/]+)?", value):
            raise ValueError("随机分布格式无效")
        return value

    @field_validator("steadystate")
    @classmethod
    def valid_steadystate(cls, value: Optional[str]):
        if value is not None and not re.fullmatch(r"(?:iops|iops_slope|bw|bw_slope):[0-9]+(?:\.[0-9]+)?%?", value):
            raise ValueError("稳态条件格式无效，例如 iops_slope:0.1%")
        return value

    @field_validator("cpus_allowed", "numa_cpu_nodes")
    @classmethod
    def valid_cpu_list(cls, value: Optional[str]):
        if value is not None and not re.fullmatch(r"(?:all|[0-9,-]+)", value):
            raise ValueError("CPU/NUMA 节点列表格式无效，例如 0-3,8")
        return value

    @field_validator("numactl_cpu_nodes", "numactl_mem_nodes")
    @classmethod
    def valid_numactl_node_list(cls, value: Optional[str]):
        if value is not None and not re.fullmatch(r"(?:all|\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)", value):
            raise ValueError("numactl 节点格式无效，例如 0、0-1 或 0,1")
        return value

    @field_validator("numa_mem_policy")
    @classmethod
    def valid_numa_policy(cls, value: Optional[str]):
        if value is not None and not re.fullmatch(r"(?:default|local|prefer:\d+|bind:(?:all|[0-9,-]+)|interleave:(?:all|[0-9,-]+))", value):
            raise ValueError("NUMA 内存策略格式无效")
        return value

    @field_validator("verify_pattern", "buffer_pattern")
    @classmethod
    def valid_verify_pattern(cls, value: Optional[str]):
        if value is not None and not re.fullmatch(r"(?:0x)?[0-9A-Fa-f]+", value):
            raise ValueError("数据模式只能使用十六进制字符")
        return value

    @field_validator("percentile_list")
    @classmethod
    def valid_percentile_list(cls, value: str):
        try:
            values = [float(item) for item in value.split(":")]
        except ValueError as exc:
            raise ValueError("百分位列表格式无效") from exc
        if not values or len(values) > 32 or any(item <= 0 or item > 100 for item in values):
            raise ValueError("百分位必须包含 1-32 个 0 到 100 之间的数值")
        return value

    @field_validator("queue_depths")
    @classmethod
    def valid_qds(cls, value: Optional[List[int]]):
        if value is not None and (not value or len(value) > 32 or any(v < 1 or v > 1024 for v in value)):
            raise ValueError("QD 列表必须包含 1-32 个 1..1024 的整数")
        return value

    @model_validator(mode="after")
    def validate_combinations(self):
        block_modes = [self.block_size, self.block_size_range, self.block_size_split]
        if sum(value is not None for value in block_modes) > 1:
            raise ValueError("块大小、块范围和块大小分布只能选择一种")
        if (self.iodepth_batch_complete_min is not None and self.iodepth_batch_complete_max is not None
                and self.iodepth_batch_complete_min > self.iodepth_batch_complete_max):
            raise ValueError("最小完成批量不能大于最大完成批量")
        if self.thinktime_spin_us is not None and self.thinktime_us is not None and self.thinktime_spin_us > self.thinktime_us:
            raise ValueError("忙等待时间不能大于总思考时间")
        return self


class TestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    device: str = Field(min_length=1, max_length=255)
    test_type: TEST_TYPES
    parameters: FioParameters = Field(default_factory=FioParameters)
    destructive_confirmed: bool = False
    confirmation_device: Optional[str] = None

    @model_validator(mode="after")
    def apply_test_type_defaults(self):
        if self.test_type.startswith("stress_") and "runtime_seconds" not in self.parameters.model_fields_set:
            self.parameters.runtime_seconds = settings.default_stress_seconds
        if self.test_type == "qd_scan":
            if self.parameters.queue_depths is None:
                self.parameters.queue_depths = DEFAULT_QD_SCAN_DEPTHS.copy()
        else:
            self.parameters.queue_depths = None
        return self


class TestStart(BaseModel):
    destructive_confirmed: bool = False
    confirmation_device: Optional[str] = None


class TestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    device: str
    test_type: str
    status: str
    progress: float
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: Optional[float]
    error_message: Optional[str]
    result_dir: Optional[str]

    @field_serializer("created_at", "started_at", "ended_at", when_used="json")
    def serialize_utc_datetime(self, value: Optional[datetime]):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
