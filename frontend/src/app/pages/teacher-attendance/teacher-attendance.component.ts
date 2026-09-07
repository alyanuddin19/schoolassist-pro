import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { AttendanceSummary, StaffInfo, TeacherAttendanceRow } from '../../core/models';

interface MarkRow {
  teacher_id: number;
  name: string;
  email: string;
  roleLabel: string;
  status: string;
  check_in: string;
}

const ROLE_LABELS: Record<string, string> = {
  principal: 'Principal',
  subject_coordinator: 'Coordinator',
  teacher: 'Teacher',
};

@Component({
  selector: 'app-teacher-attendance',
  templateUrl: './teacher-attendance.component.html',
  styleUrls: ['./teacher-attendance.component.css'],
})
export class TeacherAttendanceComponent implements OnInit {
  date = new Date().toISOString().slice(0, 10);
  month = '';

  staff: StaffInfo[] = [];
  rows: MarkRow[] = [];
  summary: AttendanceSummary | null = null;
  monthRows: TeacherAttendanceRow[] = [];

  error = '';
  notice = '';
  saving = false;

  statuses = ['present', 'absent', 'leave', 'late'];

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.error = '';
    this.api.getStaff().subscribe({
      next: staff => {
        this.staff = staff.filter(s => s.is_active && s.role !== 'org_admin');
        this.loadSheet();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  loadSheet(): void {
    this.api.getTeacherAttendance(this.date).subscribe({
      next: saved => {
        const byTeacher = new Map(saved.map(r => [r.teacher_id, r]));
        this.rows = this.staff.map(s => {
          const record = byTeacher.get(s.id);
          return {
            teacher_id: s.id,
            name: s.name,
            email: s.email,
            roleLabel: ROLE_LABELS[s.role] || s.role,
            status: record ? record.status : 'present',
            check_in: record?.check_in || '',
          };
        });
      },
      error: (err: Error) => (this.error = err.message),
    });
    this.api.getTeacherAttendanceSummary(this.date).subscribe({
      next: res => (this.summary = res),
      error: () => {},
    });
  }

  onDateChange(): void {
    this.notice = '';
    this.month = '';
    this.monthRows = [];
    this.loadSheet();
  }

  onMonthChange(): void {
    this.notice = '';
    if (!this.month) {
      this.monthRows = [];
      return;
    }
    this.api.getTeacherAttendance(undefined, this.month).subscribe({
      next: res => (this.monthRows = res.slice().reverse()),
      error: (err: Error) => (this.error = err.message),
    });
  }

  markAll(status: string): void {
    this.rows.forEach(r => (r.status = status));
  }

  save(): void {
    this.saving = true;
    this.error = '';
    this.notice = '';
    this.api
      .saveTeacherAttendance({
        date: this.date,
        entries: this.rows.map(r => ({
          teacher_id: r.teacher_id,
          status: r.status,
          check_in: r.check_in || null,
        })),
      })
      .subscribe({
        next: () => {
          this.saving = false;
          this.notice = `Attendance saved for ${this.date}.`;
          this.loadSheet();
        },
        error: (err: Error) => {
          this.saving = false;
          this.error = err.message;
        },
      });
  }
}
