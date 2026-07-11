import { renderRecordFlow, type RecordFlowHandlers, type RecordFlowState } from './recordFlow'
import type { RecorderEngine } from '../audio/recorder'

export interface Affirmation {
  id: string
  title: string
  text: string
}

export interface AppViewProps {
  affirmations: Affirmation[]
  isCurator: boolean
  onLogout: () => void
  // Real audio/network capabilities (sv-lds.12+.13 integration). Left
  // undefined in tests and in main.ts's boot() docs-example usage, in
  // which case the record flow falls back to local-only state transitions
  // (no real mic access, no real upload) -- see recordFlowHandlers below.
  // entry.ts supplies the real implementations.
  createRecorderEngine?: (rootAudioEl: HTMLAudioElement) => RecorderEngine
  uploadTake?: (affirmationId: string, wavBlob: Blob) => Promise<{ ok: boolean }>
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

  // Local state for the record-a-take flow (sv-lds.12 UI shell + sv-lds.13
  // audio engine, wired together here). `recordFlowState` is non-null while
  // the record flow is showing in place of the normal detail content for
  // `currentAffirmation`. `currentRootAudioEl` is captured in
  // renderNormalDetail() so the real engine can play it in sync with
  // capture; `currentEngine`/`currentTakeBlob` carry state across the
  // gate->recording->review transitions. When `props.createRecorderEngine`/
  // `props.uploadTake` are undefined (tests, or a future caller that
  // doesn't wire real audio), the flow degrades to local-only state
  // transitions with no real mic access or upload.
  let currentAffirmation: Affirmation | null = null
  let currentRootAudioEl: HTMLAudioElement | null = null
  let recordFlowState: RecordFlowState | null = null
  let currentEngine: RecorderEngine | null = null
  let currentTakeBlob: Blob | null = null

  const recordFlowHandlers: RecordFlowHandlers = {
    onReady: () => {
      recordFlowState = { phase: 'recording' }
      renderDetail()
      if (props.createRecorderEngine && currentRootAudioEl) {
        currentEngine = props.createRecorderEngine(currentRootAudioEl)
        void currentEngine.start()
      }
    },
    onStop: () => {
      if (currentEngine) {
        const engine = currentEngine
        currentEngine = null
        void engine.stop().then((blob) => {
          currentTakeBlob = blob
          recordFlowState = { phase: 'review', previewUrl: URL.createObjectURL(blob) }
          renderDetail()
        })
      } else {
        recordFlowState = { phase: 'review', previewUrl: 'about:blank' }
        renderDetail()
      }
    },
    onSubmit: () => {
      const affirmation = currentAffirmation
      const blob = currentTakeBlob
      if (props.uploadTake && affirmation && blob) {
        void props.uploadTake(affirmation.id, blob)
      }
      currentTakeBlob = null
      recordFlowState = null
      renderDetail()
    },
    onReRecord: () => {
      currentTakeBlob = null
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
    currentRootAudioEl = audio

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
