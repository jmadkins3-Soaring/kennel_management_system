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

  // ── Span-merging: continuous reservation bars ──────────────────────────────

  it('merges all phases of a single reservation into one continuous cell', async () => {
    // All 4 phases of the same reservation_id must collapse into one <td colSpan=4>,
    // not four separate boxes. Regression guard for the co-housing refactor.
    const data = {
      alerts: [],
      kennels: [{
        kennel_id: 'k1',
        kennel_number: 'K-01',
        days: [{
          date: '2026-05-06',
          phases: {
            Morning:   { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [] },
            Afternoon: { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [] },
            Evening:   { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [] },
            Night:     { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [] },
          },
        }],
      }],
    }
    calendarApi.getCalendar.mockResolvedValue(data)
    render(<CalendarGrid />)
    await screen.findByText('K-01')

    const cells = document.querySelectorAll('td.cal-cell')
    expect(cells).toHaveLength(1)
    expect(cells[0].colSpan).toBe(4)
    expect(screen.getAllByText('Jones')).toHaveLength(1)
  })

  it('merges co-housed reservation phases into one continuous cell', async () => {
    // When co_residents are present, phases of the primary reservation must still
    // merge into a single span — not one box per 6-hour window.
    const data = {
      alerts: [],
      kennels: [{
        kennel_id: 'k1',
        kennel_number: 'K-01',
        days: [{
          date: '2026-05-06',
          phases: {
            Morning:   { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [{ reservation_id: 'r-b', owner_last_name: 'Smith' }] },
            Afternoon: { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [{ reservation_id: 'r-b', owner_last_name: 'Smith' }] },
            Evening:   { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [{ reservation_id: 'r-b', owner_last_name: 'Smith' }] },
            Night:     { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [{ reservation_id: 'r-b', owner_last_name: 'Smith' }] },
          },
        }],
      }],
    }
    calendarApi.getCalendar.mockResolvedValue(data)
    render(<CalendarGrid />)
    await screen.findByText('K-01')

    const cells = document.querySelectorAll('td.cal-cell')
    expect(cells).toHaveLength(1)
    expect(cells[0].colSpan).toBe(4)
  })

  it('shows both primary and co-resident names within a merged co-housed span', async () => {
    // Co-resident names must appear in the merged bar, not be lost by the merge.
    const data = {
      alerts: [],
      kennels: [{
        kennel_id: 'k1',
        kennel_number: 'K-01',
        days: [{
          date: '2026-05-06',
          phases: {
            Morning:   { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [{ reservation_id: 'r-b', owner_last_name: 'Smith' }] },
            Afternoon: { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [{ reservation_id: 'r-b', owner_last_name: 'Smith' }] },
            Evening:   { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [] },
            Night:     { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [] },
          },
        }],
      }],
    }
    calendarApi.getCalendar.mockResolvedValue(data)
    render(<CalendarGrid />)
    await screen.findByText('K-01')

    expect(screen.getByText('Jones')).toBeInTheDocument()
    expect(screen.getByText('Smith')).toBeInTheDocument()
    // Still one merged cell
    expect(document.querySelectorAll('td.cal-cell')).toHaveLength(1)
  })

  it('deduplicates co-residents collected across merged phases', async () => {
    // The same co-resident appearing in multiple phases of a merged span must
    // only produce one co-resident label, not one per phase.
    const data = {
      alerts: [],
      kennels: [{
        kennel_id: 'k1',
        kennel_number: 'K-01',
        days: [{
          date: '2026-05-06',
          phases: {
            Morning:   { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [{ reservation_id: 'r-b', owner_last_name: 'Smith' }] },
            Afternoon: { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [{ reservation_id: 'r-b', owner_last_name: 'Smith' }] },
            Evening:   { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [{ reservation_id: 'r-b', owner_last_name: 'Smith' }] },
            Night:     { status: 'Assigned', owner_last_name: 'Jones', reservation_id: 'r-a', co_residents: [{ reservation_id: 'r-b', owner_last_name: 'Smith' }] },
          },
        }],
      }],
    }
    calendarApi.getCalendar.mockResolvedValue(data)
    render(<CalendarGrid />)
    await screen.findByText('K-01')

    expect(screen.getAllByText('Smith')).toHaveLength(1)
  })
})
