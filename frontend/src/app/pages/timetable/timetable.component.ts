import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { forkJoin } from 'rxjs';
import { ClassInfo, StaffInfo, SubjectInfo, AssignmentInfo, TimetableEntryInfo } from '../../core/models';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

@Component({
  selector: 'app-timetable',
  templateUrl: './timetable.component.html',
  styleUrls: ['./timetable.component.css'],
})
export class TimetableComponent implements OnInit {
  days = DAYS;
  classes: ClassInfo[] = [];
  subjects: SubjectInfo[] = [];
  teachers: StaffInfo[] = [];
  entries: TimetableEntryInfo[] = [];
  /* Teacher → Subject → Class → Section mapping maintained on the setup page. */
  assignments: AssignmentInfo[] = [];

  classId: number | null = null;
  sectionId: number | null = null;

  /* new period form */
  day = 'Monday';
  start = '08:00';
  end = '08:40';
  subjectId: number | null = null;
  teacherId: number | null = null;

  error = '';
  notice = '';
  saving = false;
  principalPlans: { class: ClassInfo; entries: TimetableEntryInfo[]; comment: string }[] = [];

  constructor(private api: ApiService, public auth: AuthService) {}

  ngOnInit(): void {
    this.api.getClasses().subscribe({
      next: res => {
        this.classes = res;
        if (this.isPrincipal) {
          forkJoin(res.map(c => this.api.getTimetable({ class_id: c.id }))).subscribe({ next: plans => this.principalPlans = res.map((c, i) => ({ class: c, entries: plans[i], comment: '' })), error: () => {} });
        }
        if (res.length) {
          this.classId = res[0].id;
          this.onClassChange();
        }
      },
      error: (err: Error) => (this.error = err.message),
    });
    this.api.getStaff().subscribe({
      next: res => (this.teachers = res.filter(t => t.is_active && t.role !== 'org_admin')),
      error: () => {},
    });
    this.api.getAssignments().subscribe({
      next: res => {
        this.assignments = res;
        this.suggestTeacher();
      },
      error: () => {},
    });
  }

  /** Assignments that cover the class, subject and section currently being scheduled. */
  private matchingAssignments(): AssignmentInfo[] {
    if (!this.classId || !this.subjectId) {
      return [];
    }
    return this.assignments.filter(a =>
      a.class_id === this.classId
      && a.subject_id === this.subjectId
      && (!a.section_id || a.section_id === this.sectionId));
  }

  /** Staff mapped to this class + subject are offered first in the picker. */
  get assignedTeachers(): StaffInfo[] {
    const ids = new Set(this.matchingAssignments().map(a => a.teacher_id));
    return this.teachers.filter(t => ids.has(t.id));
  }

  get otherTeachers(): StaffInfo[] {
    const ids = new Set(this.matchingAssignments().map(a => a.teacher_id));
    return this.teachers.filter(t => !ids.has(t.id));
  }

  /** Pre-select the teacher when the mapping names exactly one for this period. */
  private suggestTeacher(): void {
    const matches = this.assignedTeachers;
    if (matches.length === 1 && this.teacherId !== matches[0].id) {
      this.teacherId = matches[0].id;
    }
  }

  onSubjectChange(): void {
    this.suggestTeacher();
  }

  /** Coordinators / principals build the timetable; the owner only views it. */
  get canEdit(): boolean {
    return (
      this.auth.role === 'subject_coordinator' ||
      this.isIndividual
    );
  }
  get isPrincipal(): boolean { return this.auth.role === 'principal'; }
  planEntries(plan: { entries: TimetableEntryInfo[] }, day: string): TimetableEntryInfo[] { return plan.entries.filter(x => x.day === day).sort((a,b) => a.start_time.localeCompare(b.start_time)); }
  decidePlan(plan: { class: ClassInfo; comment: string }, approved: boolean): void { const action = approved ? this.api.approveTimetable(plan.class.id, plan.comment) : this.api.returnTimetable(plan.class.id, plan.comment); action.subscribe({ next: () => { this.notice = `${plan.class.name} timetable ${approved ? 'approved' : 'returned'} and sent to the coordinator.`; }, error: (e: Error) => this.error = e.message }); }

  get isIndividual(): boolean {
    const membership = this.auth.memberships.find(m => m.organization_id === this.auth.activeOrganizationId);
    return membership?.organization_type === 'individual';
  }

  get selectedClass(): ClassInfo | undefined {
    return this.classes.find(c => c.id === this.classId);
  }

  /** Section label for the card header (templates cannot hold arrow functions). */
  get selectedSectionName(): string {
    const sections = this.selectedClass?.sections || [];
    return sections.find(s => s.id === this.sectionId)?.name || '';
  }

  onClassChange(): void {
    this.sectionId = null;
    this.entries = [];
    this.subjects = [];
    if (!this.classId) {
      return;
    }
    this.api.getSubjects(this.classId).subscribe({
      next: res => {
        this.subjects = res;
        this.subjectId = res.length ? res[0].id : null;
        this.suggestTeacher();
      },
      error: () => {},
    });
    this.loadEntries();
  }

  onSectionChange(): void {
    this.suggestTeacher();
    this.loadEntries();
  }

  loadEntries(): void {
    if (!this.classId) {
      return;
    }
    this.api
      .getTimetable({ class_id: this.classId, section_id: this.sectionId || undefined })
      .subscribe({
        next: res => (this.entries = res),
        error: (err: Error) => (this.error = err.message),
      });
  }

  entriesFor(day: string): TimetableEntryInfo[] {
    return this.entries
      .filter(e => e.day === day)
      .sort((a, b) => a.start_time.localeCompare(b.start_time));
  }

  addPeriod(): void {
    this.error = '';
    this.notice = '';
    if (!this.classId || !this.subjectId) {
      this.error = 'Select a class and subject first.';
      return;
    }
    if (this.end <= this.start) {
      this.error = 'End time must be after start time.';
      return;
    }
    this.saving = true;
    this.api
      .createTimetableEntry({
        class_id: this.classId,
        section_id: this.sectionId,
        subject_id: this.subjectId,
        teacher_id: this.teacherId,
        day: this.day,
        start_time: this.start,
        end_time: this.end,
      })
      .subscribe({
        next: () => {
          this.saving = false;
          this.notice = 'Period added to the timetable.';
          this.loadEntries();
        },
        error: (err: Error) => {
          this.saving = false;
          this.error = err.message;
        },
      });
  }

  remove(entry: TimetableEntryInfo): void {
    if (!confirm(`Remove ${entry.subject} on ${entry.day} ${entry.start_time}?`)) {
      return;
    }
    this.api.deleteTimetableEntry(entry.id).subscribe({
      next: () => this.loadEntries(),
      error: (err: Error) => (this.error = err.message),
    });
  }
}
