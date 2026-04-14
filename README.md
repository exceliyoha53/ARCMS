# ARCMS — Academic Result & Course Management System

A production-grade academic result management backend built for the
Air Force Institute of Technology, Kaduna. Replaces manual result
distribution with a secure, role-based digital system.

---

## The Problem

Nigerian university result management is largely manual — lecturers
submit paper score sheets, results get pasted on notice boards,
students photograph them and share on WhatsApp. Errors are common,
resolution is slow, and transcript generation can take weeks.

ARCMS digitises the entire pipeline.

---

## What It Does

**For Lecturers & Exam Officers**
Upload an Excel score sheet (.xlsx) for any course. The system
validates every row — matric number format, CA ≤ 30, exam ≤ 70 —
and rejects the entire upload if any row fails. Clean data only.

**For HODs**
See all pending score uploads grouped by course. One-click approval
triggers automatic GPA and CGPA recalculation for every affected
student using AFIT's official 5-point grading scale.

**For Students**
Log in, enter your matric number, see your complete result history —
every semester, every course, CA score, exam score, grade, GPA, CGPA.
Download an official PDF transcript in seconds.

**For Registrars**
Manage departments, academic sessions, student accounts, and staff
accounts from a single dashboard. Full audit trail on every action.

---

## Grading System

AFIT 5-point scale, enforced at the database and application layer:

| Score | Grade | Points |
|-------|-------|--------|
| 70–100 | A | 5.0 |
| 60–69 | B | 4.0 |
| 50–59 | C | 3.0 |
| 45–49 | D | 2.0 |
| 40–44 | E | 1.0 |
| 0–39 | F | 0.0 |

GPA = Σ(credit units × grade points) / Σ(credit units)

---

## Stack

- **FastAPI** — async Python web framework
- **PostgreSQL** — production database with connection pooling
- **psycopg2** — database driver with ThreadedConnectionPool
- **JWT + bcrypt** — authentication and password hashing
- **Pydantic v2** — request/response validation with custom validators
- **openpyxl** — Excel score sheet parsing
- **WeasyPrint + Jinja2** — PDF transcript generation
- **Role-based access control** — 5 roles: student, lecturer, HOD, exam officer, registrar

---

## Roles & Access

| Role | Can Do |
|------|--------|
| Registrar | Create accounts, departments, sessions |
| HOD | Approve score uploads, view all students |
| Lecturer | Upload score sheets |
| Exam Officer | Upload score sheets |
| Student | View own results, download transcript |

---

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/arcms
cd arcms
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/arcms
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
INSTITUTION_NAME=Air Force Institute of Technology
INSTITUTION_ADDRESS=PMB 2104, Kaduna, Nigeria
```

Seed the first registrar:
```powershell
python seed_admin.py
```

Run the development server:
```powershell
uvicorn app.main:app --reload
```

---

## Future Plans

* **Bulk student import** — registrar uploads one Excel file to onboard an entire year group at once.
* **Historical data import** — one-time Excel upload for existing students to backdate all past semester results.
* **Email notifications** — students notified when results are approved.
* **AI result summaries** — LLM-generated department performance analysis for HODs ("Pass rate dropped 12% this semester — here's why").
* **Mobile-responsive UI** — students checking results from phones.
* **HND/ND support** — extend grading engine for diploma programmes.
* **Multi-institution** — configurable for any Nigerian university.
* **Result ratification workflow** — senate-level approval before results go live.
* **Docker deployment** — containerised for one-command cloud deployment.