import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { ClassInfo, QuestionCounts, SubjectInfo, WorksheetInfo } from '../../core/models';

interface WorksheetListItem {
  id: number;
  title: string;
  topic?: string | null;
  class: string;
  subject: string;
  created_at?: string | null;
}

@Component({
  selector: 'app-worksheets',
  templateUrl: './worksheets.component.html',
  styleUrls: ['./worksheets.component.css'],
})
export class WorksheetsComponent implements OnInit {
  classes: ClassInfo[] = [];
  subjects: SubjectInfo[] = [];
  allSubjects: SubjectInfo[] = [];
  worksheets: WorksheetListItem[] = [];

  /* generator form */
  classId: number | null = null;
  sectionId: number | null = null;
  subjectId: number | null = null;
  topic = '';
  title = '';
  instructions = '';
  difficulty = 'medium';
  language = 'en';
  mcq = 5;
  short = 3;
  long = 1;
  generating = false;

  /* preview */
  preview: WorksheetInfo | null = null;
  previewTab: 'content' | 'answer' | 'scheme' = 'content';

  /* list filter */
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
    this.api.getWorksheets(params).subscribe({
      next: res => (this.worksheets = res),
      error: (err: Error) => (this.error = err.message),
    });
  }

  get sectionsForClass(): ClassInfo['sections'] {
    return this.classes.find(c => c.id === this.classId)?.sections || [];
  }

  generate(): void {
    this.error = '';
    this.notice = '';
    if (!this.classId || !this.subjectId) {
      this.error = 'Please choose the class and subject.';
      return;
    }
    if (this.topic.trim().length < 2) {
      this.error = 'Please enter the topic (e.g. "digestion", "fractions").';
      return;
    }
    const counts: QuestionCounts = {
      mcq: this.mcq || 0,
      short: this.short || 0,
      long: this.long || 0,
    };
    if (counts.mcq + counts.short + counts.long === 0) {
      this.error = 'Choose at least one question (MCQ, short or long).';
      return;
    }
    this.generating = true;
    this.api.generateWorksheet({
      class_id: this.classId,
      section_id: this.sectionId || null,
      subject_id: this.subjectId,
      topic: this.topic.trim(),
      title: this.title.trim() || undefined,
      instructions: this.instructions.trim() || undefined,
      difficulty: this.difficulty,
      language: this.language,
      question_counts: counts,
    }).subscribe({
      next: worksheet => {
        this.generating = false;
        this.preview = worksheet;
        this.previewTab = 'content';
        this.notice = 'Worksheet generated with answer key and marking scheme.';
        this.loadList();
      },
      error: (err: Error) => {
        this.generating = false;
        this.error = err.message;
      },
    });
  }

  openWorksheet(id: number): void {
    this.error = '';
    this.api.getWorksheet(id).subscribe({
      next: res => {
        this.preview = res;
        this.previewTab = 'content';
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  closePreview(): void {
    this.preview = null;
  }

  setPreviewTab(tab: 'content' | 'answer' | 'scheme'): void {
    this.previewTab = tab;
  }

  exportWorksheet(format: 'pdf' | 'docx'): void {
    if (!this.preview) {
      return;
    }
    this.api.downloadFile(
      `/exports/worksheet/${this.preview.id}?format=${format}`,
      `${this.preview.title || 'worksheet'}.${format}`,
    );
  }

  deleteWorksheet(id: number): void {
    if (!confirm('Delete this worksheet?')) {
      return;
    }
    this.api.deleteWorksheet(id).subscribe({
      next: () => {
        if (this.preview?.id === id) {
          this.preview = null;
        }
        this.loadList();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }
}
