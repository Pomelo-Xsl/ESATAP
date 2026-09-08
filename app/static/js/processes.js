function processMessage(text, type = 'success') {
  document.querySelector('#process-message').innerHTML = `<div class="alert alert-${type === 'error' ? 'danger' : 'success'}">${text}</div>`;
}

async function loadProcesses() {
  const body = document.querySelector('#process-rows');
  try {
    const rows = await api('/api/tests/processes/running');
    document.querySelector('#process-count').textContent = rows.filter(item => item.running).length;
    body.innerHTML = rows.length ? rows.map(item => `<tr>
      <td><code>${item.test_id}</code></td><td>${item.pid}</td>
      <td><span class="status ${item.running ? 'status-running' : 'status-stopped'}">${item.running ? '运行中' : '已结束'}</span></td>
      <td><a href="/tasks/${item.test_id}/live">实时监控</a></td>
      <td><button class="btn btn-sm btn-outline-danger" data-stop="${item.test_id}">停止</button></td></tr>`).join('')
      : '<tr><td colspan="5" class="empty">当前没有由本平台运行的 fio 进程</td></tr>';
    body.querySelectorAll('[data-stop]').forEach(button => button.onclick = () => stopProcess(button.dataset.stop));
  } catch (error) {
    body.innerHTML = `<tr><td colspan="5" class="empty">读取失败：${error.message}</td></tr>`;
  }
}

async function stopProcess(id) {
  if (!confirm('确定停止这个任务对应的 fio 进程？')) return;
  try {
    await api(`/api/tests/${id}/stop`, {method: 'POST'});
    processMessage('停止信号已发送');
    setTimeout(loadProcesses, 700);
  } catch (error) { processMessage(error.message, 'error'); }
}

document.querySelector('#refresh-processes').onclick = loadProcesses;
loadProcesses();
setInterval(loadProcesses, 5000);
