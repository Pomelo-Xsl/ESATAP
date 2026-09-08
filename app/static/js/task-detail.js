const parameterLabels = {block_size: '块大小', queue_depth: '队列深度', num_jobs: '并发任务数', runtime_seconds: '运行时间（秒）', size: '测试容量', precondition: '全盘写预处理', queue_depths: 'QD 扫描序列'};
const smartLabels = {critical_warning: '严重警告', temperature: '温度（K）', available_spare: '可用备用空间（%）', percentage_used: '寿命消耗（%）', data_units_read: '读取数据单元', data_units_written: '写入数据单元', host_read_commands: '主机读命令', host_write_commands: '主机写命令', controller_busy_time: '控制器忙碌时间', power_cycles: '上电次数', power_on_hours: '通电小时', unsafe_shutdowns: '异常断电', media_errors: '介质错误', error_information_log_entries: '错误日志条目'};
const destructiveTypes = new Set(['seq_write_128k', 'rand_write_4k', 'randrw_70_30', 'randrw_50_50', 'stress_rand_write', 'stress_seq_write']);
let requiresDestructive = destructiveTypes.has(TEST_TYPE);

function displayValue(value) {
  if (value === null || value === undefined) return '—';
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'boolean') return value ? '是' : '否';
  return value;
}

function renderParameters(parameters) {
  document.querySelector('#parameter-table').innerHTML = Object.entries(parameters).map(([key, value]) =>
    `<div><span>${parameterLabels[key] || key}</span><strong>${displayValue(value)}</strong></div>`).join('');
}

function renderPerformance(summary) {
  const runs = summary?.runs || [];
  document.querySelector('#performance-table').innerHTML = runs.length ? `<table class="table"><thead><tr><th>阶段</th><th>方向</th><th>IOPS</th><th>MB/s</th><th>平均时延</th><th>P99</th><th>错误</th></tr></thead><tbody>${runs.flatMap(run =>
    Object.entries(run.directions || {}).map(([direction, metric]) => `<tr><td>${run.phase || 'run'} / QD ${run.queue_depth}</td><td>${direction === 'read' ? '读取' : '写入'}</td><td>${metric.iops}</td><td>${metric.bandwidth_mb_per_sec}</td><td>${metric.latency_us?.mean ?? '—'} μs</td><td>${metric.latency_us?.p99 ?? '—'} μs</td><td>${run.error_count || 0}</td></tr>`)).join('')}</tbody></table>` : '<div class="empty">任务尚未生成性能结果</div>';
}

function renderSmart(result) {
  const before = result.smart_before || {}, after = result.smart_after || {}, delta = result.smart_delta || {};
  const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])];
  document.querySelector('#smart-table').innerHTML = keys.length ? `<table class="table"><thead><tr><th>指标</th><th>测试前</th><th>测试后</th><th>变化量</th></tr></thead><tbody>${keys.map(key => `<tr><td>${smartLabels[key] || key}</td><td>${displayValue(before[key])}</td><td>${displayValue(after[key])}</td><td class="delta">${displayValue(delta[key])}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">尚无 SMART 前后快照</div>';
}

function escapeHtml(text) {
  const element = document.createElement('div');
  element.textContent = text;
  return element.innerHTML;
}

function renderLogs(logs) {
  document.querySelector('#error-summary').innerHTML = logs.error
    ? `<div class="alert alert-danger"><strong>任务异常：</strong>${logs.error}</div>`
    : '<div class="alert alert-success compact">没有记录到任务异常</div>';
  const entries = Object.entries(logs.files || {});
  document.querySelector('#log-list').innerHTML = entries.length ? entries.map(([name, content], index) =>
    `<details ${index === 0 ? 'open' : ''}><summary>${name}<span>${content.length.toLocaleString()} 字符</span></summary><pre>${escapeHtml(content)}</pre></details>`).join('') : '<div class="empty">暂无日志文件</div>';
}

async function loadDetail() {
  try {
    const [task, result, logs] = await Promise.all([api(`/api/tests/${TEST_ID}`), api(`/api/tests/${TEST_ID}/results`), api(`/api/tests/${TEST_ID}/logs`)]);
    requiresDestructive = requiresDestructive || task.parameters.precondition === true;
    renderParameters(task.parameters);
    renderPerformance(result.summary);
    renderSmart(result);
    renderLogs(logs);
  } catch (error) {
    document.querySelector('#detail-message').innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
  }
}

const startButton = document.querySelector('#start-task');
if (startButton) startButton.onclick = async () => {
  const input = document.querySelector('#start-confirm-device');
  const destructive = requiresDestructive;
  if (destructive && input.value !== TEST_DEVICE) {
    document.querySelector('#detail-message').innerHTML = `<div class="alert alert-danger">写测试必须完整输入 ${TEST_DEVICE}</div>`;
    return;
  }
  if (!confirm(destructive ? '该写测试会永久覆盖目标设备数据，确定启动？' : '确定启动这个只读测试？')) return;
  try {
    await api(`/api/tests/${TEST_ID}/start`, {method: 'POST', body: JSON.stringify({destructive_confirmed: destructive, confirmation_device: destructive ? input.value : null})});
    location.href = `/tasks/${TEST_ID}/live`;
  } catch (error) {
    document.querySelector('#detail-message').innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
  }
};

document.querySelector('#refresh-detail').onclick = loadDetail;
loadDetail();
