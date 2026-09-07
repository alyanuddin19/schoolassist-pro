import { Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { ApiService, ChatRequestData } from '../../core/api.service';
import { AiAssistantService } from '../../core/ai-assistant.service';
import { AuthService } from '../../core/auth.service';
import { VoiceService } from '../../core/voice.service';
import { ActionDisplay, ChatUiMessage } from '../../core/models';

@Component({
  selector: 'app-ai-assistant',
  templateUrl: './ai-assistant.component.html',
  styleUrls: ['./ai-assistant.component.css'],
})
export class AiAssistantComponent implements OnInit, OnDestroy {
  @ViewChild('messagesBox', { static: false }) messagesBox?: ElementRef<HTMLDivElement>;
  @ViewChild('messageInput', { static: false }) messageInput?: ElementRef<HTMLTextAreaElement>;

  open = false;
  messages: ChatUiMessage[] = [];
  draft = '';
  language = 'en';
  sending = false;
  voiceOut = false;
  listening = false;
  interimText = '';

  imageBase64: string | null = null;
  imageMime: string | null = null;
  imageName = '';
  imagePreview: string | null = null;

  sessionId: number | null = null;
  currentPage = '/dashboard';

  suggestions: { label: string; prompt: string }[] = [
    { label: 'Worksheet', prompt: 'Generate a worksheet for Class 5 Science on digestion.' },
    { label: 'Weekly test', prompt: 'Create a weekly test for Class 7 English grammar.' },
    { label: 'Weak students', prompt: 'Show weak students in Class 9 Physics.' },
    { label: 'Class performance', prompt: 'Show class performance for Class 8.' },
    { label: 'Urdu worksheet', prompt: 'Class 6 ke liye Urdu mein Maths ki worksheet banao.' },
  ];

  private subscriptions: Subscription[] = [];

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private voice: VoiceService,
    private assistant: AiAssistantService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.subscriptions.push(
      this.assistant.opened$.subscribe(() => this.openWidget()),
    );
    this.subscriptions.push(
      this.router.events.subscribe(() => {
        this.currentPage = this.router.url.split('?')[0] || '/dashboard';
      }),
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(s => s.unsubscribe());
    this.voice.stopRecognition();
    this.voice.stopSpeaking();
  }

  get canListen(): boolean {
    return this.voice.recognitionSupported;
  }

  get canSpeak(): boolean {
    return this.voice.synthesisSupported;
  }

  openWidget(): void {
    this.open = true;
    if (this.messages.length === 0) {
      this.messages.push({
        role: 'assistant',
        content: this.welcomeMessage(),
      });
    }
    setTimeout(() => this.messageInput?.nativeElement.focus(), 100);
  }

  closeWidget(): void {
    this.open = false;
    this.stopListening();
    this.voice.stopSpeaking();
  }

  toggleListening(): void {
    if (this.listening) {
      this.stopListening();
      return;
    }
    this.voice.startRecognition(
      this.language,
      interim => {
        this.interimText = interim;
      },
      final => {
        this.interimText = '';
        this.draft = this.draft ? `${this.draft} ${final}`.trim() : final;
      },
      errorMessage => {
        this.messages.push({ role: 'assistant', content: `🎙️ ${errorMessage}` });
      },
      () => {
        this.listening = false;
        this.interimText = '';
      },
    );
    this.listening = true;
  }

  stopListening(): void {
    this.voice.stopRecognition();
    this.listening = false;
    this.interimText = '';
  }

  toggleVoiceOut(): void {
    this.voiceOut = !this.voiceOut;
    if (!this.voiceOut) {
      this.voice.stopSpeaking();
    }
  }

  speakMessage(message: ChatUiMessage): void {
    if (message.role === 'assistant' && message.content) {
      this.voice.speak(message.content, this.language);
    }
  }

  onImageSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files && input.files[0];
    if (!file) {
      return;
    }
    if (!/^image\/(png|jpe?g|webp|gif)$/.test(file.type)) {
      this.messages.push({ role: 'assistant', content: '⚠️ Please attach a PNG, JPG, WEBP or GIF image.' });
      input.value = '';
      return;
    }
    if (file.size > 4 * 1024 * 1024) {
      this.messages.push({ role: 'assistant', content: '⚠️ Image is larger than 4 MB. Please attach a smaller image.' });
      input.value = '';
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result || '');
      const base64 = dataUrl.split(',')[1] || '';
      this.imageBase64 = base64;
      this.imageMime = file.type;
      this.imageName = file.name;
      this.imagePreview = dataUrl;
    };
    reader.readAsDataURL(file);
    input.value = '';
  }

  removeImage(): void {
    this.imageBase64 = null;
    this.imageMime = null;
    this.imagePreview = null;
    this.imageName = '';
  }

  useSuggestion(prompt: string): void {
    this.draft = prompt;
    this.send();
  }

  send(): void {
    const text = this.draft.trim();
    if (!text || this.sending) {
      return;
    }
    const userMessage: ChatUiMessage = {
      role: 'user',
      content: text,
      imagePreview: this.imagePreview,
    };
    this.messages.push(userMessage);

    const history = this.messages
      .filter(m => !m.pending && m.content && m !== userMessage)
      .slice(-10)
      .map(m => ({ role: m.role, content: m.content }));

    const request: ChatRequestData = {
      message: text,
      history,
      language: this.language,
      current_page: this.currentPage,
    };
    if (this.imageBase64) {
      request.image_base64 = this.imageBase64;
      request.image_mime = this.imageMime || 'image/png';
    }
    if (this.sessionId) {
      request.session_id = this.sessionId;
    }

    this.draft = '';
    this.removeImage();
    this.sending = true;
    this.scrollToBottom();

    this.api.sendChat(request).subscribe({
      next: res => {
        this.sending = false;
        this.sessionId = res.session_id || this.sessionId;
        const assistantMessage: ChatUiMessage = {
          role: 'assistant',
          content: res.reply || '…',
          action: res.action || null,
          actionStatus: res.action_status || null,
          display: res.action_result?.display || null,
          errorText: res.action_result?.error || null,
        };
        this.messages.push(assistantMessage);
        this.scrollToBottom();
        if (this.voiceOut) {
          this.voice.speak(res.reply || '', this.language);
        }
      },
      error: (err: Error) => {
        this.sending = false;
        this.messages.push({ role: 'assistant', content: `⚠️ ${err.message}` });
        this.scrollToBottom();
      },
    });
  }

  navigateTo(display: ActionDisplay): void {
    if (display.route) {
      this.closeWidget();
      this.router.navigate([display.route]);
    }
  }

  onDraftKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  trackByIndex(index: number): number {
    return index;
  }

  private welcomeMessage(): string {
    const name = this.auth.user?.full_name?.split(' ')[0] || 'Teacher';
    return `Assalam-o-Alaikum ${name}! I am your SchoolAssist AI assistant. I can generate worksheets and tests, ` +
      `show marksheet results, find weak students, create reports and open dashboard pages for you. ` +
      `Try: "Generate a worksheet for Class 5 Science on digestion" or type in Urdu / Roman Urdu.`;
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      const box = this.messagesBox?.nativeElement;
      if (box) {
        box.scrollTop = box.scrollHeight;
      }
    }, 50);
  }
}
