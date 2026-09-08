let rows = [];
const statusNames = {pending: '等待中', running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止'};

function showMessage(text, type = 'success') {
  const el = document.querySelector('#task-message');
  el.className = `toast-message show ${type}`;
  el.textContent = text;
  setTimeout(() => el.classList.remove('show'), 3000);
}

function actions(task) {
  const primary = task.status === 'running'
    ? `<a class="btn btn-sm btn-accent" href="/tasks/${task.id}/live">实时监控</a>`
    : `<a class="btn btn-sm btn-outline-light" href="/tasks/${task.id}">查看详情</a>`;
  const analysis = task.status === 'completed'
    ? `<a class="btn btn-sm btn-outline-light" href="/tasks/${task.id}/analysis">结果分析</a>` : '';
  const remove = task.status !== 'running'
    ? `<button class="btn btn-sm btn-outline-danger" data-delete="${task.id}" data-name="${task.name}">删除记录</button>` : '';
  return `<div class="table-actions">${primary}${analysis}${remove}</div>`;
}

function render() {
  const query = document.querySelector('#filter').value.toLowerCase();
  const filtered = rows.filter(task => `${task.name} ${task.device} ${task.status} ${task.test_type}`.toLowerCase().includes(query));
  const body = document.querySelector('#task-rows');
  body.innerHTML = filtered.map(task => `<tr>
    <td><a href="/tasks/${task.id}">${task.name}</a><small class="task-id">${task.id.slice(0, 8)}</small></td>
    <td><code>${task.device}</code></td><td>${task.test_type}</td>
    <td><span class="status status-${task.status}">${statusNames[task.status] || task.status}</span></td>
    <td><div class="progress"><div class="progress-bar" style="width:${task.progress}%"></div></div><small>${task.progress.toFixed(0)}%</small></td>
    <td>${task.duration_seconds ?? '—'}s</td><td>${actions(task)}</td></tr>`).join('') || '<tr><td colspan="7" class="empty">没有匹配任务</td></tr>';
  body.querySelectorAll('[data-delete]').forEach(button => {
    button.onclick = () => deleteTask(button.dataset.delete, button.dataset.name);
  });
}

async function loadTasks() {
  try { rows = await api('/api/tests'); render(); }
  catch (error) { showMessage(error.message, 'error'); }
}

async function deleteTask(id, name) {
  if (!confirm(`确定删除“${name}”的任务记录？\n\n原始测试结果文件会保留。`)) return;
  try {
    await api(`/api/tests/${id}`, {method: 'DELETE'});
    rows = rows.filter(task => task.id !== id);
    render();
    showMessage('任务记录已删除，原始结果已保留');
  } catch (error) { showMessage(error.message, 'error'); }
}

document.querySelector('#filter').oninput = render;
document.querySelector('#refresh-tasks').onclick = loadTasks;
loadTasks();
