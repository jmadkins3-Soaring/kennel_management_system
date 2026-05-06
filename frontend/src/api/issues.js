import client from './client'

export const listIssues = (params = {}) =>
  client.get('/issues', { params }).then(r => r.data)

export const getIssue = id =>
  client.get(`/issues/${id}`).then(r => r.data)

export const createIssue = body =>
  client.post('/issues', body).then(r => r.data)

export const resolveIssue = (id, body) =>
  client.post(`/issues/${id}/resolve`, body).then(r => r.data)
