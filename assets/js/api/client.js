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
