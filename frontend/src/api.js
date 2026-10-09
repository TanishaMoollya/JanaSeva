const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'
export function token() { return localStorage.getItem('janaseva_token') }
export async function request(path, options = {}) {
  const headers = new Headers(options.headers || {})
  if (token()) headers.set('Authorization', `Bearer ${token()}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API}${path}`, { ...options, headers })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try { const body = await response.json(); message = body.detail || message } catch {}
    throw new Error(message)
  }
  return response.status === 204 ? null : response.json()
}
export async function download(path) {
  const headers = new Headers()
  if (token()) headers.set('Authorization', `Bearer ${token()}`)
  const response = await fetch(`${API}${path}`, { headers })
  if (!response.ok) throw new Error('Could not download this attachment')
  return response.blob()
}
