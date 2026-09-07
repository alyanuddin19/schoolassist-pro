/* Shared API models for SchoolAssist frontend. */

export type Role = 'org_admin' | 'principal' | 'vice_principal' | 'subject_coordinator' | 'teacher';

export interface User {
  id: number;
  email: string;
  full_name: string;
  phone?: string | null;
  is_active: boolean;
}

export interface Membership {
  organization_id: number;
  organization_name: string;
  organization_type: 'school' | 'individual' | string;
  role: Role | string;
}

export interface AuthResponse {
  access_token: string;
  user: User;
  memberships: Membership[];
  default_organization_id: number;
}

export interface Plan {
  id: number;
  code: string;
  name: string;
  teacher_seats: number;
  price_pkr: number;
  currency: string;
  billing_period: string;
  features?: string[] | null;
}

export interface SeatUsage {
  applies: boolean;
  seats_total: number;
  seats_used: number;
  seats_remaining: number;
  student_seats_total?: number | null;
  student_seats_used?: number;
  plan_code?: string | null;
  plan_name?: string | null;
  payment_provider?: string | null;
  payment_status?: string | null;
}

export interface OrgOverview {
  organization: { id: number; name: string; type: string; city?: string | null; created_at?: string | null };
  role: string;
  seats: SeatUsage;
  counts: Record<string, number>;
  role_counts?: Record<string, number>;
  active_members?: number;
  headcount?: { students: number; teachers: number; classes: number; staff: number };
  attendance_today?: {
    date: string;
    students: { present: number; absent: number; leave: number; late: number; marked: number };
    teachers: { present: number; absent: number; leave: number; late: number; marked: number };
  };
  upcoming_exams?: { id: number; term: string; class: string; subject: string; date: string; start_time: string; end_time: string }[];
}

export interface SectionInfo {
  id: number;
  name: string;
  class_id: number;
  class_teacher_id?: number | null;
  class_teacher?: string | null;
  /** Active students enrolled in this section. */
  students?: number;
}

export interface ClassInfo {
  id: number;
  name: string;
  grade_level?: number | null;
  level?: 'primary' | 'secondary' | null;
  capacity?: number | null;
  students: number;
  sections: SectionInfo[];
}

export interface SubjectInfo { id: number; name: string; code?: string | null; }

export interface StudentInfo {
  id: number;
  name: string;
  roll_no: string;
  class_id: number;
  class: string;
  section_id?: number | null;
  section?: string | null;
  guardian_name?: string | null;
  guardian_phone?: string | null;
  is_active?: boolean;
}

export interface TeacherInfo { id: number; name: string; email: string; role: string; is_active?: boolean; }

export interface StaffInfo {
  id: number;
  name: string;
  email: string;
  phone?: string | null;
  role: string;
  is_active: boolean;
  member_id: number;
  employee_id?: string | null;
  designation?: string | null;
  /** primary = classes 1-5, secondary = 6-10, null = teaches both. */
  level?: 'primary' | 'secondary' | null;
  department?: string | null;
  qualification?: string | null;
  gender?: string | null;
  status?: string | null;
  subject_ids: number[];
}

export interface TeacherProfileInfo extends StaffInfo {
  user_id: number;
  full_name: string;
  joining_date?: string | null;
  assignments: AssignmentInfo[];
}

export interface GuardianInfo {
  id: number;
  full_name: string;
  phone?: string | null;
  email?: string | null;
  children: { id: number; name: string; relationship?: string | null }[];
}

export interface StudentProfileInfo {
  id: number;
  name: string;
  roll_no: string;
  class_id: number;
  class: string;
  section_id?: number | null;
  section?: string | null;
  is_active: boolean;
  guardian_name?: string | null;
  guardian_phone?: string | null;
  guardians: { id: number; full_name: string; phone?: string | null; email?: string | null; relationship?: string | null }[];
  attendance: { present: number; absent: number; leave: number; late: number };
  results: { title: string; subject: string; obtained: number; total: number; remarks?: string | null }[];
}

export interface AttendanceEntry { student_id: number; name: string; roll_no: string; status: string; }

export interface AttendanceSheet { date: string; saved: boolean; entries: AttendanceEntry[]; }

export interface AttendanceSummary {
  date: string;
  present: number; absent: number; leave: number; late: number;
  marked: number;
  total_students?: number;
  total_teachers?: number;
  percent?: number | null;
}

export interface TeacherAttendanceRow {
  id: number; teacher_id: number; teacher: string; date: string;
  status: string; check_in?: string | null; check_out?: string | null;
}

export interface LeaveSubstitutionInfo {
  id: number;
  date: string;
  class_id: number;
  class: string;
  subject_id?: number | null;
  subject?: string | null;
  substitute_teacher_id: number;
  substitute: string;
  note?: string | null;
}

export interface LeaveInfo {
  id: number;
  teacher_id: number;
  teacher: string;
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  status: 'pending_vp_review' | 'pending_principal_approval' | 'approved' | 'rejected';
  requested_by?: string | null;
  decided_by?: string | null;
  decided_at?: string | null;
  decision_note?: string | null;
  created_at?: string | null;
  substitutions: LeaveSubstitutionInfo[];
}

export interface TimetableEntryInfo {
  id: number;
  class_id: number; class: string;
  section_id?: number | null; section?: string | null;
  subject_id: number; subject: string;
  teacher_id?: number | null; teacher?: string | null;
  day: string; start_time: string; end_time: string;
}

export interface ExamInfo {
  id: number; term: string;
  class_id: number; class: string;
  subject_id: number; subject: string;
  date: string; day: string; start_time: string; end_time: string;
}

export interface ExamRoomInfo { id: number; name: string; capacity: number; }

export interface SeatingRoomClass {
  class: string;
  students: number;
  roll_from: string;
  roll_to: string;
}

export interface SeatingRoomSummary {
  room: string;
  capacity: number;
  total: number;
  classes: SeatingRoomClass[];
}

export interface SeatingInfo {
  plan: {
    id: number;
    term: string;
    class_id: number | null;
    level?: string | null;
    classes_per_room?: number | null;
  } | null;
  rows: { student_id: number; student: string; roll_no: string; class?: string; room: string; seat_no: number }[];
  rooms?: SeatingRoomSummary[];
}

/** Room-wise allocation before anything is saved. */
export interface SeatingPreview {
  rooms: SeatingRoomSummary[];
  students: number;
  capacity: number;
  unseated: number;
}

export interface AnnouncementInfo {
  id: number; title: string; message: string;
  audience?: string;
  target_audience?: string;
  priority?: string;
  class_id?: number | null;
  class?: string | null;
  class_name?: string | null;
  section_id?: number | null;
  is_pinned?: boolean;
  is_active?: boolean;
  created_by_id?: number | null;
  created_by_name?: string | null;
  created_at?: string | null;
  published_at?: string | null;
}

export interface SchoolSettingsInfo {
  academic_year?: string | null;
  working_days: string[];
  school_start_time?: string | null;
  school_end_time?: string | null;
  period_minutes?: number | null;
  logo?: string | null;
  school_name?: string | null;
  city?: string | null;
  phone?: string | null;
}

export interface PrincipalDashboardData {
  students: number; teachers: number; classes: number; sections: number; subjects: number; exam_rooms: number;
  attendance_today: { present: number; late: number; absent: number; on_leave: number; marked: number; alerts: { teacher: string; status: string }[] };
  pending_approvals: { type: string; title: string; description: string; submitted_by: string; status: string; date?: string | null; route: string }[];
  academic_status: { teacher_allocation_complete: number; total_classes: number; timetable_completion_percentage: number; unassigned_subjects: number; timetable_conflicts: number; alerts: string[] };
  upcoming_exams: { term: string; start_date: string; classes: number; timetable_status: string; rooms_status: string; seating_status: string }[];
  recent_announcements: { id: number; title: string; audience: string; message: string; published_at?: string | null }[];
}

export interface PrincipalSchoolOverviewData {
  summary: { students: number; teachers: number; classes: number; sections: number; subjects: number; departments: number };
  academic_levels: { level: string; classes: number; sections: number; students: number }[];
  class_overview: { id: number; name: string; academic_level: string; sections: number; students: number; class_teacher?: string | null; subjects: number; capacity?: number | null; usage?: number | null; capacity_status: string }[];
  capacity: { total: number; enrolled: number; available: number; full_classes: number; near_capacity: number; alerts: string[] };
  teacher_distribution: { name: string; teachers: number }[]; teachers_without_assignment: number;
  student_distribution: { level: string; students: number }[];
  academic_setup: { subject_setup_complete: number; teacher_allocation_complete: number; total_classes: number; unassigned_subjects: number; sections_without_teacher: number; alerts: string[] };
  exam_infrastructure: { rooms: number; capacity: number; upcoming_term?: string | null; seating_status: string };
  school_info: { name: string; academic_year?: string | null; principal?: string | null; vice_principal?: string | null; school_type: string; departments: number };
}

export interface PrincipalTeachersData {
  summary: { total: number; active: number; on_leave: number; unassigned: number };
  teachers: { id: number; name: string; employee_id: string; email: string; phone?: string | null; qualification?: string | null; department: string; designation: string; subjects: string[]; classes: string[]; academic_year?: string | null; weekly_workload: number; attendance_percentage?: number | null; attendance_marked: number; leave_count: number; status: string; assignment_status: string }[];
  departments: string[]; subjects: string[]; classes: string[];
}

export interface AdminSummary {
  enrollment: { total: number; active: number; inactive: number };
  class_wise: { class_id: number; class: string; students: number; sections: Record<string, number> }[];
  teachers: { name: string; role: string; designation?: string | null; department?: string | null; subjects: string[]; is_active: boolean }[];
  attendance: { date: string; present: number; absent: number; leave: number; late: number; marked: number }[];
  exam_schedule: { term: string; class: string; subject: string; date: string; start_time: string; end_time: string }[];
  distribution: { class: string; section: string; students: number }[];
}

export interface AssignmentInfo {
  id: number;
  teacher_id: number;
  teacher_name: string;
  class_id: number;
  class: string;
  section_id?: number | null;
  section?: string | null;
  subject_id: number;
  subject: string;
  academic_year?: string | null;
}

export interface MemberInfo {
  id: number;
  user_id: number;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  joined_at?: string | null;
  temporary_password?: string;
}

export interface InviteInfo {
  id: number;
  email: string;
  full_name?: string | null;
  role: string;
  status: string;
  invite_code: string;
  created_at?: string | null;
}

export interface PaymentInfo {
  id: number;
  amount_pkr: number;
  provider: string;
  status: string;
  description?: string | null;
  created_at?: string | null;
}

export interface QuestionCounts { mcq: number; short: number; long: number; }

export interface WorksheetInfo {
  id: number;
  title: string;
  topic?: string | null;
  class: string;
  class_id: number;
  section?: string | null;
  subject: string;
  subject_id: number;
  difficulty?: string | null;
  language?: string;
  content?: string | null;
  answer_key?: string | null;
  marking_scheme?: string | null;
  created_by?: string;
  created_at?: string | null;
}

export interface TestInfo {
  id: number;
  title: string;
  test_type: string;
  topic?: string | null;
  class: string;
  class_id: number;
  section?: string | null;
  subject: string;
  subject_id: number;
  total_marks?: number | null;
  duration_minutes?: number | null;
  language?: string;
  content?: string | null;
  answer_key?: string | null;
  marking_scheme?: string | null;
  created_by?: string;
  created_at?: string | null;
}

export interface StatsInfo {
  count: number;
  average: number;
  highest: number;
  lowest: number;
  pass_rate: number;
  average_percent: number;
}

export interface MarksheetEntryInfo {
  student_id: number;
  roll_no: string;
  name: string;
  obtained_marks: number;
  total_marks: number;
  percent: number;
  grade: string;
  remarks?: string | null;
}

export interface MarksheetInfo {
  id: number;
  title: string;
  class: string;
  class_id: number;
  section?: string | null;
  subject: string;
  subject_id: number;
  test_id?: number | null;
  exam_type?: string | null;
  total_marks: number;
  source_file_name?: string | null;
  created_at?: string | null;
  stats?: StatsInfo;
  entries?: MarksheetEntryInfo[];
}

export interface SubjectReportRow {
  marksheet_id: number;
  title: string;
  exam_type?: string | null;
  total_marks: number;
  created_at?: string | null;
  stats: StatsInfo;
  weak_students: { student_id: number; student_name: string; roll_no: string; percent: number }[];
}

export interface SubjectReport {
  marksheets: SubjectReportRow[];
}

export interface ClassSubjectStat {
  subject_id: number;
  subject_name: string;
  marksheets: number;
  stats: StatsInfo;
}

export interface ClassReport { subjects: ClassSubjectStat[]; }

export interface WeakStudentsResult {
  threshold_percent: number;
  students: { student_id: number; student_name: string; roll_no: string; average_percent: number; grade: string; assessments: number }[];
}

export interface StudentSubjectRow {
  subject_id: number;
  subject_name: string;
  assessments: number;
  average_percent: number;
  latest_percent: number;
  grade: string;
}

export interface StudentReport {
  student: { id: number; name: string; roll_no: string; class: string; section?: string | null };
  subjects: StudentSubjectRow[];
  overall_percent: number;
  overall_grade: string;
  assessment_count: number;
}

export interface FinalTermStudentRow {
  student_id: number;
  name: string;
  roll_no: string;
  section: string;
  subjects: Record<string, number | null>;
  overall_percent: number;
  grade: string;
  status: string;
}

export interface FinalTermContent {
  class: string;
  subject_order: string[];
  students: FinalTermStudentRow[];
  subject_stats: { subject: string; average: number; highest: number; lowest: number }[];
  class_average: number;
  pass_percent: number;
  marksheets_included: number;
}

export interface FinalTermReportRequestData {
  class_id: number;
  section_id?: number | null;
  title?: string;
  academic_year?: string;
}

export interface ReportInfo {
  id: number;
  report_type: string;
  title: string;
  class?: string | null;
  class_id?: number | null;
  student_id?: number | null;
  academic_year?: string | null;
  content?: FinalTermContent | any;
  created_at?: string | null;
}

/* ---------- AI chat ---------- */

export interface ChatHistoryItem { role: 'user' | 'assistant'; content: string; }

export interface ActionDisplay {
  type: string;         // table | stats | generated | route | message
  title?: string;
  text?: string;
  columns?: string[];
  rows?: Record<string, any>[];
  stats?: { label: string; value: any }[];
  route?: string;
  kind?: string;
}

export interface ChatActionInfo { name: string; params?: Record<string, any> | null; }

export interface ChatResponse {
  session_id: number;
  reply: string;
  action?: ChatActionInfo | null;
  action_status?: string | null;
  action_result?: { display?: ActionDisplay; error?: string; [key: string]: any } | null;
}

export interface ChatUiMessage {
  role: 'user' | 'assistant';
  content: string;
  action?: ChatActionInfo | null;
  actionStatus?: string | null;
  display?: ActionDisplay | null;
  errorText?: string | null;
  imagePreview?: string | null;
  pending?: boolean;
}

export interface TeacherDashboardData {
  user: { name: string; role: string };
  organization: { name: string; type: string };
  stats: Record<string, number>;
  assignments: { id: number; class: string; subject: string; academic_year?: string | null }[];
  recent_worksheets: { id: number; title: string; class: string; subject: string; created_at?: string | null }[];
  recent_tests: { id: number; title: string; test_type: string; class: string; subject: string; total_marks?: number | null; created_at?: string | null }[];
  recent_marksheets: { id: number; title: string; class: string; subject: string; created_at?: string | null }[];
}
