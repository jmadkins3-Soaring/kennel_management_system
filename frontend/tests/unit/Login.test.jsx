import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Login from '../../src/pages/Login'
import * as AuthCtx from '../../src/contexts/AuthContext'

vi.mock('../../src/contexts/AuthContext', () => ({ useAuth: vi.fn() }))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importActual) => ({
  ...(await importActual()),
  useNavigate: () => mockNavigate,
}))

function setup(authValue) {
  AuthCtx.useAuth.mockReturnValue(authValue)
  const utils = render(<MemoryRouter><Login /></MemoryRouter>)
  return { ...utils, passwordInput: utils.container.querySelector('input[type=password]') }
}

describe('Login', () => {
  beforeEach(() => mockNavigate.mockReset())

  it('renders username input, password input, and submit button', () => {
    const { passwordInput } = setup({ user: null, login: vi.fn() })
    expect(screen.getByRole('textbox')).toBeInTheDocument()
    expect(passwordInput).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('redirects to /calendar when already authenticated', () => {
    setup({ user: { username: 'admin' }, login: vi.fn() })
    expect(screen.queryByRole('button', { name: /sign in/i })).not.toBeInTheDocument()
  })

  it('calls login with credentials and navigates on success', async () => {
    const login = vi.fn().mockResolvedValue(undefined)
    const { passwordInput } = setup({ user: null, login })

    await userEvent.type(screen.getByRole('textbox'), 'admin')
    await userEvent.type(passwordInput, 'secret')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => expect(login).toHaveBeenCalledWith('admin', 'secret'))
    expect(mockNavigate).toHaveBeenCalledWith('/calendar', { replace: true })
  })

  it('shows API error detail on failed login', async () => {
    const login = vi.fn().mockRejectedValue({ response: { data: { detail: 'Invalid credentials' } } })
    const { passwordInput } = setup({ user: null, login })

    await userEvent.type(screen.getByRole('textbox'), 'admin')
    await userEvent.type(passwordInput, 'bad')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await screen.findByText('Invalid credentials')
  })

  it('falls back to "Login failed" when error has no detail', async () => {
    const login = vi.fn().mockRejectedValue(new Error('network'))
    const { passwordInput } = setup({ user: null, login })

    await userEvent.type(screen.getByRole('textbox'), 'x')
    await userEvent.type(passwordInput, 'y')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await screen.findByText('Login failed')
  })

  it('disables submit and shows "Signing in…" while request is in-flight', async () => {
    let resolve
    const login = vi.fn().mockReturnValue(new Promise(r => { resolve = r }))
    const { passwordInput } = setup({ user: null, login })

    await userEvent.type(screen.getByRole('textbox'), 'admin')
    await userEvent.type(passwordInput, 'pw')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    const btn = await screen.findByRole('button', { name: /signing in/i })
    expect(btn).toBeDisabled()
    resolve()
  })
})
