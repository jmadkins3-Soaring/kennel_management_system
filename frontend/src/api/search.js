import client from './client'

export const globalSearch = q =>
  client.get('/search', { params: { q } }).then(r => r.data)
