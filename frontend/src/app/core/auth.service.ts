import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { BehaviorSubject, Observable, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { AuthResponse, Membership, User } from './models';

const TOKEN_KEY = 'sa_token';
const USER_KEY = 'sa_user';
const MEMBERSHIPS_KEY = 'sa_memberships';
const ACTIVE_ORG_KEY = 'sa_active_org';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private userSubject = new BehaviorSubject<User | null>(this.readUser());
  user$ = this.userSubject.asObservable();

  // Auth endpoints are public (no bearer/org headers needed), so this service
  // calls the API directly. It must NOT inject ApiService: ApiService injects
  // AuthService for its auth headers, and that cycle crashes the app at
  // bootstrap (NG0200 cyclic dependency -> blank page).
  constructor(private http: HttpClient) {}

  get token(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  get isLoggedIn(): boolean {
    return !!this.token;
  }

  get user(): User | null {
    return this.userSubject.value;
  }

  get memberships(): Membership[] {
    try {
      return JSON.parse(localStorage.getItem(MEMBERSHIPS_KEY) || '[]');
    } catch {
      return [];
    }
  }

  get activeOrganizationId(): number | null {
    const raw = localStorage.getItem(ACTIVE_ORG_KEY);
    return raw ? Number(raw) : null;
  }

  get activeMembership(): Membership | null {
    const orgId = this.activeOrganizationId;
    if (!orgId) {
      return this.memberships[0] || null;
    }
    return this.memberships.find(m => m.organization_id === orgId) || this.memberships[0] || null;
  }

  get role(): string {
    return this.activeMembership?.role || 'teacher';
  }

  get isOwner(): boolean {
    return this.role === 'org_admin';
  }

  get isIndividual(): boolean {
    return this.activeMembership?.organization_type === 'individual';
  }

  get isAcademicLead(): boolean {
    return ['org_admin', 'principal', 'vice_principal', 'subject_coordinator'].includes(this.role);
  }

  /** Principal / vice principal run the school through the leadership desk. */
  get isLeadership(): boolean {
    return (this.role === 'principal' || this.role === 'vice_principal') && !this.isIndividual;
  }

  /** The page a user should land on right after login or an organization switch.
   *  A school owner manages the whole school, so their home is the school dashboard;
   *  individual workspaces are single-teacher setups where the teaching dashboard fits. */
  get homeRoute(): string {
    if (this.isOwner && !this.isIndividual) {
      return '/admin/dashboard';
    }
    if (this.isLeadership) {
      return '/leadership';
    }
    return '/dashboard';
  }

  get organizationName(): string {
    return this.activeMembership?.organization_name || 'SchoolAssist';
  }

  login(email: string, password: string): Observable<AuthResponse> {
    return this.post<AuthResponse>('/auth/login', { email, password });
  }

  signupIndividual(data: { full_name: string; email: string; password: string; phone?: string }): Observable<AuthResponse> {
    return this.post<AuthResponse>('/auth/signup/individual', data);
  }

  signupSchool(data: {
    full_name: string; email: string; password: string; phone?: string;
    school_name: string; city?: string; plan_code: string;
  }): Observable<AuthResponse> {
    return this.post<AuthResponse>('/auth/signup/school', data);
  }

  acceptInvite(data: { invite_code: string; email?: string; full_name?: string; password: string }): Observable<AuthResponse> {
    return this.post<AuthResponse>('/auth/invites/accept', data);
  }

  private post<T>(path: string, body: unknown): Observable<T> {
    return this.http.post<T>(`${environment.apiUrl}${path}`, body).pipe(
      map(res => {
        this.storeSession(res as AuthResponse);
        return res;
      }),
      catchError(err => this.toError(err)),
    );
  }

  private toError(err: HttpErrorResponse): Observable<never> {
    let message = 'Something went wrong. Please try again.';
    if (err.error && typeof err.error === 'object' && err.error.detail) {
      message = String(err.error.detail);
    } else if (err.status === 0) {
      message = 'Cannot reach the SchoolAssist backend. Is it running on port 8000?';
    }
    return throwError(() => new Error(message));
  }

  private storeSession(res: AuthResponse): AuthResponse {
    localStorage.setItem(TOKEN_KEY, res.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(res.user));
    localStorage.setItem(MEMBERSHIPS_KEY, JSON.stringify(res.memberships));
    localStorage.setItem(ACTIVE_ORG_KEY, String(res.default_organization_id));
    this.userSubject.next(res.user);
    return res;
  }

  /** Keeps the sidebar label in sync after the school owner renames the school. */
  updateOrganizationName(name: string): void {
    const updated = this.memberships.map(membership =>
      membership.organization_id === this.activeOrganizationId
        ? { ...membership, organization_name: name }
        : membership,
    );
    localStorage.setItem(MEMBERSHIPS_KEY, JSON.stringify(updated));
  }

  /** Keeps the topbar in sync after a user edits their own profile. */
  updateStoredUser(patch: Partial<User>): void {
    const current = this.user;
    if (!current) {
      return;
    }
    const updated = { ...current, ...patch };
    localStorage.setItem(USER_KEY, JSON.stringify(updated));
    this.userSubject.next(updated);
  }

  switchOrganization(organizationId: number): void {
    localStorage.setItem(ACTIVE_ORG_KEY, String(organizationId));
    window.location.href = this.homeRoute;
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(MEMBERSHIPS_KEY);
    localStorage.removeItem(ACTIVE_ORG_KEY);
    this.userSubject.next(null);
  }

  private readUser(): User | null {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
    } catch {
      return null;
    }
  }
}
