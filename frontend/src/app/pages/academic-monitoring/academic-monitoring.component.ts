import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../core/api.service';
@Component({selector:'app-academic-monitoring',templateUrl:'./academic-monitoring.component.html',styleUrls:['./academic-monitoring.component.css']})
export class AcademicMonitoringComponent implements OnInit { data:any; loading=true; error=''; selected:any=null; status=''; constructor(private api:ApiService){} ngOnInit(){this.load();} load(){this.loading=true;this.api.principalAcademicMonitoring().subscribe({next:x=>{this.data=x;this.loading=false;},error:e=>{this.error=e.message;this.loading=false;}});} get rows(){return (this.data?.classes||[]).filter((x:any)=>!this.status||x.status===this.status);} }
