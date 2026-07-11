import { describe, it, expect, vi, afterEach } from 'vitest'
import { uploadTake } from './api'

// No api.test.ts existed before this bead (sv-lds.13); per its brief, only
// the new uploadTake addition gets test coverage here -- the other api.ts
// functions (getMe/login/register/logout/getAffirmations) are untouched by
// this bead and left uncovered.

describe('uploadTake', () => {
  const originalFetch = global.fetch

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('POSTs multipart/form-data to /affirmations/{id}/takes with the blob under the "file" field, no manual Content-Type', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 201 }))
    global.fetch = fetchMock as unknown as typeof fetch

    const blob = new Blob([new Uint8Array([1, 2, 3])], { type: 'audio/wav' })
    const result = await uploadTake('aff-123', blob)

    expect(result).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledTimes(1)

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/affirmations/aff-123/takes')
    expect(init.method).toBe('POST')
    expect(init.credentials).toBe('same-origin')
    // fetch must set the multipart boundary itself -- no manual header.
    expect(init.headers).toBeUndefined()

    expect(init.body).toBeInstanceOf(FormData)
    const formData = init.body as FormData
    const file = formData.get('file')
    expect(file).toBeInstanceOf(Blob)
    expect((file as Blob).type).toBe('audio/wav')
    expect((file as Blob).size).toBe(3)
  })

  it('returns { ok: false, status } when the upload fails', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 413 }))
    global.fetch = fetchMock as unknown as typeof fetch

    const blob = new Blob([new Uint8Array([1])], { type: 'audio/wav' })
    const result = await uploadTake('aff-123', blob)

    expect(result).toEqual({ ok: false, status: 413 })
  })

  it('URL-encodes/interpolates the affirmation id directly into the path', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 201 }))
    global.fetch = fetchMock as unknown as typeof fetch

    await uploadTake('waking', new Blob([new Uint8Array([9])], { type: 'audio/wav' }))

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/affirmations/waking/takes')
  })
})
