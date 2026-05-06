import client from './client'
import { format } from 'date-fns'

function openPdf(url, params) {
  const q = new URLSearchParams(params).toString()
  const token = localStorage.getItem('kms_token')
  // Build a form POST to trigger PDF download with auth header
  // Simplest approach: fetch as blob and open
  return client.get(url, { params, responseType: 'blob' }).then(r => {
    const blob = new Blob([r.data], { type: 'application/pdf' })
    const href = URL.createObjectURL(blob)
    window.open(href, '_blank')
  })
}

export const downloadPacfa = () =>
  openPdf('/reports/pacfa', {})

export const downloadOccupancy = (startDate, endDate) =>
  openPdf('/reports/occupancy', {
    start_date: format(startDate, 'yyyy-MM-dd'),
    end_date:   format(endDate,   'yyyy-MM-dd'),
  })

export const downloadRevenue = (startDate, endDate) =>
  openPdf('/reports/revenue', {
    start_date: format(startDate, 'yyyy-MM-dd'),
    end_date:   format(endDate,   'yyyy-MM-dd'),
  })

export const downloadUpcoming = () =>
  openPdf('/reports/upcoming', {})

export const downloadOpenIncidents = () =>
  openPdf('/reports/open-incidents', {})
