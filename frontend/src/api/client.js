import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

client.interceptors.request.use(cfg => {
  const token = localStorage.getItem('kms_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

client.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('kms_token')
      localStorage.removeItem('kms_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default client
