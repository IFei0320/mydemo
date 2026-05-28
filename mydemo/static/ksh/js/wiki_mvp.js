  async function callApi(url, payload) {
    const headers = {'Content-Type': 'application/json'};
    const token = window.csrfToken || '';
    if (token) {
      headers['X-CSRFToken'] = token;
    }
    const res = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: payload ? JSON.stringify(payload) : JSON.stringify({})
    });
    return res.json();
  }

  function formatQueryResult(res) {
    const data = (res && res.data) || {};
    const hits = Array.isArray(data.hits) ? data.hits : [];
    const hitText = hits.length
      ? hits.map((item, idx) => `${idx + 1}. ${item.page}`).join('\n')
      : '无';

    return [
      data.answer || '暂无回答',
      '',
      '来源页面：',
      hitText
    ].join('\n');
  }

  const output = document.getElementById('output');
  const question = document.getElementById('question');
  const city = document.getElementById('city');

  document.getElementById('btnIngest').addEventListener('click', async () => {
    output.textContent = '正在摄入...';
    try {
      const data = await callApi('/mydemo/api/wiki/ingest');
      output.textContent = JSON.stringify(data, null, 2);
    } catch (e) {
      output.textContent = '摄入失败: ' + e;
    }
  });

  document.getElementById('btnLint').addEventListener('click', async () => {
    output.textContent = '正在检查...';
    try {
      const data = await callApi('/mydemo/api/wiki/lint');
      output.textContent = JSON.stringify(data, null, 2);
    } catch (e) {
      output.textContent = '检查失败: ' + e;
    }
  });

  document.getElementById('btnQuery').addEventListener('click', async () => {
    output.textContent = '正在查询...';
    try {
      const data = await callApi('/mydemo/api/wiki/query', {question: question.value, city: city.value});
      output.textContent = formatQueryResult(data);
    } catch (e) {
      output.textContent = '查询失败: ' + e;
    }
  });