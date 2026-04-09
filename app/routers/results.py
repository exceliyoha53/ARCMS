import logging
from fastapi import APIRouter, HTTPException, status, Depends
from app.auth import require_student, require_staff, get_current_user
from app.database import get_connection, return_connection, get_db_cursor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/results", tags=["Results"])

@router.get("/{matric_number}")
async def get_student_results(
    matric_number: str,
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Returns a student's full result history across all semesters.
    Students can only view their own results.
    Staff can view any student's results.

    Parameters:
        matric_number (str): The student's AFIT matric number
        current_user (dict): Injected by get_current_user dependency

    Returns:
        dict: Student profile, semester results, and course-level breakdown

    Raises:
        HTTPException 403: If student tries to view another student's results
        HTTPException 404: If student not found
    """
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try: # fetch student record
        cursor.execute("""
            SELECT s.id, s.matric_number, s.first_name, s.last_name,
                   s.current_level, s.status, s.entry_year,
                   d.name AS department, p.name AS programme
            FROM students s
            JOIN departments d ON s.department_id = d.id
            JOIN programmes p on s.programme_id = p.id
            WHERE s.matric_number = %s
        """, (matric_number.upper(),))

        student = cursor.fetchall()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student {matric_number} not found"
            )
        # staff roles can view any result, student can only view their results
        if current_user["role"] == "student":
            cursor.execute(
                "SELECT matric_number FROM students WHERE user_id = "
                "(SELECT id FROM users WHERE email = %s)",
                (current_user["email"],)
            )
            own_record = cursor.fetchone()
            if not own_record or own_record["matric_number"] != matric_number.upper():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own results"
                )
            # fetch semester result summaries
            cursor.execute("""
                SELECT
                    sr.semester_id,
                    sess.name AS session_name,
                    sem.semester_number,
                    sr.gpa,
                    sr.cgpa,
                    sr.total_units_registered,
                    sr.total_units_passed,
                    sr.academic_standing
                FROM semester_results sr
                JOIN semesters sem ON sr.semester_id = sem.id
                JOIN sessions sess ON sem.session_id = sess.id
                WHERE sr.student_id = %s
                ORDER BY sess.name, sem.semester_number
            """, (student["id"],))
            
            # [{ "semester_id": 1, "gpa": 4.05 }]
            semester_summaries = [dict(row) for row in cursor.fetchall()]

            cursor.execute("""
                SELECT
                    c.code AS course_code,
                    c.title AS course_title,
                    c.credit_units,
                    sc.ca_score,
                    sc.exam_score,
                    sc.total_score,
                    sc.grade,
                    sc.grade_point,
                    sem.id AS semester_id,
                    sess.name AS session_name,
                    sem.semester_number
                FROM scores sc
                JOIN registrations r ON sc.registration_id = r.id
                JOIN course_offerings co ON r.course_offering_id = co.id
                JOIN courses c ON co.course_id = c.id
                JOIN semesters sem ON co.semester_id = sem.id
                JOIN sessions sess ON sem.session_id = sess.id
                WHERE r.student_id = %s
                AND sc.approval_status = 'approved'
                ORDER BY sess.name, sem.semester_number, c.code
            """, (student["id"],))

            course_results = [dict(row) for row in cursor.fetchall()]

            # group courses by semester_id
            courses_by_semester = {}
            for course in course_results:
                sem_id = course["semester_id"]
                if sem_id not in courses_by_semester:
                    courses_by_semester[sem_id] = []
                courses_by_semester[sem_id].append(course)
                # { 1: [{ "code": "TEL411", "grade": "A" }] }

            for semester in semester_summaries:
                semester["courses"] = courses_by_semester.get(semester["semester_id"], [])          

            latest_cgpa = semester_summaries[-1]["cgpa"] if semester_summaries else 0.0

            logger.info(f"Results fetched for {matric_number} by {current_user['email']}")

            return {
                "student": dict(student),
                "latest_cgpa": latest_cgpa,
                "semesters": semester_summaries
            }
        
    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error fetching results for {matric_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch results"
        )
    
    finally:
        cursor.close()
        return_connection(conn)

