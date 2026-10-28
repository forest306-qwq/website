(() => {
  'use strict';
  async function send(path, data) {
    const response = await fetch(path, {method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: {'Content-Type': 'application/json', 'X-Visitor-Request': '1'},
      body: JSON.stringify(data), signal: AbortSignal.timeout(12000)});
    let result;
    try { result = await response.json(); } catch { throw new Error('服务暂时不可用，请稍后再试。'); }
    if (!response.ok || !result.ok) throw new Error(result.error || '提交失败，请稍后再试。');
  }
  const form = document.querySelector('form[data-kind]');
  const error = document.getElementById('form-error');
  if (form) form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button');
    if (button.disabled) return;
    button.disabled = true; error.textContent = '';
    const guest = form.dataset.kind === 'guest';
    const input = form.querySelector('input');
    try {
      await send(guest ? '/_visitor/enter' : '/_visitor/admin-login',
        guest ? {nickname: input.value.trim()} : {password: input.value});
      // Confirm that the browser retained the Secure cookie before leaving the form.
      // Reloading retains the original article URL and fragment.
      if (guest) {
        const check = await fetch('/_visitor/session', {cache: 'no-store', credentials: 'same-origin', signal: AbortSignal.timeout(8000)});
        if (check.status !== 204) throw new Error('浏览器没有保存登录状态，请允许本站使用 Cookie 后重试。');
      }
      location.reload();
    } catch (problem) {
      error.textContent = problem.name === 'TimeoutError' ? '连接超时，请稍后重试。' :
        (problem instanceof TypeError ? '连接失败，请检查网络后重试。' : problem.message);
      button.disabled = false;
      input.focus();
    }
  });
  const logout = document.getElementById('logout');
  if (logout) logout.addEventListener('click', async () => {
    logout.disabled = true;
    try { await send('/_visitor/admin-logout', {}); location.reload(); }
    catch (problem) { error.textContent = problem.message; logout.disabled = false; }
  });
})();
