import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { TeacherDashboardData } from '../../core/models';

@Component({
  selector: 'app-teacher-dashboard',
  templateUrl: './teacher-dashboard.component.html',
  styleUrls: ['./teacher-dashboard.component.css'],
})
export class TeacherDashboardComponent implements OnInit {
  data: TeacherDashboardData | null = null;
  loading = true;
  error = '';

  constructor(public auth: AuthService, private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    if (this.auth.role === 'subject_coordinator') {
      this.router.navigate(['/coordinator']);
      return;
    }
    this.load();
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.teacherDashboard().subscribe({
      next: res => {
        this.data = res;
        this.loading = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      },
    });
  }

  get statEntries(): { label: string; value: number; icon: string }[] {
    const stats = this.data?.stats || {};
    return [
      { label: 'My Classes', value: stats.my_classes || 0, icon: '🏫' },
      { label: 'My Subjects', value: stats.my_subjects || 0, icon: '📚' },
      { label: 'My Students', value: stats.my_students || 0, icon: '🧑‍🎓' },
      { label: 'Worksheets', value: stats.worksheets || 0, icon: '📝' },
      { label: 'Tests', value: stats.tests || 0, icon: '🧪' },
      { label: 'Marksheets', value: stats.marksheets || 0, icon: '📥' },
    ];
  }

  get firstName(): string {
    return this.auth.user?.full_name?.split(' ')[0] || 'Teacher';
  }
}
