function eligibility(device) {
  if (device.test_eligible) {
    return '<span class="status status-completed">可测试</span>';
  }
  const reasons = (device.ineligible_reasons || ['设备不满足安全测试条件']).join('、');
  return `<span class="status status-failed" title="${reasons}">禁止测试</span>`;
}

async function loadDevices() {
  const grid = document.querySelector('#device-grid');
  grid.innerHTML = '<div class="empty">正在扫描...</div>';
  try {
    const devices = await api('/api/devices');
    grid.innerHTML = devices.length ? '' : '<div class="empty">未发现 NVMe Namespace，请确认 nvme-cli 与系统权限。</div>';
    devices.forEach(device => {
      const reasons = (device.ineligible_reasons || []).join('；');
      const element = document.createElement('div');
      element.className = 'col-xl-6 device-column';
      element.innerHTML = `<div class="panel device-card">
        <div class="panel-head device-card-head"><h2><code>${device.namespace}</code></h2><div class="device-statuses"><span class="status ${device.mounted ? 'status-stopped' : 'status-completed'}">${device.mounted ? '已挂载' : '未挂载'}</span>${eligibility(device)}</div></div>
        <table class="table device-table"><colgroup><col class="label-col"><col class="value-col"><col class="label-col"><col class="value-col"></colgroup><tbody>
          <tr><th>Controller</th><td>${device.controller}</td><th>型号</th><td>${device.model || '—'}</td></tr>
          <tr><th>序列号</th><td>${device.serial || '—'}</td><th>固件</th><td>${device.firmware || '—'}</td></tr>
          <tr><th>容量</th><td>${fmtBytes(device.capacity_bytes)}</td><th>PCIe</th><td>${device.pcie_address || '—'}</td></tr>
          <tr><th>NUMA</th><td>${device.numa_node}</td><th>挂载点</th><td>${(device.mountpoints || []).join(', ') || '—'}</td></tr>
          <tr><th>分区/文件系统</th><td>${device.has_partitions ? '有分区' : '无分区'} / ${device.has_filesystem ? '有文件系统' : '无文件系统'}</td><th>系统盘</th><td>${device.is_system_disk ? '是' : '否'}</td></tr>
        </tbody></table>
        ${reasons ? `<div class="device-block-reason"><strong>禁止测试：</strong>${reasons}</div>` : '<div class="device-ready">设备满足测试条件</div>'}
        <button class="btn btn-outline-light mt-3 smart">读取 SMART</button>
      </div>`;
      element.querySelector('.smart').onclick = () => showSmart(device.namespace);
      grid.appendChild(element);
    });
  } catch (error) {
    grid.innerHTML = `<div class="empty">扫描失败：${error.message}</div>`;
  }
}

async function showSmart(device) {
  const output = document.querySelector('#smart-output');
  output.textContent = '读取中...';
  new bootstrap.Modal('#smartModal').show();
  try {
    output.textContent = JSON.stringify(await api(`/api/devices/${device.replace(/^\//, '')}/smart`), null, 2);
  } catch (error) {
    output.textContent = error.message;
  }
}

loadDevices();
