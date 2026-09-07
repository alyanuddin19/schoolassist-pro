import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { MainLayoutComponent } from './layout/main-layout/main-layout.component';
import { LoginComponent } from './components/login/login.component';
import { SignupComponent } from './components/signup/signup.component';
import { InviteComponent } from './components/invite/invite.component';
import { AuthShellComponent } from './components/auth-shell/auth-shell.component';
import { AiAssistantComponent } from './components/ai-assistant/ai-assistant.component';
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

@NgModule({
  declarations: [
    AppComponent,
    MainLayoutComponent,
    LoginComponent,
    SignupComponent,
    InviteComponent,
    AuthShellComponent,
    AiAssistantComponent,
    TeacherDashboardComponent,
    AdminDashboardComponent,
    SchoolSettingsComponent,
    TimetableComponent,
    TeacherAttendanceComponent,
    StudentAttendanceComponent,
    ExamsResultsComponent,
    AnnouncementsComponent,
    CoordinatorDashboardComponent,
    SetupComponent,
    WorksheetsComponent,
    TestsComponent,
    MarksheetsComponent,
    ReportsComponent,
    AccountSettingsComponent,
    LeadershipComponent,
    SchoolOverviewComponent,
    PrincipalTeachersComponent,
    AcademicMonitoringComponent,
    LeavesComponent,
  ],
  imports: [
    BrowserModule,
    FormsModule,
    HttpClientModule,
    AppRoutingModule,
  ],
  bootstrap: [AppComponent],
})
export class AppModule {}
