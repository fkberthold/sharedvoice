import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Regression (sv-lds.8): entry.ts must wire exactly ONE working submit listener
// onto the auth-wall login form. Two independent code paths both attach a real
// `submit` listener to the SAME rendered form:
//
//   1. views/authWall.ts's buildLoginForm bakes a `submit` listener into the
//      form at creation time, bound to whatever `handlers` renderAuthWall was
//      called with.
//   2. entry.ts's wireAuthWall(container) queries that same form afterward and
//      attaches a SECOND, independent `submit` listener bound to the real API.
//
// On first page load this is harmless: boot() renders the wall with NO-OP
// handlers, so only wireAuthWall's listener does real work. But after any failed
// login/register, entry.ts's renderAuthError() re-renders the wall with the REAL
// makeAuthHandlers baked in AND calls wireAuthWall() again -- so the new form
// carries two real listeners. From then on a single submit fires the real API
// twice (event.preventDefault() does not stop the sibling listener; only
// stopImmediatePropagation would).
//
// Symptom pinned here: submit a wrong password (1 real POST /auth/login), then
// resubmit with the right one -- the retry alone fires TWO POST /auth/login
// calls, so the total is 3 instead of the correct 2.

// Minimal Response-shaped stub covering the surface api.ts reads: `.ok`,
// `.status`, `.json()`.
function makeResponse(status: number, body: unknown = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response
}

function setInput(form: HTMLFormElement, name: string, value: string): void {
  const input = form.querySelector<HTMLInputElement>(`input[name="${name}"]`)
  if (!input) throw new Error(`missing input[name="${name}"]`)
  input.value = value
}

function submit(form: HTMLFormElement): void {
  form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
}

describe('entry.ts real-browser auth-wall wiring', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  let loginAttempts: number

  beforeEach(() => {
    // Fresh module registry so entry.ts's top-level self-invocation re-runs.
    vi.resetModules()
    // #app must exist BEFORE importing entry.ts (it reads getElementById('app')).
    document.body.innerHTML = '<div id="app"></div>'

    loginAttempts = 0
    fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()

      // Unauthenticated: boot()'s getMe() renders the auth wall on first load,
      // and any post-login re-boot stays on the wall (irrelevant to the count).
      if (url.endsWith('/auth/me')) {
        return Promise.resolve(makeResponse(401))
      }

      if (url.endsWith('/auth/login')) {
        loginAttempts += 1
        // First attempt fails (wrong password); every later attempt succeeds.
        return Promise.resolve(makeResponse(loginAttempts === 1 ? 401 : 200))
      }

      if (url.endsWith('/affirmations')) {
        return Promise.resolve(makeResponse(200, []))
      }

      return Promise.resolve(makeResponse(200))
    })

    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('fires exactly one POST /auth/login per submit (no double-wiring on retry after a failed login)', async () => {
    // entry.ts self-invokes on import: boot() -> getMe() (401) -> auth wall.
    await import('./entry')

    await vi.waitFor(() => {
      expect(document.querySelector('[data-testid="login-form"]')).not.toBeNull()
    })

    // First attempt with a wrong password -> one failed POST /auth/login, then
    // renderAuthError re-renders the wall (the moment the bug is introduced).
    const firstForm = document.querySelector<HTMLFormElement>('[data-testid="login-form"]')!
    setInput(firstForm, 'username', 'alice')
    setInput(firstForm, 'password', 'wrong-password')
    submit(firstForm)

    await vi.waitFor(() => {
      expect(document.querySelector('[data-testid="auth-error"]')?.textContent).toContain(
        'invalid credentials',
      )
    })

    // Retry with valid credentials on the freshly re-rendered form.
    const retryForm = document.querySelector<HTMLFormElement>('[data-testid="login-form"]')!
    setInput(retryForm, 'username', 'alice')
    setInput(retryForm, 'password', 'correct-password')
    submit(retryForm)

    // login() calls fetch() synchronously inside the submit handler, so the
    // retry's POST(s) are already recorded here; flush a microtask for safety.
    await Promise.resolve()

    const loginCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/auth/login'))
    // 1 failed attempt + 1 retry = 2. Today's double-wired form makes the retry
    // fire twice, yielding 3.
    expect(loginCalls.length).toBe(2)
  })
})
