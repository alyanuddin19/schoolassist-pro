import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

/** Small bridge so pages can open the floating AI assistant widget. */
@Injectable({ providedIn: 'root' })
export class AiAssistantService {
  private openSubject = new Subject<void>();

  get opened$() {
    return this.openSubject.asObservable();
  }

  open(): void {
    this.openSubject.next();
  }
}
