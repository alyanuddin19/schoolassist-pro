import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { PrincipalSchoolOverviewData } from '../../core/models';

@Component({ selector: 'app-school-overview', templateUrl: './school-overview.component.html', styleUrls: ['./school-overview.component.css'] })
export class SchoolOverviewComponent implements OnInit {
  data: PrincipalSchoolOverviewData | null = null; loading = true; error = ''; level = '';
  constructor(private api: ApiService) {}
  ngOnInit(): void { this.load(); }
  load(): void { this.loading = true; this.error = ''; this.api.principalSchoolOverview().subscribe({ next: data => { this.data = data; this.loading = false; }, error: err => { this.error = err.message; this.loading = false; } }); }
  get rows() { return this.data?.class_overview.filter(x => !this.level || x.academic_level === this.level) || []; }
  get levels() { return this.data?.academic_levels.map(x => x.level) || []; }
}
