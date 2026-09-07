import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import {
  AdminSummary, ClassInfo, FinalTermContent, FinalTermStudentRow, ReportInfo, StudentInfo,
  StudentReport, SubjectInfo, SubjectReport, WeakStudentsResult,
} from '../../core/models';

type ReportTab = 'student' | 'subject' | 'weak' | 'final' | 'summary';

const ROLE_LABELS: Record<string, string> = {
  principal: 'Principal',
  subject_coordinator: 'Coordinator',
  teacher: 'Teacher',
  org_admin: 'Owner',
};

@Component({
  selector: 'app-reports',
  templateUrl: './reports.component.html',
  styleUrls: ['./reports.component.css'],
})
export class ReportsComponent implements OnInit {
  tab: ReportTab = 'student';

  classes: ClassInfo[] = [];
  subjects: SubjectInfo[] = [];

  /* student report */
  searchQuery = '';
  searchResults: StudentInfo[] = [];
  studentReport: StudentReport | null = null;
  selectedStudent: StudentInfo | null = null;

  /* subject report */
  subjectClassId: number | null = null;
  subjectId: number | null = null;
  subjectReport: SubjectReport | null = null;
  loadingSubject = false;

  /* weak students */
  weakClassId: number | null = null;
  weakThreshold = 40;
  weakResult: WeakStudentsResult | null = null;
  loadingWeak = false;

  /* final term */
  finalReports: ReportInfo[] = [];
  finalDetail: ReportInfo | null = null;

  /* admin summary */
  summary: AdminSummary | null = null;
  loadingSummary = false;
  summarySearch = '';

  error = '';
  loading = true;

  constructor(public auth: AuthService, private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading = true;
    this.api.getClasses().subscribe({
      next: res => {
        this.classes = res;
        if (res.length) {
          if (!this.subjectClassId) {
            this.subjectClassId = res[0].id;
          }
          if (!this.weakClassId) {
            this.weakClassId = res[0].id;
          }
        }
        this.loadSubjectsForClass();
        this.loading = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      },
    });
    this.loadFinalReports();
  }

  /** Subjects taught in the selected class only. */
  loadSubjectsForClass(): void {
    const classId = this.subjectClassId;
    if (!classId) {
      this.subjects = [];
      return;
    }
    this.api.getSubjects(classId).subscribe({
      next: res => {
        if (this.subjectClassId !== classId) {
          return; /* class changed while the request was in flight */
        }
        this.subjects = res;
        if (!res.some(s => s.id === this.subjectId)) {
          this.subjectId = res.length ? res[0].id : null;
        }
      },
      error: () => {},
    });
  }

  onSubjectClassChange(): void {
    this.subjectReport = null;
    this.loadSubjectsForClass();
  }

  setTab(tab: ReportTab): void {
    this.tab = tab;
    this.error = '';
    if (tab === 'summary' && !this.summary && !this.loadingSummary) {
      this.loadAdminSummary();
    }
  }

  /* ---------------- student report ---------------- */

  searchStudents(): void {
    this.error = '';
    if (!this.searchQuery.trim()) {
      this.searchResults = [];
      return;
    }
    this.api.getStudents({ search: this.searchQuery.trim() }).subscribe({
      next: res => (this.searchResults = res.slice(0, 10)),
      error: (err: Error) => (this.error = err.message),
    });
  }

  openStudentReport(student: StudentInfo): void {
    this.error = '';
    this.selectedStudent = student;
    this.api.getStudentReport(student.id).subscribe({
      next: res => (this.studentReport = res),
      error: (err: Error) => (this.error = err.message),
    });
  }

  /* ---------------- subject report ---------------- */

  loadSubjectReport(): void {
    if (!this.subjectClassId || !this.subjectId) {
      this.error = 'Choose the class and subject.';
      return;
    }
    this.error = '';
    this.loadingSubject = true;
    this.api.getSubjectReport(this.subjectClassId, this.subjectId).subscribe({
      next: res => {
        this.subjectReport = res;
        this.loadingSubject = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loadingSubject = false;
      },
    });
  }

  /* ---------------- weak students ---------------- */

  loadWeakStudents(): void {
    if (!this.weakClassId) {
      this.error = 'Choose the class.';
      return;
    }
    this.error = '';
    this.loadingWeak = true;
    this.api.getWeakStudents({ class_id: this.weakClassId, threshold: this.weakThreshold }).subscribe({
      next: res => {
        this.weakResult = res;
        this.loadingWeak = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loadingWeak = false;
      },
    });
  }

  /* ---------------- final term reports ---------------- */

  get canCreateFinal(): boolean {
    return this.auth.isIndividual || this.auth.isAcademicLead;
  }

  loadFinalReports(): void {
    this.api.getReports({ report_type: 'final_term' }).subscribe({
      next: res => (this.finalReports = res),
      error: () => {},
    });
  }

  openFinalReport(report: ReportInfo): void {
    this.error = '';
    this.api.getReport(report.id).subscribe({
      next: res => (this.finalDetail = res),
      error: (err: Error) => (this.error = err.message),
    });
  }

  get finalContent(): FinalTermContent | null {
    return (this.finalDetail?.content as FinalTermContent) || null;
  }

  finalStudentSubjects(student: FinalTermStudentRow): (number | null)[] {
    const content = this.finalContent;
    if (!content) {
      return [];
    }
    return content.subject_order.map(subject => student.subjects?.[subject] ?? null);
  }

  exportFinalReport(format: 'pdf' | 'docx' | 'xlsx'): void {
    if (!this.finalDetail) {
      return;
    }
    this.api.downloadFile(
      `/exports/report/${this.finalDetail.id}?format=${format}`,
      `${this.finalDetail.title || 'final-report'}.${format}`,
    );
  }

  /* ---------------- admin summary ---------------- */

  /** Only the management side (owner, principal, coordinator) needs the whole-school summary. */
  get canViewSummary(): boolean {
    return this.auth.isAcademicLead || this.auth.isIndividual;
  }

  loadAdminSummary(): void {
    this.error = '';
    this.loadingSummary = true;
    this.api.getAdminSummary().subscribe({
      next: res => {
        this.summary = res;
        this.loadingSummary = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loadingSummary = false;
      },
    });
  }

  roleLabel(role: string): string {
    return ROLE_LABELS[role] || role;
  }

  /** Sections of a class rendered as "A: 12 · B: 9", or a dash when nobody is assigned yet. */
  sectionText(sections: Record<string, number>): string {
    const entries = Object.entries(sections || {});
    return entries.length ? entries.map(([name, count]) => `${name}: ${count}`).join(' · ') : '—';
  }

  /** Strength bar relative to the largest class, so the biggest class always fills the track. */
  barWidth(students: number): number {
    const largest = Math.max(...(this.summary?.class_wise || []).map(row => row.students), 0);
    return largest > 0 ? Math.round((students / largest) * 100) : 0;
  }

  /** Share of the active enrollment, used in the distribution table. */
  sharePercent(students: number): string {
    const active = this.summary?.enrollment.active || 0;
    return active > 0 ? ((students / active) * 100).toFixed(1) : '0.0';
  }

  get summaryTeachers(): AdminSummary['teachers'] {
    const term = this.summarySearch.trim().toLowerCase();
    const teachers = this.summary?.teachers || [];
    if (!term) {
      return teachers;
    }
    return teachers.filter(t =>
      [t.name, t.designation, t.department, ...(t.subjects || [])]
        .some(value => (value || '').toLowerCase().includes(term)),
    );
  }

  printSummary(): void {
    window.print();
  }
}
