import { Injectable } from '@angular/core';

/* Minimal typings for the Web Speech API (not in lib.dom for all TS versions). */
interface SpeechRecognitionAlternativeLike { transcript: string; confidence: number; }
interface SpeechRecognitionResultLike {
  readonly length: number;
  isFinal: boolean;
  [index: number]: SpeechRecognitionAlternativeLike;
}
interface SpeechRecognitionResultListLike {
  readonly length: number;
  [index: number]: SpeechRecognitionResultLike;
}
interface SpeechRecognitionEventLike extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultListLike;
}
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: Event & { error?: string }) => void) | null;
  onend: (() => void) | null;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

@Injectable({ providedIn: 'root' })
export class VoiceService {
  private recognition: SpeechRecognitionLike | null = null;
  private listening = false;

  get recognitionSupported(): boolean {
    return typeof window !== 'undefined' &&
      !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  }

  get synthesisSupported(): boolean {
    return typeof window !== 'undefined' && 'speechSynthesis' in window;
  }

  speechLanguage(uiLanguage: string): string {
    switch (uiLanguage) {
      case 'ur': return 'ur-PK';
      default: return 'en-US'; // English and Roman Urdu both type/listen in English letters
    }
  }

  startRecognition(
    language: string,
    onInterim: (text: string) => void,
    onFinal: (text: string) => void,
    onError: (message: string) => void,
    onEnd: () => void,
  ): void {
    if (!this.recognitionSupported) {
      onError('Voice input is not supported in this browser. Please use Chrome or Edge.');
      return;
    }
    this.stopRecognition();

    const ctor: SpeechRecognitionCtor =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new ctor();
    recognition.lang = this.speechLanguage(language);
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: SpeechRecognitionEventLike) => {
      let interim = '';
      let final = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0]?.transcript || '';
        if (result.isFinal) {
          final += transcript;
        } else {
          interim += transcript;
        }
      }
      if (interim) {
        onInterim(interim);
      }
      if (final) {
        onFinal(final.trim());
      }
    };

    recognition.onerror = (event: Event & { error?: string }) => {
      const code = event.error || 'unknown';
      if (code === 'not-allowed' || code === 'service-not-allowed') {
        onError('Microphone permission was denied. Allow mic access to use voice input.');
      } else if (code !== 'aborted' && code !== 'no-speech') {
        onError(`Voice input error: ${code}`);
      }
    };

    recognition.onend = () => {
      this.listening = false;
      onEnd();
    };

    this.recognition = recognition;
    this.listening = true;
    recognition.start();
  }

  stopRecognition(): void {
    if (this.recognition && this.listening) {
      try {
        this.recognition.stop();
      } catch {
        /* ignore */
      }
      this.listening = false;
    }
  }

  get isListening(): boolean {
    return this.listening;
  }

  speak(text: string, language: string): void {
    if (!this.synthesisSupported || !text) {
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(this.stripMarkdown(text));
    utterance.lang = this.speechLanguage(language);
    utterance.rate = 0.95;
    const voices = window.speechSynthesis.getVoices();
    const langPrefix = utterance.lang.split('-')[0];
    const match = voices.find(v => v.lang === utterance.lang) ||
      voices.find(v => v.lang.startsWith(langPrefix));
    if (match) {
      utterance.voice = match;
    }
    window.speechSynthesis.speak(utterance);
  }

  stopSpeaking(): void {
    if (this.synthesisSupported) {
      window.speechSynthesis.cancel();
    }
  }

  private stripMarkdown(text: string): string {
    return (text || '')
      .replace(/[*_`#>]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 1200);
  }
}
