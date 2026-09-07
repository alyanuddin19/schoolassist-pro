import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { PrincipalTeachersData } from '../../core/models';

@Component({ selector: 'app-principal-teachers', templateUrl: './principal-teachers.component.html', styleUrls: ['./principal-teachers.component.css'] })
export class PrincipalTeachersComponent implements OnInit {
  data: PrincipalTeachersData | null = null; loading = true; error = ''; query = ''; department = ''; subject = ''; className = ''; assignment = ''; status = ''; selected: PrincipalTeachersData['teachers'][number] | null = null;
  constructor(private api: ApiService) {}
  ngOnInit(): void { this.load(); }
  load(): void { this.loading = true; this.api.principalTeachers().subscribe({ next: data => { this.data = data; this.loading = false; }, error: err => { this.error = err.message; this.loading = false; } }); }
  get teachers() { const q = this.query.toLowerCase().trim(); return (this.data?.teachers || []).filter(x => (!q || `${x.name} ${x.employee_id}`.toLowerCase().includes(q)) && (!this.department || x.department === this.department) && (!this.subject || x.subjects.includes(this.subject)) && (!this.className || x.classes.includes(this.className)) && (!this.assignment || x.assignment_status === this.assignment) && (!this.status || x.status === this.status)); }
}
