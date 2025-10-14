import cfg from './config.js';

const elChat = document.getElementById('chat');
const elInput = document.getElementById('input');
const elSend = document.getElementById('send');
const elStatus = document.getElementById('status');
const elResults = document.getElementById('results');

const clientId = String(cfg.CLIENT_ID || '234');
let coords = { latitude: 58.107415, longitude: -12.075336 }; // Default fallback coords
let history = []; // array of { role: 'user'|'assistant', content: string }

// Geolocation disabled; always use configured coordinates.

elSend.addEventListener('click', onSend);
elInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    onSend();
  }
});

function renderMessage(role, content) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.textContent = content;
  elChat.appendChild(div);
  elChat.scrollTop = elChat.scrollHeight;
}

async function onSend() {
  const text = (elInput.value || '').trim();
  if (!text) return;

  // Display user message immediately
  renderMessage('user', text);
  clearResults();

  // Prepare request: do NOT include the current message in conversation_history
  const payload = {
    latitude: coords.latitude,
    longitude: coords.longitude,
    client_id: clientId,
    query: text,
    conversation_history: history.slice(-5), // last 5 turns from previous messages
  };

  let reply = '';
  let searchTriggered = false;
  let resultList = null;
  let total = null;
  let errorMessage = '';

  setBusy(true, 'Thinking...');
  try {
    const res = await fetch(cfg.API_BASE_URL + '/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const errBody = await res.json();
        if (errBody && (errBody.detail || errBody.message)) {
          detail += `: ${errBody.detail || errBody.message}`;
        }
      } catch {}
      throw new Error(detail);
    }

    const data = await res.json();
    reply = typeof data?.ai_response === 'string'
      ? data.ai_response
      : typeof data?.response === 'string'
        ? data.response
        : '';

    errorMessage = typeof data?.error === 'string' ? data.error : '';

    searchTriggered = Object.prototype.hasOwnProperty.call(data || {}, 'results');
    if (searchTriggered) {
      resultList = Array.isArray(data.results) ? data.results : [];
      total = typeof data?.total === 'number' ? data.total : null;
      if (!reply) {
        reply = resultList.length > 0
          ? 'Here are a few options around Sangamner that could help.'
          : 'I could not find listings for that just yet, but feel free to try another query!';
      }
    }
  } catch (err) {
    console.error(err);
    errorMessage = err?.message ? String(err.message) : 'Unexpected error';
    const detail = errorMessage && errorMessage !== 'Unexpected error'
      ? ` (${errorMessage})`
      : '';
    reply = `Sorry, something went wrong. Please try again in a moment.${detail}`;
  } finally {
    setBusy(false);
    elInput.value = '';
    elInput.focus();
  }

  if (searchTriggered) {
    renderResults(resultList || [], { total });
  }

  history.push({ role: 'user', content: text });
  if (reply) {
    history.push({ role: 'assistant', content: reply });
  }
  if (history.length > 10) {
    history = history.slice(-10);
  }

  renderMessage('assistant', reply || 'I am here if you need anything else.');
  setStatus(errorMessage ? `Warning: ${errorMessage}` : '');
}

function setBusy(busy, message) {
  elSend.disabled = !!busy;
  elInput.disabled = !!busy;
  if (typeof message === 'string') {
    setStatus(message);
  }
}

function setStatus(message = '') {
  elStatus.textContent = message;
}

function clearResults() {
  if (!elResults) return;
  elResults.innerHTML = '';
  elResults.classList.add('hidden');
}

function renderResults(results, meta = {}) {
  if (!elResults) return;
  elResults.innerHTML = '';

  if (!results) {
    elResults.classList.add('hidden');
    return;
  }

  const header = document.createElement('div');
  header.className = 'results-header';
  const total = typeof meta.total === 'number' ? meta.total : results.length;
  header.textContent = total > 0 ? `Found ${total} option${total === 1 ? '' : 's'} nearby` : 'No matches found right now';
  elResults.appendChild(header);

  if (results.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'result-empty';
    empty.textContent = 'No Sangamner listings matched this search. Try another query or tweak the location.';
    elResults.appendChild(empty);
    elResults.classList.remove('hidden');
    return;
  }

  results.forEach((item) => {
    const card = createResultCard(item);
    elResults.appendChild(card);
  });

  elResults.classList.remove('hidden');
}

function createResultCard(item = {}) {
  const card = document.createElement('div');
  card.className = 'result-card';

  const payload = item.payload || {};
  const title = payload.business_name || payload.business_type || 'Unnamed business';
  const heading = document.createElement('h3');
  heading.textContent = title;
  card.appendChild(heading);

  const metaWrap = document.createElement('div');
  metaWrap.className = 'result-meta';

  const phone = payload.phone || '';
  if (phone) {
    const span = document.createElement('span');
    span.textContent = phone;
    metaWrap.appendChild(span);
  }

  const distance = formatDistance(item.distance_km);
  if (distance) {
    const span = document.createElement('span');
    span.textContent = distance;
    metaWrap.appendChild(span);
  }

  const city = payload.city || '';
  if (city) {
    const span = document.createElement('span');
    span.textContent = city;
    metaWrap.appendChild(span);
  }

  if (metaWrap.childElementCount > 0) {
    card.appendChild(metaWrap);
  }

  const description = payload.description || '';
  if (description) {
    const descEl = document.createElement('div');
    descEl.className = 'result-description';
    descEl.textContent = description;
    card.appendChild(descEl);
  }

  return card;
}

function formatDistance(value) {
  if (value === null || value === undefined || value === '') return '';
  const num = Number(value);
  if (Number.isNaN(num)) return '';
  if (!Number.isFinite(num) || num < 0) return '';
  if (num === 0) return '0 km away';
  if (num < 1) {
    return `${(num * 1000).toFixed(0)} m away`;
  }
  return `${num.toFixed(1)} km away`;
}
