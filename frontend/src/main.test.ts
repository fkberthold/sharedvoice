import { describe, it, expect, vi } from 'vitest'
import { boot, type BootApi, type MeResponse } from './main'
import type { Affirmation } from './views/appView'

// Contract (sv-lds.8): boot(container, api) calls api.getMe(). If it resolves
// null (unauthenticated) it renders the auth wall into the container. If it
// resolves a MeResponse (authenticated) it renders the app view, populated from
// api.getAffirmations(), into the container. The API is injected so the boot
// dispatch can be tested without any network calls.

function makeApi(overrides: Partial<BootApi> = {}): BootApi {
  return {
    getMe: vi.fn().mockResolvedValue(null),
    getAffirmations: vi.fn().mockResolvedValue([]),
    ...overrides,
  }
}

describe('boot', () => {
  it('renders the auth wall when getMe resolves null', async () => {
    const container = document.createElement('div')
    const api = makeApi({ getMe: vi.fn().mockResolvedValue(null) })

    await boot(container, api)

    expect(container.querySelector('[data-testid="login-form"]')).not.toBeNull()
  })

  it('renders the app view with affirmations when getMe resolves a user', async () => {
    const container = document.createElement('div')
    const me: MeResponse = { username: 'alice', is_curator: false }
    const affirmations: Affirmation[] = [{ id: 'waking', text: 'You are waking gently.' }]
    const api = makeApi({
      getMe: vi.fn().mockResolvedValue(me),
      getAffirmations: vi.fn().mockResolvedValue(affirmations),
    })

    await boot(container, api)

    expect(api.getAffirmations).toHaveBeenCalled()
    expect(container.querySelector('audio[src="/affirmations/waking/root"]')).not.toBeNull()
  })
})
