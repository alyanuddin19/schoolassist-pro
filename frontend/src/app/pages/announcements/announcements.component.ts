import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { AnnouncementInfo, ClassInfo } from '../../core/models';

@Component({
  selector: 'app-announcements',
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <h1>Announcements</h1>
          <p class="page-sub">Publish and review school notices for staff, students, parents, or a class.</p>
        </div>
        <button class="btn primary" *ngIf="canPublish" (click)="showForm = !showForm">
          {{ showForm ? 'Cancel' : 'New announcement' }}
        </button>
      </div>

      <div class="alert error" *ngIf="error">{{ error }}</div>
      <div class="alert success" *ngIf="notice">{{ notice }}</div>

      <section class="card form-card" *ngIf="canPublish && showForm">
        <div class="card-head"><h3>Create announcement</h3></div>
        <div class="form-grid">
          <label class="field full">
            <span>Title</span>
            <input type="text" [(ngModel)]="title" placeholder="e.g. Parent-teacher meeting" />
          </label>
          <label class="field full">
            <span>Message</span>
            <textarea [(ngModel)]="message" rows="4" placeholder="Write the announcement"></textarea>
          </label>
          <label class="field">
            <span>Audience</span>
            <select [(ngModel)]="audience">
              <option value="school">Whole school</option>
              <option value="teachers">Teachers</option>
              <option value="students">Students</option>
              <option value="parents">Parents</option>
              <option value="class">Specific class</option>
            </select>
          </label>
          <label class="field">
            <span>Class</span>
            <select [(ngModel)]="classId" [disabled]="audience !== 'class'">
              <option [ngValue]="null">All classes</option>
              <option *ngFor="let c of classes" [ngValue]="c.id">{{ c.name }}</option>
            </select>
          </label>
        </div>
        <div class="row-actions submit-row">
          <button class="btn primary" (click)="create()" [disabled]="saving">
            {{ saving ? 'Publishing...' : 'Publish' }}
          </button>
        </div>
      </section>

      <div class="loading" *ngIf="loading">Loading announcements...</div>

      <section class="card" *ngIf="!loading">
        <div class="card-head">
          <h3>Recent announcements</h3>
          <button class="btn secondary sm" (click)="load()">Refresh</button>
        </div>
        <p class="empty" *ngIf="!announcements.length">No announcements yet.</p>
        <div class="table-scroll" *ngIf="announcements.length">
          <table class="table">
            <thead>
              <tr><th>Title</th><th>Audience</th><th>Class</th><th>Published</th></tr>
            </thead>
            <tbody>
              <tr *ngFor="let ann of announcements">
                <td>
                  <strong>{{ ann.title }}</strong>
                  <small class="muted block">{{ ann.message }}</small>
                </td>
                <td><span class="chip">{{ audienceLabel(ann) }}</span></td>
                <td>{{ ann.class || ann.class_name || '-' }}</td>
                <td>{{ (ann.published_at || ann.created_at) | date: 'mediumDate' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>
  `,
  styles: [`
    .submit-row { justify-content: flex-end; margin-top: 14px; }
    .block { display: block; margin-top: 4px; max-width: 560px; white-space: normal; }
  `],
})
export class AnnouncementsComponent implements OnInit {
  announcements: AnnouncementInfo[] = [];
  classes: ClassInfo[] = [];
  loading = true;
  saving = false;
  showForm = false;
  error = '';
  notice = '';
  title = '';
  message = '';
  audience = 'school';
  classId: number | null = null;

  constructor(private api: ApiService, public auth: AuthService) {}

  ngOnInit(): void {
    this.load();
    this.api.getClasses().subscribe({ next: classes => (this.classes = classes), error: () => {} });
  }

  get canPublish(): boolean {
    return ['org_admin', 'principal', 'vice_principal', 'subject_coordinator'].includes(this.auth.role);
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.getAnnouncements().subscribe({
      next: rows => {
        this.announcements = rows;
        this.loading = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      },
    });
  }

  create(): void {
    if (!this.title.trim() || !this.message.trim()) {
      this.error = 'Title and message are required.';
      return;
    }
    this.saving = true;
    this.error = '';
    this.notice = '';
    this.api.createAnnouncement({
      title: this.title.trim(),
      message: this.message.trim(),
      audience: this.audience,
      class_id: this.audience === 'class' ? this.classId : null,
    }).subscribe({
      next: row => {
        this.announcements = [row, ...this.announcements];
        this.saving = false;
        this.showForm = false;
        this.notice = 'Announcement published.';
        this.title = '';
        this.message = '';
        this.audience = 'school';
        this.classId = null;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.saving = false;
      },
    });
  }

  audienceLabel(ann: AnnouncementInfo): string {
    const value = ann.audience || ann.target_audience || 'school';
    const labels: Record<string, string> = {
      school: 'Whole school',
      all: 'Whole school',
      teachers: 'Teachers',
      students: 'Students',
      parents: 'Parents',
      class: 'Class',
    };
    return labels[value] || value;
  }
}
