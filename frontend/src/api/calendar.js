import client from './client'
import { format } from 'date-fns'

export function getCalendar(startDate, days = 10) {
  return client.get('/calendar', {
    params: { start: format(startDate, 'yyyy-MM-dd'), days },
  }).then(r => r.data)
}

export function getCalendarDay(date) {
  return client.get(`/calendar/day/${format(date, 'yyyy-MM-dd')}`).then(r => r.data)
}

export function getOverduePickups() {
  return client.get('/calendar/overdue').then(r => r.data)
}

export function dismissOverdue(reservationId) {
  return client.post(`/calendar/overdue/${reservationId}/dismiss`).then(r => r.data)
}
