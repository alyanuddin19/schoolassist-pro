import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { ClassInfo, QuestionCounts, SubjectInfo, TestInfo } from '../../core/models';

interface TestListItem {
  id: number;
  title: string;
  test_type: string;
  topic?: string | null;
  class: string;
  subject: string;
  total_marks?: number | null;
  created_at?: string | null;
}

const TEST_TYPE_LABELS: Record<string, string> = {
  weekly: 'Weekly Test',
  monthly: 'Monthly Test',
  mid_term: 'Mid Term',
  final_term: 'Final Term',
};

@Component({
  selector: 'app-tests',
  templateUrl: './tests.component.html',
  styleUrls: ['./tests.component.css'],
})
export class TestsComponent implements OnInit {
  classes: ClassInfo[] = [];
  subjects: SubjectInfo[] = [];
  allSubjects: SubjectInfo[] = [];
  tests: TestListItem[] = [];

  /* generator form */
  classId: number | null = null;
  sectionId: number | null = null;
  subjectId: number | null = null;
  testType = 'weekly';
  topic = '';
  title = '';
  totalMarks = 50;
  durationMinutes: number | null = 40;
  instructions = '';
  difficulty = 'medium';
  language = 'en';
  mcq = 5;
  short = 3;
  long = 1;
  generating = false;

  /* preview */
  preview: TestInfo | null = null;
  previewTab: 'content' | 'answer' | 'scheme' = 'content';

  /* list filters */
  filterClassId: number | null = null;
  filterSubjectId: number | null = null;
  filterTestType = '';

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
    const params: { class_id?: number; subject_id?: number; test_type?: string } = {};
    if (this.filterClassId) {
      params.class_id = this.filterClassId;
    }
    if (this.filterSubjectId) {
      params.subject_id = this.filterSubjectId;
    }
    if (this.filterTestType) {
      params.test_type = this.filterTestType;
    }
    this.api.getTests(params).subscribe({
      next: res => (this.tests = res),
      error: (err: Error) => (this.error = err.message),
    });
  }

  get sectionsForClass(): ClassInfo['sections'] {
    return this.classes.find(c => c.id === this.classId)?.sections || [];
  }

  typeLabel(type: string): string {
    return TEST_TYPE_LABELS[type] || type;
  }

  onTestTypeChange(): void {
    /* sensible defaults per test type */
    if (this.testType === 'weekly') {
      this.totalMarks = 25;
      this.durationMinutes = 30;
      this.mcq = 5; this.short = 2; this.long = 0;
    } else if (this.testType === 'monthly') {
      this.totalMarks = 50;
      this.durationMinutes = 60;
      this.mcq = 8; this.short = 4; this.long = 1;
    } else if (this.testType === 'mid_term') {
      this.totalMarks = 75;
      this.durationMinutes = 90;
      this.mcq = 12; this.short = 5; this.long = 2;
    } else {
      this.totalMarks = 100;
      this.durationMinutes = 120;
      this.mcq = 15; this.short = 6; this.long = 3;
    }
  }

  generate(): void {
    this.error = '';
    this.notice = '';
    if (!this.classId || !this.subjectId) {
      this.error = 'Please choose the class and subject.';
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
    this.api.generateTest({
      class_id: this.classId,
      section_id: this.sectionId || null,
      subject_id: this.subjectId,
      test_type: this.testType,
      topic: this.topic.trim() || undefined,
      title: this.title.trim() || undefined,
      total_marks: this.totalMarks || 50,
      duration_minutes: this.durationMinutes || undefined,
      instructions: this.instructions.trim() || undefined,
      difficulty: this.difficulty,
      language: this.language,
      question_counts: counts,
    }).subscribe({
      next: test => {
        this.generating = false;
        this.preview = test;
        this.previewTab = 'content';
        this.notice = `${this.typeLabel(test.test_type)} generated with answer key and marking scheme.`;
        this.loadList();
      },
      error: (err: Error) => {
        this.generating = false;
        this.error = err.message;
      },
    });
  }

  openTest(id: number): void {
    this.error = '';
    this.api.getTest(id).subscribe({
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

  exportTest(format: 'pdf' | 'docx'): void {
    if (!this.preview) {
      return;
    }
    this.api.downloadFile(
      `/exports/test/${this.preview.id}?format=${format}`,
      `${this.preview.title || 'test'}.${format}`,
    );
  }

  deleteTest(id: number): void {
    if (!confirm('Delete this test paper?')) {
      return;
    }
    this.api.deleteTest(id).subscribe({
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
