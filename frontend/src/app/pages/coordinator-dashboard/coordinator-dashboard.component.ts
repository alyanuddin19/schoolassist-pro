import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import {
  ClassReport, FinalTermReportRequestData, ReportInfo, WeakStudentsResult,
} from '../../core/models';

interface CoordinatorClass { id: number; name: string; grade_level?: number | null; }

@Component({
  selector: 'app-coordinator-dashboard',
  templateUrl: './coordinator-dashboard.component.html',
  styleUrls: ['./coordinator-dashboard.component.css'],
})
export class CoordinatorDashboardComponent implements OnInit {
  classes: CoordinatorClass[] = [];
  selectedClassId: number | null = null;
  selectedClassName = '';

  classPerformance: ClassReport | null = null;
  weakStudents: WeakStudentsResult | null = null;
  finalReports: ReportInfo[] = [];

  academicYear = '';
  creatingReport = false;
  loading = true;
  error = '';
  notice = '';

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    const now = new Date();
    const startYear = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
    this.academicYear = `${startYear}-${startYear + 1}`;
    this.load();
  }

  load(classId?: number): void {
    this.loading = true;
    this.error = '';
    this.api.coordinatorDashboard(classId).subscribe({
      next: res => {
        this.classes = res.classes || [];
        this.selectedClassId = res.selected_class?.id || null;
        this.selectedClassName = res.selected_class?.name || '';
        this.classPerformance = res.class_performance || null;
        this.weakStudents = res.weak_students || null;
        this.finalReports = res.final_reports || [];
        this.loading = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      },
    });
  }

  onClassChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const classId = Number(select.value);
    if (classId) {
      this.notice = '';
      this.load(classId);
    }
  }

  createFinalReport(): void {
    if (!this.selectedClassId) {
      this.error = 'Please select a class first.';
      return;
    }
    const request: FinalTermReportRequestData = {
      class_id: this.selectedClassId,
      academic_year: this.academicYear.trim() || undefined,
    };
    this.creatingReport = true;
    this.error = '';
    this.notice = '';
    this.api.createFinalTermReport(request).subscribe({
      next: report => {
        this.creatingReport = false;
        this.notice = `Final term report "${report.title}" created. Find it in the Reports page.`;
        this.load(this.selectedClassId || undefined);
      },
      error: (err: Error) => {
        this.creatingReport = false;
        this.error = err.message;
      },
    });
  }

  exportReport(report: ReportInfo, format: 'pdf' | 'docx' | 'xlsx'): void {
    this.api.downloadFile(`/exports/report/${report.id}?format=${format}`, `${report.title}.${format}`);
  }

  get hasData(): boolean {
    return !!this.classPerformance?.subjects?.length;
  }
}
