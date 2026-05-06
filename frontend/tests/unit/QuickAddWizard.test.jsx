import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QuickAddWizard from '../../src/pages/Calendar/QuickAddWizard'
import * as ownersApi from '../../src/api/owners'
import * as dogsApi from '../../src/api/dogs'
import * as kennelsApi from '../../src/api/kennels'
import * as reservationsApi from '../../src/api/reservations'
import * as activityTypesApi from '../../src/api/activityTypes'

vi.mock('../../src/api/owners', () => ({
  listOwners: vi.fn(),
  createOwner: vi.fn(),
  getOwnerDogs: vi.fn(),
}))
vi.mock('../../src/api/dogs', () => ({ createDog: vi.fn() }))
vi.mock('../../src/api/kennels', () => ({ listKennels: vi.fn() }))
vi.mock('../../src/api/reservations', () => ({ createReservation: vi.fn() }))
vi.mock('../../src/api/activityTypes', () => ({ listActivityTypes: vi.fn() }))

const OWNER  = { owner_id: 'o1', first_name: 'Jane', last_name: 'Doe', phone: '555-1234' }
const DOG    = { dog_id: 'd1', name: 'Rex', breed: 'Labrador', size_class: 'L' }
const KENNEL = { kennel_id: 'k1', kennel_number: 'K-01', max_size_class: 'L', sqft: 40 }

function setup(props = {}) {
  return render(<QuickAddWizard onClose={vi.fn()} onSuccess={vi.fn()} {...props} />)
}

describe('QuickAddWizard — Step 1 (Owner)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ownersApi.getOwnerDogs.mockResolvedValue([])
    kennelsApi.listKennels.mockResolvedValue([KENNEL])
    activityTypesApi.listActivityTypes.mockResolvedValue([])
  })

  it('renders step 1 header and owner search UI', () => {
    setup()
    expect(screen.getByText(/step 1 of 5/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/last name/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create new owner/i })).toBeInTheDocument()
  })

  it('shows validation error when Next is clicked with no owner selected', async () => {
    setup()
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText(/select or create an owner/i)).toBeInTheDocument()
  })

  it('does not call listOwners until debounce fires', async () => {
    vi.useFakeTimers()
    ownersApi.listOwners.mockResolvedValue([OWNER])
    setup()

    fireEvent.change(screen.getByPlaceholderText(/last name/i), { target: { value: 'Doe' } })
    expect(ownersApi.listOwners).not.toHaveBeenCalled()

    act(() => vi.advanceTimersByTime(350))
    vi.useRealTimers()

    await waitFor(() => expect(ownersApi.listOwners).toHaveBeenCalledWith({ q: 'Doe' }))
  })

  it('renders owner results after debounce', async () => {
    vi.useFakeTimers()
    ownersApi.listOwners.mockResolvedValue([OWNER])
    setup()

    fireEvent.change(screen.getByPlaceholderText(/last name/i), { target: { value: 'Doe' } })
    act(() => vi.advanceTimersByTime(350))
    vi.useRealTimers()

    await screen.findByText('Doe, Jane')
  })

  it('clears results when search query is emptied', async () => {
    vi.useFakeTimers()
    ownersApi.listOwners.mockResolvedValue([OWNER])
    setup()

    fireEvent.change(screen.getByPlaceholderText(/last name/i), { target: { value: 'Doe' } })
    act(() => vi.advanceTimersByTime(350))
    vi.useRealTimers()
    await screen.findByText('Doe, Jane')

    fireEvent.change(screen.getByPlaceholderText(/last name/i), { target: { value: '' } })
    await waitFor(() => expect(screen.queryByText('Doe, Jane')).not.toBeInTheDocument())
  })

  it('shows selected owner badge after clicking a result', async () => {
    vi.useFakeTimers()
    ownersApi.listOwners.mockResolvedValue([OWNER])
    setup()

    fireEvent.change(screen.getByPlaceholderText(/last name/i), { target: { value: 'Doe' } })
    act(() => vi.advanceTimersByTime(350))
    vi.useRealTimers()
    fireEvent.click(await screen.findByText('Doe, Jane'))

    expect(screen.getByText(/selected:/i)).toBeInTheDocument()
  })

  it('shows new owner form when "+ Create New Owner" is clicked', async () => {
    setup()
    await userEvent.click(screen.getByRole('button', { name: /create new owner/i }))
    const inputs = screen.getAllByRole('textbox')
    // First two inputs in the new owner grid are First Name and Last Name
    expect(inputs[0]).toBeInTheDocument()
    expect(inputs[1]).toBeInTheDocument()
    expect(screen.getByText(/first name/i)).toBeInTheDocument()
    expect(screen.getByText(/last name/i)).toBeInTheDocument()
  })

  it('validates first and last name are required for new owner', async () => {
    setup()
    await userEvent.click(screen.getByRole('button', { name: /create new owner/i }))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText(/first and last name required/i)).toBeInTheDocument()
  })

  it('advances to step 2 after an owner is selected', async () => {
    vi.useFakeTimers()
    ownersApi.listOwners.mockResolvedValue([OWNER])
    setup()

    fireEvent.change(screen.getByPlaceholderText(/last name/i), { target: { value: 'Doe' } })
    act(() => vi.advanceTimersByTime(350))
    vi.useRealTimers()
    fireEvent.click(await screen.findByText('Doe, Jane'))

    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await screen.findByText(/step 2 of 5/i)
  })

  it('Back button is not shown on step 1', () => {
    setup()
    expect(screen.queryByRole('button', { name: /back/i })).not.toBeInTheDocument()
  })

  it('Back button on step 2 returns to step 1', async () => {
    vi.useFakeTimers()
    ownersApi.listOwners.mockResolvedValue([OWNER])
    setup()

    fireEvent.change(screen.getByPlaceholderText(/last name/i), { target: { value: 'Doe' } })
    act(() => vi.advanceTimersByTime(350))
    vi.useRealTimers()
    fireEvent.click(await screen.findByText('Doe, Jane'))

    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await screen.findByText(/step 2 of 5/i)

    await userEvent.click(screen.getByRole('button', { name: /back/i }))
    expect(screen.getByText(/step 1 of 5/i)).toBeInTheDocument()
  })

  it('calls onClose when the modal ✕ button is clicked', async () => {
    const onClose = vi.fn()
    setup({ onClose })
    await userEvent.click(screen.getByRole('button', { name: '✕' }))
    expect(onClose).toHaveBeenCalled()
  })
})

describe('QuickAddWizard — Step 2 (Dog)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ownersApi.listOwners.mockResolvedValue([OWNER])
    kennelsApi.listKennels.mockResolvedValue([KENNEL])
    activityTypesApi.listActivityTypes.mockResolvedValue([])
  })

  async function goToStep2(dogList = []) {
    ownersApi.getOwnerDogs.mockResolvedValue(dogList)
    vi.useFakeTimers()
    setup()

    fireEvent.change(screen.getByPlaceholderText(/last name/i), { target: { value: 'Doe' } })
    act(() => vi.advanceTimersByTime(350))
    vi.useRealTimers()
    fireEvent.click(await screen.findByText('Doe, Jane'))

    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await screen.findByText(/step 2 of 5/i)
  }

  it('shows "No dogs on file" when owner has no dogs', async () => {
    await goToStep2([])
    expect(screen.getByText(/no dogs on file/i)).toBeInTheDocument()
  })

  it('lists existing dogs for the selected owner', async () => {
    await goToStep2([DOG])
    await screen.findByText('Rex')
  })

  it('shows selected dog badge after clicking a dog', async () => {
    await goToStep2([DOG])
    fireEvent.click(await screen.findByText('Rex'))
    expect(screen.getByText(/selected:/i)).toBeInTheDocument()
  })

  it('shows validation error when Next is clicked with no dog selected', async () => {
    await goToStep2([])
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText(/select at least one dog/i)).toBeInTheDocument()
  })

  it('shows new dog form when "+ Add New Dog" is clicked', async () => {
    await goToStep2([])
    await userEvent.click(screen.getByRole('button', { name: /add new dog/i }))
    expect(screen.getByRole('button', { name: /add to list/i })).toBeInTheDocument()
  })
})

describe('QuickAddWizard — Step 3 (Dates)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ownersApi.createOwner.mockResolvedValue(OWNER)
    ownersApi.getOwnerDogs.mockResolvedValue([])
    dogsApi.createDog.mockResolvedValue(DOG)
    kennelsApi.listKennels.mockResolvedValue([KENNEL])
    activityTypesApi.listActivityTypes.mockResolvedValue([])
  })

  async function goToStep3() {
    setup()
    // Step 1: create new owner
    await userEvent.click(screen.getByRole('button', { name: /create new owner/i }))
    const inputs = screen.getAllByRole('textbox')
    await userEvent.type(inputs[0], 'Jane')  // First Name
    await userEvent.type(inputs[1], 'Doe')   // Last Name
    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    // Step 2: add new dog — must click "Add to List" then "Next"
    await screen.findByText(/step 2 of 5/i)
    await userEvent.click(screen.getByRole('button', { name: /add new dog/i }))
    const dogInputs = screen.getAllByRole('textbox')
    await userEvent.type(dogInputs[0], 'Rex')
    await userEvent.click(screen.getByRole('button', { name: /add to list/i }))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    await screen.findByText(/step 3 of 5/i)
  }

  it('shows drop-off date and time fields', async () => {
    await goToStep3()
    expect(screen.getByText(/drop-off date/i)).toBeInTheDocument()
    expect(screen.getByText(/drop-off time/i)).toBeInTheDocument()
  })

  it('shows phase label derived from drop-off time', async () => {
    await goToStep3()
    // pickup defaults to 09:00 (Morning); set drop-off to Evening so it's unique
    const timeInputs = document.querySelectorAll('input[type=time]')
    fireEvent.change(timeInputs[0], { target: { value: '19:00' } })
    await screen.findByText('Evening')
  })

  it('shows Afternoon phase for 14:00', async () => {
    await goToStep3()
    const timeInputs = document.querySelectorAll('input[type=time]')
    fireEvent.change(timeInputs[0], { target: { value: '14:00' } })
    await screen.findByText('Afternoon')
  })

  it('hides pickup fields when open-ended is checked', async () => {
    await goToStep3()
    await userEvent.click(screen.getByRole('checkbox'))
    expect(screen.queryByText(/pick-up date/i)).not.toBeInTheDocument()
  })

  it('shows validation error when pickup is missing and not open-ended', async () => {
    await goToStep3()
    const dateInputs = document.querySelectorAll('input[type=date]')
    fireEvent.change(dateInputs[0], { target: { value: '2026-06-01' } })
    // leave pickup empty
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText(/pick-up date\/time required/i)).toBeInTheDocument()
  })

  it('advances to step 4 when all date fields are filled', async () => {
    await goToStep3()
    const dateInputs = document.querySelectorAll('input[type=date]')
    const timeInputs = document.querySelectorAll('input[type=time]')
    fireEvent.change(dateInputs[0], { target: { value: '2026-06-01' } })
    fireEvent.change(timeInputs[0], { target: { value: '09:00' } })
    fireEvent.change(dateInputs[1], { target: { value: '2026-06-05' } })
    fireEvent.change(timeInputs[1], { target: { value: '09:00' } })
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await screen.findByText(/step 4 of 5/i)
  })
})

describe('QuickAddWizard — Step 5 (Submit)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ownersApi.createOwner.mockResolvedValue(OWNER)
    ownersApi.getOwnerDogs.mockResolvedValue([])
    dogsApi.createDog.mockResolvedValue(DOG)
    kennelsApi.listKennels.mockResolvedValue([KENNEL])
    activityTypesApi.listActivityTypes.mockResolvedValue([])
    reservationsApi.createReservation.mockResolvedValue({ reservation_id: 'r1' })
  })

  async function goToStep5() {
    // Prefill kennel so step 4 auto-selects it
    setup({ prefill: { kennelId: 'k1', kennelNumber: 'K-01' } })

    // Step 1
    await userEvent.click(screen.getByRole('button', { name: /create new owner/i }))
    const inputs = screen.getAllByRole('textbox')
    await userEvent.type(inputs[0], 'Jane')
    await userEvent.type(inputs[1], 'Doe')
    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    // Step 2 — add new dog: type name, click "Add to List", then Next
    await screen.findByText(/step 2 of 5/i)
    await userEvent.click(screen.getByRole('button', { name: /add new dog/i }))
    const dogInputs = screen.getAllByRole('textbox')
    await userEvent.type(dogInputs[0], 'Rex')
    await userEvent.click(screen.getByRole('button', { name: /add to list/i }))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    // Step 3
    await screen.findByText(/step 3 of 5/i)
    const dateInputs = document.querySelectorAll('input[type=date]')
    const timeInputs = document.querySelectorAll('input[type=time]')
    fireEvent.change(dateInputs[0], { target: { value: '2026-06-01' } })
    fireEvent.change(timeInputs[0], { target: { value: '09:00' } })
    fireEvent.change(dateInputs[1], { target: { value: '2026-06-05' } })
    fireEvent.change(timeInputs[1], { target: { value: '09:00' } })
    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    // Step 4 — wait for kennel list to load (pre-assignment via prefill), then Next
    await screen.findByText(/step 4 of 5/i)
    await screen.findAllByText('K-01')
    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    await screen.findByText(/step 5 of 5/i)
  }

  it('shows confirmation summary on step 5', async () => {
    await goToStep5()
    expect(screen.getAllByText(/rex/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/K-01/).length).toBeGreaterThan(0)
  })

  it('calls createReservation with correct payload on submit', async () => {
    await goToStep5()
    await userEvent.click(screen.getByRole('button', { name: /create.*reservation/i }))
    await waitFor(() => expect(reservationsApi.createReservation).toHaveBeenCalledWith(
      expect.objectContaining({
        dog_id: DOG.dog_id,
        kennel_id: KENNEL.kennel_id,
        dropoff_datetime: '2026-06-01T09:00:00',
        pickup_datetime: '2026-06-05T09:00:00',
      })
    ))
  })

  it('calls onSuccess after reservation is created', async () => {
    const onSuccess = vi.fn()
    setup({ prefill: { kennelId: 'k1', kennelNumber: 'K-01' }, onSuccess })

    // Navigate via the same path
    await userEvent.click(screen.getByRole('button', { name: /create new owner/i }))
    let inputs = screen.getAllByRole('textbox')
    await userEvent.type(inputs[0], 'Jane')
    await userEvent.type(inputs[1], 'Doe')
    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    await screen.findByText(/step 2 of 5/i)
    await userEvent.click(screen.getByRole('button', { name: /add new dog/i }))
    inputs = screen.getAllByRole('textbox')
    await userEvent.type(inputs[0], 'Rex')
    await userEvent.click(screen.getByRole('button', { name: /add to list/i }))
    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    await screen.findByText(/step 3 of 5/i)
    const dateInputs = document.querySelectorAll('input[type=date]')
    const timeInputs = document.querySelectorAll('input[type=time]')
    fireEvent.change(dateInputs[0], { target: { value: '2026-06-01' } })
    fireEvent.change(timeInputs[0], { target: { value: '09:00' } })
    fireEvent.change(dateInputs[1], { target: { value: '2026-06-05' } })
    fireEvent.change(timeInputs[1], { target: { value: '09:00' } })
    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    await screen.findByText(/step 4 of 5/i)
    await screen.findAllByText('K-01')
    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    await screen.findByText(/step 5 of 5/i)
    await userEvent.click(screen.getByRole('button', { name: /create.*reservation/i }))

    await waitFor(() => expect(onSuccess).toHaveBeenCalled())
  })

  it('shows error when createReservation fails', async () => {
    reservationsApi.createReservation.mockRejectedValue({
      response: { data: { detail: 'Kennel not available' } },
    })
    await goToStep5()
    await userEvent.click(screen.getByRole('button', { name: /create.*reservation/i }))
    await screen.findByText(/kennel not available/i)
  })
})
