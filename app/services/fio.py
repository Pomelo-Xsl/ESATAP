from __future__ import annotations

from dataclasses import dataclass

from app.schemas.tasks import FioParameters


PROFILES = {
    "seq_read_128k": ("read", "128k", None), "seq_write_128k": ("write", "128k", None),
    "rand_read_4k": ("randread", "4k", None), "rand_write_4k": ("randwrite", "4k", None),
    "randrw_70_30": ("randrw", "4k", 70), "randrw_50_50": ("randrw", "4k", 50),
    "qd_scan": ("randread", "4k", None), "stress_rand_write": ("randwrite", "4k", None),
    "stress_seq_write": ("write", "128k", None),
}
DESTRUCTIVE_TYPES = {"seq_write_128k", "rand_write_4k", "randrw_70_30", "randrw_50_50", "stress_rand_write", "stress_seq_write"}


def is_destructive(test_type: str, parameters: FioParameters) -> bool:
    return test_type in DESTRUCTIVE_TYPES or parameters.precondition


@dataclass
class FioCommandBuilder:
    fio_binary: str = "fio"

    def build(self, device: str, test_type: str, params: FioParameters, output_file: str, log_prefix: str, queue_depth: int | None = None) -> list[str]:
        if test_type not in PROFILES:
            raise ValueError("不支持的测试类型")
        rw, default_bs, readmix = PROFILES[test_type]
        bs = params.block_size or default_bs
        args = [
            self.fio_binary, f"--name={test_type}", f"--filename={device}", "--ioengine=io_uring",
            "--direct=1", "--time_based=1", "--group_reporting=1", "--output-format=json+",
            "--lat_percentiles=1", "--percentile_list=50:90:95:99:99.9:99.99", "--log_avg_msec=1000",
            f"--rw={rw}", f"--bs={bs}", f"--iodepth={queue_depth or params.queue_depth}",
            f"--numjobs={params.num_jobs}", f"--runtime={params.runtime_seconds}", f"--size={params.size}",
            f"--write_iops_log={log_prefix}", f"--write_bw_log={log_prefix}", f"--write_lat_log={log_prefix}",
            f"--output={output_file}",
        ]
        if readmix is not None:
            args.append(f"--rwmixread={readmix}")
        return args

