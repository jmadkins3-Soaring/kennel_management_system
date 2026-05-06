import axios from 'axios'

export async function login(username, password) {
  const params = new URLSearchParams({ username, password })
  const { data } = await axios.post('/api/auth/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data
}
