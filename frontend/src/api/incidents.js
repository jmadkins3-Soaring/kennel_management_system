import client from './client'

export const listIncidents = (params = {}) =>
  client.get('/incidents', { params }).then(r => r.data)

export const getIncident = id =>
  client.get(`/incidents/${id}`).then(r => r.data)

export const createIncident = body =>
  client.post('/incidents', body).then(r => r.data)

export const resolveIncident = (id, body) =>
  client.post(`/incidents/${id}/resolve`, body).then(r => r.data)
