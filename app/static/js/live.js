const chart = echarts.init(document.querySelector('#live-chart'));
const statusNames = {pending: '等待启动', queued: '排队中', running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止'};
chart.setOption({
  backgroundColor: 'transparent',
  tooltip: {trigger: 'axis'},
  legend: {textStyle: {color: '#9db1b8'}},
  xAxis: {type: 'category', data: [], axisLabel: {color: '#89a3ad'}},
  yAxis: [
    {name: 'IOPS', axisLabel: {color: '#89a3ad'}},
    {name: 'MB/s · μs · °C', axisLabel: {color: '#89a3ad'}},
  ],
  series: [
    {name: 'IOPS', type: 'line', data: [], smooth: true},
    {name: '带宽 MB/s', type: 'line', yAxisIndex: 1, data: []},
    {name: '时延 μs', type: 'line', yAxisIndex: 1, data: []},
    {name: '温度 °C', type: 'line', yAxisIndex: 1, data: []},
  ],
});

function formatElapsed(totalSeconds) {
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return [hours, minutes, remainder].map(value => String(value).padStart(2, '0')).join(':');
}

function elapsedSeconds(task) {
  if (task.duration_seconds !== null && task.duration_seconds !== undefined) {
    return task.duration_seconds;
  }
  if (!task.started_at) return null;
  const startedAt = Date.parse(task.started_at);
  if (!Number.isFinite(startedAt)) return null;
  return Math.max(0, (Date.now() - startedAt) / 1000);
}

async function poll() {
  try {
    const [task, result] = await Promise.all([
      api(`/api/tests/${TEST_ID}`),
      api(`/api/tests/${TEST_ID}/results`),
    ]);
    const queueSuffix = task.status === 'queued' && task.queue_position ? `（第 ${task.queue_position} 位）` : '';
    document.querySelector('#status').textContent = `${statusNames[task.status] || task.status}${queueSuffix}`;
    document.querySelector('#progress').textContent = `${task.progress.toFixed(0)}%`;
    document.querySelector('#stop').textContent = task.status === 'queued' ? '取消排队' : '停止任务';
    const elapsed = elapsedSeconds(task);
    document.querySelector('#elapsed').textContent = elapsed === null ? '—' : formatElapsed(elapsed);

    const timeseries = result.summary?.timeseries || {};
    const iops = timeseries.iops || [];
    const bandwidth = timeseries.bandwidth_kib_s || [];
    const latency = timeseries.latency_ns || [];
    const temperature = timeseries.temperature_kelvin || [];
    chart.setOption({
      xAxis: {data: iops.map(point => `${(point.time_ms / 1000).toFixed(0)}s`)},
      series: [
        {data: iops.map(point => point.value)},
        {data: bandwidth.map(point => point.value * 1024 / 1e6)},
        {data: latency.map(point => point.value / 1000)},
        {data: temperature.map(point => point.value - 273.15)},
      ],
    });
    if (['completed', 'failed', 'stopped'].includes(task.status)) {
      setTimeout(() => location.href = `/tasks/${TEST_ID}`, 1200);
    } else {
      setTimeout(poll, 1500);
    }
  } catch (_error) {
    setTimeout(poll, 3000);
  }
}

document.querySelector('#stop').onclick = async () => {
  const queued = document.querySelector('#status').textContent.startsWith('排队中');
  if (confirm(queued ? '确定取消这个排队任务？' : '只会终止此任务对应的 fio 进程。确定停止？')) {
    await api(`/api/tests/${TEST_ID}/stop`, {method: 'POST'});
  }
};

poll();
