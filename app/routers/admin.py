import logging
from fastapi import APIRouter, HTTPException, status, Depends
from app.auth import require_registrar, require_staff
from app.database import get_connection, return_connection, get_db_cursor
from app.models.schemas import StudentCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/students", status_code=status.HTTP_201_CREATED)
def register_student(
    student_data: StudentCreate, current_user: dict = Depends(require_registrar)
) -> dict:
    """
    Registers a new student in the system.
    Only the registrar can create student records.
    Creates both a users record and a students profile record.

    Parameters:
        student_data (StudentCreate): Student details including matric number
        current_user (dict): Injected by require_registrar

    Returns:
        dict: Created student profile

    Raises:
        HTTPException 400: If matric number already exists
        HTTPException 404: If department or programme not found
    """
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
        cursor.execute(
            "SELECT id FROM students WHERE matric_number = %s",
            (student_data.matric_number,),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Matric number {student_data.matric_number} already registered",
            )

        cursor.execute(
            "SELECT id FROM departments WHERE id = %s", (student_data.department_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department {student_data.department_id} not found",
            )
        cursor.execute(
            """
            INSERT INTO students (
                user_id, matric_number, first_name, last_name,
                department_id, programme_id, current_level, entry_year
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, matric_number, first_name, last_name,
                      current_level, status
        """,
            (
                student_data.user_id,
                student_data.matric_number,
                student_data.first_name,
                student_data.last_name,
                student_data.department_id,
                student_data.programme_id,
                student_data.current_level,
                student_data.entry_year,
            ),
        )

        conn.commit()
        new_student = dict(cursor.fetchone())
        logger.info(
            f"Student registered: {student_data.matric_number} "
            f"by registrar {current_user['email']}"
        )
        return new_student

    except HTTPException:
        raise

    except Exception as e:
        conn.rollback()
        logger.error(f"Student registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Student registration failed",
        )

    finally:
        cursor.close()
        return_connection(conn)


@router.get("/students")
def list_students(current_user: dict = Depends(require_staff)) -> list[dict]:
    """
    Returns a list of all registered students.
    Accessible by all staff roles.

    Parameters:
        current_user (dict): Injected by require_staff

    Returns:
        list[dict]: All student records with department and programme names
    """
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
        cursor.execute("""
            SELECT s.id, s.matric_number, s.first_name, s.last_name,
                   s.current_level, s.status, s.entry_year,
                   d.name AS department, p.name AS programme
            FROM students s
            JOIN departments d ON s.department_id = d.id
            JOIN programmes p ON s.programme_id = p.id
            ORDER BY s.matric_number
        """)

        students = [dict(row) for row in cursor.fetchall()]
        logger.info(
            f"{current_user['email']} fetched student list — {len(students)} students"
        )

        return students

    except Exception as e:
        logger.error(f"Error fetching students: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch students",
        )

    finally:
        cursor.close()
        return_connection(conn)


@router.post("/departments", status_code=status.HTTP_201_CREATED)
def create_department(
    name: str, code: str, current_user: dict = Depends(require_registrar)
) -> dict:
    """
    Creates a new department.
    Only registrar can create departments.

    Parameters:
        name (str): Full department name e.g. Telecommunications Engineering
        code (str): Short code e.g. TEE409
        current_user (dict): Injected by require_registrar

    Returns:
        dict: Created department record
    """
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
        cursor.execute(
            """
            INSERT INTO departments (name, code)
            VALUES (%s, %s)
            RETURNING id, name, code
        """,
            (name, code.upper()),
        )

        conn.commit()
        dept = dict(cursor.fetchone())
        logger.info(f"Department created: {code} by {current_user['email']}")
        return dept

    except Exception as e:
        conn.rollback()
        logger.error(f"Department creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create department",
        )

    finally:
        cursor.close()
        return_connection(conn)


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(
    name: str, current_user: dict = Depends(require_registrar)
) -> dict:
    """
    Creates a new academic session.
    Each session automatically gets two semesters created.
    Only registrar can create sessions.

    Parameters:
        name (str): Session name e.g. 2024/2025
        current_user (dict): Injected by require_registrar

    Returns:
        dict: Created session with both semesters
    """
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
        cursor.execute(
            """
            INSERT INTO sessions (name, is_current)
            VALUES (%s, FALSE)
            RETURNING id, name
        """,
            (name,),
        )

        session = dict(cursor.fetchone())

        for semester_num in [1, 2]:
            cursor.execute(
                """
                INSERT INTO semesters (session_id, semester_number, is_current)
                VALUES (%s, %s, FALSE)
            """,
                (session["id"], semester_num),
            )

        conn.commit()
        logger.info(f"Session {name} created by {current_user['email']}")

        return {
            "session": session,
            "semesters_created": 2,
            "message": f"Session {name} created with Semester 1 and Semester 2",
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Session creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create session",
        )

    finally:
        cursor.close()
        return_connection(conn)
