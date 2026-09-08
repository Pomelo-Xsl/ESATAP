const destructiveProfiles = new Set(['seq_write_128k', 'rand_write_4k', 'randrw_70_30', 'randrw_50_50', 'stress_rand_write', 'stress_seq_write']);
const destructiveRw = new Set(['write', 'trim', 'randwrite', 'randtrim', 'rw', 'readwrite', 'randrw', 'trimwrite']);
const form = document.querySelector('#test-form');
const type = document.querySelector('#test-type');
const danger = document.querySelector('#danger-box');

const optionalTextFields = [
  'block_size', 'block_size_range', 'block_size_split', 'io_size', 'offset', 'offset_increment', 'buffer_pattern',
  'rw', 'random_distribution', 'random_generator', 'rate', 'rate_min', 'rate_process',
  'sync_file_range', 'verify', 'verify_pattern', 'cpus_allowed', 'cpus_allowed_policy',
  'numactl_cpu_nodes', 'numactl_mem_nodes', 'numa_cpu_nodes', 'numa_mem_policy', 'io_submit_mode', 'rw_sequencer', 'steadystate', 'zonemode',
  'zonesize', 'zonerange', 'zoneskip', 'zonecapacity', 'unified_rw_reporting',
];
const optionalNumberFields = [
  'iodepth_batch', 'iodepth_batch_complete_min', 'iodepth_batch_complete_max', 'iodepth_low',
  'ramp_time_seconds', 'start_delay_seconds', 'loops', 'number_ios', 'buffer_compress_percentage',
  'dedupe_percentage', 'rwmixread', 'rwmixcycle', 'percentage_random', 'randseed', 'rate_iops',
  'rate_iops_min', 'rate_cycle_ms', 'thinktime_us', 'thinktime_spin_us', 'thinktime_blocks',
  'latency_target_us', 'latency_window_us', 'latency_percentile', 'fsync', 'fdatasync',
  'verify_interval', 'trim_percentage', 'trim_backlog', 'trim_backlog_batch', 'nice', 'prio_class',
  'prio', 'sqthread_poll_cpu', 'cmdprio_percentage', 'cmdprio_class', 'cmdprio', 'log_hist_msec',
  'log_hist_coarseness', 'log_compression', 'steadystate_duration_seconds', 'steadystate_ramp_time_seconds',
  'max_open_zones', 'job_max_open_zones',
];
const optionalBooleanFields = [
  'invalidate', 'refill_buffers', 'scramble_buffers', 'zero_buffers', 'thread', 'serialize_overlap',
  'randrepeat', 'allrandrepeat', 'norandommap', 'softrandommap', 'latency_run', 'end_fsync',
  'do_verify', 'verify_fatal', 'verify_dump', 'trim_verify_zero', 'hipri', 'fixedbufs',
  'registerfiles', 'sqthread_poll', 'atomic', 'nowait', 'read_beyond_wp', 'log_max_value', 'log_offset',
];

function isDestructive() {
  const rw = form.elements.rw.value;
  const trimPercentage = Number(form.elements.trim_percentage.value || 0);
  return destructiveProfiles.has(type.value) || destructiveRw.has(rw) || form.elements.precondition.checked || trimPercentage > 0;
}

function syncForm() {
  const isQdScan = type.value === 'qd_scan';
  danger.classList.toggle('d-none', !isDestructive());
  document.querySelector('#qd-scan-options').classList.toggle('d-none', !isQdScan);
  document.querySelector('#queue-depth-field').classList.toggle('d-none', isQdScan);
  if (type.value.startsWith('stress_') && form.elements.runtime_seconds.value === '60') {
    form.elements.runtime_seconds.value = '86400';
  }
}

type.addEventListener('change', syncForm);
form.elements.rw.addEventListener('change', syncForm);
form.elements.precondition.addEventListener('change', syncForm);
form.elements.trim_percentage.addEventListener('input', syncForm);
document.querySelectorAll('.block-mode').forEach(input => input.addEventListener('input', () => {
  if (!input.value) return;
  document.querySelectorAll('.block-mode').forEach(other => {
    if (other !== input) other.value = '';
  });
}));
syncForm();

api('/api/devices').then(devices => {
  const select = document.querySelector('#device-select');
  select.innerHTML = '<option value="">请选择满足安全条件的 NVMe SSD</option>' + devices.map(device => {
    const reasons = (device.ineligible_reasons || []).join('、');
    const suffix = device.test_eligible ? '' : `（禁止测试：${reasons}）`;
    return `<option value="${device.namespace}" ${device.test_eligible ? '' : 'disabled'}>${device.namespace} · ${device.model || '未知型号'}${suffix}</option>`;
  }).join('');
}).catch(error => {
  document.querySelector('#device-select').innerHTML = `<option>${error.message}</option>`;
});

function buildParameters(data) {
  const parameters = {
    io_engine: data.get('io_engine'),
    queue_depth: Number(data.get('queue_depth')),
    num_jobs: Number(data.get('num_jobs')),
    runtime_seconds: Number(data.get('runtime_seconds')),
    size: data.get('size'),
    direct: data.get('direct') === 'true',
    time_based: data.get('time_based') === 'true',
    precondition: form.elements.precondition.checked,
    group_reporting: data.get('group_reporting') === 'true',
    latency_percentiles: data.get('latency_percentiles') === 'true',
    log_avg_msec: Number(data.get('log_avg_msec')),
    percentile_list: data.get('percentile_list'),
  };
  optionalTextFields.forEach(name => {
    const value = String(data.get(name) || '').trim();
    if (value) parameters[name] = value;
  });
  optionalNumberFields.forEach(name => {
    const raw = String(data.get(name) || '').trim();
    if (raw !== '') parameters[name] = Number(raw);
  });
  optionalBooleanFields.forEach(name => {
    if (form.elements[name].checked) parameters[name] = true;
  });
  if (type.value === 'qd_scan') {
    parameters.queue_depths = String(data.get('queue_depths')).split(',').map(value => Number(value.trim())).filter(Number.isFinite);
  }
  return parameters;
}

function buildPayload(data) {
  const destructive = isDestructive();
  return {
    name: data.get('name'),
    device: data.get('device'),
    test_type: data.get('test_type'),
    parameters: buildParameters(data),
    destructive_confirmed: destructive ? document.querySelector('#danger-confirm').checked : false,
    confirmation_device: destructive ? document.querySelector('#confirm-device').value : null,
  };
}

function escapeHtml(value) {
  const element = document.createElement('div');
  element.textContent = value;
  return element.innerHTML;
}

function renderCommandArgument(argument) {
  const separator = argument.indexOf('=');
  if (separator < 0) return `<span class="command-option">${escapeHtml(argument)}</span>`;
  return `<span class="command-option">${escapeHtml(argument.slice(0, separator))}</span><span class="command-equals">=</span><span class="command-value">${escapeHtml(argument.slice(separator + 1))}</span>`;
}

function renderCommandGroups(item) {
  const totalArguments = item.groups.reduce((total, group) => total + group.arguments.length, 0);
  let position = 0;
  const executable = `<div class="command-line command-executable"><span>${escapeHtml(item.argv[0] || 'fio')}</span><span class="command-continuation">\\</span></div>`;
  const groups = item.groups.map(group => `<div class="command-group">
    <div class="command-group-label">${escapeHtml(group.label)}</div>
    <div class="command-group-lines">${group.arguments.map(argument => {
      position += 1;
      return `<div class="command-line"><span class="command-indent">&nbsp;&nbsp;</span><span class="command-token">${renderCommandArgument(argument)}</span>${position < totalArguments ? '<span class="command-continuation">\\</span>' : ''}</div>`;
    }).join('')}</div>
  </div>`).join('');
  return executable + groups;
}

let previewTimer;
let previewRequest = 0;
let previewCommandText = '';

async function refreshCommandPreview() {
  const data = new FormData(form);
  const target = String(data.get('device') || '');
  const preview = document.querySelector('#command-preview');
  const status = document.querySelector('#command-preview-status');
  const copy = document.querySelector('#copy-command');
  if (!target) {
    preview.innerHTML = '<div class="command-placeholder">选择目标 Namespace 后将在此显示完整命令。</div>';
    status.textContent = '请选择目标设备';
    copy.disabled = true;
    previewCommandText = '';
    return;
  }
  const requestNumber = ++previewRequest;
  status.textContent = '正在生成…';
  try {
    const result = await api('/api/tests/preview-command', {method: 'POST', body: JSON.stringify(buildPayload(data))});
    if (requestNumber !== previewRequest) return;
    previewCommandText = result.commands.map(item => item.command).join('\n\n');
    preview.innerHTML = result.commands.map((item, index) => `<div class="command-item">
      <div class="command-item-head"><span>${item.phase === 'precondition' ? '全盘写预处理' : item.phase.startsWith('qd_') ? `QD ${item.queue_depth}` : '测试命令'}</span><span>${index + 1} / ${result.commands.length}</span></div>
      <div class="command-code">${renderCommandGroups(item)}</div>
    </div>`).join('');
    status.textContent = `${result.commands.length} 条命令`;
    copy.disabled = false;
  } catch (error) {
    if (requestNumber !== previewRequest) return;
    preview.innerHTML = `<div class="alert alert-danger mb-0">${escapeHtml(error.message)}</div>`;
    status.textContent = '参数需要修正';
    copy.disabled = true;
    previewCommandText = '';
  }
}

function scheduleCommandPreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(refreshCommandPreview, 250);
}

form.addEventListener('input', scheduleCommandPreview);
form.addEventListener('change', scheduleCommandPreview);
document.querySelector('#copy-command').addEventListener('click', async () => {
  if (!previewCommandText) return;
  const button = document.querySelector('#copy-command');
  try {
    await navigator.clipboard.writeText(previewCommandText);
    button.textContent = '已复制';
    setTimeout(() => { button.textContent = '复制全部命令'; }, 1600);
  } catch (_error) {
    button.textContent = '复制失败';
  }
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  const data = new FormData(form);
  const payload = buildPayload(data);
  const message = document.querySelector('#form-message');
  try {
    const task = await api('/api/tests', {method: 'POST', body: JSON.stringify(payload)});
    await api(`/api/tests/${task.id}/start`, {method: 'POST', body: JSON.stringify({
      destructive_confirmed: payload.destructive_confirmed,
      confirmation_device: payload.confirmation_device,
    })});
    location.href = `/tasks/${task.id}/live`;
  } catch (error) {
    message.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
  }
});
