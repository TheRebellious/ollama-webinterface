/**
 * Send an HTTP GET request to backend endpoint and parse JSON response.
 *
 * @param {string} path - Request URL/path.
 * @returns {Promise<any>} Parsed JSON response.
 */
export async function get(path) {
  const response = await fetch(path);
  if (!response.ok) {
    // FG-004: Offline detection - show status on network errors (503, ECONNREFUSED, ENOTFOUND)
    if ([503, 502].includes(response.status)) {
      console.warn("Server error - may be offline or over rate limit");
    } else if (response.status === 401) {
      throw new Error("Authentication required");
    } else {
      const message = await response.text();
      throw new Error(message || `HTTP ${response.status}`);
    }
  }
  return response.json();
}

/**
 * Retry a fetch request with exponential backoff on transient network errors.
 * Returns the response or null if max retries exhausted.
 *
 * @param {string} path - Request path.
 * @param {object} [options] - Fetch options.
 * @param {number} [maxRetries=3] - Maximum retry attempts.
 * @param {number} [baseDelay=1000] - Initial delay in ms between retries.
 * @returns {Promise<Response|null>} Response or null after max retries.
 */
export async function fetchWithRetry(path, options = {}, maxRetries = 3, baseDelay = 1000) {
  let lastError;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(path, options);
      return response;
    } catch (error) {
      lastError = error;
      if (attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt);
        console.warn(`Network error: ${error.message}, retrying in ${delay}ms...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  // Handle errors after retries exhausted
  if (lastError instanceof TypeError && lastError.message.includes("fetch")) {
    console.warn("Network error during fetch");
  } else if (lastError.message === "Failed to fetch") {
    console.warn("Failed to fetch - may be offline or server unreachable");
  }
  return null;
}

/**
 * Send an HTTP POST request with JSON payload.
 *
 * @param {string} path - Request URL/path.
 * @param {any} payload - Object to JSON-serialize and send in request body.
 * @returns {Promise<Response>} Raw Fetch Response object (useful for body stream or json).
 */
export async function post(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `HTTP ${response.status}`);
  }
  return response;
}

/**
 * Retry a POST request with exponential backoff on transient network errors.
 * Returns the response or null if max retries exhausted.
 *
 * @param {string} path - Request path.
 * @param {any} payload - Object to JSON-serialize and send in request body.
 * @param {object} [options] - Fetch options.
 * @param {number} [maxRetries=3] - Maximum retry attempts.
 * @param {number} [baseDelay=1000] - Initial delay in ms between retries.
 * @returns {Promise<Response|null>} Response or null after max retries.
 */
export async function postWithRetry(path, payload, options = {}, maxRetries = 3, baseDelay = 1000) {
  let lastError;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        ...options,
      });
      return response;
    } catch (error) {
      lastError = error;
      if (attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt);
        console.warn(`Network error: ${error.message}, retrying in ${delay}ms...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  // Handle errors after retries exhausted
  if (lastError instanceof TypeError && lastError.message.includes("fetch")) {
    console.warn("Network error during fetch");
  } else if (lastError.message === "Failed to fetch") {
    console.warn("Failed to fetch - may be offline or server unreachable");
  }
  return null;
}
