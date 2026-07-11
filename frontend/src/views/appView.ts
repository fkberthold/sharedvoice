import { renderRecordFlow, type RecordFlowHandlers, type RecordFlowState } from './recordFlow'

export interface Affirmation {
  id: string
  title: string
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

  const logout = document.createElement('button')
  logout.type = 'button'
  logout.className = 'btn btn-secondary'
  logout.setAttribute('data-testid', 'logout')
  logout.textContent = 'Log out'
  logout.addEventListener('click', () => {
    props.onLogout()
  })
  header.appendChild(logout)
  container.appendChild(header)

  const layout = document.createElement('div')
  layout.className = 'app-layout'

  const nav = document.createElement('nav')
  nav.className = 'affirmation-nav'
  const detail = document.createElement('div')
  detail.className = 'affirmation-detail'

  const navButtons = new Map<string, HTMLButtonElement>()

  // Local state for the record-a-take flow (sv-lds.12). `recordFlowState` is
  // non-null while the record flow is showing in place of the normal detail
  // content for `currentAffirmation`. The handlers below are PLACEHOLDER
  // state-machine transitions only -- this bead proves the wiring, not real
  // audio capture. sv-lds.13 (sibling bead, parallel worktree) owns the real
  // audio engine; central replaces these placeholder transitions with calls
  // into that engine when both beads are integrated in entry.ts.
  let currentAffirmation: Affirmation | null = null
  let recordFlowState: RecordFlowState | null = null

  const recordFlowHandlers: RecordFlowHandlers = {
    onReady: () => {
      recordFlowState = { phase: 'recording' }
      renderDetail()
    },
    onStop: () => {
      // TODO(central): replace this placeholder previewUrl with the real
      // object URL produced by sv-lds.13's audio engine once it's wired in.
      recordFlowState = { phase: 'review', previewUrl: 'about:blank' }
      renderDetail()
    },
    onSubmit: () => {
      // TODO(central): replace with a real submit-to-server call. For now,
      // discard local state and return to the normal detail view.
      recordFlowState = null
      renderDetail()
    },
    onReRecord: () => {
      recordFlowState = { phase: 'gate' }
      renderDetail()
    },
  }

  function renderNormalDetail(affirmation: Affirmation): void {
    const title = document.createElement('h2')
    title.setAttribute('data-testid', 'detail-title')
    title.textContent = affirmation.title
    detail.appendChild(title)

    const text = document.createElement('p')
    text.className = 'affirmation-text'
    text.setAttribute('data-testid', 'detail-text')
    text.textContent = affirmation.text
    detail.appendChild(text)

    const audio = document.createElement('audio')
    audio.className = 'affirmation-audio'
    audio.setAttribute('src', `/affirmations/${affirmation.id}/root`)
    audio.controls = true
    detail.appendChild(audio)

    if (props.isCurator) {
      const stub = document.createElement('button')
      stub.type = 'button'
      stub.className = 'btn btn-stub'
      stub.setAttribute('data-testid', 'upload-stub')
      stub.textContent = 'Upload root (coming soon)'
      stub.disabled = true
      // Intentionally inert: no click handler wired. Real upload wiring is a
      // future bead; this is a visible-but-inert placeholder only.
      detail.appendChild(stub)
    }

    const recordTrigger = document.createElement('button')
    recordTrigger.type = 'button'
    recordTrigger.className = 'btn btn-primary'
    recordTrigger.setAttribute('data-testid', 'record-trigger')
    recordTrigger.textContent = 'Record your take'
    recordTrigger.addEventListener('click', () => {
      recordFlowState = { phase: 'gate' }
      renderDetail()
    })
    detail.appendChild(recordTrigger)
  }

  function renderDetail(): void {
    if (!currentAffirmation) {
      return
    }

    detail.innerHTML = ''

    if (recordFlowState) {
      detail.appendChild(renderRecordFlow(recordFlowState, recordFlowHandlers))
      return
    }

    renderNormalDetail(currentAffirmation)
  }

  function selectAffirmation(affirmation: Affirmation): void {
    for (const [id, btn] of navButtons) {
      btn.classList.toggle('active', id === affirmation.id)
    }

    currentAffirmation = affirmation
    recordFlowState = null
    renderDetail()
  }

  for (const affirmation of props.affirmations) {
    const navButton = document.createElement('button')
    navButton.type = 'button'
    navButton.className = 'nav-item'
    navButton.setAttribute('data-testid', `nav-item-${affirmation.id}`)
    navButton.textContent = affirmation.title
    navButton.addEventListener('click', () => selectAffirmation(affirmation))
    navButtons.set(affirmation.id, navButton)
    nav.appendChild(navButton)
  }

  layout.appendChild(nav)
  layout.appendChild(detail)
  container.appendChild(layout)

  const first = props.affirmations[0]
  if (first) {
    selectAffirmation(first)
  } else {
    const empty = document.createElement('p')
    empty.className = 'affirmation-empty'
    empty.textContent = 'No affirmations yet.'
    detail.appendChild(empty)
  }

  return container
}
