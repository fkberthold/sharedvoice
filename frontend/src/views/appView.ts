export interface Affirmation {
  id: string
  text: string
}

export interface AppViewProps {
  affirmations: Affirmation[]
  isCurator: boolean
  onLogout: () => void
}

export function renderAppView(props: AppViewProps): HTMLElement {
  const container = document.createElement('div')

  const list = document.createElement('ul')
  for (const affirmation of props.affirmations) {
    const item = document.createElement('li')

    const label = document.createElement('span')
    label.textContent = affirmation.text
    item.appendChild(label)

    const audio = document.createElement('audio')
    audio.setAttribute('src', `/affirmations/${affirmation.id}/root`)
    audio.controls = true
    item.appendChild(audio)

    list.appendChild(item)
  }
  container.appendChild(list)

  if (props.isCurator) {
    const stub = document.createElement('button')
    stub.type = 'button'
    stub.setAttribute('data-testid', 'upload-stub')
    stub.textContent = 'Upload root (coming soon)'
    stub.disabled = true
    // Intentionally inert: no click handler wired. Real upload wiring is a
    // future bead; this is a visible-but-inert placeholder only.
    container.appendChild(stub)
  }

  const logout = document.createElement('button')
  logout.type = 'button'
  logout.setAttribute('data-testid', 'logout')
  logout.textContent = 'Log out'
  logout.addEventListener('click', () => {
    props.onLogout()
  })
  container.appendChild(logout)

  return container
}
