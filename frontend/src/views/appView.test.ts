import { describe, it, expect, vi } from 'vitest'
import { renderAppView, type Affirmation, type AppViewProps } from './appView'

// Contract (sv-lds.8): renderAppView(props) returns an HTMLElement listing
// affirmations. Each affirmation renders a real HTML <audio> element sourced at
// exactly /affirmations/{id}/root (an <audio> tag, NOT a Web Audio buffer source
// -- iOS mute-switch safety). A curator-only upload stub is present only when
// isCurator is true, is labelled "Upload root (coming soon)", and is inert
// (no click/submit handler wired). A logout button invokes props.onLogout.
//
// Stable test hooks the implementation MUST provide:
//   audio[src="/affirmations/{id}/root"]  one per affirmation
//   [data-testid="upload-stub"]           curator-only inert upload control
//   [data-testid="logout"]                logout button -> calls props.onLogout

const UPLOAD_STUB_TEXT = 'Upload root (coming soon)'

function baseProps(overrides: Partial<AppViewProps> = {}): AppViewProps {
  const affirmations: Affirmation[] = [
    { id: 'waking', text: 'You are waking gently.' },
    { id: 'resting', text: 'You are resting deeply.' },
  ]
  return {
    affirmations,
    isCurator: false,
    onLogout: vi.fn(),
    ...overrides,
  }
}

describe('renderAppView', () => {
  it('renders an <audio> element with the exact root src for each affirmation', () => {
    const el = renderAppView(baseProps())

    const waking = el.querySelector('audio[src="/affirmations/waking/root"]')
    const resting = el.querySelector('audio[src="/affirmations/resting/root"]')
    expect(waking).not.toBeNull()
    expect(resting).not.toBeNull()

    // Must be real <audio> tags, not Web Audio buffer sources.
    expect(waking!.tagName).toBe('AUDIO')
    expect(resting!.tagName).toBe('AUDIO')
    expect(el.querySelectorAll('audio').length).toBe(2)
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
})
