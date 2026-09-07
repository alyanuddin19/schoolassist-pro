import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { ClassInfo, MarksheetInfo, SubjectInfo } from '../../core/models';

@Component({
  selector: 'app-marksheets',
  templateUrl: './marksheets.component.html',
  styleUrls: ['./marksheets.component.css'],
})
export class MarksheetsComponent implements OnInit {
  classes: ClassInfo[] = [];
  subjects: SubjectInfo[] = [];
  allSubjects: SubjectInfo[] = [];
  marksheets: MarksheetInfo[] = [];

  /* upload form */
  classId: number | null = null;
  sectionId: number | null = null;
  subjectId: number | null = null;
  examType = 'weekly';
  title = '';
  totalMarks = 50;
  uploading = false;
  importResult: { imported: number; unmatched: { roll_no: string }[] } | null = null;

  /* detail view */
  detail: MarksheetInfo | null = null;

  /* filters */
  filterClassId: number | null = null;
  filterSubjectId: number | null = null;

  error = '';
  notice = '';
  loading = true;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading = true;
    this.api.getClasses().subscribe({
      next: res => {
        this.classes = res;
        if (res.length && !this.classId) {
          this.classId = res[0].id;
          this.filterClassId = res[0].id;
        }
        this.loadSubjectsForClass();
        this.loading = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      },
    });
    this.api.getSubjects().subscribe({
      next: res => (this.allSubjects = res),
      error: () => {},
    });
    this.loadList();
  }

  /** Subjects taught in the selected class only. */
  loadSubjectsForClass(): void {
    const classId = this.classId;
    if (!classId) {
      this.subjects = this.allSubjects;
      return;
    }
    this.api.getSubjects(classId).subscribe({
      next: res => {
        if (this.classId !== classId) {
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

  onClassChange(): void {
    this.sectionId = null;
    this.loadSubjectsForClass();
  }

  loadList(): void {
    const params: { class_id?: number; subject_id?: number } = {};
    if (this.filterClassId) {
      params.class_id = this.filterClassId;
    }
    if (this.filterSubjectId) {
      params.subject_id = this.filterSubjectId;
    }
    this.api.getMarksheets(params).subscribe({
      next: res => (this.marksheets = res),
      error: (err: Error) => (this.error = err.message),
    });
  }

  get sectionsForClass(): ClassInfo['sections'] {
    return this.classes.find(c => c.id === this.classId)?.sections || [];
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files && input.files[0];
    if (!file) {
      return;
    }
    this.error = '';
    this.notice = '';
    this.importResult = null;
    if (!this.classId || !this.subjectId) {
      this.error = 'Choose the class and subject for this marksheet first.';
      input.value = '';
      return;
    }
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('class_id', String(this.classId));
    form.append('subject_id', String(this.subjectId));
    if (this.sectionId) {
      form.append('section_id', String(this.sectionId));
    }
    form.append('exam_type', this.examType);
    form.append('total_marks', String(this.totalMarks || 100));
    if (this.title.trim()) {
      form.append('title', this.title.trim());
    }

    this.uploading = true;
    this.api.uploadMarksheet(form).subscribe({
      next: (res: { marksheet: MarksheetInfo; imported: number; unmatched: { roll_no: string }[] }) => {
        this.uploading = false;
        this.detail = res.marksheet;
        this.importResult = { imported: res.imported, unmatched: res.unmatched || [] };
        this.notice = `${res.imported} student marks imported.`;
        input.value = '';
        this.loadList();
      },
      error: (err: Error) => {
        this.uploading = false;
        this.error = err.message;
        input.value = '';
      },
    });
  }

  openMarksheet(id: number): void {
    this.error = '';
    this.api.getMarksheet(id).subscribe({
      next: res => {
        this.detail = res;
        this.importResult = null;
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  closeDetail(): void {
    this.detail = null;
    this.importResult = null;
  }

  exportMarksheet(format: 'xlsx' | 'pdf'): void {
    if (!this.detail) {
      return;
    }
    this.api.downloadFile(
      `/exports/marksheet/${this.detail.id}?format=${format}`,
      `${this.detail.title || 'marksheet'}.${format}`,
    );
  }

  deleteMarksheet(id: number): void {
    if (!confirm('Delete this marksheet? Student analytics will update.')) {
      return;
    }
    this.api.deleteMarksheet(id).subscribe({
      next: () => {
        if (this.detail?.id === id) {
          this.detail = null;
        }
        this.loadList();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }
}
