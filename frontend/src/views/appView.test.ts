import { describe, it, expect, vi } from 'vitest'
import { renderAppView, type Affirmation, type AppViewProps } from './appView'

// Contract (sv-uhx, supersedes sv-lds.8's flat-list contract): renderAppView(props)
// returns an HTMLElement with a two-pane layout -- a side nav listing every
// affirmation's TITLE, and a detail pane showing only the currently SELECTED
// affirmation (title + text + a real HTML <audio> element sourced at exactly
// /affirmations/{id}/root -- iOS mute-switch safety, NOT a Web Audio buffer
// source). The first affirmation is selected by default. Clicking a nav item
// switches the detail pane (and the nav's active-item indicator) to that
// affirmation. A curator-only upload stub lives in the detail pane, present only
// when isCurator is true, labelled "Upload root (coming soon)", and inert (no
// click/submit handler wired). A logout button (page-level, not nav-scoped)
// invokes props.onLogout.
//
// Stable test hooks the implementation MUST provide:
//   [data-testid="nav-item-{id}"]     one per affirmation, textContent = title
//   [data-testid="detail-title"]      selected affirmation's title
//   [data-testid="detail-text"]       selected affirmation's text
//   audio[src="/affirmations/{id}/root"]  exactly one, for the SELECTED affirmation only
//   [data-testid="upload-stub"]       curator-only inert upload control, in the detail pane
//   [data-testid="logout"]            logout button -> calls props.onLogout
//
// sv-lds.12: the detail pane also carries a "Record your take" trigger,
// visible for ANY logged-in member (not curator-gated, unlike upload-stub).
// Clicking it swaps in the recordFlow.ts view (starting at its 'gate' phase)
// in place of the normal detail content. recordFlow.ts's own phase/handler
// contract is covered by recordFlow.test.ts, not here.
//   [data-testid="record-trigger"]    visible for every member, opens the record flow

const UPLOAD_STUB_TEXT = 'Upload root (coming soon)'

function baseProps(overrides: Partial<AppViewProps> = {}): AppViewProps {
  const affirmations: Affirmation[] = [
    { id: 'waking', title: 'Waking Affirmation', text: 'You are waking gently.' },
    { id: 'resting', title: 'Resting Affirmation', text: 'You are resting deeply.' },
  ]
  return {
    affirmations,
    isCurator: false,
    onLogout: vi.fn(),
    ...overrides,
  }
}

describe('renderAppView', () => {
  it('renders a nav item with the title for each affirmation', () => {
    const el = renderAppView(baseProps())

    const wakingNav = el.querySelector('[data-testid="nav-item-waking"]')
    const restingNav = el.querySelector('[data-testid="nav-item-resting"]')
    expect(wakingNav).not.toBeNull()
    expect(restingNav).not.toBeNull()
    expect(wakingNav!.textContent).toContain('Waking Affirmation')
    expect(restingNav!.textContent).toContain('Resting Affirmation')
  })

  it('selects the first affirmation in the detail pane by default', () => {
    const el = renderAppView(baseProps())

    expect(el.querySelector('[data-testid="detail-title"]')!.textContent).toContain('Waking Affirmation')
    expect(el.querySelector('[data-testid="detail-text"]')!.textContent).toContain('You are waking gently.')

    const audio = el.querySelector('audio[src="/affirmations/waking/root"]')
    expect(audio).not.toBeNull()
    expect(audio!.tagName).toBe('AUDIO')
    // Only the selected affirmation's audio element exists at a time.
    expect(el.querySelectorAll('audio').length).toBe(1)

    expect(el.querySelector('[data-testid="nav-item-waking"]')!.classList.contains('active')).toBe(true)
    expect(el.querySelector('[data-testid="nav-item-resting"]')!.classList.contains('active')).toBe(false)
  })

  it('clicking a nav item switches the detail pane and the active indicator', () => {
    const el = renderAppView(baseProps())

    const restingNav = el.querySelector<HTMLElement>('[data-testid="nav-item-resting"]')!
    restingNav.click()

    expect(el.querySelector('[data-testid="detail-title"]')!.textContent).toContain('Resting Affirmation')
    expect(el.querySelector('[data-testid="detail-text"]')!.textContent).toContain('You are resting deeply.')
    expect(el.querySelector('audio[src="/affirmations/resting/root"]')).not.toBeNull()
    expect(el.querySelectorAll('audio').length).toBe(1)

    expect(el.querySelector('[data-testid="nav-item-waking"]')!.classList.contains('active')).toBe(false)
    expect(el.querySelector('[data-testid="nav-item-resting"]')!.classList.contains('active')).toBe(true)
  })

  it('does not render the upload stub when isCurator is false', () => {
    const el = renderAppView(baseProps({ isCurator: false }))
    expect(el.querySelector('[data-testid="upload-stub"]')).toBeNull()
    expect(el.textContent ?? '').not.toContain(UPLOAD_STUB_TEXT)
  })

  it('renders the inert upload stub when isCurator is true', () => {
    const el = renderAppView(baseProps({ isCurator: true }))

    const stub = el.querySelector<HTMLElement>('[data-testid="upload-stub"]')
    expect(stub).not.toBeNull()
    expect(stub!.textContent).toContain(UPLOAD_STUB_TEXT)

    // Stubbed / not wired: no onclick property handler, and activating it does
    // not throw and does not invoke onLogout.
    const onLogout = vi.fn()
    const el2 = renderAppView(baseProps({ isCurator: true, onLogout }))
    const stub2 = el2.querySelector<HTMLElement>('[data-testid="upload-stub"]')!
    expect(stub2.onclick).toBeNull()
    expect(() => stub2.click()).not.toThrow()
    expect(onLogout).not.toHaveBeenCalled()
  })

  it('invokes onLogout when the logout button is clicked', () => {
    const onLogout = vi.fn()
    const el = renderAppView(baseProps({ onLogout }))

    const logout = el.querySelector<HTMLElement>('[data-testid="logout"]')
    expect(logout).not.toBeNull()

    logout!.click()
    expect(onLogout).toHaveBeenCalledTimes(1)
  })

  it('renders an empty state without crashing when there are no affirmations', () => {
    const el = renderAppView(baseProps({ affirmations: [] }))
    expect(() => el.querySelectorAll('*')).not.toThrow()
    expect(el.querySelector('audio')).toBeNull()
  })

  it('renders the record trigger for a non-curator member', () => {
    const el = renderAppView(baseProps({ isCurator: false }))
    expect(el.querySelector('[data-testid="record-trigger"]')).not.toBeNull()
  })

  it('renders the record trigger for a curator too (not curator-gated)', () => {
    const el = renderAppView(baseProps({ isCurator: true }))
    expect(el.querySelector('[data-testid="record-trigger"]')).not.toBeNull()
  })

  it('clicking the record trigger swaps in the record flow gate phase', () => {
    const el = renderAppView(baseProps())

    expect(el.querySelector('[data-testid="record-ready"]')).toBeNull()

    const trigger = el.querySelector<HTMLElement>('[data-testid="record-trigger"]')!
    trigger.click()

    // The gate phase's ready button is now showing in the detail pane, and
    // the normal detail content it swapped out is gone.
    expect(el.querySelector('[data-testid="record-ready"]')).not.toBeNull()
    expect(el.querySelector('[data-testid="detail-title"]')).toBeNull()
    expect(el.querySelector('[data-testid="record-trigger"]')).toBeNull()
  })

  it('walks the record flow gate -> recording -> review placeholder states via the trigger', () => {
    const el = renderAppView(baseProps())

    el.querySelector<HTMLElement>('[data-testid="record-trigger"]')!.click()
    el.querySelector<HTMLElement>('[data-testid="record-ready"]')!.click()

    expect(el.querySelector('[data-testid="record-stop"]')).not.toBeNull()

    el.querySelector<HTMLElement>('[data-testid="record-stop"]')!.click()

    const audio = el.querySelector('audio')
    expect(audio).not.toBeNull()
    expect(el.querySelector('[data-testid="record-submit"]')).not.toBeNull()
    expect(el.querySelector('[data-testid="record-rerecord"]')).not.toBeNull()
  })

  it('re-selecting an affirmation from the nav resets an in-progress record flow', () => {
    const el = renderAppView(baseProps())

    el.querySelector<HTMLElement>('[data-testid="record-trigger"]')!.click()
    expect(el.querySelector('[data-testid="record-ready"]')).not.toBeNull()

    el.querySelector<HTMLElement>('[data-testid="nav-item-resting"]')!.click()

    expect(el.querySelector('[data-testid="record-ready"]')).toBeNull()
    expect(el.querySelector('[data-testid="detail-title"]')!.textContent).toContain('Resting Affirmation')
    expect(el.querySelector('[data-testid="record-trigger"]')).not.toBeNull()
  })
})
