import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import {
  ClassInfo, ExamInfo, ExamRoomInfo, SeatingInfo, SeatingPreview, SeatingRoomSummary, StudentInfo,
} from '../../core/models';

type SeatingRow = SeatingInfo['rows'][number];

/** One room of the saved plan: its seat list plus each class's roll range. */
interface RoomPlanGroup {
  room: string;
  capacity: number;
  seats: number;
  rows: SeatingRow[];
  ranges: { class: string; students: number; roll_from: string; roll_to: string }[];
}

interface PaperRow {
  subjectId: number;
  subject: string;
  date: string;
  start: string;
  end: string;
}

const TERM_SUGGESTIONS = ['Monthly Test', 'Mid Term', 'Final Term'];

@Component({
  selector: 'app-exams-results',
  templateUrl: './exams-results.component.html',
  styleUrls: ['./exams-results.component.css'],
})
export class ExamsResultsComponent implements OnInit {
  tab: 'timetable' | 'seating' = 'timetable';
  terms = TERM_SUGGESTIONS;

  term = '';
  classId: number | null = null;
  /* School level filter: only that level's classes are offered in the picks. */
  levelFilter: 'all' | 'primary' | 'secondary' = 'all';

  classes: ClassInfo[] = [];
  students: StudentInfo[] = [];
  rows: PaperRow[] = [];
  savedExams: ExamInfo[] = [];
  allExams: ExamInfo[] = [];

  rooms: ExamRoomInfo[] = [];
  roomName = '';
  roomCapacity = 30;
  seating: SeatingInfo = { plan: null, rows: [], rooms: [] };
  /* Room-wise allocation preview — the step before the real plan is saved. */
  preview: SeatingPreview | null = null;
  previewing = false;
  /* How many different classes one room may hold; null mixes every class. */
  classesPerRoom: number | null = null;
  perRoomChoices = [1, 2, 3, 4, 5, 6];

  notice = '';
  error = '';
  saving = false;
  generating = false;
  loaded = false;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.getClasses().subscribe({
      next: res => (this.classes = res),
      error: (err: Error) => (this.error = err.message),
    });
    this.loadRooms();
    this.loadAllExams();
  }

  loadAllExams(): void {
    this.api.getExams({}).subscribe({ next: exams => (this.allExams = exams), error: () => {} });
  }

  get selectedClass(): ClassInfo | undefined {
    return this.classes.find(c => c.id === this.classId);
  }

  get classLabel(): string {
    if (this.selectedClass) {
      return this.selectedClass.name;
    }
    return this.levelFilter === 'all' ? 'All classes' : `All ${this.levelFilter} classes`;
  }

  /** The class dropdowns only list the classes of the chosen school level. */
  get levelClasses(): ClassInfo[] {
    if (this.levelFilter === 'all') {
      return this.classes;
    }
    return this.classes.filter(c => c.level === this.levelFilter);
  }

  /** Sent to the backend so "all classes" means all of the chosen level. */
  get levelParam(): string | null {
    return this.levelFilter === 'all' ? null : this.levelFilter;
  }

  /** Label of the "no single class" option, scoped to the chosen level. */
  get allClassesOption(): string {
    return this.levelFilter === 'all'
      ? 'All classes (mixed seating)'
      : `All ${this.levelFilter} classes (mixed seating)`;
  }

  get totalCapacity(): number {
    return this.rooms.reduce((sum, room) => sum + room.capacity, 0);
  }

  day(date: string): string {
    if (!date) {
      return '—';
    }
    return new Intl.DateTimeFormat('en-US', { weekday: 'long', timeZone: 'UTC' }).format(
      new Date(`${date}T00:00:00Z`),
    );
  }

  /* ---------------- exam timetable ---------------- */

  onTermChange(): void {
    this.notice = '';
    this.error = '';
    this.loadClassData();
  }

  onClassChange(): void {
    this.notice = '';
    this.error = '';
    this.loadClassData();
  }

  /** A new level narrows the class list; a class outside it is reset. */
  onLevelChange(): void {
    const selected = this.selectedClass;
    if (selected && this.levelFilter !== 'all' && selected.level !== this.levelFilter) {
      this.classId = null;
    }
    this.loadClassData();
  }

  loadClassData(): void {
    this.rows = [];
    this.students = [];
    this.savedExams = [];
    this.seating = { plan: null, rows: [], rooms: [] };
    this.preview = null;
    this.loaded = false;
    /* Without a class the timetable has nothing to edit, but the seating plan
       still works: it then seats every class mixed across the rooms. */
    this.api.getStudents({ class_id: this.classId }).subscribe({
      next: res => (this.students = res),
      error: (err: Error) => (this.error = err.message),
    });
    if (!this.classId) {
      this.loadSeating();
      this.loadPreview();
      return;
    }
    this.api.getSubjects(this.classId).subscribe({
      next: subjects => {
        this.rows = subjects.map(s => ({ subjectId: s.id, subject: s.name, date: '', start: '', end: '' }));
        this.loaded = true;
        this.mergeSavedExams();
      },
      error: (err: Error) => (this.error = err.message),
    });
    this.mergeSavedExams();
    this.loadSeating();
    this.loadPreview();
  }

  private mergeSavedExams(): void {
    if (!this.classId || !this.term) {
      this.savedExams = [];
      return;
    }
    this.api.getExams({ class_id: this.classId, term: this.term }).subscribe({
      next: exams => {
        this.savedExams = exams;
        const bySubject = new Map(exams.map(e => [e.subject_id, e]));
        this.rows.forEach(row => {
          const saved = bySubject.get(row.subjectId);
          if (saved) {
            row.date = saved.date;
            row.start = saved.start_time;
            row.end = saved.end_time;
          }
        });
      },
      error: () => {},
    });
  }

  saveTimetable(): void {
    this.error = '';
    this.notice = '';
    if (!this.term.trim() || !this.classId) {
      this.error = 'Select an exam term and class first.';
      return;
    }
    if (!this.rows.length) {
      this.error = 'This class has no subjects. Assign subjects to the class first.';
      return;
    }
    if (this.rows.some(r => !r.date || !r.start || !r.end)) {
      this.error = 'Every subject needs a date, start time and end time.';
      return;
    }
    if (this.rows.some(r => r.end <= r.start)) {
      this.error = 'End time must be after the start time.';
      return;
    }
    const overlap = this.rows.some((r, i) =>
      this.rows.some((o, j) => i !== j && r.date === o.date && r.start < o.end && r.end > o.start),
    );
    if (overlap) {
      this.error = 'Two papers overlap on the same date and time. Adjust the timings.';
      return;
    }
    this.saving = true;
    this.api
      .saveExamSchedule({
        term: this.term.trim(),
        class_id: this.classId,
        papers: this.rows.map(r => ({
          subject_id: r.subjectId,
          date: r.date,
          start_time: r.start,
          end_time: r.end,
        })),
      })
      .subscribe({
        next: () => {
          this.saving = false;
          this.notice = `Exam timetable saved for ${this.term} · ${this.classLabel}.`;
          this.mergeSavedExams();
        },
        error: (err: Error) => {
          this.saving = false;
          this.error = err.message;
        },
      });
  }

  removeExam(exam: ExamInfo): void {
    if (!confirm(`Remove the ${exam.subject} paper on ${exam.date}?`)) {
      return;
    }
    this.api.deleteExam(exam.id).subscribe({
      next: () => {
        this.notice = 'Paper removed.';
        this.mergeSavedExams();
        this.loadAllExams();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  /* ---------------- rooms ---------------- */

  loadRooms(): void {
    this.api.getExamRooms().subscribe({
      next: res => {
        this.rooms = res;
        /* The allocation preview depends on the rooms, so refresh it too. */
        this.loadPreview();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  addRoom(): void {
    this.error = '';
    if (!this.roomName.trim() || this.roomCapacity < 1) {
      this.error = 'Enter a room name and a capacity of at least 1.';
      return;
    }
    this.api.createExamRoom({ name: this.roomName.trim(), capacity: this.roomCapacity }).subscribe({
      next: () => {
        this.roomName = '';
        this.roomCapacity = 30;
        this.notice = 'Room added.';
        this.loadRooms();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  removeRoom(room: ExamRoomInfo): void {
    if (!confirm(`Remove ${room.name}?`)) {
      return;
    }
    this.api.deleteExamRoom(room.id).subscribe({
      next: () => {
        this.loadRooms();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  /** The admin edits a room's name or capacity right in the table. */
  saveRoom(room: ExamRoomInfo): void {
    this.error = '';
    if (!room.name.trim() || room.capacity < 1) {
      this.error = 'Room name cannot be empty and capacity must be at least 1.';
      return;
    }
    this.api.updateExamRoom(room.id, { name: room.name.trim(), capacity: room.capacity }).subscribe({
      next: () => {
        this.notice = `${room.name} updated.`;
        this.loadRooms();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  /* ---------------- seating plan ---------------- */

  loadSeating(): void {
    if (!this.term.trim()) {
      this.seating = { plan: null, rows: [], rooms: [] };
      return;
    }
    this.api.getSeating(this.term.trim(), this.classId).subscribe({
      next: res => (this.seating = res),
      error: () => (this.seating = { plan: null, rows: [], rooms: [] }),
    });
  }

  /** Room-wise allocation preview: counts per class per room, nothing saved. */
  loadPreview(): void {
    if (!this.rooms.length) {
      this.preview = null;
      return;
    }
    this.previewing = true;
    this.error = '';
    this.api.previewSeating(this.classId, this.classesPerRoom, this.levelParam).subscribe({
      next: res => {
        this.preview = res;
        this.previewing = false;
      },
      error: (err: Error) => {
        this.previewing = false;
        this.error = err.message;
      },
    });
  }

  /** The admin picked a different class mix per room: re-run the preview. */
  onPerRoomChange(): void {
    this.loadPreview();
  }

  generateSeating(): void {
    this.error = '';
    this.notice = '';
    if (!this.term.trim()) {
      this.error = 'Enter an exam term first.';
      return;
    }
    if (!this.rooms.length) {
      this.error = 'Add at least one examination room with its capacity first.';
      return;
    }
    this.generating = true;
    this.api
      .generateSeating({
        term: this.term.trim(),
        class_id: this.classId,
        level: this.levelParam,
        classes_per_room: this.classesPerRoom,
      })
      .subscribe({
        next: () => {
          this.generating = false;
          this.notice = `Seating plan generated for ${this.term} · ${this.classLabel}.`;
          this.loadSeating();
          this.loadPreview();
        },
        error: (err: Error) => {
          this.generating = false;
          this.error = err.message;
        },
      });
  }

  /** How full a room is, for its progress bar. */
  fillPercent(room: SeatingRoomSummary): number {
    if (!room.capacity) {
      return 0;
    }
    return Math.min(100, Math.round((room.total / room.capacity) * 100));
  }

  /** The saved plan grouped room by room for the room-wise student list. */
  get seatingRooms(): RoomPlanGroup[] {
    const groups: { room: string; rows: SeatingRow[] }[] = [];
    for (const row of this.seating.rows) {
      const group = groups.find(item => item.room === row.room);
      if (group) {
        group.rows.push(row);
      } else {
        groups.push({ room: row.room, rows: [row] });
      }
    }
    return groups.map(group => {
      const summary = (this.seating.rooms || []).find(item => item.room === group.room);
      /* Roll range per class inside this room, e.g. "Class 1 — Roll no. 5-19". */
      const byClass = new Map<string, SeatingRow[]>();
      for (const row of group.rows) {
        const key = row.class || '—';
        const list = byClass.get(key);
        if (list) {
          list.push(row);
        } else {
          byClass.set(key, [row]);
        }
      }
      const ranges = Array.from(byClass.entries()).map(([name, list]) => {
        const rolls = list
          .map(item => item.roll_no)
          .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
        return { class: name, students: list.length, roll_from: rolls[0], roll_to: rolls[rolls.length - 1] };
      });
      return {
        room: group.room,
        capacity: summary ? summary.capacity : group.rows.length,
        seats: group.rows.length,
        rows: group.rows,
        ranges,
      };
    });
  }

  /** Room-wise CSV so the final plan can be printed or shared from Excel. */
  downloadSeating(): void {
    const lines = ['Room,Seat no.,Roll no.,Student,Class'];
    for (const row of this.seating.rows) {
      lines.push(
        [row.room, row.seat_no, row.roll_no, row.student, row.class || '']
          .map(value => `"${String(value).replace(/"/g, '""')}"`)
          .join(','),
      );
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `seating-plan-${this.term.trim() || 'term'}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  /** Class-wise PDF of the saved plan (only the selected class, if any). */
  downloadSeatingPdf(): void {
    if (!this.term.trim() || !this.seating.rows.length) {
      return;
    }
    this.api.downloadSeatingPdf(this.term.trim(), this.classId);
  }

  printSeating(): void {
    window.print();
  }
}
