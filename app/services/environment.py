import subprocess
import platform


def tool_version(args: list[str]) -> str:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
        return (proc.stdout or proc.stderr).strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return "未安装或不可用"


def environment_info() -> dict[str, str]:
    return {"fio": tool_version(["fio", "--version"]), "nvme_cli": tool_version(["nvme", "version"]),
            "operating_system": platform.platform(), "python": platform.python_version()}
