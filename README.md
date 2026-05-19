# University Management System - System 18 Community
## Phases 1, 2, 3, 4

### Modules Included
| Module | Phase | Technical Name |
|--------|-------|---------------|
| University Core | 1 | `university_core` |
| Student Information | 2 | `university_student` |
| Admission | 3 | `university_admission` |
| Curriculum | 4 | `university_curriculum` |

### Installation Order
Install in this exact order:
1. `university_core`
2. `university_student`
3. `university_admission`
4. `university_curriculum`

### Ministry Excel Import
The `university_student` module maps directly to the Ministry Excel columns:
| Excel Column | System Field | Description |
|---|---|---|
| FRMNO | ministry_form_number | Ministry Form Number |
| FAC | ministry_fac_code | Faculty Code |
| UNIV_ID | ministry_university_id_code | University ID Code |
| N1 | name_part1_ar | First Name |
| N2 | name_part2_ar | Father's Name |
| N3 | name_part3_ar | Grandfather's Name |
| N4 | name_part4_ar | Family Name |
| SCNAME | school_name | School Name |
| GOBNO | gob_number | Governorate Number |
| FACNAME | faculty_name_ar | Faculty Name (Arabic) |
| GOBOLS | admission_type_text | Admission Type Text |
| YEAR | academic_year_str | Academic Year String |
| NATIONAL_ID | national_id | National ID |
| SEX | gender_code | Gender Code (1/2) |
| UNIVERSITY | university_name_ar | University Name (Arabic) |

### Arabic Language Support
All modules support Arabic via:
1. `translate=True` on all label/name fields
2. `i18n/ar.po` translation files in each module
3. Install Arabic language in System: Settings → Translations → Languages → Add Arabic
4. The system will auto-translate menu items, field labels, and buttons

### Security Groups (defined in university_core)
- **Super Admin**: Full access to all models
- **University Manager**: Hierarchy configuration, batch management
- **Academic Coordinator**: Curriculum, timetable, attendance (read-only finance)
- **Head of Admissions**: Full admission workflow
- **Finance Officer**: Finance only, read student status
- **Teacher**: Own sessions + grade entry only
- **Medical Committee**: Medical review stage only
- **HR Manager**: HR/payroll only
- **Student Portal User**: Own record only (read-only)
