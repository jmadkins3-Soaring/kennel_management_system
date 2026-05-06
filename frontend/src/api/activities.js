import client from './client'

export const listActivities = (params = {}) =>
  client.get('/activities', { params }).then(r => r.data)

export const createActivity = body =>
  client.post('/activities', body).then(r => r.data)

export const confirmActivity = id =>
  client.post(`/activities/${id}/confirm`).then(r => r.data)
