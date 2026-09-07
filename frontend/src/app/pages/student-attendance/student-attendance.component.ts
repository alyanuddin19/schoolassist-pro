import { Component } from '@angular/core';

@Component({
  selector: 'app-student-attendance',
  template: `<section class="page"><h1>Student attendance</h1><p>Select a class to view and record attendance.</p></section>`,
  styles: [`.page { padding: 24px; } h1 { margin-top: 0; }`],
})
export class StudentAttendanceComponent {}
