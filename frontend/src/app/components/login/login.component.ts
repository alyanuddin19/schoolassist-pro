import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css'],
})
export class LoginComponent {
  email = '';
  password = '';
  loading = false;
  error = '';
  info = '';
  showPassword = false;
  rememberMe = true;

  private static readonly REMEMBER_KEY = 'schoolassist.remember_email';

  constructor(private auth: AuthService, private router: Router) {
    const saved = localStorage.getItem(LoginComponent.REMEMBER_KEY);
    if (saved) {
      this.email = saved;
    }
  }

  submit(): void {
    this.error = '';
    this.info = '';
    if (!this.email.trim() || !this.password) {
      this.error = 'Please enter your email and password.';
      return;
    }
    if (this.rememberMe) {
      localStorage.setItem(LoginComponent.REMEMBER_KEY, this.email.trim().toLowerCase());
    } else {
      localStorage.removeItem(LoginComponent.REMEMBER_KEY);
    }
    this.loading = true;
    this.auth.login(this.email.trim().toLowerCase(), this.password).subscribe({
      next: () => this.router.navigate([this.auth.homeRoute]),
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      },
    });
  }

  forgotPassword(): void {
    this.error = '';
    this.info = 'Password reset is not available online yet. Please contact your school owner or admin to reset your password.';
  }
}
