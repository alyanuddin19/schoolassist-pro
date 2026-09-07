import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { PrincipalDashboardData } from '../../core/models';

@Component({
  selector: 'app-leadership',
  templateUrl: './leadership.component.html',
  styleUrls: ['./leadership.component.css'],
})
export class LeadershipComponent implements OnInit {
  data: PrincipalDashboardData | null = null;
  loading = true; error = '';
  constructor(private api: ApiService) {}
  ngOnInit(): void { this.api.principalDashboard().subscribe({ next: data => { this.data = data; this.loading = false; }, error: err => { this.error = err.message; this.loading = false; } }); }
  get summaryCards(): { label: string; value: string | number; route: string; icon: string }[] {
    const d = this.data; if (!d) return [];
    return [{ label: 'Total Students', value: d.students, route: '/reports', icon: '🧑‍🎓' }, { label: 'Total Teachers', value: d.teachers, route: '/leadership?tab=teachers', icon: '👩‍🏫' }, { label: 'Total Classes', value: d.classes, route: '/leadership?tab=academic', icon: '🏫' }, { label: 'Teacher Attendance Today', value: `${d.attendance_today.present} / ${d.attendance_today.marked} Present`, route: '/teacher-attendance', icon: '✓' }, { label: 'Upcoming Exams', value: d.upcoming_exams.length, route: '/exams', icon: '📝' }, { label: 'Pending Approvals', value: d.pending_approvals.length, route: '/leaves', icon: '⏳' }];
  }
}
