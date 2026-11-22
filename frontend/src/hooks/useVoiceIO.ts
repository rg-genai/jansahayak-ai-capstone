import { useCallback, useEffect, useRef, useState } from 'react'
import { apiFetch } from '../api'

interface SpeechRecognitionInstance {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal?: boolean }> }) => void) | null
  onerror: ((ev: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionInstance
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance
  }
}

export function useVoiceIO(speechLang: string) {
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [isLoadingAudio, setIsLoadingAudio] = useState(false)
  const [voiceError, setVoiceError] = useState<string | null>(null)
  const recRef = useRef<SpeechRecognitionInstance | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const blobUrlRef = useRef<string | null>(null)

  const sttSupported =
    typeof window !== 'undefined' &&
    Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)
  // Server Neural TTS works in ALL browsers across all 6 Indian languages (zero OS voice packs needed!)
  const ttsSupported = typeof window !== 'undefined'

  const stopSpeaking = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      audioRef.current = null
    }
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current)
      blobUrlRef.current = null
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
    setIsSpeaking(false)
    setIsLoadingAudio(false)
  }, [])

  const startListening = useCallback(
    (onTranscript: (text: string) => void) => {
      setVoiceError(null)
      if (!sttSupported) {
        setVoiceError('Microphone voice input requires Chrome or Edge browser.')
        return
      }
      const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition
      if (!Ctor) return
      const rec = new Ctor()
      rec.lang = speechLang
      rec.interimResults = false
      rec.continuous = false
      rec.onresult = (event) => {
        const transcript = event.results?.[0]?.[0]?.transcript || ''
        if (transcript.trim()) onTranscript(transcript.trim())
      }
      rec.onerror = (ev) => {
        if (ev.error === 'not-allowed') {
          setVoiceError('Microphone permission denied. Please allow mic access in your browser address bar.')
        } else if (ev.error === 'no-speech') {
          setVoiceError('No speech heard — tap the mic and speak clearly.')
        } else {
          setVoiceError(`Voice input error (${ev.error}).`)
        }
        setIsListening(false)
      }
      rec.onend = () => {
        setIsListening(false)
      }
      recRef.current = rec
      setIsListening(true)
      try {
        rec.start()
      } catch {
        setIsListening(false)
      }
    },
    [speechLang, sttSupported],
  )

  const stopListening = useCallback(() => {
    recRef.current?.stop()
    setIsListening(false)
  }, [])

  const speak = useCallback(
    async (text: string) => {
      setVoiceError(null)
      stopSpeaking()
      setIsLoadingAudio(true)

      const langCode = speechLang.split('-')[0].toLowerCase()
      try {
        // Call Server Indian Neural TTS (Microsoft Edge Neural / gTTS fallback — works for en/hi/mr/bn/ta/te on ANY OS!)
        const resp = await apiFetch('/api/voice/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, language: langCode }),
        })
        if (!resp.ok) {
          throw new Error(`TTS HTTP ${resp.status}`)
        }
        const blob = await resp.blob()
        const url = URL.createObjectURL(blob)
        blobUrlRef.current = url

        const audio = new Audio(url)
        audioRef.current = audio
        audio.onplay = () => {
          setIsLoadingAudio(false)
          setIsSpeaking(true)
        }
        audio.onended = () => {
          stopSpeaking()
        }
        audio.onerror = () => {
          stopSpeaking()
          setVoiceError('Audio playback interrupted.')
        }
        await audio.play()
      } catch {
        setIsLoadingAudio(false)
        // Fallback to browser SpeechSynthesis only if server TTS is unreachable
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
          const clean = text.replace(/\[\d+\]|[*#>`_-]+|https?:\/\/\S+/g, ' ').slice(0, 1000)
          const utter = new SpeechSynthesisUtterance(clean)
          utter.lang = speechLang
          utter.onstart = () => setIsSpeaking(true)
          utter.onend = () => setIsSpeaking(false)
          utter.onerror = () => {
            setIsSpeaking(false)
            setVoiceError('Could not play audio. Please check server connectivity.')
          }
          window.speechSynthesis.speak(utter)
        } else {
          setVoiceError('Could not generate audio right now.')
        }
      }
    },
    [speechLang, stopSpeaking],
  )

  useEffect(() => {
    return () => {
      recRef.current?.stop()
      stopSpeaking()
    }
  }, [stopSpeaking])

  return {
    sttSupported,
    ttsSupported,
    isListening,
    isSpeaking,
    isLoadingAudio,
    voiceError,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
  }
}
