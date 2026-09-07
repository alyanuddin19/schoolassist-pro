import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/api.service';
import {
  AssignmentInfo, InviteInfo, MemberInfo, OrgOverview, PaymentInfo, Plan,
  StaffInfo, SubjectInfo, TimetableEntryInfo,
} from '../../core/models';

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

interface TeacherForm {
  full_name: string;
  email: string;
  phone: string;
  role: string;
  designation: string;
  /** primary / secondary; empty means the teacher covers both levels. */
  level: string;
  qualification: string;
  gender: string;
  joining_date: string;
  password: string;
  send_email: boolean;
  subject_ids: number[];
}

function blankTeacherForm(): TeacherForm {
  return {
    full_name: '', email: '', phone: '', role: 'teacher', designation: 'Teacher',
    level: '', qualification: '', gender: '', joining_date: '', password: '',
    send_email: true, subject_ids: [],
  };
}

@Component({
  selector: 'app-admin-dashboard',
  templateUrl: './admin-dashboard.component.html',
  styleUrls: ['./admin-dashboard.component.css'],
})
export class AdminDashboardComponent implements OnInit {
  /* The tab bar is gone: overview is the dashboard itself and the staff view is
     reached from the sidebar (Teachers). */
  tab: 'overview' | 'staff' = 'overview';
  showPlans = false;
  /* Teachers page: which of the two entry forms is open right now. */
  staffMode: 'add' | 'invite' = 'add';
  /* The staff list opens on demand from the Show Teachers button. */
  showStaff = false;

  overview: OrgOverview | null = null;
  members: MemberInfo[] = [];
  invites: InviteInfo[] = [];
  payments: PaymentInfo[] = [];
  plans: Plan[] = [];
  staff: StaffInfo[] = [];
  subjects: SubjectInfo[] = [];
  assignments: AssignmentInfo[] = [];
  todaySchedule: TimetableEntryInfo[] = [];
  todayName = DAY_NAMES[new Date().getDay()];

  loading = false;
  error = '';
  notice = '';

  /* create teacher form */
  form: TeacherForm = blankTeacherForm();
  creatingTeacher = false;
  credentials: { name: string; email: string; password: string; employee_id: string; emailed: boolean } | null = null;

  /* edit teacher */
  editing: StaffInfo | null = null;
  editForm: TeacherForm = blankTeacherForm();
  savingEdit = false;
  staffSearch = '';

  /* invite form */
  inviteEmail = '';
  inviteName = '';
  inviteRole = 'teacher';
  creatingInvite = false;
  lastInviteCode = '';

  constructor(private api: ApiService, private route: ActivatedRoute) {}

  ngOnInit(): void {
    const routeTab = this.route.snapshot.data['tab'];
    if (routeTab === 'staff' || routeTab === 'overview') {
      this.tab = routeTab;
    }
    this.route.queryParamMap.subscribe(params => {
      const tab = params.get('tab');
      if (tab === 'staff' || tab === 'overview') {
        this.tab = tab;
      }
    });
    this.loadAll();
  }

  loadAll(): void {
    this.loading = true;
    this.error = '';
    this.api.adminDashboard().subscribe({
      next: res => {
        this.overview = res;
        this.loading = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      },
    });
    this.api.getMembers().subscribe({ next: res => (this.members = res), error: () => {} });
    this.api.getInvites().subscribe({ next: res => (this.invites = res), error: () => {} });
    this.api.getPayments().subscribe({ next: res => (this.payments = res), error: () => {} });
    this.api.getPlans().subscribe({ next: res => (this.plans = res), error: () => {} });
    this.loadStaff();
    this.loadSubjects();
    this.loadAssignments();
    this.loadTodaySchedule();
  }

  loadStaff(): void {
    this.api.getStaff().subscribe({ next: res => (this.staff = res), error: () => {} });
  }

  loadSubjects(): void {
    this.api.getSubjects().subscribe({ next: res => (this.subjects = res), error: () => {} });
  }

  loadAssignments(): void {
    this.api.getAssignments().subscribe({ next: res => (this.assignments = res), error: () => {} });
  }

  loadTodaySchedule(): void {
    this.api.getTimetable({}).subscribe({
      next: entries => (this.todaySchedule = entries.filter(e => e.day === this.todayName)),
      error: () => {},
    });
  }

  get visibleStaff(): StaffInfo[] {
    const term = this.staffSearch.trim().toLowerCase();
    if (!term) {
      return this.staff;
    }
    return this.staff.filter(s =>
      [s.name, s.email, s.designation || '', s.employee_id || '', s.level || '']
        .join(' ')
        .toLowerCase()
        .includes(term),
    );
  }

  subjectName(id: number): string {
    return this.subjects.find(s => s.id === id)?.name || '';
  }

  assignedClasses(userId: number): string {
    const list = this.assignments.filter(a => a.teacher_id === userId);
    if (!list.length) {
      return '—';
    }
    return [...new Set(list.map(a => (a.section ? `${a.class} · ${a.section}` : a.class)))].join(', ');
  }

  toggleSubject(form: TeacherForm, subjectId: number): void {
    const index = form.subject_ids.indexOf(subjectId);
    if (index >= 0) {
      form.subject_ids.splice(index, 1);
    } else {
      form.subject_ids.push(subjectId);
    }
  }

  get seatPercent(): number {
    const seats = this.overview?.seats;
    if (!seats || !seats.seats_total) {
      return 0;
    }
    return Math.min(100, Math.round((seats.seats_used / seats.seats_total) * 100));
  }

  get studentSeatPercent(): number {
    const seats = this.overview?.seats;
    if (!seats || !seats.student_seats_total) {
      return 0;
    }
    return Math.min(100, Math.round(((seats.student_seats_used ?? 0) / seats.student_seats_total) * 100));
  }

  get activeMembers(): number {
    return this.members.filter(member => member.is_active).length;
  }

  get roleLabels(): Record<string, string> {
    return {
      org_admin: 'School Owner',
      principal: 'Principal',
      vice_principal: 'Vice Principal',
      subject_coordinator: 'Subject Coordinator',
      teacher: 'Teacher',
    };
  }

  /** Primary covers classes 1-5, secondary 6-10; blank means both. */
  levelLabel(level?: string | null): string {
    if (level === 'primary') {
      return 'Primary (1-5)';
    }
    return level === 'secondary' ? 'Secondary (6-10)' : 'Both levels';
  }

  createTeacher(): void {
    this.error = '';
    this.notice = '';
    this.credentials = null;
    const form = this.form;
    if (!form.full_name.trim() || !form.email.trim() || !form.designation.trim()) {
      this.error = 'Name, email and designation are required.';
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) {
      this.error = 'Enter a valid email address — the login account is created with it.';
      return;
    }
    if (form.password && form.password.length < 6) {
      this.error = 'Temporary password must be at least 6 characters.';
      return;
    }
    this.creatingTeacher = true;
    this.api
      .createTeacher({
        full_name: form.full_name.trim(),
        email: form.email.trim().toLowerCase(),
        phone: form.phone.trim() || undefined,
        role: form.role,
        designation: form.designation.trim(),
        level: form.level || undefined,
        qualification: form.qualification.trim() || undefined,
        gender: form.gender || undefined,
        joining_date: form.joining_date || undefined,
        subject_ids: form.subject_ids,
        password: form.password || undefined,
        send_email: form.send_email,
      })
      .subscribe({
        next: res => {
          this.creatingTeacher = false;
          this.form = blankTeacherForm();
          this.credentials = {
            name: res.full_name,
            email: res.email,
            password: res.temporary_password,
            employee_id: res.employee_id,
            emailed: !!res.email_sent,
          };
          this.notice = res.email_sent
            ? `Login account created for ${res.full_name}. Credentials were emailed to ${res.email}.`
            : `Login account created for ${res.full_name}. Share the temporary password below — it is shown only once.`;
          this.showStaff = true;
          this.loadAll();
        },
        error: (err: Error) => {
          this.creatingTeacher = false;
          this.error = err.message;
        },
      });
  }

  startEdit(member: StaffInfo): void {
    this.editing = member;
    this.notice = '';
    this.error = '';
    this.editForm = {
      full_name: member.name,
      email: member.email,
      phone: member.phone || '',
      role: member.role,
      designation: member.designation || 'Teacher',
      level: member.level || '',
      qualification: member.qualification || '',
      gender: member.gender || '',
      joining_date: '',
      password: '',
      send_email: false,
      subject_ids: [...member.subject_ids],
    };
    this.api.getTeacherProfile(member.id).subscribe({
      next: profile => {
        this.editForm.joining_date = profile.joining_date || '';
        this.editForm.level = profile.level || '';
        this.editForm.subject_ids = [...profile.subject_ids];
      },
      error: () => {},
    });
  }

  cancelEdit(): void {
    this.editing = null;
  }

  saveEdit(): void {
    if (!this.editing) {
      return;
    }
    const form = this.editForm;
    if (!form.full_name.trim()) {
      this.error = 'Name cannot be empty.';
      return;
    }
    this.savingEdit = true;
    this.error = '';
    this.notice = '';
    const payload: Record<string, any> = {
      full_name: form.full_name.trim(),
      phone: form.phone.trim() || null,
      role: form.role,
      designation: form.designation.trim(),
      level: form.level,
      qualification: form.qualification.trim() || null,
      gender: form.gender || null,
      joining_date: form.joining_date || null,
    };
    this.api.updateTeacher(this.editing.id, payload).subscribe({
      next: () => {
        this.api.setTeacherSubjects(this.editing!.id, form.subject_ids).subscribe({
          next: () => {
            this.savingEdit = false;
            this.editing = null;
            this.notice = 'Teacher details updated.';
            this.loadAll();
          },
          error: (err: Error) => {
            this.savingEdit = false;
            this.error = err.message;
          },
        });
      },
      error: (err: Error) => {
        this.savingEdit = false;
        this.error = err.message;
      },
    });
  }

  toggleActive(member: StaffInfo): void {
    const next = !member.is_active;
    const verb = next ? 'Activate' : 'Deactivate';
    if (!confirm(`${verb} ${member.name}? ${next ? 'They will regain access.' : 'Their login will stop working and the seat is freed.'}`)) {
      return;
    }
    this.api.updateTeacher(member.id, { is_active: next }).subscribe({
      next: () => {
        this.notice = `${member.name} is now ${next ? 'active' : 'inactive'}.`;
        this.loadAll();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  dismissCredentials(): void {
    this.credentials = null;
  }

  createInvite(): void {
    this.error = '';
    this.notice = '';
    if (!this.inviteEmail.trim()) {
      this.error = 'Please enter the teacher email to invite.';
      return;
    }
    this.creatingInvite = true;
    this.api.createInvite({
      email: this.inviteEmail.trim().toLowerCase(),
      full_name: this.inviteName.trim() || undefined,
      role: this.inviteRole,
    }).subscribe({
      next: invite => {
        this.creatingInvite = false;
        this.lastInviteCode = invite.invite_code;
        this.notice = `Invite created. Share this code with the teacher: ${invite.invite_code}`;
        this.inviteEmail = '';
        this.inviteName = '';
        this.api.getInvites().subscribe({ next: res => (this.invites = res), error: () => {} });
      },
      error: (err: Error) => {
        this.creatingInvite = false;
        this.error = err.message;
      },
    });
  }

  revokeInvite(invite: InviteInfo): void {
    if (!confirm(`Revoke the invite for ${invite.email}?`)) {
      return;
    }
    this.api.revokeInvite(invite.id).subscribe({
      next: () => {
        this.api.getInvites().subscribe({ next: res => (this.invites = res), error: () => {} });
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  deactivateMember(member: MemberInfo): void {
    if (!confirm(`Deactivate ${member.full_name}? Their account will no longer consume a teacher seat.`)) {
      return;
    }
    this.api.deactivateMember(member.id).subscribe({
      next: () => this.loadAll(),
      error: (err: Error) => (this.error = err.message),
    });
  }

  changePlan(plan: Plan): void {
    this.error = '';
    this.notice = '';
    if (!confirm(`Switch to the ${plan.name} (${plan.teacher_seats} teacher seats, PKR ${plan.price_pkr}/month)? Payment is sandboxed in the MVP.`)) {
      return;
    }
    this.api.changePlan(plan.code).subscribe({
      next: () => {
        this.notice = `Plan changed to ${plan.name}. A sandboxed payment record was created.`;
        this.loadAll();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  copyCode(code: string): void {
    navigator.clipboard?.writeText(code).then(
      () => (this.notice = `Invite code copied: ${code}`),
      () => (this.notice = `Invite code: ${code}`),
    );
  }
}
