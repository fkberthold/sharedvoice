export interface RecordFlowHandlers {
  onReady: () => void // gate confirmed ("I'm ready" clicked)
  onStop: () => void // manual stop button clicked during recording
  onSubmit: () => void // review state: submit button clicked
  onReRecord: () => void // review state: re-record button clicked (discard, back to gate)
}

export type RecordFlowState =
  | { phase: 'gate' }
  | { phase: 'recording' }
  | { phase: 'review'; previewUrl: string } // an object URL for a preview <audio> element

function makeButton(testId: string, label: string, className: string, onClick: () => void): HTMLButtonElement {
  const button = document.createElement('button')
  button.type = 'button'
  button.className = className
  button.setAttribute('data-testid', testId)
  button.textContent = label
  button.addEventListener('click', () => {
    onClick()
  })
  return button
}

function renderGatePhase(handlers: RecordFlowHandlers): HTMLElement {
  const wrapper = document.createElement('div')
  wrapper.className = 'record-flow-gate'

  const heading = document.createElement('h3')
  heading.setAttribute('data-testid', 'record-gate-heading')
  heading.textContent = 'Before you record'
  wrapper.appendChild(heading)

  const message = document.createElement('p')
  message.className = 'record-gate-message'
  message.setAttribute('data-testid', 'record-gate-message')
  message.textContent = 'Please put on headphones before you begin -- this keeps the root recitation out of your microphone.'
  wrapper.appendChild(message)

  const ready = makeButton('record-ready', "I'm ready", 'btn btn-primary', handlers.onReady)
  wrapper.appendChild(ready)

  return wrapper
}

function renderRecordingPhase(handlers: RecordFlowHandlers): HTMLElement {
  const wrapper = document.createElement('div')
  wrapper.className = 'record-flow-recording'

  const indicator = document.createElement('p')
  indicator.className = 'record-indicator'
  indicator.setAttribute('data-testid', 'record-indicator')
  indicator.textContent = 'Recording...'
  wrapper.appendChild(indicator)

  const stop = makeButton('record-stop', 'Stop', 'btn btn-secondary', handlers.onStop)
  wrapper.appendChild(stop)

  return wrapper
}

function renderReviewPhase(state: { phase: 'review'; previewUrl: string }, handlers: RecordFlowHandlers): HTMLElement {
  const wrapper = document.createElement('div')
  wrapper.className = 'record-flow-review'

  const heading = document.createElement('h3')
  heading.setAttribute('data-testid', 'record-review-heading')
  heading.textContent = 'Review your take'
  wrapper.appendChild(heading)

  const audio = document.createElement('audio')
  audio.className = 'record-preview-audio'
  audio.setAttribute('src', state.previewUrl)
  audio.controls = true
  wrapper.appendChild(audio)

  const submit = makeButton('record-submit', 'Submit', 'btn btn-primary', handlers.onSubmit)
  wrapper.appendChild(submit)

  const reRecord = makeButton('record-rerecord', 'Re-record', 'btn btn-secondary', handlers.onReRecord)
  wrapper.appendChild(reRecord)

  return wrapper
}

export function renderRecordFlow(state: RecordFlowState, handlers: RecordFlowHandlers): HTMLElement {
  const container = document.createElement('div')
  container.className = 'record-flow'
  container.setAttribute('data-testid', 'record-flow')

  let phaseEl: HTMLElement
  switch (state.phase) {
    case 'gate':
      phaseEl = renderGatePhase(handlers)
      break
    case 'recording':
      phaseEl = renderRecordingPhase(handlers)
      break
    case 'review':
      phaseEl = renderReviewPhase(state, handlers)
      break
  }

  container.appendChild(phaseEl)
  return container
}
