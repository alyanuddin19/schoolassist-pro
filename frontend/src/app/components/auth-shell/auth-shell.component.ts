import { Component, Input } from '@angular/core';

/**
 * Shared split-screen frame for the public auth pages (login / signup /
 * invite): marketing hero on the left, the page's card projected into the
 * centre and a decorative dashboard preview on the right.
 */
@Component({
  selector: 'app-auth-shell',
  templateUrl: './auth-shell.component.html',
  styleUrls: ['./auth-shell.component.css'],
})
export class AuthShellComponent {
  /** Hide the right-hand dashboard preview (used by the wide signup card). */
  @Input() showMockup = true;
}
