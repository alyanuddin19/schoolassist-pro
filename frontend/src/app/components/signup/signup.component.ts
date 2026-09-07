import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Plan } from '../../core/models';

@Component({
  selector: 'app-signup',
  templateUrl: './signup.component.html',
  styleUrls: ['./signup.component.css'],
})
export class SignupComponent implements OnInit {
  step: 'choose' | 'individual' | 'school' = 'choose';
  loading = false;
  error = '';
  plans: Plan[] = [];
  plansLoaded = false;
  selectedPlanCode = '';

  /* shared fields */
  fullName = '';
  email = '';
  phone = '';
  password = '';
  confirmPassword = '';

  /* school fields */
  schoolName = '';
  city = '';

  constructor(private auth: AuthService, private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.api.getPlans().subscribe({
      next: plans => {
        this.plans = plans;
        this.selectedPlanCode = plans.length ? plans[plans.length - 1].code : '';
        this.plansLoaded = true;
      },
      error: () => {
        /* plans are optional for rendering; signup will validate server-side */
        this.plansLoaded = true;
      },
    });
  }

  chooseIndividual(): void {
    this.error = '';
    this.step = 'individual';
  }

  chooseSchool(): void {
    this.error = '';
    this.step = 'school';
  }

  backToChoose(): void {
    this.error = '';
    this.step = 'choose';
  }

  submitIndividual(): void {
    this.error = '';
    if (!this.validateCommon()) {
      return;
    }
    this.loading = true;
    this.auth.signupIndividual({
      full_name: this.fullName.trim(),
      email: this.email.trim().toLowerCase(),
      password: this.password,
      phone: this.phone.trim() || undefined,
    }).subscribe({
      next: () => this.router.navigate([this.auth.homeRoute]),
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      },
    });
  }

  submitSchool(): void {
    this.error = '';
    if (!this.validateCommon()) {
      return;
    }
    if (!this.schoolName.trim()) {
      this.error = 'Please enter your school name.';
      return;
    }
    if (!this.selectedPlanCode) {
      this.error = 'Please choose a teacher-seat plan.';
      return;
    }
    this.loading = true;
    this.auth.signupSchool({
      full_name: this.fullName.trim(),
      email: this.email.trim().toLowerCase(),
      password: this.password,
      phone: this.phone.trim() || undefined,
      school_name: this.schoolName.trim(),
      city: this.city.trim() || undefined,
      plan_code: this.selectedPlanCode,
    }).subscribe({
      next: () => this.router.navigate([this.auth.homeRoute]),
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      },
    });
  }

  selectPlan(code: string): void {
    this.selectedPlanCode = code;
  }

  private validateCommon(): boolean {
    if (!this.fullName.trim()) {
      this.error = 'Please enter your full name.';
      return false;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(this.email.trim())) {
      this.error = 'Please enter a valid email address.';
      return false;
    }
    if (this.password.length < 6) {
      this.error = 'Password must be at least 6 characters.';
      return false;
    }
    if (this.password !== this.confirmPassword) {
      this.error = 'Passwords do not match.';
      return false;
    }
    return true;
  }
}
