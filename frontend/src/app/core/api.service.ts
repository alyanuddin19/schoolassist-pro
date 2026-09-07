import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';
import {
  AssignmentInfo, ChatResponse, ClassInfo, ClassReport, FinalTermReportRequestData,
  MarksheetInfo, MemberInfo, OrgOverview, PaymentInfo, Plan, QuestionCounts, ReportInfo,
  SubjectInfo, SubjectReport, StudentInfo, StudentReport, TeacherInfo, TestInfo, WeakStudentsResult,
  WorksheetInfo, InviteInfo, StaffInfo, TeacherProfileInfo, GuardianInfo, StudentProfileInfo,
  AttendanceSheet, AttendanceSummary, TeacherAttendanceRow, TimetableEntryInfo, ExamInfo,
  ExamRoomInfo, SeatingInfo, SeatingPreview, AnnouncementInfo, SchoolSettingsInfo, AdminSummary,
  LeaveInfo, User,
  PrincipalDashboardData,
  PrincipalSchoolOverviewData,
  PrincipalTeachersData,
} from './models';

export interface ChatRequestData {
  message: string;
  history: { role: 'user' | 'assistant'; content: string }[];
  language: string;
  current_page?: string;
  image_base64?: string;
  image_mime?: string;
  session_id?: number;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private base = environment.apiUrl;

  constructor(private http: HttpClient, private auth: AuthService) {}

  private headers(): HttpHeaders {
    let headers = new HttpHeaders();
    const token = this.auth.token;
    if (token) {
      headers = headers.set('Authorization', `Bearer ${token}`);
    }
    const orgId = this.auth.activeOrganizationId;
    if (orgId) {
      headers = headers.set('X-Organization-Id', String(orgId));
    }
    return headers;
  }

  private get<T>(path: string, params?: Record<string, any>): Observable<T> {
    let httpParams = new HttpParams();
    if (params) {
      for (const key of Object.keys(params)) {
        const value = params[key];
        if (value !== undefined && value !== null && value !== '') {
          httpParams = httpParams.set(key, String(value));
        }
      }
    }
    return this.http
      .get<T>(`${this.base}${path}`, { headers: this.headers(), params: httpParams })
      .pipe(catchError(err => this.handleError(err)));
  }

  private post<T>(path: string, body: any): Observable<T> {
    return this.http
      .post<T>(`${this.base}${path}`, body, { headers: this.headers() })
      .pipe(catchError(err => this.handleError(err)));
  }

  private patch<T>(path: string, body: any): Observable<T> {
    return this.http
      .patch<T>(`${this.base}${path}`, body, { headers: this.headers() })
      .pipe(catchError(err => this.handleError(err)));
  }

  private put<T>(path: string, body: any): Observable<T> {
    return this.http
      .put<T>(`${this.base}${path}`, body, { headers: this.headers() })
      .pipe(catchError(err => this.handleError(err)));
  }

  private delete<T>(path: string): Observable<T> {
    return this.http
      .delete<T>(`${this.base}${path}`, { headers: this.headers() })
      .pipe(catchError(err => this.handleError(err)));
  }

  private handleError(err: HttpErrorResponse) {
    let message = 'Something went wrong. Please try again.';
    if (err.error && typeof err.error === 'object' && err.error.detail) {
      message = String(err.error.detail);
    } else if (err.status === 0) {
      message = 'Cannot reach the SchoolAssist backend. Is it running on port 8000?';
    }
    return throwError(() => new Error(message));
  }

  /* ---------------- plans / organization ---------------- */

  getPlans(): Observable<Plan[]> {
    return this.http.get<Plan[]>(`${this.base}/org/plans`)
      .pipe(catchError(err => this.handleError(err)));
  }

  getOrgOverview(): Observable<OrgOverview> {
    return this.get<OrgOverview>('/org/overview');
  }

  principalDashboard(): Observable<PrincipalDashboardData> {
    return this.get<PrincipalDashboardData>('/dashboard/principal');
  }

  principalSchoolOverview(): Observable<PrincipalSchoolOverviewData> {
    return this.get<PrincipalSchoolOverviewData>('/dashboard/principal/school-overview');
  }

  principalTeachers(): Observable<PrincipalTeachersData> {
    return this.get<PrincipalTeachersData>('/dashboard/principal/teachers');
  }
  principalAcademicMonitoring(): Observable<any> { return this.get<any>('/dashboard/principal/academic-monitoring'); }

  getMembers(): Observable<MemberInfo[]> {
    return this.get<MemberInfo[]>('/org/members');
  }

  createMember(data: { email: string; full_name: string; role: string; password?: string }): Observable<MemberInfo> {
    return this.post<MemberInfo>('/org/members', data);
  }

  updateMember(memberId: number, data: { role?: string; is_active?: boolean }): Observable<MemberInfo> {
    return this.patch<MemberInfo>(`/org/members/${memberId}`, data);
  }

  deactivateMember(memberId: number): Observable<any> {
    return this.delete<any>(`/org/members/${memberId}`);
  }

  getInvites(): Observable<InviteInfo[]> {
    return this.get<InviteInfo[]>('/org/invites');
  }

  createInvite(data: { email: string; full_name?: string; role?: string }): Observable<InviteInfo> {
    return this.post<InviteInfo>('/org/invites', data);
  }

  revokeInvite(inviteId: number): Observable<any> {
    return this.delete<any>(`/org/invites/${inviteId}`);
  }

  changePlan(planCode: string): Observable<any> {
    return this.post<any>('/org/subscription/change-plan', { plan_code: planCode });
  }

  getPayments(): Observable<PaymentInfo[]> {
    return this.get<PaymentInfo[]>('/org/payments');
  }

  /* ---------------- dashboards ---------------- */

  teacherDashboard(): Observable<any> {
    return this.get<any>('/dashboard/teacher');
  }

  adminDashboard(): Observable<OrgOverview> {
    return this.get<OrgOverview>('/dashboard/admin');
  }

  coordinatorDashboard(classId?: number): Observable<any> {
    return this.get<any>('/dashboard/coordinator', classId ? { class_id: classId } : undefined);
  }

  /* ---------------- academics ---------------- */

  getClasses(): Observable<ClassInfo[]> {
    return this.get<ClassInfo[]>('/academics/classes');
  }

  createClass(data: { name: string; grade_level?: number | null; capacity?: number | null }): Observable<ClassInfo> {
    return this.post<ClassInfo>('/academics/classes', data);
  }

  updateClass(classId: number, data: { name?: string; grade_level?: number | null; capacity?: number | null }): Observable<ClassInfo> {
    return this.patch<ClassInfo>(`/academics/classes/${classId}`, data);
  }

  deleteClass(classId: number): Observable<any> {
    return this.delete<any>(`/academics/classes/${classId}`);
  }

  createSection(data: { class_id: number; name: string; class_teacher_id?: number | null }): Observable<any> {
    return this.post<any>('/academics/sections', data);
  }

  updateSection(sectionId: number, data: { name?: string; class_teacher_id?: number | null }): Observable<any> {
    return this.patch<any>(`/academics/sections/${sectionId}`, data);
  }

  deleteSection(sectionId: number): Observable<any> {
    return this.delete<any>(`/academics/sections/${sectionId}`);
  }

  getSubjects(classId?: number): Observable<SubjectInfo[]> {
    return this.get<SubjectInfo[]>('/academics/subjects', classId ? { class_id: classId } : undefined);
  }

  getClassSubjectIds(classId: number): Observable<{ class_id: number; subject_ids: number[] }> {
    return this.get<{ class_id: number; subject_ids: number[] }>(`/academics/classes/${classId}/subjects`);
  }

  setClassSubjects(classId: number, subjectIds: number[]): Observable<{ class_id: number; subject_ids: number[] }> {
    return this.put<{ class_id: number; subject_ids: number[] }>(`/academics/classes/${classId}/subjects`, { subject_ids: subjectIds });
  }

  createSubject(data: { name: string; code?: string }): Observable<SubjectInfo> {
    return this.post<SubjectInfo>('/academics/subjects', data);
  }

  updateSubject(subjectId: number, data: { name?: string; code?: string | null }): Observable<SubjectInfo> {
    return this.patch<SubjectInfo>(`/academics/subjects/${subjectId}`, data);
  }

  deleteSubject(subjectId: number): Observable<any> {
    return this.delete<any>(`/academics/subjects/${subjectId}`);
  }

  getStudents(params: { class_id?: number | null; section_id?: number | null; search?: string; include_inactive?: boolean }): Observable<StudentInfo[]> {
    return this.get<StudentInfo[]>('/academics/students', params);
  }

  createStudent(data: {
    class_id: number; section_id?: number | null; roll_no: string; name: string;
    guardian_name?: string; guardian_phone?: string;
  }): Observable<any> {
    return this.post<any>('/academics/students', data);
  }

  deactivateStudent(studentId: number): Observable<any> {
    return this.delete<any>(`/academics/students/${studentId}`);
  }

  importStudents(file: File, classId: number): Observable<any> {
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('class_id', String(classId));
    return this.http
      .post(`${this.base}/academics/students/import`, form, { headers: this.headers() })
      .pipe(catchError(err => this.handleError(err)));
  }

  getAssignments(): Observable<AssignmentInfo[]> {
    return this.get<AssignmentInfo[]>('/academics/teacher-assignments');
  }

  createAssignment(data: {
    teacher_id: number; class_id: number; section_id?: number | null; subject_id: number; academic_year?: string;
  }): Observable<AssignmentInfo> {
    return this.post<AssignmentInfo>('/academics/teacher-assignments', data);
  }

  deleteAssignment(assignmentId: number): Observable<any> {
    return this.delete<any>(`/academics/teacher-assignments/${assignmentId}`);
  }

  getTeachers(): Observable<TeacherInfo[]> {
    return this.get<TeacherInfo[]>('/academics/teachers');
  }

  getStaff(): Observable<StaffInfo[]> {
    return this.get<StaffInfo[]>('/academics/teachers');
  }

  createTeacher(data: {
    full_name: string; email: string; phone?: string; role?: string; designation?: string;
    level?: string; qualification?: string; department?: string; gender?: string; joining_date?: string;
    subject_ids?: number[]; password?: string; send_email?: boolean;
  }): Observable<any> {
    return this.post<any>('/academics/teachers', data);
  }

  updateTeacher(userId: number, data: Record<string, any>): Observable<any> {
    return this.patch<any>(`/academics/teachers/${userId}`, data);
  }

  getTeacherProfile(userId: number): Observable<TeacherProfileInfo> {
    return this.get<TeacherProfileInfo>(`/academics/teachers/${userId}`);
  }

  setTeacherSubjects(userId: number, subjectIds: number[]): Observable<any> {
    return this.put<any>(`/academics/teachers/${userId}/subjects`, { subject_ids: subjectIds });
  }

  updateStudent(studentId: number, data: Record<string, any>): Observable<any> {
    return this.patch<any>(`/academics/students/${studentId}`, data);
  }

  getStudentProfile(studentId: number): Observable<StudentProfileInfo> {
    return this.get<StudentProfileInfo>(`/academics/students/${studentId}`);
  }

  getGuardians(): Observable<GuardianInfo[]> {
    return this.get<GuardianInfo[]>('/academics/guardians');
  }

  createGuardian(data: { full_name: string; phone?: string; email?: string }): Observable<GuardianInfo> {
    return this.post<GuardianInfo>('/academics/guardians', data);
  }

  updateGuardian(guardianId: number, data: { full_name?: string; phone?: string | null; email?: string | null }): Observable<GuardianInfo> {
    return this.patch<GuardianInfo>(`/academics/guardians/${guardianId}`, data);
  }

  deleteGuardian(guardianId: number): Observable<any> {
    return this.delete<any>(`/academics/guardians/${guardianId}`);
  }

  /* ---- own account (every logged-in user) ---- */

  updateMyProfile(data: { full_name?: string; phone?: string | null }): Observable<User> {
    return this.patch<User>('/auth/me', data);
  }

  changeMyPassword(data: { current_password: string; new_password: string }): Observable<any> {
    return this.post<any>('/auth/me/password', data);
  }

  linkGuardian(studentId: number, data: Record<string, any>): Observable<any> {
    return this.post<any>(`/academics/students/${studentId}/guardians`, data);
  }

  unlinkGuardian(studentId: number, guardianId: number): Observable<any> {
    return this.delete<any>(`/academics/students/${studentId}/guardians/${guardianId}`);
  }

  /* ---------------- attendance ---------------- */

  getStudentAttendanceSheet(classId: number, date: string, sectionId?: number): Observable<AttendanceSheet> {
    return this.get<AttendanceSheet>('/ops/attendance/students', { class_id: classId, date, section_id: sectionId });
  }

  saveStudentAttendance(data: { class_id: number; section_id?: number | null; date: string; entries: { student_id: number; status: string }[] }): Observable<any> {
    return this.post<any>('/ops/attendance/students', data);
  }

  getStudentAttendanceSummary(date?: string): Observable<AttendanceSummary> {
    return this.get<AttendanceSummary>('/ops/attendance/students/summary', date ? { date } : undefined);
  }

  getTeacherAttendance(date?: string, month?: string): Observable<TeacherAttendanceRow[]> {
    return this.get<TeacherAttendanceRow[]>('/ops/attendance/teachers', { date, month });
  }

  saveTeacherAttendance(data: { date: string; entries: { teacher_id: number; status: string; check_in?: string | null; check_out?: string | null }[] }): Observable<any> {
    return this.post<any>('/ops/attendance/teachers', data);
  }

  getTeacherAttendanceSummary(date?: string): Observable<AttendanceSummary> {
    return this.get<AttendanceSummary>('/ops/attendance/teachers/summary', date ? { date } : undefined);
  }

  /* ---------------- staff leaves ---------------- */

  getLeaves(status?: string): Observable<LeaveInfo[]> {
    return this.get<LeaveInfo[]>('/leaves', status ? { status } : undefined);
  }

  createLeave(data: { teacher_id?: number | null; start_date: string; end_date: string; reason: string }): Observable<LeaveInfo> {
    return this.post<LeaveInfo>('/leaves', data);
  }

  decideLeave(leaveId: number, data: { status: string; note?: string }): Observable<LeaveInfo> {
    return this.patch<LeaveInfo>(`/leaves/${leaveId}/decision`, data);
  }

  addLeaveSubstitution(leaveId: number, data: {
    date: string; class_id: number; subject_id?: number | null; substitute_teacher_id: number; note?: string;
  }): Observable<LeaveInfo> {
    return this.post<LeaveInfo>(`/leaves/${leaveId}/substitutions`, data);
  }

  removeLeaveSubstitution(substitutionId: number): Observable<LeaveInfo> {
    return this.delete<LeaveInfo>(`/leaves/substitutions/${substitutionId}`);
  }

  /* ---------------- timetable / exams / seating ---------------- */

  getTimetable(params: { class_id?: number; section_id?: number; teacher_id?: number }): Observable<TimetableEntryInfo[]> {
    return this.get<TimetableEntryInfo[]>('/ops/timetable', params);
  }

  createTimetableEntry(data: {
    class_id: number; section_id?: number | null; subject_id: number; teacher_id?: number | null;
    day: string; start_time: string; end_time: string;
  }): Observable<TimetableEntryInfo> {
    return this.post<TimetableEntryInfo>('/ops/timetable', data);
  }

  deleteTimetableEntry(entryId: number): Observable<any> {
    return this.delete<any>(`/ops/timetable/${entryId}`);
  }
  submitTimetable(classId: number): Observable<any> { return this.post<any>(`/ops/timetable/${classId}/submit`, {}); }
  approveTimetable(classId: number, comment?: string): Observable<any> { return this.post<any>(`/ops/timetable/${classId}/approve`, { comment }); }
  returnTimetable(classId: number, comment?: string): Observable<any> { return this.post<any>(`/ops/timetable/${classId}/return`, { comment }); }

  getExams(params: { class_id?: number; term?: string }): Observable<ExamInfo[]> {
    return this.get<ExamInfo[]>('/ops/exams', params);
  }

  saveExamSchedule(data: { term: string; class_id: number; papers: { subject_id: number; date: string; start_time: string; end_time: string }[] }): Observable<any> {
    return this.post<any>('/ops/exams', data);
  }

  deleteExam(examId: number): Observable<any> {
    return this.delete<any>(`/ops/exams/${examId}`);
  }

  getUpcomingExams(limit = 6): Observable<ExamInfo[]> {
    return this.get<ExamInfo[]>('/ops/exams/upcoming', { limit });
  }

  getExamRooms(): Observable<ExamRoomInfo[]> {
    return this.get<ExamRoomInfo[]>('/ops/exams/rooms');
  }

  createExamRoom(data: { name: string; capacity: number }): Observable<ExamRoomInfo> {
    return this.post<ExamRoomInfo>('/ops/exams/rooms', data);
  }

  updateExamRoom(roomId: number, data: { name?: string; capacity?: number }): Observable<ExamRoomInfo> {
    return this.patch<ExamRoomInfo>(`/ops/exams/rooms/${roomId}`, data);
  }

  deleteExamRoom(roomId: number): Observable<any> {
    return this.delete<any>(`/ops/exams/rooms/${roomId}`);
  }

  getSeating(term: string, classId?: number | null): Observable<SeatingInfo> {
    return this.get<SeatingInfo>('/ops/exams/seating', { term, class_id: classId });
  }

  previewSeating(
    classId?: number | null,
    classesPerRoom?: number | null,
    level?: string | null,
  ): Observable<SeatingPreview> {
    return this.get<SeatingPreview>('/ops/exams/seating/preview', {
      class_id: classId,
      level: level,
      classes_per_room: classesPerRoom,
    });
  }

  generateSeating(data: {
    term: string;
    class_id: number | null;
    level?: string | null;
    classes_per_room?: number | null;
  }): Observable<any> {
    return this.post<any>('/ops/exams/seating', data);
  }

  /** Class-wise seating plan PDF for the saved plan of a term. */
  downloadSeatingPdf(term: string, classId?: number | null): void {
    let path = `/ops/exams/seating/pdf?term=${encodeURIComponent(term)}`;
    let filename = `seating-plan-${term.trim().replace(/\s+/g, '-').toLowerCase()}`;
    if (classId) {
      path += `&class_id=${classId}`;
      filename += `-class-${classId}`;
    }
    this.downloadFile(path, `${filename}.pdf`);
  }

  /* ---------------- announcements / settings ---------------- */

  getAnnouncements(classId?: number | null): Observable<AnnouncementInfo[]> {
    return this.get<AnnouncementInfo[]>('/school/announcements', classId ? { class_id: classId } : undefined);
  }

  createAnnouncement(data: {
    title: string; message: string;
    audience?: string;
    target_audience?: string;
    priority?: string;
    class_id?: number | null;
    section_id?: number | null;
    is_pinned?: boolean;
  }): Observable<AnnouncementInfo> {
    const audience = data.audience || data.target_audience || 'school';
    return this.post<AnnouncementInfo>('/school/announcements', {
      title: data.title,
      message: data.message,
      audience,
      class_id: data.class_id,
      section_id: data.section_id,
    });
  }

  deleteAnnouncement(id: number): Observable<any> {
    return this.delete<any>(`/school/announcements/${id}`);
  }

  getSchoolSettings(): Observable<SchoolSettingsInfo> {
    return this.get<SchoolSettingsInfo>('/school/settings');
  }

  updateSchoolSettings(data: Record<string, any>): Observable<SchoolSettingsInfo> {
    return this.put<SchoolSettingsInfo>('/school/settings', data);
  }

  updateOrgProfile(data: { name?: string; city?: string; phone?: string }): Observable<any> {
    return this.patch<any>('/org/profile', data);
  }

  getAdminSummary(): Observable<AdminSummary> {
    return this.get<AdminSummary>('/reports/admin-summary');
  }

  /* ---------------- worksheets ---------------- */

  generateWorksheet(data: {
    class_id: number; section_id?: number | null; subject_id: number; topic: string;
    title?: string; instructions?: string; difficulty: string; language: string;
    question_counts: QuestionCounts;
  }): Observable<WorksheetInfo> {
    return this.post<WorksheetInfo>('/worksheets/generate', data);
  }

  getWorksheets(params?: { class_id?: number; subject_id?: number }): Observable<WorksheetInfo[]> {
    return this.get<WorksheetInfo[]>('/worksheets', params);
  }

  getWorksheet(id: number): Observable<WorksheetInfo> {
    return this.get<WorksheetInfo>(`/worksheets/${id}`);
  }

  deleteWorksheet(id: number): Observable<any> {
    return this.delete<any>(`/worksheets/${id}`);
  }

  /* ---------------- tests ---------------- */

  generateTest(data: {
    class_id: number; section_id?: number | null; subject_id: number; test_type: string;
    topic?: string; title?: string; total_marks: number; duration_minutes?: number;
    instructions?: string; difficulty: string; language: string;
    question_counts: QuestionCounts;
  }): Observable<TestInfo> {
    return this.post<TestInfo>('/tests/generate', data);
  }

  getTests(params?: { class_id?: number; subject_id?: number; test_type?: string }): Observable<TestInfo[]> {
    return this.get<TestInfo[]>('/tests', params);
  }

  getTest(id: number): Observable<TestInfo> {
    return this.get<TestInfo>(`/tests/${id}`);
  }

  deleteTest(id: number): Observable<any> {
    return this.delete<any>(`/tests/${id}`);
  }

  /* ---------------- marksheets ---------------- */

  uploadMarksheet(form: FormData): Observable<any> {
    return this.http
      .post(`${this.base}/marksheets/upload`, form, { headers: this.headers() })
      .pipe(catchError(err => this.handleError(err)));
  }

  getMarksheets(params?: { class_id?: number; subject_id?: number }): Observable<MarksheetInfo[]> {
    return this.get<MarksheetInfo[]>('/marksheets', params);
  }

  getMarksheet(id: number): Observable<MarksheetInfo> {
    return this.get<MarksheetInfo>(`/marksheets/${id}`);
  }

  deleteMarksheet(id: number): Observable<any> {
    return this.delete<any>(`/marksheets/${id}`);
  }

  /* ---------------- reports ---------------- */

  getStudentReport(studentId: number): Observable<StudentReport> {
    return this.get<StudentReport>(`/reports/students/${studentId}`);
  }

  getSubjectReport(classId: number, subjectId: number): Observable<SubjectReport> {
    return this.get<SubjectReport>('/reports/subject', { class_id: classId, subject_id: subjectId });
  }

  getClassPerformance(classId: number): Observable<ClassReport> {
    return this.get<ClassReport>('/reports/class-performance', { class_id: classId });
  }

  getWeakStudents(params: { class_id: number; subject_id?: number; threshold?: number }): Observable<WeakStudentsResult> {
    return this.get<WeakStudentsResult>('/reports/weak-students', params);
  }

  createFinalTermReport(data: FinalTermReportRequestData): Observable<ReportInfo> {
    return this.post<ReportInfo>('/reports/final-term', data);
  }

  getReports(params?: { report_type?: string; class_id?: number }): Observable<ReportInfo[]> {
    return this.get<ReportInfo[]>('/reports', params);
  }

  getReport(id: number): Observable<ReportInfo> {
    return this.get<ReportInfo>(`/reports/${id}`);
  }

  /* ---------------- AI chat ---------------- */

  sendChat(data: ChatRequestData): Observable<ChatResponse> {
    return this.post<ChatResponse>('/chat', data);
  }

  /* ---------------- exports (authorized download) ---------------- */

  downloadFile(path: string, filename: string): void {
    this.http.get(`${this.base}${path}`, { headers: this.headers(), responseType: 'blob' })
      .subscribe({
        next: (blob: Blob) => {
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = filename;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(url);
        },
        error: () => alert('Download failed. Please try again.'),
      });
  }
}
