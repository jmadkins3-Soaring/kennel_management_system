import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import CalendarGrid from './CalendarGrid'
import OverdueBanner from './OverdueBanner'
import QuickAddWizard from './QuickAddWizard'
import CheckInModal from './CheckInModal'
import CheckOutModal from './CheckOutModal'
import ReservationDetailModal from './ReservationDetailModal'
import IncidentFormModal from './IncidentFormModal'

export default function CalendarPage() {
  const navigate = useNavigate()
  const [modal, setModal] = useState(null) // { type, cell }
  const [overdueItems, setOverdueItems] = useState([])
  const [refresh, setRefresh] = useState(0)

  const handleAction = useCallback((action, cell) => {
    if (action === 'new-reservation') {
      setModal({ type: 'quick-add', cell })
    } else if (action === 'checkin') {
      setModal({ type: 'checkin', cell })
    } else if (action === 'checkout') {
      setModal({ type: 'checkout', cell })
    } else if (action === 'view-reservation') {
      setModal({ type: 'reservation-detail', cell })
    } else if (action === 'add-incident') {
      setModal({ type: 'incident', cell })
    } else if (action === 'view-dog') {
      navigate(`/dogs?highlight=${cell.reservationId}`)
    } else if (action === 'view-owner') {
      navigate(`/owners`)
    }
  }, [navigate])

  function closeModal() { setModal(null) }
  function afterAction() { setModal(null); setRefresh(r => r + 1) }
  function handleOverdueDismiss(id) {
    setOverdueItems(items => items.map(i => i.reservation_id === id ? { ...i, dismissed: true } : i))
  }

  return (
    <Layout>
      <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - var(--nav-h))' }}>
        <OverdueBanner items={overdueItems} onDismiss={handleOverdueDismiss} />

        <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', background: '#fff', display: 'flex', alignItems: 'center', gap: 10 }}>
          <h1 style={{ fontSize: 16, fontWeight: 600 }}>Calendar</h1>
          <div style={{ flex: 1 }} />
          <button className="btn btn-primary btn-sm" onClick={() => setModal({ type: 'quick-add', cell: null })}>
            + Quick Add Schedule
          </button>
        </div>

        <CalendarGrid key={refresh} onAction={handleAction} />

        {modal?.type === 'quick-add' && (
          <QuickAddWizard
            prefill={modal.cell}
            onClose={closeModal}
            onSuccess={afterAction}
          />
        )}
        {modal?.type === 'checkin' && (
          <CheckInModal
            reservationId={modal.cell.reservationId}
            onClose={closeModal}
            onSuccess={afterAction}
          />
        )}
        {modal?.type === 'checkout' && (
          <CheckOutModal
            reservationId={modal.cell.reservationId}
            onClose={closeModal}
            onSuccess={afterAction}
          />
        )}
        {modal?.type === 'reservation-detail' && (
          <ReservationDetailModal
            reservationId={modal.cell.reservationId}
            onClose={closeModal}
            onRefresh={afterAction}
          />
        )}
        {modal?.type === 'incident' && (
          <IncidentFormModal
            reservationId={modal.cell.reservationId}
            onClose={closeModal}
            onSuccess={closeModal}
          />
        )}
      </div>
    </Layout>
  )
}
