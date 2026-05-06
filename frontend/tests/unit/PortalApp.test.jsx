import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { PortalEntry } from '../../src/pages/Portal/PortalApp'
import * as portalApi from '../../src/api/portal'

vi.mock('../../src/api/portal', () => ({
  verifyToken:               vi.fn(),
  getPortalDogs:             vi.fn(),
  getPortalReservations:     vi.fn(),
  createPortalReservation:   vi.fn(),
  updatePortalReservation:   vi.fn(),
  cancelPortalReservation:   vi.fn(),
  getPortalAvailability:     vi.fn(),
  requestLink:               vi.fn(),
}))

vi.mock('react-router-dom', async (importActual) => ({
  ...(await importActual()),
  useParams: () => ({ token: 'test-token' }),
}))

function setup() {
  return render(<MemoryRouter><PortalEntry /></MemoryRouter>)
}

describe('PortalEntry — token verification', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    portalApi.getPortalDogs.mockResolvedValue([])
    portalApi.getPortalReservations.mockResolvedValue([])
  })

  it('shows spinner while verifying', () => {
    portalApi.verifyToken.mockReturnValue(new Promise(() => {}))
    setup()
    expect(document.querySelector('.spinner')).toBeInTheDocument()
  })

  it('shows error message and request-link form on invalid token', async () => {
    portalApi.verifyToken.mockRejectedValue({
      response: { data: { detail: 'Token expired' } },
    })
    setup()
    // error rendered as: <p>⚠️ {error}</p> — two text nodes, so match with regex
    await screen.findByText(/token expired/i)
    expect(screen.getByRole('button', { name: /request link/i })).toBeInTheDocument()
  })

  it('falls back to generic message when error has no detail', async () => {
    portalApi.verifyToken.mockRejectedValue(new Error('network'))
    setup()
    await screen.findByText(/invalid or expired link/i)
  })

  it('stores session_token in sessionStorage on valid token', async () => {
    portalApi.verifyToken.mockResolvedValue({ session_token: 'sess-xyz' })
    setup()
    await waitFor(() => expect(sessionStorage.getItem('portal_token')).toBe('sess-xyz'))
  })

  it('renders PortalHome tabs after successful verification', async () => {
    portalApi.verifyToken.mockResolvedValue({ session_token: 'sess' })
    setup()
    await screen.findByText(/my dogs/i)
    expect(screen.getByRole('button', { name: /reservations/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /availability/i })).toBeInTheDocument()
  })
})

describe('RequestNewLink', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    portalApi.verifyToken.mockRejectedValue({ response: { data: { detail: 'Expired' } } })
  })

  it('sends email and shows confirmation on success', async () => {
    portalApi.requestLink.mockResolvedValue({})
    setup()
    await screen.findByRole('button', { name: /request link/i })

    await userEvent.type(screen.getByPlaceholderText(/your email/i), 'user@example.com')
    await userEvent.click(screen.getByRole('button', { name: /request link/i }))

    await screen.findByText(/link sent/i)
  })

  it('shows error message when request-link fails', async () => {
    portalApi.requestLink.mockRejectedValue({ response: { data: { detail: 'Email not found' } } })
    setup()
    await screen.findByRole('button', { name: /request link/i })

    await userEvent.type(screen.getByPlaceholderText(/your email/i), 'x@y.com')
    await userEvent.click(screen.getByRole('button', { name: /request link/i }))

    await screen.findByText('Email not found')
  })

  it('hides the form after a successful send', async () => {
    portalApi.requestLink.mockResolvedValue({})
    setup()
    await screen.findByRole('button', { name: /request link/i })

    await userEvent.type(screen.getByPlaceholderText(/your email/i), 'a@b.com')
    await userEvent.click(screen.getByRole('button', { name: /request link/i }))

    await screen.findByText(/link sent/i)
    expect(screen.queryByRole('button', { name: /request link/i })).not.toBeInTheDocument()
  })
})

describe('PortalHome — My Dogs tab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    portalApi.verifyToken.mockResolvedValue({ session_token: 'sess' })
    portalApi.getPortalReservations.mockResolvedValue([])
  })

  it('shows "No dogs on file" when list is empty', async () => {
    portalApi.getPortalDogs.mockResolvedValue([])
    setup()
    await screen.findByText(/no dogs on file/i)
  })

  it('renders dog name, breed, and size class', async () => {
    portalApi.getPortalDogs.mockResolvedValue([
      { dog_id: 'd1', name: 'Buddy', breed: 'Golden', size_class: 'L', vaccination_records: [] },
    ])
    setup()
    await screen.findByText('Buddy')
    expect(screen.getByText(/golden/i)).toBeInTheDocument()
  })

  it('shows medical notes in red when present', async () => {
    portalApi.getPortalDogs.mockResolvedValue([
      { dog_id: 'd1', name: 'Buddy', breed: 'Golden', size_class: 'L',
        medical_notes: 'Allergic to chicken', vaccination_records: [] },
    ])
    setup()
    await screen.findByText(/allergic to chicken/i)
  })
})

describe('PortalHome — Reservations tab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    portalApi.verifyToken.mockResolvedValue({ session_token: 'sess' })
    portalApi.getPortalDogs.mockResolvedValue([])
  })

  it('shows "No reservations found" when list is empty', async () => {
    portalApi.getPortalReservations.mockResolvedValue([])
    setup()
    await screen.findByText(/my dogs/i)
    await userEvent.click(screen.getByRole('button', { name: /reservations/i }))
    await screen.findByText(/no reservations found/i)
  })

  it('renders Scheduled status for an upcoming reservation', async () => {
    portalApi.getPortalReservations.mockResolvedValue([
      {
        reservation_id: 'r1',
        dropoff_datetime: '2026-06-01T09:00:00',
        pickup_datetime:  '2026-06-05T09:00:00',
        pickup_open_ended: false,
        cancelled: false,
        checkin_datetime: null,
        checkout_datetime: null,
      },
    ])
    setup()
    await screen.findByText(/my dogs/i)
    await userEvent.click(screen.getByRole('button', { name: /reservations/i }))
    await screen.findByText(/scheduled/i)
  })

  it('shows Modify and Cancel buttons for an unchecked-in reservation', async () => {
    portalApi.getPortalReservations.mockResolvedValue([
      {
        reservation_id: 'r1',
        dropoff_datetime: '2026-06-01T09:00:00',
        pickup_datetime:  '2026-06-05T09:00:00',
        pickup_open_ended: false,
        cancelled: false,
        checkin_datetime: null,
        checkout_datetime: null,
      },
    ])
    setup()
    await screen.findByText(/my dogs/i)
    await userEvent.click(screen.getByRole('button', { name: /reservations/i }))
    await screen.findByRole('button', { name: /modify/i })
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument()
  })
})

describe('PortalHome — Availability tab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    portalApi.verifyToken.mockResolvedValue({ session_token: 'sess' })
    portalApi.getPortalDogs.mockResolvedValue([])
    portalApi.getPortalReservations.mockResolvedValue([])
  })

  it('renders size class select and date range inputs', async () => {
    setup()
    await screen.findByText(/my dogs/i)
    await userEvent.click(screen.getByRole('button', { name: /availability/i }))
    expect(screen.getByRole('combobox')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /check availability/i })).toBeInTheDocument()
  })

  it('shows availability table after check', async () => {
    portalApi.getPortalAvailability.mockResolvedValue([
      { date: '2026-06-01', available: true },
      { date: '2026-06-02', available: false },
    ])
    setup()
    await screen.findByText(/my dogs/i)
    await userEvent.click(screen.getByRole('button', { name: /availability/i }))
    await userEvent.click(screen.getByRole('button', { name: /check availability/i }))
    await screen.findByText('2026-06-01')
    expect(screen.getByText('Available')).toBeInTheDocument()
    expect(screen.getByText('Busy')).toBeInTheDocument()
  })
})
