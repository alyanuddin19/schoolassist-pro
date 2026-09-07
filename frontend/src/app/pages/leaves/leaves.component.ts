import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { LeaveInfo } from '../../core/models';

@Component({
  selector: 'app-leaves',
  template: `<section class="page"><h1>{{ isPrincipal ? 'Leave Approvals' : 'Leave Request' }}</h1>
    <p class="hint">{{ isPrincipal ? 'Review teacher leave requests and approve or reject them with a reason.' : 'Submit your leave request for Principal approval.' }}</p>
    <p *ngIf="error" class="error">{{ error }}</p><p *ngIf="notice" class="notice">{{ notice }}</p>
    <form (ngSubmit)="requestLeave()" class="card" *ngIf="!isPrincipal">
      <h2>New leave request</h2><label>Start <input type="date" name="start" [(ngModel)]="startDate" required></label>
      <label>End <input type="date" name="end" [(ngModel)]="endDate" required></label>
      <label>Reason <input name="reason" [(ngModel)]="reason" required></label>
      <button type="submit">Submit for Principal approval</button>
    </form>
    <p class="empty" *ngIf="isPrincipal && !leaves.length">No teacher leave requests are waiting for your review.</p>
    <div class="card" *ngFor="let leave of leaves"><h2>{{ leave.teacher }} <small>{{ leave.start_date }} – {{ leave.end_date }} · {{ leave.days }} day(s)</small></h2>
      <p>{{ leave.reason }}</p><strong>{{ statusLabel(leave.status) }}</strong>
      <div class="actions" *ngIf="isPrincipal && leave.status === 'pending_principal_approval'"><input [(ngModel)]="decisionNote" [name]="'note' + leave.id" placeholder="Approval / rejection reason"><button (click)="decide(leave, 'approved')">Approve</button><button class="danger" (click)="decide(leave, 'rejected')">Reject</button></div>
    </div></section>`,
  styles: [`.page{padding:24px;max-width:900px}.card{background:#fff;border:1px solid #e4e7ec;border-radius:12px;padding:16px;margin:16px 0}.card label{display:inline-flex;flex-direction:column;margin:0 12px 12px 0;gap:5px}.card input{padding:8px}.hint,small{color:#667085}.error{color:#b42318}.notice{color:#067647}.actions{margin-top:12px;display:flex;gap:8px}button{background:#2457a6;color:#fff;border:0;border-radius:7px;padding:9px 12px;cursor:pointer}.danger{background:#b42318}`],
})
export class LeavesComponent implements OnInit {
  leaves: LeaveInfo[] = []; startDate = ''; endDate = ''; reason = ''; decisionNote = ''; error = ''; notice = '';
  constructor(private api: ApiService, private auth: AuthService) {}
  ngOnInit(): void { this.load(); }
  get isPrincipal(): boolean { return this.auth.role === 'principal'; }
  load(): void { this.api.getLeaves().subscribe({ next: x => this.leaves = x, error: e => this.error = e.message }); }
  requestLeave(): void { this.api.createLeave({ start_date: this.startDate, end_date: this.endDate, reason: this.reason }).subscribe({ next: () => { this.notice = 'Leave request sent for Principal approval.'; this.reason = ''; this.load(); }, error: e => this.error = e.message }); }
  decide(leave: LeaveInfo, status: string): void { this.api.decideLeave(leave.id, { status, note: this.decisionNote.trim() || undefined }).subscribe({ next: () => { this.notice = 'Decision saved.'; this.decisionNote = ''; this.load(); }, error: e => this.error = e.message }); }
  statusLabel(value: string): string { return ({ pending_principal_approval: 'Pending Principal approval', approved: 'Approved', rejected: 'Rejected' } as Record<string, string>)[value] || value; }
}
