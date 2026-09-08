# 企业级 SSD 自动化测试与分析平台

Enterprise SSD Automated Testing and Analysis Platform。面向 Ubuntu Server 的单机 Web 平台，以 FastAPI、SQLite、fio、nvme-cli、Jinja2 和 ECharts 实现 NVMe SSD 发现、测试编排、后台执行、实时状态、SMART 前后对比、结果分析与 HTML 报告。

## 功能

- 扫描 NVMe Controller/Namespace，展示型号、序列号、固件、容量、PCIe、NUMA、挂载/分区/文件系统及系统盘状态。
- 提供 128K 顺序读写、4K 随机读写、70/30 与 50/50 混合、QD 1—256 扫描、随机写与顺序写压力测试，以及可选顺序写预处理。
- 创建页面提供分组式 fio 参数面板，覆盖 NVMe 测试常用的 I/O 引擎、读写模式、块大小/分布、队列批量、范围与偏移、混合比例、随机分布、速率、目标时延、校验、TRIM、CPU/NUMA、io_uring 和日志统计参数；支持通过 numactl 绑定 CPU 与内存 NUMA 节点，所有字段均由后端白名单校验。
- 创建任务前实时展示由实际命令生成器输出的完整 fio 命令；QD 扫描和预处理会逐条预览，并支持一键复制。
- 后台任务不依赖浏览器连接；全平台同一时间只运行一个 SSD 测试，其余任务跨设备按创建顺序持久化排队并自动接续，避免并发 I/O 干扰性能结果；可取消排队或精确停止本任务的 fio 进程组。
- 保存 fio JSON+、IOPS/带宽/时延日志、命令参数、stdout/stderr、SMART 前后快照和周期采样；异常退出仍保留目录。
- 统一输出 IOPS、十进制 MB/s、μs、原始 byte 容量，并展示 P50—P99.99。
- 提供仪表盘、设备、创建、实时、运行进程、历史、结构化详情、分析页面与可下载 HTML 报告；全部日常操作均可从 Web 界面完成。

## 目录

```text
app/
  api/          API 与页面路由
  core/         配置、数据库
  models/       SQLAlchemy 任务模型
  schemas/      Pydantic 请求/响应
  services/     设备、SMART、fio、安全、任务、分析
  templates/    Jinja2 页面和报告
  static/       CSS、JavaScript、ECharts 页面逻辑
tests/          无真实盘写入的 pytest 测试
data/           SQLite 数据库
results/        每任务原始结果与日志
scripts/        Ubuntu 安装和启动脚本
```

## Ubuntu 22.04 / 24.04 安装

```bash
sudo apt update
sudo apt install -y python3-venv fio nvme-cli numactl util-linux
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p data results
```

也可运行 `bash scripts/install-ubuntu.sh`。建议使用较新的 fio 3.x；`io_uring` 需要受支持的内核。读取 NVMe SMART 与访问裸盘通常需要 root 或精确配置的 udev/group 权限。不要直接以开放到公网的 root Web 服务方式部署。

## 配置与数据库

环境变量见 `.env.example`：

- `SSD_PLATFORM_DATABASE_URL`：默认 `sqlite:///./data/ssd_platform.db`
- `SSD_PLATFORM_RESULTS_DIR`：默认 `./results`
- `SSD_PLATFORM_DEFAULT_STRESS_SECONDS`：默认 86400（24 小时）

首次启动自动创建 SQLite 表，无需单独迁移命令。启动：

```bash
bash scripts/run.sh
# 或
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 `http://服务器IP:8000/`。设备扫描、SMART、任务创建/启停、运行监控、历史删除、日志、分析和报告均提供前端页面，不需要手工调用 API。

## 测试

```bash
.venv/bin/pytest -q
```

测试通过 mock/样例 JSON 验证命令生成、安全拦截、SMART/fio 解析、任务状态、停止逻辑和 API；不会执行真实 fio/nvme 写操作。

## 极重要的安全警告

顺序写、随机写、混合读写、写压力测试和全盘顺序写预处理都会覆盖数据；TRIM/Discard 同样破坏数据，本版本不提供其执行入口。平台只允许测试经确认的非旋转 NVMe SSD Namespace，并统一拒绝系统盘、启动盘、已挂载设备、含分区或文件系统的设备、只读设备及正被内核存储栈占用的设备。写测试还要求勾选风险确认并手工输入完整设备名。若设备状态无法确认则拒绝执行。生产部署前仍应实施物理隔离、资产复核、最小权限和结果备份。

## 示例截图

- `docs/screenshots/dashboard.png`（预留）
- `docs/screenshots/analysis.png`（预留）

页面使用 Bootstrap/ECharts CDN；离线环境可将对应静态文件下载到 `app/static/vendor/` 后替换模板链接。

## 当前版本边界

当前版本不包含用户权限、多节点调度、消息队列、容器编排、PDF 原生生成、邮件通知和 TRIM/格式化。HTML 报告可由浏览器打印为 PDF。服务重启时不会重新接管既有 fio 进程，因此生产运维应在无运行任务时升级或重启服务。
