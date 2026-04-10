import re  # regex for matric number validation
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


# ---- AUTH SCHEMAS ----------------------------------


class UserCreate(BaseModel):
    """
    Request schema for creating any user account.
    Role determines what the user can access in the system.

    Parameters:
        email (EmailStr): Valid email address
        password (str): Raw password — will be hashed before storage
        role (str): One of student, lecturer, hod, exam_officer, registrar
    """

    email: EmailStr
    password: str
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Ensures role is one of the five allowed values."""
        allowed = {"student", "lecturer", "hod", "exam_officer", "registrar"}
        if v not in allowed:
            raise ValueError(f"Role must be one of: {', '.join(allowed)}")
        return v


class UserLogin(BaseModel):
    """
    Request schema for login.

    Parameters:
        email (EmailStr): User's email
        password (str): Raw password to verify
    """

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """
    Response schema for successful login.
    Returns JWT token and its type.

    Parameters:
        access_token (str): Signed JWT string
        token_type (str): Always 'bearer'
        role (str): The user's role - frontend uses this to render correct dashboard
    """

    access_token: str
    token_type: str
    role: str


class UserResponse(BaseModel):
    """
    Response schema for user data.
    Never exposes password_hash.

    Parameters:
        id (int): Database ID
        email (str): User's email
        role (str): User's role
        created_at (datetime): Account creation timestamp
    """

    id: int
    email: str
    role: str
    created_at: datetime


# ----- STUDENT SCHEMAS --------------------------------------


class StudentCreate(BaseModel):
    """
    Request schema for registering a new student.
    Validates matric number format against AFIT pattern.

    Parameters:
        user_id (int): The users table ID this student links to
        matric_number (str): AFIT matric format e.g. U22TE1022
        first_name (str): Student's first name
        last_name (str): Student's last name
        department_id (int): Foreign key to departments table
        programme_id (int): Foreign key to programmes table
        entry_year (int): Year of entry e.g. 2022
        current_level (int): 100, 200, 300, 400, or 500
    """

    user_id: int
    matric_number: str
    first_name: str
    last_name: str
    department_id: int
    programme_id: int
    entry_year: int
    current_level: int = 100

    @field_validator("matric_number")
    @classmethod
    def validate_matric_number(cls, v: str) -> str:
        """
        Validates matric number against AFIT format.
        Pattern: U + 2-digit year + 2 or 3-letter dept code + 4-digit number
        Example: U22TE1022
        """
        pattern = r"^[A-Z]\d{2}[A-Z]{2,4}\d{3,5}$"
        if not re.match(pattern, v.upper()):
            raise ValueError(
                f"Invalid matric number format: {v}. Expected format: U22TE1022"
            )
        return v.upper()

    @field_validator("current_level")
    @classmethod
    def validate_level(cls, v: int) -> int:
        """Ensures level is one of the valid AFIT academic levels."""
        if v not in {100, 200, 300, 400, 500}:
            raise ValueError("Level must be 100, 200, 300, 400, or 500")
        return v


class StudentResponse(BaseModel):
    """
    Response schema for student data.

    Parameters:
        id (int): Database ID
        matric_number (str): AFIT matric number
        first_name (str): First name
        last_name (str): Last name
        current_level (int): Current academic level
        status (str): active, probation, withdrawn, or graduated
    """

    id: int
    matric_number: str
    first_name: str
    last_name: str
    current_level: int
    status: str


# ------ SCORE SCHEMAS ------------------------------------------


class ScoreUpload(BaseModel):
    """
    Request schema for a single student's score in one course.
    Used inside the Excel upload parser — each row becomes one ScoreUpload.
    Validates CA and exam score ranges per AFIT regulations.

    Parameters:
        matric_number (str): Student's matric number
        ca_score (float): Continuous assessment score out of 30
        exam_score (float): Examination score out of 70
    """

    matric_number: str
    ca_score: float
    exam_score: float

    @field_validator("ca_score")
    @classmethod
    def validate_ca(cls, v: float) -> float:
        """CA score must be between 0 and 30."""
        if not (0 <= v <= 30):
            raise ValueError(f"CA score {v} is invalid. Must be between 0 and 30")
        return round(v, 2)

    @field_validator("exam_score")
    @classmethod
    def validate_exam(cls, v: float) -> float:
        """Exam score must be between 0 and 70."""
        if not (0 <= v <= 70):
            raise ValueError(f"Exam score {v} is invalid. Must be between 0 and 70")
        return round(v, 2)


class ScoreResponse(BaseModel):
    """
    Response schema for a single score record.

    Parameters:
        id (int): Database ID
        matric_number (str): Student's matric number
        ca_score (float): CA score out of 30
        exam_score (float): Exam score out of 70
        total_score (float): Computed total out of 100
        grade (str): Letter grade A-F
        grade_point (float): Grade point 0.0-5.0
        approval_status (str): pending, approved, or rejected
    """

    id: int
    matric_number: str
    ca_score: float
    exam_score: float
    total_score: float
    grade: str
    grade_point: float
    approval_status: str


class BulkScoreUpload(BaseModel):
    """
    Request schema for uploading scores for an entire course.
    Wraps a list of individual student scores with course context.

    Parameters:
        course_offering_id (int): Which course offering these scores belong to
        scores (list[ScoreUpload]): List of student scores from the Excel file
    """

    course_offering_id: int
    scores: list[ScoreUpload]


# --------- RESULT SCHEMAS ---------------------------------------------


class SemesterResultResponse(BaseModel):
    """
    Response schema for a student's semester result summary.

    Parameters:
        semester_id (int): Which semester
        gpa (float): Semester GPA
        cgpa (float): Cumulative GPA up to this semester
        total_units_registered (int): Units attempted
        total_units_passed (int): Units passed
        academic_standing (str): good_standing, poor_standing, or probation
    """

    semester_id: int
    gpa: float
    cgpa: float
    total_units_registered: int
    total_units_passed: int
    academic_standing: str


class CourseResultResponse(BaseModel):
    """
    Response schema for a single course result.
    Used in result sheets and transcripts.

    Parameters:
        course_code (str): e.g. TCE401
        course_title (str): Full course name
        credit_units (int): Credit unit weight
        ca_score (float): CA score
        exam_score (float): Exam score
        total_score (float): Total out of 100
        grade (str): Letter grade
        grade_point (float): Grade point value
    """

    course_code: str
    course_title: str
    credit_units: int
    ca_score: float
    exam_score: float
    total_score: float
    grade: str
    grade_point: float


# ----- TRANSCRIPT SCHEMAS -------------------------------------
class TranscriptRequest(BaseModel):
    """
    Request schema for generating a transcript.

    Parameters:
        student_id (int): The student's database ID
        purpose (Optional[str]): Reason for transcript e.g. scholarship, postgraduate
    """

    student_id: int
    purpose: Optional[str] = None


class TranscriptSemesterBlock(BaseModel):
    """
    One semester block inside a transcript.
    Groups all courses taken in a semester with the semester GPA.

    Parameters:
        session_name (str): e.g. 2023/2024
        semester_number (int): 1 or 2
        level (int): 100, 200, 300, 400, 500
        courses (list[CourseResultResponse]): All courses that semester
        gpa (float): Semester GPA
        cgpa (float): Cumulative GPA after this semester
        total_units (int): Units registered that semester
    """

    session_name: str
    semester_number: int
    level: int
    courses: list[CourseResultResponse]
    gpa: float
    cgpa: float
    total_units: int


class TranscriptResponse(BaseModel):
    """
    Full transcript response — everything needed to render the PDF.

    Parameters:
        matric_number (str): Student's matric number
        full_name (str): Student's full name
        programme (str): Degree programme name
        department (str): Department name
        entry_year (int): Year of first admission
        semesters (list[TranscriptSemesterBlock]): All semester blocks
        final_cgpa (float): Overall CGPA
        degree_classification (str): e.g. First Class Honours
        generated_at (datetime): When this transcript was generated
    """

    matric_number: str
    full_name: str
    programme: str
    department: str
    entry_year: int
    semesters: list[TranscriptSemesterBlock]
    final_cgpa: float
    degree_classification: str
    generated_at: datetime
