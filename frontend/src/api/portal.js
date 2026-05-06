import axios from 'axios'

// Portal uses a separate session token, not the staff JWT
const portalClient = axios.create({ baseURL: '/api/portal' })

portalClient.interceptors.request.use(cfg => {
  const token = sessionStorage.getItem('portal_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

export const requestLink = email =>
  axios.post('/api/portal/request-link', { email }).then(r => r.data)

export const verifyToken = token =>
  axios.get(`/api/portal/verify/${token}`).then(r => r.data)

export const getPortalDogs = () =>
  portalClient.get('/dogs').then(r => r.data)

export const getPortalReservations = () =>
  portalClient.get('/reservations').then(r => r.data)

export const createPortalReservation = body =>
  portalClient.post('/reservations', body).then(r => r.data)

export const updatePortalReservation = (id, body) =>
  portalClient.put(`/reservations/${id}`, body).then(r => r.data)

export const cancelPortalReservation = (id, body) =>
  portalClient.post(`/reservations/${id}/cancel`, body).then(r => r.data)

export const getPortalAvailability = params =>
  portalClient.get('/availability', { params }).then(r => r.data)
