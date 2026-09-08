function eligibility(device) {
  if (device.test_eligible) {
    return '<span class="status status-completed">可测试</span>';
  }
  const reasons = (device.ineligible_reasons || ['设备不满足安全测试条件']).join('、');
  return `<span class="status status-failed" title="${reasons}">禁止测试</span>`;
}

function escapeDeviceText(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
}

async function loadDevices() {
  const grid = document.querySelector('#device-grid');
  grid.innerHTML = '<div class="empty">正在扫描...</div>';
  try {
    const devices = await api('/api/devices');
    grid.innerHTML = devices.length ? '' : '<div class="empty">未发现 NVMe Namespace，请确认 nvme-cli 与系统权限。</div>';
    devices.forEach(device => {
      const reasons = (device.ineligible_reasons || []).join('；');
      const safeReasons = escapeDeviceText(reasons || '设备满足测试条件');
      const safeModel = escapeDeviceText(device.model || '—');
      const safeSerial = escapeDeviceText(device.serial || '—');
      const element = document.createElement('div');
      element.className = 'col-xl-6 device-column';
      element.innerHTML = `<div class="panel device-card">
        <div class="panel-head device-card-head"><h2><code>${device.namespace}</code></h2><div class="device-statuses"><span class="status ${device.mounted ? 'status-stopped' : 'status-completed'}">${device.mounted ? '已挂载' : '未挂载'}</span>${eligibility(device)}</div></div>
        <table class="table device-table"><colgroup><col class="label-col"><col class="value-col"><col class="label-col"><col class="value-col"></colgroup><tbody>
          <tr><th>Controller</th><td class="device-value" title="${escapeDeviceText(device.controller)}">${escapeDeviceText(device.controller)}</td><th>型号</th><td class="device-value" title="${safeModel}">${safeModel}</td></tr>
          <tr><th>序列号</th><td class="device-value" title="${safeSerial}">${safeSerial}</td><th>固件</th><td class="device-value" title="${escapeDeviceText(device.firmware || '—')}">${escapeDeviceText(device.firmware || '—')}</td></tr>
          <tr><th>容量</th><td class="device-value">${fmtBytes(device.capacity_bytes)}</td><th>PCIe</th><td class="device-value" title="${escapeDeviceText(device.pcie_address || '—')}">${escapeDeviceText(device.pcie_address || '—')}</td></tr>
          <tr><th>NUMA</th><td class="device-value">${escapeDeviceText(device.numa_node)}</td><th>挂载点</th><td class="device-value" title="${escapeDeviceText((device.mountpoints || []).join(', ') || '—')}">${escapeDeviceText((device.mountpoints || []).join(', ') || '—')}</td></tr>
          <tr><th>分区/文件系统</th><td class="device-value" title="${device.has_partitions ? '有分区' : '无分区'} / ${device.has_filesystem ? '有文件系统' : '无文件系统'}">${device.has_partitions ? '有分区' : '无分区'} / ${device.has_filesystem ? '有文件系统' : '无文件系统'}</td><th>系统盘</th><td class="device-value">${device.is_system_disk ? '是' : '否'}</td></tr>
          <tr class="eligibility-row"><th>测试资格</th><td colspan="3"><span class="eligibility-detail ${device.test_eligible ? 'eligible' : 'blocked'}" title="${safeReasons}">${device.test_eligible ? '设备满足测试条件' : `禁止测试：${safeReasons}`}</span></td></tr>
        </tbody></table>
        <div class="device-card-actions"><button class="btn btn-outline-light smart">读取 SMART</button></div>
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
