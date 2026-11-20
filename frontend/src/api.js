const base = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const sessionResponses = new Map();
const inFlight = new Map();
const REQUEST_TIMEOUT_MS = 10000;
const MAX_RETRIES = 3;

function isMultipart(body) {
  return typeof FormData !== 'undefined' && body instanceof FormData;
}

function requestKey(path, options) {
  const method = (options.method || 'GET').toUpperCase();
  if (isMultipart(options.body)) return null;
  const body = typeof options.body === 'string' ? options.body : '';
  return `${method}:${path}:${body}`;
}

const pause = (attempt) => new Promise(resolve => setTimeout(resolve, 250 * (attempt + 1)));

async function fetchJson(path, options = {}) {
  const multipart = isMultipart(options.body);
  const headers = { ...(multipart ? {} : { 'Content-Type': 'application/json' }), ...(options.headers || {}) };
  let lastError;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(base + path, { ...options, headers, signal: controller.signal });
      if (!response.ok) {
        const error = new Error(`request_failed_${response.status}`);
        error.status = response.status;
        throw error;
      }
      return await response.json();
    } catch (error) {
      lastError = error;
      if (error.status >= 400 && error.status < 500) break;
      if (attempt < MAX_RETRIES) await pause(attempt);
    } finally {
      clearTimeout(timeout);
    }
  }
  throw lastError || new Error('request_failed');
}

function fetchOnce(path, options, key) {
  if (key && inFlight.has(key)) return inFlight.get(key);
  const promise = fetchJson(path, options).then(value => {
    if (key) sessionResponses.set(key, value);
    return value;
  }).finally(() => {
    if (key) inFlight.delete(key);
  });
  if (key) inFlight.set(key, promise);
  return promise;
}

/**
 * Successful JSON responses are kept for this browser session. If one is
 * already available, return it immediately and refresh it in the background.
 */
export function api(path, options = {}, { onRefresh } = {}) {
  const key = requestKey(path, options);
  const cached = key ? sessionResponses.get(key) : undefined;
  if (cached !== undefined) {
    fetchOnce(path, options, key).then(value => onRefresh?.(value)).catch(() => {});
    return Promise.resolve(cached);
  }
  return fetchOnce(path, options, key);
}

let healthStarted = false;
export function warmBackend() {
  if (healthStarted) return;
  healthStarted = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  fetch(base + '/health', { signal: controller.signal })
    .catch(() => {})
    .finally(() => clearTimeout(timeout));
}
