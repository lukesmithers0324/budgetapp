document.getElementById('f').onsubmit = async e => {
  e.preventDefault();
  const r = await fetch('/api/login', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Budget': '1'}, body: JSON.stringify({password: pw.value, code: code.value})});
  if (r.ok) { const n = new URLSearchParams(location.search).get('next'); location.href = n && n[0] === '/' && n[1] !== '/' ? n : '/'; }
  else document.getElementById('err').textContent = (await r.json().catch(() => ({}))).error || 'Login failed.';
};
