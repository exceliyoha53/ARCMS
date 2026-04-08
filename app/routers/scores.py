import logging
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from app.auth import require_lecturer, require_hod
from app.database import get_connection, return_connection, get_db_cursor
from app.services.excel_parser import parse_score_sheet  # reads the excel file
from app.services.gpa_service import recalculate_student_gpa  # triggered after approval
from app.gpa_engine import get_grade
import io  # reads file bytes in memory without saving to disk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scores", tags=["Scores"])

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_scores(
    course_offering_id: int = Form(...), # which course these scores belong to
    file: UploadFile = File(...),  # the excel file
    current_user: dict = Depends(require_lecturer)  # only lectures, hod, exam_officer
) -> dict:
    """
    Uploads a score sheet for a specific course offering.
    Accepts an Excel file (.xlsx) with columns: matric_number, ca_score, exam_score.
    Validates every row before saving — partial uploads are rejected entirely.
    All scores saved with approval_status='pending' until HOD approves.

    Parameters:
        course_offering_id (int): Form field — which course offering these scores are for
        file (UploadFile): The Excel file with student scores
        current_user (dict): Injected by require_lecturer dependency

    Returns:
        dict: Summary of upload — how many saved, how many failed validation

    Raises:
        HTTPException 400: If file is not .xlsx or validation fails
        HTTPException 404: If course offering not found
    """
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx files are accepted"
        )

    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
        cursor.execute(
            "SELECT id, lecturer_id FROM course_offerings WHERE id = %s",
            (course_offering_id,)
        )

        offering = cursor.fetchone()
        if not offering:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course offering {course_offering_id} not found"
            )
        
        file_bytes = await file.read() # read from memory - no disk writes
        file_buffer = io.BytesIO(file_bytes) # wrap bytes so openpyxl can read it

        parsed_scores, errors = parse_score_sheet(file_buffer)

        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Upload rejected due to validation errors. Fix all errors and re-upload.",
                    "errors": errors  # list of {row, matric_number, error} dicts
                }
            )
        cursor.execute(
            "SELECT id FROM lecturers WHERE user_id = (SELECT id FROM users WHERE email = %s)",
            (current_user["email"],)
        )
        
        lecturer = cursor.fetchone()
        lecturer_id = lecturer["id"] if lecturer else None

        saved_count = 0

        for score_data in parsed_scores:
            cursor.execute(
                "SELECT id FROM students WHERE matric_number = %s",
                (score_data.matric_number,)
            )

            student = cursor.fetchone()

            if not student: # student not registered in the system - skip with warning
                logger.warning(f"Student not found: {score_data.matric_number}")
                continue

            # confirm student is registered for this course
            cursor.execute("""
                SELECT id FROM registrations
                WHERE student_id = %s AND course_offering_id = %s
            """, (student["id"], course_offering_id))
            
            registration = cursor.fetchone()
            
            if not registration:
                logger.warning(
                    f"Student {score_data.matric_number} not registered for offering {course_offering_id}"
                )
                continue

            total_score = score_data.ca_score + score_data.exam_score
            grade, grade_point = get_grade(total_score)

            # allowing reupload to correct mistakes
            cursor.execute("""
                INSERT INTO scores (
                    registration_id, ca_score, exam_score,
                    grade, grade_point, uploaded_by, approval_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                ON CONFLICT (registration_id)
                DO UPDATE SET
                    ca_score = EXCLUDED.ca_score,
                    exam_score = EXCLUDED.exam_score,
                    grade = EXCLUDED.grade,
                    grade_point = EXCLUDED.grade_point,
                    uploaded_by = EXCLUDED.uploaded_by,
                    approval_status = 'pending',
                    uploaded_at = CURRENT_TIMESTAMP
            """, (
                registration["id"],
                score_data.ca_score,
                score_data.exam_score,
                grade,
                grade_point,
                lecturer_id
            ))

            saved_count += 1

        conn.commit()
        logger.info(
        f"Score upload complete for offering {course_offering_id} "
        f"by {current_user['email']} — {saved_count} records saved"
        )

        return {
            "message": "Upload successful",
            "course_offering_id": course_offering_id,
            "records_saved": saved_count,
            "status": "pending_approval"
        }
    
    except HTTPException:
        raise

    except Exception as e:
        conn.rollback()
        logger.error(f"Score upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Score upload failed"
        )

    finally:
        cursor.close()
        return_connection(conn)

@router.get("/pending")
async def get_pending_scores(
    current_user: dict = Depends(require_hod)  # only the HOD can see pending approvals
) -> list[dict]:
    """
    Returns all score uploads pending HOD approval.
    Groups by course offering so HOD sees one entry per course, not per student.

    Parameters:
        current_user (dict): Injected by require_hod dependency

    Returns:
        list[dict]: Pending course offerings with score counts
    """
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
        cursor.execute("""
            SELECT
                co.id AS course_offering_id,
                c.code AS course_code,
                c.title AS course_title,
                c.credit_units,
                COUNT(s.id) AS student_count,
                MAX(s.uploaded_at) AS last_uploaded_at
            FROM scores s
            JOIN registrations r ON s.registration_id = r.id
            JOIN course_offerings co ON r.course_offering_id = co.id
            JOIN courses c ON co.course_id = c.id
            WHERE s.approval_status = 'pending'
            GROUP BY co.id, c.code, c.title, c.credit_units
            ORDER BY last_uploaded_at DESC
        """
        )

        pending = [dict(row) for row in cursor.fetchall()]
        logger.info(f"HOD {current_user['email']} fetched {len(pending)} pending course uploads")
        return pending

    except Exception as e:
        logger.error(f"Error fetching pending scores: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch pending scores"
        )

    finally:
        cursor.close()
        return_connection(conn)


@router.post("/approve/{course_offering_id}")
async def approve_scores(
    course_offering_id: int,
    current_user: dict = Depends(require_hod)
) -> dict:
    """
    Approves all pending scores for a course offering.
    After approval, triggers GPA recalculation for every affected student.
    This is what makes results visible to students.

    Parameters:
        course_offering_id (int): Which course offering to approve
        current_user (dict): Injected by require_hod dependency

    Returns:
        dict: Approval summary with count of approved scores

    Raises:
        HTTPException 404: If no pending scores found for this offering
    """
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
       cursor.execute(
           "SELECT id FROM users WHERE email = %s",
            (current_user["email"],)
        )
       hod_user = cursor.fetchone()
       hod_id = hod_user["id"]

       cursor.execute("""
            SELECT s.id, r.student_id
            FROM scores s
            JOIN registrations r ON s.registration_id = r.id
            WHERE r.course_offering_id = %s AND s.approval_status = 'pending'
        """, (course_offering_id,))

       pending_scores = cursor.fetchall()

       if not pending_scores:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pending scores found for this course offering"
            )
       # approve all scores and record who approved and when
       cursor.execute("""
            UPDATE scores
            SET
                approval_status = 'approved',
                approved_by = %s,
                approved_at = CURRENT_TIMESTAMP
            WHERE id = ANY(%s)
        """, (hod_id, [row["id"] for row in pending_scores]))

       conn.commit()
       
       #unique student IDs affected by the approval
       affected_students = list(set(row["student_id"] for row in pending_scores))

       for student_id in affected_students:
           await recalculate_student_gpa(student_id, conn)

        
       logger.info(
                f"HOD {current_user['email']} approved {len(pending_scores)} scores "
                f"for offering {course_offering_id}"
            )

       return {
            "message": "Scores approved successfully",
            "course_offering_id": course_offering_id,
            "scores_approved": len(pending_scores),
            "students_affected": len(affected_students)
        }

    except HTTPException:
        raise

    except Exception as e:
        conn.rollback()
        logger.error(f"Approval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Approval failed"
        )

    finally:
        cursor.close()
        return_connection(conn)
