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
  container.className = 'app-view'

  const header = document.createElement('div')
  header.className = 'app-header'
  const heading = document.createElement('h1')
  heading.textContent = 'Affirmations'
  header.appendChild(heading)

  if (props.isCurator) {
    const stub = document.createElement('button')
    stub.type = 'button'
    stub.className = 'btn btn-stub'
    stub.setAttribute('data-testid', 'upload-stub')
    stub.textContent = 'Upload root (coming soon)'
    stub.disabled = true
    // Intentionally inert: no click handler wired. Real upload wiring is a
    // future bead; this is a visible-but-inert placeholder only.
    header.appendChild(stub)
  }
  container.appendChild(header)

  const list = document.createElement('ul')
  list.className = 'affirmation-list'
  for (const affirmation of props.affirmations) {
    const item = document.createElement('li')
    item.className = 'affirmation-item'

    const label = document.createElement('span')
    label.className = 'affirmation-text'
    label.textContent = affirmation.text
    item.appendChild(label)

    const audio = document.createElement('audio')
    audio.className = 'affirmation-audio'
    audio.setAttribute('src', `/affirmations/${affirmation.id}/root`)
    audio.controls = true
    item.appendChild(audio)

    list.appendChild(item)
  }
  container.appendChild(list)

  const footer = document.createElement('div')
  footer.className = 'app-footer'
  const logout = document.createElement('button')
  logout.type = 'button'
  logout.className = 'btn btn-secondary'
  logout.setAttribute('data-testid', 'logout')
  logout.textContent = 'Log out'
  logout.addEventListener('click', () => {
    props.onLogout()
  })
  footer.appendChild(logout)
  container.appendChild(footer)

  return container
}
