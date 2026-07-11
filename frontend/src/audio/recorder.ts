// Real audio engine for the record-a-take flow (sv-lds.13). Captures raw
// mic PCM via an AudioWorklet -- NEVER MediaRecorder (constitution hard
// constraint) -- while the root <audio> element plays in sync, then
// encodes the accumulated samples as a WAV blob on stop().
//
// jsdom cannot exercise getUserMedia/AudioContext/AudioWorklet, so
// createRecorderEngine is not meaningfully unit-testable here; only
// encodeWav (pure, no browser APIs) gets real test coverage. See
// recorder.test.ts for a wiring/sequencing smoke test of the engine built
// on hand-rolled fakes.

export interface RecorderEngine {
  /** Requests mic permission, starts AudioWorklet capture, and starts root
   * <audio> playback in sync. Must be called from within a user-gesture
   * handler (e.g. the "I'm ready" tap) so AudioContext.resume() satisfies
   * the browser autoplay-gesture requirement. */
  start(): Promise<void>
  /** Stops capture + playback and resolves with the encoded WAV blob
   * (audio/wav). Idempotent: if capture already auto-stopped (root
   * playback's `ended` event fired), returns the same result without
   * re-running teardown. */
  stop(): Promise<Blob>
}

const WORKLET_PROCESSOR_NAME = 'sv-pcm-capture-processor'

// AudioWorkletProcessor source, loaded via a Blob URL at runtime (see
// loadWorkletModule below) rather than as a separate file that Vite's
// asset pipeline would need to know how to serve/bundle for both `pnpm
// dev` and `pnpm build`. A Blob URL sidesteps that entirely -- no bundler
// config, no dev-vs-build path divergence, and it keeps the whole engine
// self-contained in this one file, matching the project's "vanilla TS,
// thin structure" convention. The tradeoff is a runtime string instead of
// a type-checked module; the processor body is small and simple enough
// (accumulate + postMessage) that this is an easy trade.
const PCM_WORKLET_SOURCE = `
class SvPcmCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0]
    const channel = input && input[0]
    if (channel && channel.length > 0) {
      // Copy: the Float32Array backing 'channel' is reused by the audio
      // engine on the next render quantum.
      this.port.postMessage(channel.slice())
    }
    return true
  }
}
registerProcessor('${WORKLET_PROCESSOR_NAME}', SvPcmCaptureProcessor)
`

async function loadWorkletModule(audioContext: AudioContext): Promise<void> {
  const blob = new Blob([PCM_WORKLET_SOURCE], { type: 'application/javascript' })
  const url = URL.createObjectURL(blob)
  try {
    await audioContext.audioWorklet.addModule(url)
  } finally {
    URL.revokeObjectURL(url)
  }
}

/** Pure: write a standard 44-byte RIFF/WAVE header (PCM, mono, 16-bit)
 * followed by int16-quantized samples (clamped to [-1, 1] first). No
 * browser API calls -- fully unit-testable. */
export function encodeWav(samples: Float32Array, sr: number): Blob {
  const numChannels = 1
  const bitsPerSample = 16
  const bytesPerSample = bitsPerSample / 8
  const blockAlign = numChannels * bytesPerSample
  const byteRate = sr * blockAlign
  const dataSize = samples.length * bytesPerSample

  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)

  writeAsciiString(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeAsciiString(view, 8, 'WAVE')

  writeAsciiString(view, 12, 'fmt ')
  view.setUint32(16, 16, true) // Subchunk1Size (16 for PCM)
  view.setUint16(20, 1, true) // AudioFormat = 1 (PCM)
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sr, true)
  view.setUint32(28, byteRate, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, bitsPerSample, true)

  writeAsciiString(view, 36, 'data')
  view.setUint32(40, dataSize, true)

  let offset = 44
  for (let i = 0; i < samples.length; i++, offset += bytesPerSample) {
    const clamped = Math.max(-1, Math.min(1, samples[i]))
    const intSample = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff
    view.setInt16(offset, intSample, true)
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

function writeAsciiString(view: DataView, offset: number, value: string): void {
  for (let i = 0; i < value.length; i++) {
    view.setUint8(offset + i, value.charCodeAt(i))
  }
}

/** Real browser implementation: getUserMedia -> AudioContext (resumed from
 * the calling user gesture) -> AudioWorklet capture, with root <audio>
 * playback started in sync and auto-stop wired to its 'ended' event. */
export function createRecorderEngine(rootAudioEl: HTMLAudioElement): RecorderEngine {
  let mediaStream: MediaStream | null = null
  let audioContext: AudioContext | null = null
  let workletNode: AudioWorkletNode | null = null
  let sourceNode: AudioNode | null = null
  let silentGainNode: AudioNode | null = null
  let chunks: Float32Array[] = []
  let sampleRate = 48000
  let stopPromise: Promise<Blob> | null = null

  function handleEnded(): void {
    void stop()
  }

  async function start(): Promise<void> {
    chunks = []
    stopPromise = null

    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        autoGainControl: false,
        noiseSuppression: false,
        channelCount: 1,
      },
    })

    audioContext = new AudioContext()
    await audioContext.resume()
    sampleRate = audioContext.sampleRate

    await loadWorkletModule(audioContext)

    sourceNode = audioContext.createMediaStreamSource(mediaStream)
    workletNode = new AudioWorkletNode(audioContext, WORKLET_PROCESSOR_NAME)
    workletNode.port.onmessage = (event: MessageEvent) => {
      chunks.push(event.data as Float32Array)
    }

    sourceNode.connect(workletNode)
    // Route through a zero-gain node to destination: AudioWorkletNodes are
    // only guaranteed to keep processing while reachable from the
    // destination in every browser's implementation, but we must not let
    // the user hear their own mic input echoed back.
    silentGainNode = audioContext.createGain()
    ;(silentGainNode as GainNode).gain.value = 0
    workletNode.connect(silentGainNode)
    silentGainNode.connect(audioContext.destination)

    rootAudioEl.addEventListener('ended', handleEnded, { once: true })
    await rootAudioEl.play()
  }

  async function stop(): Promise<Blob> {
    if (stopPromise) {
      return stopPromise
    }
    stopPromise = teardownAndEncode()
    return stopPromise
  }

  async function teardownAndEncode(): Promise<Blob> {
    rootAudioEl.removeEventListener('ended', handleEnded)
    rootAudioEl.pause()

    if (workletNode) {
      workletNode.port.onmessage = null
      workletNode.disconnect()
      workletNode = null
    }
    if (silentGainNode) {
      silentGainNode.disconnect()
      silentGainNode = null
    }
    if (sourceNode) {
      sourceNode.disconnect()
      sourceNode = null
    }
    if (mediaStream) {
      for (const track of mediaStream.getTracks()) {
        track.stop()
      }
      mediaStream = null
    }

    const sr = sampleRate
    if (audioContext) {
      await audioContext.close()
      audioContext = null
    }

    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
    const samples = new Float32Array(totalLength)
    let offset = 0
    for (const chunk of chunks) {
      samples.set(chunk, offset)
      offset += chunk.length
    }
    chunks = []

    return encodeWav(samples, sr)
  }

  return { start, stop }
}
