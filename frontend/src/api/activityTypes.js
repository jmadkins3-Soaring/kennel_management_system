import client from './client'

export const listActivityTypes = () =>
  client.get('/activity-types').then(r => r.data)

export const createActivityType = body =>
  client.post('/activity-types', body).then(r => r.data)

export const updateActivityType = (id, body) =>
  client.put(`/activity-types/${id}`, body).then(r => r.data)
