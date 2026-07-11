// Real browser entrypoint. Kept separate from main.ts so main.ts's `boot`
// export stays a pure, network-free dispatch function that can be unit
// tested with an injected fake api. This module wires the real HTTP calls
// (src/api.ts) and re-renders the DOM tree boot() produces so its
// otherwise-inert forms/buttons actually do something.
import './style.css'
import { boot, type BootApi } from './main'
import { renderAuthWall, type AuthWallHandlers } from './views/authWall'
import * as realApi from './api'
import { createRecorderEngine } from './audio/recorder'

// createRecorderEngine lives in audio/recorder.ts (sv-lds.13); everything
// else BootApi needs (getMe/getAffirmations/uploadTake) is already on
// realApi (src/api.ts) -- this is the record-a-take flow's real-capability
// injection point (sv-lds.12 + sv-lds.13 integration).
const bootApi: BootApi = { ...realApi, createRecorderEngine }

async function start(container: HTMLElement): Promise<void> {
  await boot(container, bootApi)
  wire(container)
}

function wire(container: HTMLElement): void {
  wireAuthWall(container)
  wireLogout(container)
}

function makeAuthHandlers(container: HTMLElement): AuthWallHandlers {
  return {
    onLogin: (username, password) => {
      void realApi.login(username, password).then((result) => {
        if (result.ok) {
          void start(container)
        } else {
          renderAuthError(container, result.status === 401 ? 'invalid credentials' : 'login failed')
        }
      })
    },
    onRegister: (joinCode, username, displayName, password) => {
      void realApi.register(joinCode, username, displayName, password).then((result) => {
        if (result.ok) {
          void start(container)
        } else if (result.status === 403) {
          renderAuthError(container, 'wrong community code')
        } else if (result.status === 409) {
          renderAuthError(container, 'username taken')
        } else {
          renderAuthError(container, 'registration failed')
        }
      })
    },
  }
}

function renderAuthError(container: HTMLElement, message: string): void {
  container.innerHTML = ''
  // renderAuthWall bakes the real handlers straight into the form's submit
  // listener (see views/authWall.ts's buildLoginForm/buildRegisterForm), so
  // this form is already fully wired. Do NOT also call wireAuthWall here --
  // that would attach a second, independent real submit listener onto the
  // same form, causing a resubmit to fire the real API call twice.
  container.appendChild(renderAuthWall(makeAuthHandlers(container), message))
}

// boot() renders the auth wall with inert (no-op) handlers -- BootApi has no
// login/register methods. Wire the real handlers onto the rendered form(s)
// here by reading the entered field values and invoking the real handlers.
function wireAuthWall(container: HTMLElement): void {
  const handlers = makeAuthHandlers(container)

  const loginForm = container.querySelector<HTMLFormElement>('[data-testid="login-form"]')
  loginForm?.addEventListener('submit', (event) => {
    event.preventDefault()
    const username = loginForm.querySelector<HTMLInputElement>('input[name="username"]')!.value
    const password = loginForm.querySelector<HTMLInputElement>('input[name="password"]')!.value
    handlers.onLogin(username, password)
  })

  const registerForm = container.querySelector<HTMLFormElement>('[data-testid="register-form"]')
  registerForm?.addEventListener('submit', (event) => {
    event.preventDefault()
    const joinCode = registerForm.querySelector<HTMLInputElement>('input[name="join_code"]')!.value
    const username = registerForm.querySelector<HTMLInputElement>('input[name="username"]')!.value
    const displayName = registerForm.querySelector<HTMLInputElement>('input[name="display_name"]')!.value
    const password = registerForm.querySelector<HTMLInputElement>('input[name="password"]')!.value
    handlers.onRegister(joinCode, username, displayName, password)
  })
}

// boot() renders the app view with an inert (no-op) onLogout -- BootApi has
// no logout method. Wire the real logout call onto the rendered button here.
function wireLogout(container: HTMLElement): void {
  const logout = container.querySelector<HTMLElement>('[data-testid="logout"]')
  logout?.addEventListener('click', () => {
    void realApi.logout().then(() => start(container))
  })
}

const container = document.getElementById('app')
if (container) {
  void start(container)
}
