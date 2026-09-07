import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import {
  AssignmentInfo, ClassInfo, GuardianInfo, SectionInfo, StudentInfo, StudentProfileInfo,
  SubjectInfo, TeacherInfo,
} from '../../core/models';

const RELATIONSHIPS = ['Father', 'Mother', 'Guardian', 'Grandfather', 'Grandmother', 'Uncle', 'Aunt', 'Sibling', 'Other'];

interface StudentForm {
  name: string;
  roll_no: string;
  class_id: number | null;
  section_id: number | null;
  guardian_name: string;
  guardian_phone: string;
}

function blankStudentForm(): StudentForm {
  return { name: '', roll_no: '', class_id: null, section_id: null, guardian_name: '', guardian_phone: '' };
}

interface ClassForm {
  name: string;
  grade_level: number | null;
  capacity: number | null;
}

interface SectionForm {
  name: string;
  class_teacher_id: number | null;
}

/** One editable section row inside the Edit Class card. */
interface SectionRow extends SectionForm {
  id: number;
}

/** One box in the class grid: a whole class, or a single section of it. */
interface ClassCard {
  classInfo: ClassInfo;
  section: SectionInfo | null;
  students: number;
}

interface SubjectForm {
  name: string;
  code: string;
}

interface GuardianForm {
  full_name: string;
  phone: string;
  email: string;
}

@Component({
  selector: 'app-setup',
  templateUrl: './setup.component.html',
  styleUrls: ['./setup.component.css'],
})
export class SetupComponent implements OnInit {
  tab: 'classes' | 'subjects' | 'students' | 'assignments' = 'classes';

  classes: ClassInfo[] = [];
  subjects: SubjectInfo[] = [];
  students: StudentInfo[] = [];
  assignments: AssignmentInfo[] = [];
  teachers: TeacherInfo[] = [];

  loading = false;
  error = '';
  notice = '';

  /* class form */
  newClassName = '';
  /* Classes are split into levels: primary is grades 1-5, secondary 6-10. */
  newClassLevel: 'primary' | 'secondary' = 'primary';
  newGradeLevel: number | null = 1;
  newClassCapacity: number | null = null;
  levelFilter: 'all' | 'primary' | 'secondary' = 'all';
  gradeChoices = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  sectionName = '';
  sectionClassId: number | null = null;
  sectionTeacherId: number | null = null;

  /* class & section editing */
  editingClass: ClassInfo | null = null;
  classForm: ClassForm = { name: '', grade_level: null, capacity: null };
  /* Sections are edited inline, inside the Edit Class card itself. */
  sectionRows: SectionRow[] = [];
  newSectionName = '';
  newSectionTeacherId: number | null = null;
  editingSection: SectionInfo | null = null;
  editingSectionClass: ClassInfo | null = null;
  sectionForm: SectionForm = { name: '', class_teacher_id: null };
  savingStructure = false;

  /* subject form */
  newSubjectName = '';
  newSubjectCode = '';
  editingSubject: SubjectInfo | null = null;
  subjectForm: SubjectForm = { name: '', code: '' };
  savingSubject = false;

  /* subjects per class */
  csClassId: number | null = null;
  csSelected: number[] = [];
  csSaving = false;

  /* student form */
  /* Level first, then only that level's classes are offered. */
  studentLevel: 'all' | 'primary' | 'secondary' = 'all';
  studentClassId: number | null = null;
  studentSectionId: number | null = null;
  studentRollNo = '';
  studentName = '';
  guardianName = '';
  guardianPhone = '';
  importClassId: number | null = null;
  /* Bulk import is two-step: choose the file, then confirm with OK. */
  importFile: File | null = null;
  importing = false;

  /* student list filters */
  filterClassId: number | null = null;
  filterSectionId: number | null = null;
  studentSearch = '';
  showInactive = false;
  /* The list opens on demand: Show Students → filters → Apply → table. */
  showStudentFilters = false;
  studentsApplied = false;

  /* student edit */
  editingStudent: StudentInfo | null = null;
  editForm: StudentForm = blankStudentForm();
  savingStudent = false;

  /* student profile + guardians */
  profile: StudentProfileInfo | null = null;
  loadingProfile = false;
  guardians: GuardianInfo[] = [];
  relationships = RELATIONSHIPS;
  guardianMode: 'existing' | 'new' = 'existing';
  linkGuardianId: number | null = null;
  linkRelationship = 'Father';
  newGuardianName = '';
  newGuardianPhone = '';
  newGuardianEmail = '';
  savingGuardian = false;

  /* guardian directory */
  guardianSearch = '';
  editingGuardian: GuardianInfo | null = null;
  guardianForm: GuardianForm = { full_name: '', phone: '', email: '' };

  /* assignment form */
  assignTeacherId: number | null = null;
  assignClassId: number | null = null;
  assignSectionId: number | null = null;
  assignSubjectId: number | null = null;
  assignSubjects: SubjectInfo[] = [];
  academicYear = '';

  constructor(public auth: AuthService, private api: ApiService, private route: ActivatedRoute) {}

  ngOnInit(): void {
    const routeTab = this.route.snapshot.data['tab'];
    if (routeTab === 'classes' || routeTab === 'subjects' || routeTab === 'students' || routeTab === 'assignments') {
      this.tab = routeTab;
    }
    this.route.queryParamMap.subscribe(params => {
      const tab = params.get('tab');
      if (tab === 'classes' || tab === 'subjects' || tab === 'students' || tab === 'assignments') {
        this.tab = tab;
      }
    });
    const now = new Date();
    const startYear = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
    this.academicYear = `${startYear}-${startYear + 1}`;
    this.load();
  }

  get canManage(): boolean {
    return this.auth.isIndividual || this.auth.isAcademicLead;
  }

  /** Each section gets its own heading now that the tab strip is gone. */
  get pageTitle(): string {
    switch (this.tab) {
      case 'subjects': return 'Subject Management';
      case 'students': return 'Student Management';
      case 'assignments': return 'Teacher Assignments';
      default: return 'Class & Section Management';
    }
  }

  get pageSubtitle(): string {
    switch (this.tab) {
      case 'subjects': return 'Create subjects and assign subjects to each class.';
      case 'students': return 'Add, import and manage students by class and section.';
      case 'assignments': return 'Assign teachers to classes, sections and subjects.';
      default: return 'Create and manage classes, sections and class capacity.';
    }
  }

  /** Grade choices follow the level picked in the Add Class form. */
  get levelGrades(): number[] {
    return this.newClassLevel === 'secondary' ? [6, 7, 8, 9, 10] : [1, 2, 3, 4, 5];
  }

  /** Classes are shown per level; the chips narrow the list to one level. */
  get levelGroups(): { title: string; hint: string; cards: ClassCard[] }[] {
    const groups = [
      { title: 'Primary', hint: 'Classes 1-5', cards: this.cardsFor(this.byLevel('primary')) },
      { title: 'Secondary', hint: 'Classes 6-10', cards: this.cardsFor(this.byLevel('secondary')) },
      { title: 'Other', hint: 'Grade not set', cards: this.cardsFor(this.classes.filter(c => !c.level)) },
    ];
    if (this.levelFilter === 'all') {
      return groups.filter(group => group.cards.length);
    }
    return groups.filter(group => group.title.toLowerCase() === this.levelFilter);
  }

  /** A class with sections gets one card per section, so every section shows
   *  up as its own full class card in the grid. */
  private cardsFor(list: ClassInfo[]): ClassCard[] {
    const cards: ClassCard[] = [];
    for (const classInfo of list) {
      if (!classInfo.sections?.length) {
        cards.push({ classInfo, section: null, students: classInfo.students });
        continue;
      }
      for (const section of classInfo.sections) {
        cards.push({ classInfo, section, students: section.students ?? 0 });
      }
    }
    return cards;
  }

  private byLevel(level: 'primary' | 'secondary'): ClassInfo[] {
    return this.classes
      .filter(classInfo => classInfo.level === level)
      .sort((a, b) =>
        (a.grade_level ?? 99) - (b.grade_level ?? 99) ||
        a.name.localeCompare(b.name, undefined, { numeric: true }));
  }

  /** Switching level moves the grade picker into that range. */
  onLevelChange(): void {
    this.newGradeLevel = this.levelGrades[0];
  }

  /** Typing "Class 8" moves the level and grade pickers to match, so the name
   *  and the level never disagree. */
  onClassNameChange(): void {
    const match = this.newClassName.match(/\d+/);
    if (!match) {
      return;
    }
    const grade = Number(match[0]);
    if (grade < 1 || grade > 10) {
      return;
    }
    this.newClassLevel = grade <= 5 ? 'primary' : 'secondary';
    this.newGradeLevel = grade;
  }

  levelLabel(classInfo: ClassInfo): string {
    if (classInfo.level === 'primary') {
      return 'Primary';
    }
    return classInfo.level === 'secondary' ? 'Secondary' : '';
  }

  load(): void {
    this.loading = true;
    this.error = '';
    this.api.getClasses().subscribe({
      next: res => {
        this.classes = res;
        if (!this.studentClassId && res.length) {
          this.studentClassId = res[0].id;
          this.importClassId = res[0].id;
        }
        if (!this.assignClassId && res.length) {
          this.assignClassId = res[0].id;
        }
        if (!this.csClassId && res.length) {
          this.csClassId = res[0].id;
        }
        if (!this.sectionClassId && res.length) {
          this.sectionClassId = res[0].id;
        }
        this.loadClassSubjects();
        this.loadAssignSubjects();
        this.loading = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loading = false;
      },
    });
    this.api.getSubjects().subscribe({ next: res => (this.subjects = res), error: () => {} });
    this.loadStudents();
    this.loadAssignments();
    this.loadGuardians();
    /* Only active teaching staff can be given a class; the school owner is not a teacher. */
    this.api.getTeachers().subscribe({
      next: res => (this.teachers = res.filter(t => t.is_active !== false && t.role !== 'org_admin')),
      error: () => {},
    });
  }

  loadStudents(): void {
    const params: { class_id?: number; section_id?: number; search?: string; include_inactive?: boolean } = {};
    if (this.filterClassId) {
      params.class_id = this.filterClassId;
    }
    if (this.filterSectionId) {
      params.section_id = this.filterSectionId;
    }
    const term = this.studentSearch.trim();
    if (term) {
      params.search = term;
    }
    if (this.showInactive) {
      params.include_inactive = true;
    }
    this.api.getStudents(params).subscribe({
      next: res => (this.students = [...res].sort(this.byRollNoThenName)),
      error: () => {},
    });
  }

  /** Roll numbers are stored as text, so order them the human way — 2 before
   *  10 — and break ties by name. */
  private byRollNoThenName(a: StudentInfo, b: StudentInfo): number {
    const roll = a.roll_no.localeCompare(b.roll_no, undefined, { numeric: true });
    return roll !== 0 ? roll : a.name.localeCompare(b.name);
  }

  loadGuardians(): void {
    this.api.getGuardians().subscribe({ next: res => (this.guardians = res), error: () => {} });
  }

  loadAssignments(): void {
    this.api.getAssignments().subscribe({ next: res => (this.assignments = res), error: () => {} });
  }

  /* ------------ classes & sections ------------ */

  createClass(): void {
    if (!this.newClassName.trim()) {
      this.error = 'Please enter a class name (e.g. Class 8).';
      return;
    }
    this.api.createClass({
      name: this.newClassName.trim(),
      grade_level: this.newGradeLevel ?? undefined,
      capacity: this.newClassCapacity ?? undefined,
    }).subscribe({
      next: () => {
        this.notice = `Class "${this.newClassName.trim()}" created.`;
        this.newClassName = '';
        this.newGradeLevel = this.levelGrades[0];
        this.newClassCapacity = null;
        this.load();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  startEditClass(classInfo: ClassInfo): void {
    this.error = '';
    this.notice = '';
    this.editingSection = null;
    this.editingClass = classInfo;
    this.classForm = {
      name: classInfo.name,
      grade_level: classInfo.grade_level ?? null,
      capacity: classInfo.capacity ?? null,
    };
    this.syncSectionRows(classInfo);
    this.newSectionName = '';
    this.newSectionTeacherId = null;
  }

  cancelEditClass(): void {
    this.editingClass = null;
  }

  private syncSectionRows(classInfo: ClassInfo): void {
    this.sectionRows = (classInfo.sections || []).map(section => ({
      id: section.id,
      name: section.name,
      class_teacher_id: section.class_teacher_id ?? null,
    }));
  }

  /** Section changes only touch the class tree, so reloading classes is enough. */
  private reloadClassesThen(done: () => void): void {
    this.api.getClasses().subscribe({
      next: res => {
        this.classes = res;
        done();
      },
      error: (err: Error) => {
        this.savingStructure = false;
        this.error = err.message;
      },
    });
  }

  /** Re-point the edit card at the freshly loaded class and refresh its rows. */
  private refreshEditingClass(): void {
    const target = this.editingClass;
    if (!target) {
      return;
    }
    const fresh = this.classes.find(classInfo => classInfo.id === target.id);
    if (!fresh) {
      this.editingClass = null;
      return;
    }
    this.editingClass = fresh;
    this.syncSectionRows(fresh);
  }

  saveSectionRow(row: SectionRow): void {
    if (!row.name.trim()) {
      this.error = 'The section needs a name.';
      return;
    }
    this.savingStructure = true;
    this.error = '';
    this.api.updateSection(row.id, {
      name: row.name.trim(),
      class_teacher_id: row.class_teacher_id,
    }).subscribe({
      next: () => {
        this.notice = `Section ${row.name.trim()} updated.`;
        this.reloadClassesThen(() => {
          this.savingStructure = false;
          this.refreshEditingClass();
        });
      },
      error: (err: Error) => {
        this.savingStructure = false;
        this.error = err.message;
      },
    });
  }

  removeSectionRow(row: SectionRow): void {
    const target = this.editingClass;
    if (!target || !confirm(`Remove section ${row.name} from ${target.name}?`)) {
      return;
    }
    this.savingStructure = true;
    this.error = '';
    this.api.deleteSection(row.id).subscribe({
      next: () => {
        this.notice = `Section ${row.name} removed.`;
        this.reloadClassesThen(() => {
          this.savingStructure = false;
          this.refreshEditingClass();
        });
      },
      error: (err: Error) => {
        this.savingStructure = false;
        this.error = err.message;
      },
    });
  }

  addSectionToEditingClass(): void {
    const target = this.editingClass;
    if (!target) {
      return;
    }
    if (!this.newSectionName.trim()) {
      this.error = 'Please enter a section name (e.g. A, B, Morning).';
      return;
    }
    this.savingStructure = true;
    this.error = '';
    this.api.createSection({
      class_id: target.id,
      name: this.newSectionName.trim(),
      class_teacher_id: this.newSectionTeacherId,
    }).subscribe({
      next: () => {
        this.notice = `Section ${this.newSectionName.trim()} added to ${target.name}.`;
        this.newSectionName = '';
        this.newSectionTeacherId = null;
        this.reloadClassesThen(() => {
          this.savingStructure = false;
          this.refreshEditingClass();
        });
      },
      error: (err: Error) => {
        this.savingStructure = false;
        this.error = err.message;
      },
    });
  }

  saveClass(): void {
    const target = this.editingClass;
    if (!target) {
      return;
    }
    if (!this.classForm.name.trim()) {
      this.error = 'The class needs a name.';
      return;
    }
    this.savingStructure = true;
    this.error = '';
    this.api.updateClass(target.id, {
      name: this.classForm.name.trim(),
      grade_level: this.classForm.grade_level,
      capacity: this.classForm.capacity,
    }).subscribe({
      next: () => {
        this.savingStructure = false;
        this.notice = `${this.classForm.name.trim()} updated.`;
        this.editingClass = null;
        this.load();
      },
      error: (err: Error) => {
        this.savingStructure = false;
        this.error = err.message;
      },
    });
  }

  /** Strength bar so a full class is obvious at a glance. */
  capacityPercent(classInfo: ClassInfo): number {
    if (!classInfo.capacity) {
      return 0;
    }
    return Math.min(100, Math.round((classInfo.students / classInfo.capacity) * 100));
  }

  addSection(): void {
    if (!this.sectionClassId) {
      this.error = 'Select the class this section belongs to.';
      return;
    }
    if (!this.sectionName.trim()) {
      this.error = 'Please enter a section name (e.g. A, B, Morning).';
      return;
    }
    const className = this.classes.find(c => c.id === this.sectionClassId)?.name || 'the class';
    this.api.createSection({
      class_id: this.sectionClassId,
      name: this.sectionName.trim(),
      class_teacher_id: this.sectionTeacherId,
    }).subscribe({
      next: () => {
        this.notice = `Section "${this.sectionName.trim()}" added to ${className}.`;
        this.sectionName = '';
        this.sectionTeacherId = null;
        this.load();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  startEditSection(section: SectionInfo, classInfo: ClassInfo): void {
    this.error = '';
    this.notice = '';
    this.editingClass = null;
    this.editingSection = section;
    this.editingSectionClass = classInfo;
    this.sectionForm = {
      name: section.name,
      class_teacher_id: section.class_teacher_id ?? null,
    };
  }

  cancelEditSection(): void {
    this.editingSection = null;
    this.editingSectionClass = null;
  }

  saveSection(): void {
    const target = this.editingSection;
    if (!target) {
      return;
    }
    if (!this.sectionForm.name.trim()) {
      this.error = 'The section needs a name.';
      return;
    }
    this.savingStructure = true;
    this.error = '';
    this.api.updateSection(target.id, {
      name: this.sectionForm.name.trim(),
      class_teacher_id: this.sectionForm.class_teacher_id,
    }).subscribe({
      next: () => {
        this.savingStructure = false;
        this.notice = `Section ${this.sectionForm.name.trim()} updated.`;
        this.cancelEditSection();
        this.load();
      },
      error: (err: Error) => {
        this.savingStructure = false;
        this.error = err.message;
      },
    });
  }

  deleteClass(classInfo: ClassInfo): void {
    if (!confirm(`Delete ${classInfo.name}? Students, marksheets and assignments linked to it may become unusable.`)) {
      return;
    }
    this.api.deleteClass(classInfo.id).subscribe({
      next: () => this.load(),
      error: (err: Error) => (this.error = err.message),
    });
  }

  deleteSection(sectionId: number, className: string): void {
    if (!confirm(`Remove this section from ${className}?`)) {
      return;
    }
    this.api.deleteSection(sectionId).subscribe({
      next: () => this.load(),
      error: (err: Error) => (this.error = err.message),
    });
  }

  /* ------------ subjects ------------ */

  createSubject(): void {
    if (!this.newSubjectName.trim()) {
      this.error = 'Please enter a subject name (e.g. Mathematics).';
      return;
    }
    this.api.createSubject({
      name: this.newSubjectName.trim(),
      code: this.newSubjectCode.trim() || undefined,
    }).subscribe({
      next: () => {
        this.notice = `Subject "${this.newSubjectName.trim()}" is ready.`;
        this.newSubjectName = '';
        this.newSubjectCode = '';
        this.load();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  startEditSubject(subject: SubjectInfo): void {
    this.error = '';
    this.notice = '';
    this.editingSubject = subject;
    this.subjectForm = { name: subject.name, code: subject.code || '' };
  }

  cancelEditSubject(): void {
    this.editingSubject = null;
    this.savingSubject = false;
  }

  saveSubject(): void {
    const target = this.editingSubject;
    if (!target) {
      return;
    }
    const name = this.subjectForm.name.trim();
    if (!name) {
      this.error = 'The subject needs a name.';
      return;
    }
    this.savingSubject = true;
    this.error = '';
    /* An empty code box means "remove the short code", so send an explicit null. */
    this.api.updateSubject(target.id, { name, code: this.subjectForm.code.trim() || null }).subscribe({
      next: () => {
        this.savingSubject = false;
        this.editingSubject = null;
        this.notice = `Subject "${name}" updated.`;
        this.load();
      },
      error: (err: Error) => {
        this.savingSubject = false;
        this.error = err.message;
      },
    });
  }

  deleteSubject(subject: SubjectInfo): void {
    if (!confirm(`Delete subject ${subject.name}?`)) {
      return;
    }
    this.api.deleteSubject(subject.id).subscribe({
      next: () => this.load(),
      error: (err: Error) => (this.error = err.message),
    });
  }

  /* ------------ subjects per class ------------ */

  loadClassSubjects(): void {
    if (!this.csClassId) {
      this.csSelected = [];
      return;
    }
    this.api.getClassSubjectIds(this.csClassId).subscribe({
      next: res => (this.csSelected = res.subject_ids || []),
      error: (err: Error) => (this.error = err.message),
    });
  }

  onCsClassChange(): void {
    this.loadClassSubjects();
  }

  toggleCsSubject(subjectId: number): void {
    this.csSelected = this.csSelected.includes(subjectId)
      ? this.csSelected.filter(id => id !== subjectId)
      : [...this.csSelected, subjectId];
  }

  saveClassSubjects(): void {
    if (!this.csClassId) {
      this.error = 'Select a class first.';
      return;
    }
    this.csSaving = true;
    this.error = '';
    this.notice = '';
    this.api.setClassSubjects(this.csClassId, this.csSelected).subscribe({
      next: () => {
        this.csSaving = false;
        this.notice = 'Subjects for this class updated.';
      },
      error: (err: Error) => {
        this.csSaving = false;
        this.error = err.message;
      },
    });
  }

  /* ------------ students ------------ */

  /** The Add Student form has its own class picker, separate from the list filters. */
  onStudentClassChange(): void {
    this.studentSectionId = null;
  }

  /** Classes offered to the Add Student form, narrowed by the chosen level. */
  get studentClassOptions(): ClassInfo[] {
    if (this.studentLevel === 'all') {
      return this.classes;
    }
    return this.classes.filter(classInfo => classInfo.level === this.studentLevel);
  }

  /** Changing level keeps a valid class selected — or falls back to the first. */
  onStudentLevelChange(): void {
    this.studentSectionId = null;
    const options = this.studentClassOptions;
    if (!options.some(classInfo => classInfo.id === this.studentClassId)) {
      this.studentClassId = options.length ? options[0].id : null;
    }
  }

  onFilterClassChange(): void {
    this.filterSectionId = null;
    this.loadStudents();
  }

  resetStudentFilters(): void {
    this.filterClassId = null;
    this.filterSectionId = null;
    this.studentSearch = '';
    this.showInactive = false;
    this.loadStudents();
  }

  get sectionsForStudentClass(): ClassInfo['sections'] {
    return this.sectionsOf(this.studentClassId);
  }

  get filterSections(): ClassInfo['sections'] {
    return this.sectionsOf(this.filterClassId);
  }

  get sectionsForEditClass(): ClassInfo['sections'] {
    return this.sectionsOf(this.editForm.class_id);
  }

  private sectionsOf(classId: number | null): ClassInfo['sections'] {
    return this.classes.find(c => c.id === classId)?.sections || [];
  }

  get sectionsForAssignClass(): ClassInfo['sections'] {
    const classInfo = this.classes.find(c => c.id === this.assignClassId);
    return classInfo?.sections || [];
  }

  createStudent(): void {
    if (!this.studentClassId) {
      this.error = 'Please select a class first.';
      return;
    }
    if (!this.studentRollNo.trim() || !this.studentName.trim()) {
      this.error = 'Roll number and student name are required.';
      return;
    }
    this.api.createStudent({
      class_id: this.studentClassId,
      section_id: this.studentSectionId || null,
      roll_no: this.studentRollNo.trim(),
      name: this.studentName.trim(),
      guardian_name: this.guardianName.trim() || undefined,
      guardian_phone: this.guardianPhone.trim() || undefined,
    }).subscribe({
      next: () => {
        this.notice = `Student "${this.studentName.trim()}" added.`;
        this.studentRollNo = '';
        this.studentName = '';
        this.guardianName = '';
        this.guardianPhone = '';
        this.refreshAfterStudentChange();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  /** Student counts live on the class cards, so both lists are refreshed together. */
  private refreshAfterStudentChange(): void {
    this.loadStudents();
    this.api.getClasses().subscribe({ next: res => (this.classes = res), error: () => {} });
  }

  /** Stage the file first; nothing is uploaded until the user presses OK. */
  onImportFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files && input.files[0];
    input.value = '';
    if (!file) {
      return;
    }
    this.importFile = file;
    this.error = '';
    this.notice = '';
  }

  confirmImport(): void {
    if (!this.importClassId) {
      this.error = 'Select the class for the import first.';
      return;
    }
    if (!this.importFile) {
      this.error = 'Choose an Excel or CSV file first.';
      return;
    }
    const fileName = this.importFile.name;
    this.importing = true;
    this.api.importStudents(this.importFile, this.importClassId).subscribe({
      next: (res: { created: number; skipped_duplicates: string[] }) => {
        const skipped = res.skipped_duplicates?.length
          ? ` (${res.skipped_duplicates.length} duplicates skipped)`
          : '';
        this.notice = `${res.created} students imported from ${fileName}${skipped}.`;
        this.importing = false;
        this.importFile = null;
        this.refreshAfterStudentChange();
      },
      error: (err: Error) => {
        this.importing = false;
        this.error = err.message;
      },
    });
  }

  cancelImport(): void {
    this.importFile = null;
  }

  applyStudents(): void {
    this.studentsApplied = true;
    this.loadStudents();
  }

  deactivateStudent(student: StudentInfo): void {
    if (!confirm(`Mark ${student.name} (${student.roll_no}) as inactive? The record is kept for reports.`)) {
      return;
    }
    this.setStudentStatus(student, false);
  }

  /** Active / Inactive toggle — inactive students disappear from attendance and seating. */
  setStudentStatus(student: StudentInfo, active: boolean): void {
    this.api.updateStudent(student.id, { is_active: active }).subscribe({
      next: () => {
        this.notice = `${student.name} is now ${active ? 'active' : 'inactive'}.`;
        this.refreshAfterStudentChange();
        if (this.profile?.id === student.id) {
          this.openProfile(student);
        }
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  /* ------------ edit student ------------ */

  startEditStudent(student: StudentInfo): void {
    this.editingStudent = student;
    this.error = '';
    this.notice = '';
    this.editForm = {
      name: student.name,
      roll_no: student.roll_no,
      class_id: student.class_id,
      section_id: student.section_id ?? null,
      guardian_name: student.guardian_name || '',
      guardian_phone: student.guardian_phone || '',
    };
  }

  cancelEditStudent(): void {
    this.editingStudent = null;
    this.editForm = blankStudentForm();
  }

  onEditClassChange(): void {
    this.editForm.section_id = null;
  }

  saveStudent(): void {
    const student = this.editingStudent;
    if (!student) {
      return;
    }
    if (!this.editForm.name.trim() || !this.editForm.roll_no.trim() || !this.editForm.class_id) {
      this.error = 'Name, roll number and class are required.';
      return;
    }
    this.savingStudent = true;
    this.error = '';
    this.api.updateStudent(student.id, {
      name: this.editForm.name.trim(),
      roll_no: this.editForm.roll_no.trim(),
      class_id: this.editForm.class_id,
      /* 0 means "whole class" — the backend only clears the section for a real id change. */
      section_id: this.editForm.section_id || null,
      guardian_name: this.editForm.guardian_name.trim(),
      guardian_phone: this.editForm.guardian_phone.trim(),
    }).subscribe({
      next: () => {
        this.savingStudent = false;
        this.notice = `${this.editForm.name.trim()} updated.`;
        this.cancelEditStudent();
        this.refreshAfterStudentChange();
      },
      error: (err: Error) => {
        this.savingStudent = false;
        this.error = err.message;
      },
    });
  }

  /* ------------ student profile ------------ */

  openProfile(student: StudentInfo): void {
    this.error = '';
    this.loadingProfile = true;
    this.profile = null;
    this.resetGuardianForm();
    this.api.getStudentProfile(student.id).subscribe({
      next: res => {
        this.profile = res;
        this.loadingProfile = false;
      },
      error: (err: Error) => {
        this.error = err.message;
        this.loadingProfile = false;
      },
    });
  }

  closeProfile(): void {
    this.profile = null;
    this.resetGuardianForm();
  }

  get profileAttendanceTotal(): number {
    const a = this.profile?.attendance;
    return a ? a.present + a.absent + a.leave + a.late : 0;
  }

  get profileAttendancePercent(): string {
    const a = this.profile?.attendance;
    const total = this.profileAttendanceTotal;
    if (!a || !total) {
      return '—';
    }
    return `${Math.round(((a.present + a.late) / total) * 100)}%`;
  }

  percent(obtained: number, total: number): string {
    return total > 0 ? Math.round((obtained / total) * 100).toString() : '0';
  }

  /* ------------ guardians ------------ */

  private resetGuardianForm(): void {
    this.guardianMode = 'existing';
    this.linkGuardianId = null;
    this.linkRelationship = 'Father';
    this.newGuardianName = '';
    this.newGuardianPhone = '';
    this.newGuardianEmail = '';
  }

  /** Guardians already linked to the open student cannot be picked again. */
  get availableGuardians(): GuardianInfo[] {
    const linked = new Set((this.profile?.guardians || []).map(g => g.id));
    return this.guardians.filter(g => !linked.has(g.id));
  }

  saveGuardianLink(): void {
    const student = this.profile;
    if (!student) {
      return;
    }
    this.error = '';
    const payload: Record<string, any> = { relationship: this.linkRelationship || null };
    if (this.guardianMode === 'existing') {
      if (!this.linkGuardianId) {
        this.error = 'Choose the parent or guardian to link.';
        return;
      }
      payload.guardian_id = this.linkGuardianId;
    } else {
      if (!this.newGuardianName.trim()) {
        this.error = 'Enter the guardian name.';
        return;
      }
      if (this.newGuardianEmail.trim() && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(this.newGuardianEmail.trim())) {
        this.error = 'That email address does not look right.';
        return;
      }
      payload.full_name = this.newGuardianName.trim();
      payload.phone = this.newGuardianPhone.trim() || null;
      payload.email = this.newGuardianEmail.trim() || null;
    }
    this.savingGuardian = true;
    this.api.linkGuardian(student.id, payload).subscribe({
      next: () => {
        this.savingGuardian = false;
        this.notice = 'Guardian linked.';
        this.resetGuardianForm();
        this.openProfile(student);
        this.loadGuardians();
      },
      error: (err: Error) => {
        this.savingGuardian = false;
        this.error = err.message;
      },
    });
  }

  removeGuardianLink(guardianId: number, guardianName: string): void {
    const student = this.profile;
    if (!student) {
      return;
    }
    if (!confirm(`Unlink ${guardianName} from ${student.name}?`)) {
      return;
    }
    this.api.unlinkGuardian(student.id, guardianId).subscribe({
      next: () => {
        this.notice = 'Guardian unlinked.';
        this.openProfile(student);
        this.loadGuardians();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  /* ------------ guardian directory ------------ */

  /** Directory search covers the guardian, their contact details and their children. */
  get directoryGuardians(): GuardianInfo[] {
    const term = this.guardianSearch.trim().toLowerCase();
    if (!term) {
      return this.guardians;
    }
    return this.guardians.filter(g =>
      g.full_name.toLowerCase().includes(term)
      || (g.phone || '').toLowerCase().includes(term)
      || (g.email || '').toLowerCase().includes(term)
      || g.children.some(c => c.name.toLowerCase().includes(term)));
  }

  startEditGuardian(guardian: GuardianInfo): void {
    this.error = '';
    this.notice = '';
    this.editingGuardian = guardian;
    this.guardianForm = {
      full_name: guardian.full_name,
      phone: guardian.phone || '',
      email: guardian.email || '',
    };
  }

  cancelEditGuardian(): void {
    this.editingGuardian = null;
  }

  saveGuardian(): void {
    const target = this.editingGuardian;
    if (!target) {
      return;
    }
    const name = this.guardianForm.full_name.trim();
    if (!name) {
      this.error = 'The guardian needs a name.';
      return;
    }
    const email = this.guardianForm.email.trim();
    if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      this.error = 'That email address does not look right.';
      return;
    }
    this.savingGuardian = true;
    this.error = '';
    this.api.updateGuardian(target.id, {
      full_name: name,
      phone: this.guardianForm.phone.trim() || null,
      email: email || null,
    }).subscribe({
      next: () => {
        this.savingGuardian = false;
        this.editingGuardian = null;
        this.notice = `${name} updated.`;
        this.loadGuardians();
        if (this.profile) {
          this.openProfile(this.profile);
        }
      },
      error: (err: Error) => {
        this.savingGuardian = false;
        this.error = err.message;
      },
    });
  }

  deleteGuardian(guardian: GuardianInfo): void {
    if (guardian.children.length) {
      this.error = `${guardian.full_name} is still linked to ${guardian.children.length} student(s). Unlink them first.`;
      return;
    }
    if (!confirm(`Remove ${guardian.full_name} from the guardian directory?`)) {
      return;
    }
    this.api.deleteGuardian(guardian.id).subscribe({
      next: () => {
        this.notice = `${guardian.full_name} removed.`;
        this.loadGuardians();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  /** Opens one of a guardian's children, even when the current filters hide them. */
  openChild(studentId: number): void {
    this.error = '';
    this.loadingProfile = true;
    this.resetGuardianForm();
    this.api.getStudentProfile(studentId).subscribe({
      next: res => {
        this.profile = res;
        this.loadingProfile = false;
      },
      error: (err: Error) => {
        this.loadingProfile = false;
        this.error = err.message;
      },
    });
  }

  /* ------------ assignments ------------ */

  loadAssignSubjects(): void {
    if (!this.assignClassId) {
      this.assignSubjects = [];
      return;
    }
    this.api.getSubjects(this.assignClassId).subscribe({
      next: res => {
        this.assignSubjects = res;
        if (!res.some(s => s.id === this.assignSubjectId)) {
          this.assignSubjectId = null;
        }
      },
      error: () => {},
    });
  }

  onAssignClassChange(): void {
    this.assignSectionId = null;
    this.loadAssignSubjects();
  }

  createAssignment(): void {
    if (!this.assignTeacherId || !this.assignClassId || !this.assignSubjectId) {
      this.error = 'Please choose the teacher, class and subject.';
      return;
    }
    this.api.createAssignment({
      teacher_id: this.assignTeacherId,
      class_id: this.assignClassId,
      section_id: this.assignSectionId || null,
      subject_id: this.assignSubjectId,
      academic_year: this.academicYear.trim() || undefined,
    }).subscribe({
      next: () => {
        this.notice = 'Teaching assignment saved.';
        this.loadAssignments();
      },
      error: (err: Error) => (this.error = err.message),
    });
  }

  deleteAssignment(assignment: AssignmentInfo): void {
    if (!confirm(`Remove ${assignment.teacher_name} from ${assignment.class} ${assignment.subject}?`)) {
      return;
    }
    this.api.deleteAssignment(assignment.id).subscribe({
      next: () => this.loadAssignments(),
      error: (err: Error) => (this.error = err.message),
    });
  }
}
