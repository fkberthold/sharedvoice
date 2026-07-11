import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { encodeWav, createRecorderEngine } from './recorder'

// --- encodeWav -------------------------------------------------------------
//
// Pure function, no browser APIs -- this is the real, thorough test coverage
// for this module. Writes a standard 44-byte RIFF/WAVE header (PCM, mono,
// 16-bit) followed by the int16-quantized samples, clamped to [-1, 1] first.

function readAsciiChars(view: DataView, offset: number, length: number): string {
  let s = ''
  for (let i = 0; i < length; i++) {
    s += String.fromCharCode(view.getUint8(offset + i))
  }
  return s
}

// jsdom's Blob implementation does not provide .arrayBuffer()/.text() (only
// slice/size/type) -- FileReader.readAsArrayBuffer is jsdom's real,
// fully-implemented way to pull bytes back out of a Blob in this test
// environment.
function readBlobAsArrayBuffer(blob: Blob): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as ArrayBuffer)
    reader.onerror = () => reject(reader.error)
    reader.readAsArrayBuffer(blob)
  })
}

describe('encodeWav', () => {
  it('returns a Blob with the audio/wav MIME type', () => {
    const blob = encodeWav(new Float32Array([0]), 48000)
    expect(blob).toBeInstanceOf(Blob)
    expect(blob.type).toBe('audio/wav')
  })

  it('produces a blob of exactly 44 (header) + 2*numSamples bytes', () => {
    const samples = new Float32Array([0, 0.5, -0.5, 1, -1])
    const blob = encodeWav(samples, 48000)
    expect(blob.size).toBe(44 + samples.length * 2)
  })

  it('handles zero samples (header-only blob)', () => {
    const blob = encodeWav(new Float32Array([]), 48000)
    expect(blob.size).toBe(44)
  })

  it('writes a correct RIFF/WAVE/fmt /data header for a given sample rate', async () => {
    const sr = 44100
    const samples = new Float32Array([0, 0, 0])
    const blob = encodeWav(samples, sr)
    const buffer = await readBlobAsArrayBuffer(blob)
    const view = new DataView(buffer)
    const dataSize = samples.length * 2

    expect(readAsciiChars(view, 0, 4)).toBe('RIFF')
    expect(view.getUint32(4, true)).toBe(36 + dataSize) // ChunkSize
    expect(readAsciiChars(view, 8, 4)).toBe('WAVE')
    expect(readAsciiChars(view, 12, 4)).toBe('fmt ')
    expect(view.getUint32(16, true)).toBe(16) // Subchunk1Size (PCM)
    expect(view.getUint16(20, true)).toBe(1) // AudioFormat = PCM
    expect(view.getUint16(22, true)).toBe(1) // NumChannels = mono
    expect(view.getUint32(24, true)).toBe(sr) // SampleRate
    expect(view.getUint32(28, true)).toBe(sr * 2) // ByteRate = sr * blockAlign
    expect(view.getUint16(32, true)).toBe(2) // BlockAlign = channels * bytesPerSample
    expect(view.getUint16(34, true)).toBe(16) // BitsPerSample
    expect(readAsciiChars(view, 36, 4)).toBe('data')
    expect(view.getUint32(40, true)).toBe(dataSize) // Subchunk2Size
  })

  it('uses the exact sample rate passed in, distinct from a different call', async () => {
    const blobA = encodeWav(new Float32Array([0]), 16000)
    const blobB = encodeWav(new Float32Array([0]), 48000)
    const viewA = new DataView(await readBlobAsArrayBuffer(blobA))
    const viewB = new DataView(await readBlobAsArrayBuffer(blobB))
    expect(viewA.getUint32(24, true)).toBe(16000)
    expect(viewB.getUint32(24, true)).toBe(48000)
  })

  it('quantizes in-range samples to 16-bit PCM, preserving order', async () => {
    const samples = new Float32Array([0, 0.5, -0.5])
    const blob = encodeWav(samples, 48000)
    const view = new DataView(await readBlobAsArrayBuffer(blob))

    // DataView#setInt16 truncates fractional values toward zero (ECMA-262
    // ToInt16 uses ToIntegerOrInfinity, not rounding), so 0.5 * 0x7fff =
    // 16383.5 truncates to 16383, not 16384.
    expect(view.getInt16(44, true)).toBe(0)
    expect(view.getInt16(46, true)).toBe(Math.trunc(0.5 * 0x7fff))
    expect(view.getInt16(48, true)).toBe(Math.trunc(-0.5 * 0x8000))
  })

  it('maps +1 and -1 to the full positive/negative int16 range', async () => {
    const samples = new Float32Array([1, -1])
    const blob = encodeWav(samples, 48000)
    const view = new DataView(await readBlobAsArrayBuffer(blob))

    expect(view.getInt16(44, true)).toBe(32767)
    expect(view.getInt16(46, true)).toBe(-32768)
  })

  it('clamps out-of-range samples before quantizing', async () => {
    const samples = new Float32Array([2.5, -3.7, 1.0001, -1.0001])
    const blob = encodeWav(samples, 48000)
    const view = new DataView(await readBlobAsArrayBuffer(blob))

    expect(view.getInt16(44, true)).toBe(32767) // 2.5 clamped to 1
    expect(view.getInt16(46, true)).toBe(-32768) // -3.7 clamped to -1
    expect(view.getInt16(48, true)).toBe(32767) // 1.0001 clamped to 1
    expect(view.getInt16(50, true)).toBe(-32768) // -1.0001 clamped to -1
  })
})

// --- createRecorderEngine ---------------------------------------------------
//
// Real browser implementation (getUserMedia + AudioContext + AudioWorklet).
// jsdom does not implement any of these, so we hand-roll minimal fakes for
// the pieces the engine touches and assert on the CONTRACT (constraints
// passed to getUserMedia, resume-before-worklet-registration ordering,
// root <audio> play/pause, cleanup on stop, auto-stop on 'ended'). This is a
// smoke test of wiring/sequencing, not a real exercise of Web Audio
// behavior -- that genuinely can't be done in jsdom and needs manual
// verification in a real browser.

class FakeMessagePort {
  onmessage: ((ev: MessageEvent) => void) | null = null
  postMessage = vi.fn()
}

class FakeAudioWorkletNode {
  static instances: FakeAudioWorkletNode[] = []
  port = new FakeMessagePort()
  connect = vi.fn()
  disconnect = vi.fn()
  constructor(
    public context: unknown,
    public name: string,
  ) {
    FakeAudioWorkletNode.instances.push(this)
  }
}

class FakeAudioNode {
  connect = vi.fn()
  disconnect = vi.fn()
  gain = { value: 1 }
}

class FakeAudioContext {
  static instances: FakeAudioContext[] = []
  sampleRate = 48000
  destination = {}
  audioWorklet = { addModule: vi.fn().mockResolvedValue(undefined) }
  resume = vi.fn().mockResolvedValue(undefined)
  close = vi.fn().mockResolvedValue(undefined)
  createMediaStreamSource = vi.fn(() => new FakeAudioNode())
  createGain = vi.fn(() => new FakeAudioNode())
  constructor() {
    FakeAudioContext.instances.push(this)
  }
}

function fakeTrack(): MediaStreamTrack {
  return { stop: vi.fn() } as unknown as MediaStreamTrack
}

function fakeMediaStream(): MediaStream {
  const tracks = [fakeTrack(), fakeTrack()]
  return { getTracks: () => tracks } as unknown as MediaStream
}

describe('createRecorderEngine', () => {
  let getUserMedia: ReturnType<typeof vi.fn>
  let audioEl: HTMLAudioElement

  beforeEach(() => {
    FakeAudioWorkletNode.instances = []
    FakeAudioContext.instances = []

    getUserMedia = vi.fn().mockResolvedValue(fakeMediaStream())
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia },
      configurable: true,
    })

    vi.stubGlobal('AudioContext', FakeAudioContext)
    vi.stubGlobal('AudioWorkletNode', FakeAudioWorkletNode)
    // jsdom has no createObjectURL implementation; the engine only needs a
    // string back to feed into audioWorklet.addModule.
    ;(URL as unknown as { createObjectURL: unknown }).createObjectURL = vi.fn(() => 'blob:fake-worklet-url')
    ;(URL as unknown as { revokeObjectURL: unknown }).revokeObjectURL = vi.fn()

    audioEl = document.createElement('audio')
    audioEl.play = vi.fn().mockResolvedValue(undefined)
    audioEl.pause = vi.fn()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests mic access with echoCancellation/autoGainControl/noiseSuppression off and channelCount 1', async () => {
    const engine = createRecorderEngine(audioEl)
    await engine.start()

    expect(getUserMedia).toHaveBeenCalledTimes(1)
    expect(getUserMedia).toHaveBeenCalledWith({
      audio: {
        echoCancellation: false,
        autoGainControl: false,
        noiseSuppression: false,
        channelCount: 1,
      },
    })
  })

  it('creates and resumes an AudioContext, then registers the worklet module', async () => {
    const engine = createRecorderEngine(audioEl)
    await engine.start()

    expect(FakeAudioContext.instances.length).toBe(1)
    const ctx = FakeAudioContext.instances[0]
    expect(ctx.resume).toHaveBeenCalledTimes(1)
    expect(ctx.audioWorklet.addModule).toHaveBeenCalledTimes(1)
    expect(ctx.audioWorklet.addModule.mock.calls[0][0]).toEqual(expect.any(String))
  })

  it('starts root <audio> playback in sync with capture start', async () => {
    const engine = createRecorderEngine(audioEl)
    await engine.start()

    expect(audioEl.play).toHaveBeenCalledTimes(1)
  })

  it('never uses MediaRecorder', async () => {
    const engine = createRecorderEngine(audioEl)
    await engine.start()
    expect(FakeAudioWorkletNode.instances.length).toBe(1)
  })

  it('stop() releases mic tracks, disconnects the worklet, closes the context, pauses audio, and returns a WAV blob', async () => {
    const engine = createRecorderEngine(audioEl)
    await engine.start()

    const node = FakeAudioWorkletNode.instances[0]
    node.port.onmessage?.({ data: new Float32Array([0.1, 0.2]) } as MessageEvent)
    node.port.onmessage?.({ data: new Float32Array([0.3]) } as MessageEvent)

    const streamResult = await getUserMedia.mock.results[0].value
    const blob = await engine.stop()

    expect(blob).toBeInstanceOf(Blob)
    expect(blob.type).toBe('audio/wav')
    expect(blob.size).toBe(44 + 3 * 2) // 3 accumulated samples total

    for (const track of streamResult.getTracks()) {
      expect(track.stop).toHaveBeenCalledTimes(1)
    }
    expect(node.disconnect).toHaveBeenCalled()
    expect(FakeAudioContext.instances[0].close).toHaveBeenCalledTimes(1)
    expect(audioEl.pause).toHaveBeenCalledTimes(1)
  })

  it('auto-stops capture when the root <audio> element fires "ended"', async () => {
    const engine = createRecorderEngine(audioEl)
    await engine.start()

    const streamResult = await getUserMedia.mock.results[0].value
    audioEl.dispatchEvent(new Event('ended'))
    // Cleanup runs asynchronously (awaits audioContext.close()); flush microtasks.
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()

    for (const track of streamResult.getTracks()) {
      expect(track.stop).toHaveBeenCalledTimes(1)
    }
    expect(FakeAudioContext.instances[0].close).toHaveBeenCalledTimes(1)
  })

  it('is idempotent: calling stop() after an auto-stop resolves without re-running teardown', async () => {
    const engine = createRecorderEngine(audioEl)
    await engine.start()

    audioEl.dispatchEvent(new Event('ended'))
    const blob = await engine.stop()

    expect(blob).toBeInstanceOf(Blob)
    expect(FakeAudioContext.instances[0].close).toHaveBeenCalledTimes(1)
  })
})
