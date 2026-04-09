import logging
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import FileResponse # returns a file download
from app.auth import get_current_user
from app.database import get_connection, return_connection, get_db_cursor
from app.services.transcript_service import generate_transcript_pdf
from app.gpa_engine import get_degree_classification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcript", tags=["Transcript"])

@router.get("/generate/{matric_number}")
async def generate_transcripts(
    matric_number: str,
    purpose: str = "general",
    current_user: dict = Depends(get_current_user)
) -> FileResponse:
    """
    Generates and returns an official PDF transcript for a student.
    Students can only generate their own transcript.
    Staff can generate any student's transcript.
    Records the generation in transcript_requests for audit trail.

    Parameters:
        matric_number (str): Student's AFIT matric number
        purpose (str): Reason for transcript — scholarship, postgraduate, employment
        current_user (dict): Injected by get_current_user

    Returns:
        FileResponse: PDF file download

    Raises:
        HTTPException 403: If student requests another student's transcript
        HTTPException 404: If student or results not found
    """
    conn = get_connection()
    cursor = get_db_cursor(conn)

    try:
        cursor.execute("""
            SELECT s.id, s.matric_number, s.first_name, s.last_name,
                s.entry_year, s.current_level,
                d.name AS department,
                p.name AS programme, p.degree_type
            FROM students s
            JOIN departments d ON s.department_id = d.id
            JOIN programmes p ON s.programme_id = p.id
            WHERE s.matric_number = %s
        """, (matric_number.upper(),))

        student = cursor.fetchone()
            
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student {matric_number} not found"
            )
        
        #students can only generate their own transcript
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
                    detail="You can only generate your own transcript"
                )
            
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
                sem.semester_number,
                sess.name AS session_name,
                (s2.current_level - (
                SELECT COUNT(DISTINCT sem2.session_id)
                FROM semesters sem2
                WHERE sem2.id <= sem.id
                ) * 100) AS level
            FROM scores sc
            JOIN registrations r ON sc.registration_id = r.id
            JOIN students s2 ON r.student_id = s2.id
            JOIN course_offerings co ON r.course_offering_id = co.id
            JOIN courses c ON co.course_id = c.id
            JOIN semesters sem ON co.semester_id = sem.id
            JOIN sessions sess ON sem.session_id = sess.id
            WHERE r.student_id = %s
            AND sc.approval_status = 'approved'
            ORDER BY sess.name, sem.semester_number, c.code
        """, (student["id"],))
        
        all_results = [dict(row) for row in cursor.fetchall()]

        if not all_results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No approved results found for this student"
            )
        
        cursor.execute("""
            SELECT sr.semester_id, sr.gpa, sr.cgpa, sr.total_units_registered
            FROM semester_results sr
            WHERE sr.student_id = %s
            ORDER BY sr.semester_id
        """, (student["id"],))

        semester_gpas = {row["semester_id"]: dict(row) for row in cursor.fetchall()}
        # .values() ignores keys gives only values
        final_cgpa = max((v["cgpa"] for v in semester_gpas.values() if v["cgpa"] is not None), default=0.0)

        degree_classification = get_degree_classification(final_cgpa)
        #record transcript generation for audit trail
        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (current_user["email"],)
        )
        requester = cursor.fetchone()

        cursor.execute("""
             INSERT INTO transcript_requests (student_id, generated_by, purpose)
            VALUES (%s, %s, %s)
        """, (student["id"], requester["id"], purpose))

        conn.commit()

        # build transcript data structure for PDF generation
        transcript_data = {
            "student": dict(student),
            "results": all_results,
            "semester_gpas": semester_gpas,
            "final_cgpa": final_cgpa,
            "degree_classification": degree_classification,
            "purpose": purpose
        }

        pdf_path = await generate_transcript_pdf(transcript_data)

        logger.info(
           f"Transcript generated for {matric_number} "
           f"by {current_user['email']} — purpose: {purpose}"
        )

        # return pdf as downloadable file
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"transcript_{matric_number}.pdf"
        )
    
    except HTTPException:
        raise

    except Exception as e:
        conn.rollback()
        logger.error(f"Transcript generation error for {matric_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcript generation failed"
        )
    
    finally:
        cursor.close()
        return_connection(conn)
