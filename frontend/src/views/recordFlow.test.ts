import { describe, it, expect, vi } from 'vitest'
import { renderRecordFlow, type RecordFlowHandlers, type RecordFlowState } from './recordFlow'

// Contract (sv-lds.12, locked via MemPalace drawer "sv-lds.12 + sv-lds.13 --
// PRE-DISPATCH CONTRACT LOCK", sharedvoice/decisions, 2026-07-10):
// renderRecordFlow(state, handlers) returns an HTMLElement rendering ONE of
// three phases based on state.phase -- 'gate' | 'recording' | 'review'. This
// view touches zero real audio/browser APIs; all behavior is proven via
// mocked handlers + jsdom DOM queries, matching authWall.ts's convention.
//
// Stable test hooks the implementation MUST provide:
//   [data-testid="record-ready"]      gate phase: "I'm ready" button -> onReady()
//   [data-testid="record-stop"]       recording phase: "Stop" button -> onStop()
//   [data-testid="record-submit"]     review phase: "Submit" button -> onSubmit()
//   [data-testid="record-rerecord"]   review phase: "Re-record" button -> onReRecord()
//   review phase: an <audio controls> element with src === state.previewUrl

function makeHandlers(): RecordFlowHandlers {
  return {
    onReady: vi.fn(),
    onStop: vi.fn(),
    onSubmit: vi.fn(),
    onReRecord: vi.fn(),
  }
}

describe('renderRecordFlow', () => {
  describe('gate phase', () => {
    const state: RecordFlowState = { phase: 'gate' }

    it('renders a headphone warning and the "I\'m ready" button', () => {
      const el = renderRecordFlow(state, makeHandlers())

      const ready = el.querySelector('[data-testid="record-ready"]')
      expect(ready).not.toBeNull()

      // Some reasonable headphone-use message must be present somewhere in the phase.
      expect((el.textContent ?? '').toLowerCase()).toContain('headphone')
    })

    it('clicking the ready button calls onReady', () => {
      const handlers = makeHandlers()
      const el = renderRecordFlow(state, handlers)

      const ready = el.querySelector<HTMLElement>('[data-testid="record-ready"]')!
      ready.click()

      expect(handlers.onReady).toHaveBeenCalledTimes(1)
    })

    it('does not render recording or review controls', () => {
      const el = renderRecordFlow(state, makeHandlers())
      expect(el.querySelector('[data-testid="record-stop"]')).toBeNull()
      expect(el.querySelector('[data-testid="record-submit"]')).toBeNull()
      expect(el.querySelector('[data-testid="record-rerecord"]')).toBeNull()
      expect(el.querySelector('audio')).toBeNull()
    })
  })

  describe('recording phase', () => {
    const state: RecordFlowState = { phase: 'recording' }

    it('renders a recording-in-progress indicator and the Stop button', () => {
      const el = renderRecordFlow(state, makeHandlers())

      const stop = el.querySelector('[data-testid="record-stop"]')
      expect(stop).not.toBeNull()

      expect((el.textContent ?? '').toLowerCase()).toContain('record')
    })

    it('clicking the stop button calls onStop', () => {
      const handlers = makeHandlers()
      const el = renderRecordFlow(state, handlers)

      const stop = el.querySelector<HTMLElement>('[data-testid="record-stop"]')!
      stop.click()

      expect(handlers.onStop).toHaveBeenCalledTimes(1)
    })

    it('does not render gate or review controls', () => {
      const el = renderRecordFlow(state, makeHandlers())
      expect(el.querySelector('[data-testid="record-ready"]')).toBeNull()
      expect(el.querySelector('[data-testid="record-submit"]')).toBeNull()
      expect(el.querySelector('[data-testid="record-rerecord"]')).toBeNull()
      expect(el.querySelector('audio')).toBeNull()
    })
  })

  describe('review phase', () => {
    const previewUrl = 'blob:http://localhost/fake-preview-url'
    const state: RecordFlowState = { phase: 'review', previewUrl }

    it('renders a preview <audio controls> element sourced at previewUrl', () => {
      const el = renderRecordFlow(state, makeHandlers())

      const audio = el.querySelector<HTMLAudioElement>('audio')
      expect(audio).not.toBeNull()
      expect(audio!.getAttribute('src')).toBe(previewUrl)
      expect(audio!.controls).toBe(true)
    })

    it('renders submit and re-record buttons', () => {
      const el = renderRecordFlow(state, makeHandlers())
      expect(el.querySelector('[data-testid="record-submit"]')).not.toBeNull()
      expect(el.querySelector('[data-testid="record-rerecord"]')).not.toBeNull()
    })

    it('clicking submit calls onSubmit', () => {
      const handlers = makeHandlers()
      const el = renderRecordFlow(state, handlers)

      el.querySelector<HTMLElement>('[data-testid="record-submit"]')!.click()

      expect(handlers.onSubmit).toHaveBeenCalledTimes(1)
      expect(handlers.onReRecord).not.toHaveBeenCalled()
    })

    it('clicking re-record calls onReRecord', () => {
      const handlers = makeHandlers()
      const el = renderRecordFlow(state, handlers)

      el.querySelector<HTMLElement>('[data-testid="record-rerecord"]')!.click()

      expect(handlers.onReRecord).toHaveBeenCalledTimes(1)
      expect(handlers.onSubmit).not.toHaveBeenCalled()
    })

    it('does not render gate or recording controls', () => {
      const el = renderRecordFlow(state, makeHandlers())
      expect(el.querySelector('[data-testid="record-ready"]')).toBeNull()
      expect(el.querySelector('[data-testid="record-stop"]')).toBeNull()
    })
  })
})
