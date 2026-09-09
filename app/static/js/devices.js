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
  const content = document.querySelector('#smart-content');
  content.innerHTML = '<pre id="smart-output">读取中...</pre>';
  new bootstrap.Modal('#smartModal').show();
  try {
    const smart = await api(`/api/devices/${device.replace(/^\//, '')}/smart`);
    const {raw_data: raw, raw_json: rawJson, ...summary} = smart;
    const rows = (raw?.fields || []).map(field => `<tr>
      <td><code>${escapeDeviceText(field.byte_field)}</code></td>
      <td>${escapeDeviceText(field.name)}</td>
      <td>${field.value === null ? '—' : escapeDeviceText(field.value)}${field.unit ? ` ${escapeDeviceText(field.unit)}` : ''}</td>
      <td class="raw-hex">${escapeDeviceText(field.hex)}</td>
      <td>${escapeDeviceText(field.description)}</td>
    </tr>`).join('');
    const rawBlock = raw?.available ? `<details class="smart-raw" open><summary>512-byte Raw Data 字段解析</summary>
      <div class="table-responsive"><table class="table smart-raw-table"><thead><tr><th>Byte</th><th>字段</th><th>解析值</th><th>原始 Hex</th><th>含义</th></tr></thead><tbody>${rows}</tbody></table></div>
      <details class="smart-raw nested"><summary>完整 512-byte Hex Dump</summary><pre>${escapeDeviceText(raw.hex_dump)}</pre></details>
    </details>` : `<div class="alert alert-warning">Raw Data 获取失败：${escapeDeviceText(raw?.error || '未知错误')}</div>`;
    content.innerHTML = `<h6>标准化 SMART 指标</h6><pre id="smart-output">${escapeDeviceText(JSON.stringify(summary, null, 2))}</pre>
      ${rawBlock}
      <details class="smart-raw"><summary>nvme-cli 完整原始 JSON</summary><pre>${escapeDeviceText(JSON.stringify(rawJson || {}, null, 2))}</pre></details>`;
  } catch (error) {
    content.innerHTML = `<div class="alert alert-danger">${escapeDeviceText(error.message)}</div>`;
  }
}

loadDevices();
