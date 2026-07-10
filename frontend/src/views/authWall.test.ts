import { describe, it, expect, vi } from 'vitest'
import { renderAuthWall, type AuthWallHandlers } from './authWall'

// Contract (sv-lds.8): renderAuthWall(handlers, errorMessage?) returns an
// HTMLElement containing a login form by default, a register form reachable via
// a toggle control, and an error slot that shows a passed-in error string.
//
// Stable test hooks the implementation MUST provide:
//   [data-testid="login-form"]        a <form> with inputs name="username", name="password"
//   [data-testid="register-form"]     a <form> with inputs name="join_code",
//                                      name="username", name="display_name", name="password"
//   [data-testid="toggle-auth-mode"]  a control that switches login <-> register view
//   [data-testid="auth-error"]        element rendering the errorMessage text (present when provided)
// Forms handle the DOM "submit" event and invoke the handlers with the entered values.

function makeHandlers(): AuthWallHandlers {
  return {
    onLogin: vi.fn(),
    onRegister: vi.fn(),
  }
}

function submit(form: HTMLFormElement): void {
  form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
}

describe('renderAuthWall', () => {
  it('renders the login form by default', () => {
    const el = renderAuthWall(makeHandlers())
    const loginForm = el.querySelector('[data-testid="login-form"]')
    expect(loginForm).not.toBeNull()
  })

  it('submitting the login form calls onLogin with username and password', () => {
    const handlers = makeHandlers()
    const el = renderAuthWall(handlers)

    const loginForm = el.querySelector<HTMLFormElement>('[data-testid="login-form"]')
    expect(loginForm).not.toBeNull()

    const username = loginForm!.querySelector<HTMLInputElement>('input[name="username"]')!
    const password = loginForm!.querySelector<HTMLInputElement>('input[name="password"]')!
    username.value = 'alice'
    password.value = 's3cret'

    submit(loginForm!)

    expect(handlers.onLogin).toHaveBeenCalledTimes(1)
    expect(handlers.onLogin).toHaveBeenCalledWith('alice', 's3cret')
  })

  it('toggling shows the register form whose submit calls onRegister with all four fields', () => {
    const handlers = makeHandlers()
    const el = renderAuthWall(handlers)

    const toggle = el.querySelector<HTMLElement>('[data-testid="toggle-auth-mode"]')
    expect(toggle).not.toBeNull()
    toggle!.click()

    const registerForm = el.querySelector<HTMLFormElement>('[data-testid="register-form"]')
    expect(registerForm).not.toBeNull()

    const joinCode = registerForm!.querySelector<HTMLInputElement>('input[name="join_code"]')!
    const username = registerForm!.querySelector<HTMLInputElement>('input[name="username"]')!
    const displayName = registerForm!.querySelector<HTMLInputElement>('input[name="display_name"]')!
    const password = registerForm!.querySelector<HTMLInputElement>('input[name="password"]')!
    joinCode.value = 'OPEN-SESAME'
    username.value = 'bob'
    displayName.value = 'Bob B.'
    password.value = 'hunter2'

    submit(registerForm!)

    expect(handlers.onRegister).toHaveBeenCalledTimes(1)
    expect(handlers.onRegister).toHaveBeenCalledWith('OPEN-SESAME', 'bob', 'Bob B.', 'hunter2')
  })

  it('renders visible error text when an errorMessage is provided', () => {
    const el = renderAuthWall(makeHandlers(), 'Invalid credentials')
    const errorSlot = el.querySelector('[data-testid="auth-error"]')
    expect(errorSlot).not.toBeNull()
    expect(errorSlot!.textContent).toContain('Invalid credentials')
  })

  it('renders no error text when no errorMessage is provided', () => {
    const el = renderAuthWall(makeHandlers())
    const errorSlot = el.querySelector('[data-testid="auth-error"]')
    // Either the slot is absent, or present but empty.
    expect(errorSlot === null || (errorSlot.textContent ?? '').trim() === '').toBe(true)
  })
})
