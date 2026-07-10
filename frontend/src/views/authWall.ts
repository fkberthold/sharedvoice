export interface AuthWallHandlers {
  onLogin: (username: string, password: string) => void
  onRegister: (joinCode: string, username: string, displayName: string, password: string) => void
}

function makeField(labelText: string, name: string, type: string): { wrapper: HTMLElement; input: HTMLInputElement } {
  const wrapper = document.createElement('label')
  wrapper.textContent = labelText
  const input = document.createElement('input')
  input.name = name
  input.type = type
  wrapper.appendChild(input)
  return { wrapper, input }
}

function buildLoginForm(handlers: AuthWallHandlers): HTMLFormElement {
  const form = document.createElement('form')
  form.setAttribute('data-testid', 'login-form')

  const username = makeField('Username', 'username', 'text')
  const password = makeField('Password', 'password', 'password')
  form.appendChild(username.wrapper)
  form.appendChild(password.wrapper)

  const submit = document.createElement('button')
  submit.type = 'submit'
  submit.textContent = 'Log in'
  form.appendChild(submit)

  form.addEventListener('submit', (event) => {
    event.preventDefault()
    handlers.onLogin(username.input.value, password.input.value)
  })

  return form
}

function buildRegisterForm(handlers: AuthWallHandlers): HTMLFormElement {
  const form = document.createElement('form')
  form.setAttribute('data-testid', 'register-form')

  const joinCode = makeField('Community join code', 'join_code', 'text')
  const username = makeField('Username', 'username', 'text')
  const displayName = makeField('Display name', 'display_name', 'text')
  const password = makeField('Password', 'password', 'password')
  form.appendChild(joinCode.wrapper)
  form.appendChild(username.wrapper)
  form.appendChild(displayName.wrapper)
  form.appendChild(password.wrapper)

  const submit = document.createElement('button')
  submit.type = 'submit'
  submit.textContent = 'Create account'
  form.appendChild(submit)

  form.addEventListener('submit', (event) => {
    event.preventDefault()
    handlers.onRegister(joinCode.input.value, username.input.value, displayName.input.value, password.input.value)
  })

  return form
}

export function renderAuthWall(handlers: AuthWallHandlers, errorMessage?: string): HTMLElement {
  const container = document.createElement('div')

  const errorSlot = document.createElement('div')
  errorSlot.setAttribute('data-testid', 'auth-error')
  if (errorMessage) {
    errorSlot.textContent = errorMessage
  }
  container.appendChild(errorSlot)

  const loginForm = buildLoginForm(handlers)
  const registerForm = buildRegisterForm(handlers)
  registerForm.hidden = true

  const toggle = document.createElement('button')
  toggle.type = 'button'
  toggle.setAttribute('data-testid', 'toggle-auth-mode')
  toggle.textContent = 'Need an account? Register'

  toggle.addEventListener('click', () => {
    const switchingToRegister = !loginForm.hidden
    loginForm.hidden = !loginForm.hidden
    registerForm.hidden = !registerForm.hidden
    toggle.textContent = switchingToRegister ? 'Already have an account? Log in' : 'Need an account? Register'
  })

  container.appendChild(loginForm)
  container.appendChild(registerForm)
  container.appendChild(toggle)

  return container
}
