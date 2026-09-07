import { Component, HostListener, OnDestroy, OnInit } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { AuthService } from '../../core/auth.service';
import { AiAssistantService } from '../../core/ai-assistant.service';

interface NavItem {
  label: string;
  icon: string;
  route: string;
  queryParams?: Record<string, string>;
  roles?: string[]; // undefined = all roles
}

@Component({
  selector: 'app-main-layout',
  templateUrl: './main-layout.component.html',
  styleUrls: ['./main-layout.component.css'],
})
export class MainLayoutComponent implements OnInit, OnDestroy {
  sidebarOpen = true;
  isMobileView = false;
  currentPageLabel = '';
  menuOpen = false;

  navItems: NavItem[] = [
    { label: 'Dashboard', icon: 'dashboard', route: '/dashboard' },
    {
      label: 'Coordinator Dashboard', icon: 'dashboard', route: '/coordinator',
      roles: ['org_admin', 'principal', 'subject_coordinator'],
    },
    { label: 'School Admin', icon: 'school', route: '/admin', roles: ['org_admin'] },
    { label: 'Student Attendance', icon: 'attendance', route: '/attendance' },
    { label: 'Timetable', icon: 'calendar', route: '/timetable' },
    { label: 'Announcements', icon: 'announcement', route: '/announcements' },
    { label: 'Class & Student Setup', icon: 'settings', route: '/setup' },
    { label: 'Worksheets', icon: 'document', route: '/worksheets' },
    { label: 'Tests & Papers', icon: 'document', route: '/tests' },
    { label: 'Marksheets', icon: 'document', route: '/marksheets' },
    { label: 'Reports', icon: 'reports', route: '/reports' },
  ];

  adminNavItems: NavItem[] = [
    { label: 'Dashboard', icon: 'dashboard', route: '/admin/dashboard' },
    { label: 'Teachers', icon: 'teachers', route: '/admin/teachers' },
    { label: 'Students', icon: 'students', route: '/admin/students' },
    { label: 'Classes & Sections', icon: 'school', route: '/admin/classes' },
    { label: 'Subjects', icon: 'subjects', route: '/admin/subjects' },
    { label: 'Teacher Assignments', icon: 'assignment', route: '/admin/assignments' },
    { label: 'Timetable', icon: 'calendar', route: '/admin/timetable' },
    { label: 'Teacher Attendance', icon: 'attendance', route: '/admin/teacher-attendance' },
    { label: 'Exam Management', icon: 'document', route: '/admin/exam-management' },
    { label: 'Announcements', icon: 'announcement', route: '/admin/announcements' },
    { label: 'Reports', icon: 'reports', route: '/admin/reports' },
    { label: 'Settings', icon: 'settings', route: '/admin/settings' },
  ];

  /** Principal's desk: monitoring and approvals, not setup chores. */
  principalNavItems: NavItem[] = [
    { label: 'Dashboard', icon: 'dashboard', route: '/leadership' },
    { label: 'School Overview', icon: 'school', route: '/school-overview' },
    { label: 'Teachers', icon: 'teachers', route: '/leadership/teachers' },
    { label: 'Academic Monitoring', icon: 'reports', route: '/leadership/academic-monitoring' },
    { label: 'Timetable', icon: 'calendar', route: '/timetable' },
    { label: 'Exams', icon: 'document', route: '/exams' },
    { label: 'Leave Approvals', icon: 'announcement', route: '/leaves' },
    { label: 'Reports', icon: 'reports', route: '/reports' },
    { label: 'Announcements', icon: 'announcement', route: '/announcements' },
  ];

  /** Vice principal's desk: day-to-day operations and substitute planning. */
  vicePrincipalNavItems: NavItem[] = [
    { label: 'Dashboard', icon: 'dashboard', route: '/leadership' },
    { label: 'Teacher Attendance', icon: 'attendance', route: '/teacher-attendance' },
    { label: 'Leave & Substitution', icon: 'announcement', route: '/leaves' },
    { label: 'Teacher Allocation', icon: 'assignment', route: '/leadership', queryParams: { tab: 'allocation' } },
    { label: 'Timetable', icon: 'calendar', route: '/timetable' },
    { label: 'Class Overview', icon: 'school', route: '/leadership', queryParams: { tab: 'classes' } },
    { label: 'Exams', icon: 'document', route: '/exams' },
    { label: 'Daily Operations', icon: 'settings', route: '/leadership', queryParams: { tab: 'daily' } },
    { label: 'Reports', icon: 'reports', route: '/reports' },
    { label: 'Announcements', icon: 'announcement', route: '/announcements' },
  ];

  private routerSubscription: Subscription | null = null;

  constructor(public auth: AuthService, private router: Router, private ai: AiAssistantService) {}

  ngOnInit(): void {
    this.syncViewportState();
    this.updateCurrentPageLabel();
    this.routerSubscription = this.router.events.subscribe(event => {
      if (event instanceof NavigationEnd) {
        this.updateCurrentPageLabel();
        this.menuOpen = false;
        this.closeSidebar();
      }
    });
  }

  ngOnDestroy(): void {
    this.routerSubscription?.unsubscribe();
  }

  get visibleNavItems(): NavItem[] {
    if (this.auth.role === 'org_admin') {
      return this.adminNavItems;
    }
    if (this.auth.role === 'principal' && !this.auth.isIndividual) {
      return this.principalNavItems;
    }
    if (this.auth.role === 'vice_principal' && !this.auth.isIndividual) {
      return this.vicePrincipalNavItems;
    }
    return this.navItems.filter(item => !item.roles || item.roles.includes(this.auth.role));
  }

  get initials(): string {
    const name = (this.auth.user?.full_name || 'Teacher').trim();
    const parts = name.split(/\s+/).filter(Boolean);
    if (parts.length === 0) {
      return 'T';
    }
    if (parts.length === 1) {
      return parts[0].slice(0, 2).toUpperCase();
    }
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  get roleLabel(): string {
    const labels: Record<string, string> = {
      org_admin: 'School Owner',
      principal: 'Principal',
      vice_principal: 'Vice Principal',
      subject_coordinator: 'Subject Coordinator',
      teacher: 'Teacher',
    };
    return labels[this.auth.role] || this.auth.role;
  }

  toggleSidebar(): void {
    this.sidebarOpen = !this.sidebarOpen;
  }

  closeSidebar(): void {
    if (this.isMobileView) {
      this.sidebarOpen = false;
    }
  }

  openAssistant(): void {
    this.ai.open();
    this.closeSidebar();
  }

  askAssistant(): void {
    this.ai.open();
  }

  switchOrganization(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const orgId = Number(select.value);
    if (orgId && orgId !== this.auth.activeOrganizationId) {
      this.auth.switchOrganization(orgId);
    }
  }

  logout(): void {
    this.menuOpen = false;
    this.auth.logout();
    this.router.navigate(['/login']);
  }

  openAccountSettings(): void {
    this.menuOpen = false;
    this.router.navigate(['/account']);
  }

  @HostListener('window:resize')
  onWindowResize(): void {
    this.syncViewportState();
  }

  private syncViewportState(): void {
    this.isMobileView = window.innerWidth <= 960;
    this.sidebarOpen = !this.isMobileView;
  }

  private updateCurrentPageLabel(): void {
    const url = this.router.url.split('?')[0] || '';
    if (url === '/account') {
      this.currentPageLabel = 'Account Settings';
      return;
    }
    const source = this.visibleNavItems;
    const tab = this.router.parseUrl(this.router.url).queryParams['tab'];
    const match =
      source.find(
        item => item.route === url && (item.queryParams?.['tab'] || null) === (tab || null),
      ) || source.find(item => item.route === url);
    this.currentPageLabel = match ? match.label : 'Dashboard';
  }
}
