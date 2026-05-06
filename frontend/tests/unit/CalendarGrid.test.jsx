import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CalendarGrid from '../../src/pages/Calendar/CalendarGrid'
import * as calendarApi from '../../src/api/calendar'

vi.mock('../../src/api/calendar', () => ({ getCalendar: vi.fn() }))

vi.mock('../../src/pages/Calendar/CellContextMenu', () => ({
  default: ({ onAction, onClose }) => (
    <div data-testid="context-menu">
      <button onClick={() => onAction('check_in', {})}>CheckIn</button>
      <button onClick={onClose}>Close</button>
    </div>
  ),
}))

function makeData(overrides = {}) {
  return {
    alerts: [],
    kennels: [
      {
        kennel_id: 'k1',
        kennel_number: 'K-01',
        days: Array.from({ length: 10 }, (_, i) => ({
          date: `2026-05-${String(6 + i).padStart(2, '0')}`,
          phases: {
            Morning:   { status: 'Free',     owner_last_name: null,    reservation_id: null },
            Afternoon: { status: 'Assigned', owner_last_name: 'Smith', reservation_id: 'r1' },
            Evening:   { status: 'Free',     owner_last_name: null,    reservation_id: null },
            Night:     { status: 'Free',     owner_last_name: null,    reservation_id: null },
          },
        })),
      },
    ],
    ...overrides,
  }
}

describe('CalendarGrid', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls getCalendar on mount', async () => {
    calendarApi.getCalendar.mockResolvedValue(makeData())
    render(<CalendarGrid />)
    await waitFor(() => expect(calendarApi.getCalendar).toHaveBeenCalledTimes(1))
  })

  it('renders kennel rows after data loads', async () => {
    calendarApi.getCalendar.mockResolvedValue(makeData())
    render(<CalendarGrid />)
    await screen.findByText('K-01')
  })

  it('renders owner last name in assigned cells', async () => {
    calendarApi.getCalendar.mockResolvedValue(makeData())
    render(<CalendarGrid />)
    const cells = await screen.findAllByText('Smith')
    expect(cells.length).toBeGreaterThan(0)
  })

  it('shows error message when API fails', async () => {
    calendarApi.getCalendar.mockRejectedValue({ response: { data: { detail: 'Server error' } } })
    render(<CalendarGrid />)
    await screen.findByText('Server error')
  })

  it('falls back to generic message when error has no detail', async () => {
    calendarApi.getCalendar.mockRejectedValue(new Error('network'))
    render(<CalendarGrid />)
    await screen.findByText('Failed to load calendar')
  })

  it('shows PACFA alert bar when alerts are present', async () => {
    calendarApi.getCalendar.mockResolvedValue(
      makeData({ alerts: [{ dog_name: 'Buddy', duration_days: 185 }] })
    )
    render(<CalendarGrid />)
    await screen.findByText(/pacfa 181-day alert/i)
    await screen.findByText(/buddy.*185/i)
  })

  it('does not show alert bar when alerts is empty', async () => {
    calendarApi.getCalendar.mockResolvedValue(makeData({ alerts: [] }))
    render(<CalendarGrid />)
    await screen.findByText('K-01')
    expect(screen.queryByText(/pacfa 181-day alert/i)).not.toBeInTheDocument()
  })

  it('calls getCalendar a second time when Next is clicked', async () => {
    calendarApi.getCalendar.mockResolvedValue(makeData())
    render(<CalendarGrid />)
    await waitFor(() => expect(calendarApi.getCalendar).toHaveBeenCalledTimes(1))

    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => expect(calendarApi.getCalendar).toHaveBeenCalledTimes(2))
  })

  it('calls getCalendar a second time when Prev is clicked', async () => {
    calendarApi.getCalendar.mockResolvedValue(makeData())
    render(<CalendarGrid />)
    await waitFor(() => expect(calendarApi.getCalendar).toHaveBeenCalledTimes(1))

    await userEvent.click(screen.getByRole('button', { name: /prev/i }))
    await waitFor(() => expect(calendarApi.getCalendar).toHaveBeenCalledTimes(2))
  })

  it('calls getCalendar again when Refresh is clicked', async () => {
    calendarApi.getCalendar.mockResolvedValue(makeData())
    render(<CalendarGrid />)
    await waitFor(() => expect(calendarApi.getCalendar).toHaveBeenCalledTimes(1))

    await userEvent.click(screen.getByRole('button', { name: /refresh/i }))
    await waitFor(() => expect(calendarApi.getCalendar).toHaveBeenCalledTimes(2))
  })

  it('opens context menu when a cell is clicked', async () => {
    calendarApi.getCalendar.mockResolvedValue(makeData())
    render(<CalendarGrid />)
    await screen.findByText('K-01')

    fireEvent.click(document.querySelector('.cal-cell'))
    expect(screen.getByTestId('context-menu')).toBeInTheDocument()
  })

  it('fires onAction callback with action and cell info', async () => {
    calendarApi.getCalendar.mockResolvedValue(makeData())
    const onAction = vi.fn()
    render(<CalendarGrid onAction={onAction} />)
    await screen.findByText('K-01')

    fireEvent.click(document.querySelector('.cal-cell'))
    await userEvent.click(screen.getByText('CheckIn'))
    expect(onAction).toHaveBeenCalledWith('check_in', expect.any(Object))
  })

  it('closes context menu when onClose fires', async () => {
    calendarApi.getCalendar.mockResolvedValue(makeData())
    render(<CalendarGrid />)
    await screen.findByText('K-01')

    fireEvent.click(document.querySelector('.cal-cell'))
    await userEvent.click(screen.getByText('Close'))
    expect(screen.queryByTestId('context-menu')).not.toBeInTheDocument()
  })

  it('renders four phase header columns per day', async () => {
    calendarApi.getCalendar.mockResolvedValue(makeData())
    render(<CalendarGrid />)
    await screen.findByText('K-01')

    // 10 days × 4 phases = 40 phase headers; each day has AM/Noon/Eve/Ngt
    const amHeaders = screen.getAllByText('AM')
    expect(amHeaders).toHaveLength(10)
  })
})
