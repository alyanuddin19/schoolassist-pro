import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-invite',
  templateUrl: './invite.component.html',
  styleUrls: ['./invite.component.css'],
})
export class InviteComponent {
  inviteCode = '';
  fullName = '';
  email = '';
  password = '';
  confirmPassword = '';
  loading = false;
  error = '';

  constructor(private auth: AuthService, private router: Router) {}

  submit(): void {
    this.error = '';
    if (!this.inviteCode.trim()) {
      this.error = 'Please enter the invite code your school shared with you.';
      return;
    }
    if (!this.fullName.trim()) {
      this.error = 'Please enter your full name.';
      return;
    }
    if (this.password.length < 6) {
      this.error = 'Password must be at least 6 characters.';
      return;
    }
    if (this.password !== this.confirmPassword) {
      this.error = 'Passwords do not match.';
      return;
    }
    this.loading = true;
    this.auth.acceptInvite({
      invite_code: this.inviteCode.trim().toUpperCase(),
      full_name: this.fullName.trim(),
      email: this.email.trim().toLowerCase() || undefined,
      password: this.password,
    }).subscribe({
      next: () => this.router.navigate([this.auth.homeRoute]),
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      },
    });
  }
}
