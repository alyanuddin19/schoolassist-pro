import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { authGuard, ownerHomeGuard, roleGuard } from './core/guards';
import { LoginComponent } from './components/login/login.component';
import { SignupComponent } from './components/signup/signup.component';
import { InviteComponent } from './components/invite/invite.component';
import { MainLayoutComponent } from './layout/main-layout/main-layout.component';
import { TeacherDashboardComponent } from './pages/teacher-dashboard/teacher-dashboard.component';
import { AdminDashboardComponent } from './pages/admin-dashboard/admin-dashboard.component';
import { SchoolSettingsComponent } from './pages/school-settings/school-settings.component';
import { TimetableComponent } from './pages/timetable/timetable.component';
import { TeacherAttendanceComponent } from './pages/teacher-attendance/teacher-attendance.component';
import { StudentAttendanceComponent } from './pages/student-attendance/student-attendance.component';
import { ExamsResultsComponent } from './pages/exams-results/exams-results.component';
import { AnnouncementsComponent } from './pages/announcements/announcements.component';
import { CoordinatorDashboardComponent } from './pages/coordinator-dashboard/coordinator-dashboard.component';
import { SetupComponent } from './pages/setup/setup.component';
import { WorksheetsComponent } from './pages/worksheets/worksheets.component';
import { TestsComponent } from './pages/tests/tests.component';
import { MarksheetsComponent } from './pages/marksheets/marksheets.component';
import { ReportsComponent } from './pages/reports/reports.component';
import { AccountSettingsComponent } from './pages/account-settings/account-settings.component';
import { LeadershipComponent } from './pages/leadership/leadership.component';
import { SchoolOverviewComponent } from './pages/school-overview/school-overview.component';
import { PrincipalTeachersComponent } from './pages/principal-teachers/principal-teachers.component';
import { AcademicMonitoringComponent } from './pages/academic-monitoring/academic-monitoring.component';
import { LeavesComponent } from './pages/leaves/leaves.component';

const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: 'signup', component: SignupComponent },
  { path: 'invite', component: InviteComponent },
  {
    path: '',
    component: MainLayoutComponent,
    canActivate: [authGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      { path: 'dashboard', component: TeacherDashboardComponent, canActivate: [ownerHomeGuard] },
      { path: 'account', component: AccountSettingsComponent },
      {
        path: 'admin',
        canActivate: [roleGuard(['org_admin'])],
        children: [
          { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
          { path: 'dashboard', component: AdminDashboardComponent },
          { path: 'teachers', component: AdminDashboardComponent, data: { tab: 'staff' } },
          { path: 'students', component: SetupComponent, data: { tab: 'students' } },
          { path: 'classes', component: SetupComponent, data: { tab: 'classes' } },
          { path: 'subjects', component: SetupComponent, data: { tab: 'subjects' } },
          { path: 'assignments', component: SetupComponent, data: { tab: 'assignments' } },
          { path: 'timetable', component: TimetableComponent },
          { path: 'teacher-attendance', component: TeacherAttendanceComponent },
          { path: 'exams-results', redirectTo: 'exam-management', pathMatch: 'full' },
          { path: 'exam-management', component: ExamsResultsComponent },
          { path: 'announcements', component: AnnouncementsComponent },
          { path: 'reports', component: ReportsComponent },
          { path: 'settings', component: SchoolSettingsComponent },
        ],
      },
      {
        path: 'coordinator',
        component: CoordinatorDashboardComponent,
        canActivate: [roleGuard(['org_admin', 'principal', 'subject_coordinator'])],
      },
      {
        path: 'leadership',
        component: LeadershipComponent,
        canActivate: [roleGuard(['org_admin', 'principal', 'vice_principal'])],
      },
      { path: 'leadership/teachers', component: PrincipalTeachersComponent, canActivate: [roleGuard(['principal'])] },
      { path: 'leadership/academic-monitoring', component: AcademicMonitoringComponent, canActivate: [roleGuard(['principal'])] },
      { path: 'school-overview', component: SchoolOverviewComponent, canActivate: [roleGuard(['principal'])] },
      { path: 'leaves', component: LeavesComponent, canActivate: [authGuard] },
      {
        path: 'teacher-attendance',
        component: TeacherAttendanceComponent,
        canActivate: [roleGuard(['org_admin', 'principal', 'vice_principal'])],
      },
      {
        path: 'exams',
        component: ExamsResultsComponent,
        canActivate: [roleGuard(['org_admin', 'principal', 'vice_principal'])],
      },
      { path: 'timetable', component: TimetableComponent },
      { path: 'attendance', component: StudentAttendanceComponent },
      { path: 'announcements', component: AnnouncementsComponent },
      { path: 'setup', component: SetupComponent },
      { path: 'worksheets', component: WorksheetsComponent },
      { path: 'tests', component: TestsComponent },
      { path: 'marksheets', component: MarksheetsComponent },
      {
        path: 'reports',
        component: ReportsComponent,
        canActivate: [roleGuard(['org_admin', 'principal', 'vice_principal', 'subject_coordinator'])],
      },
    ],
  },
  { path: '**', redirectTo: 'login' },
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule],
})
export class AppRoutingModule {}
