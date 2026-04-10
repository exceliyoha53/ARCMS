import logging
import psycopg2.extensions
from app.gpa_engine import (
    calculate_cgpa,
    get_academic_standing,
    compute_semester_result,
)

logger = logging.getLogger(__name__)


def recalculate_student_gpa(
    student_id: int, conn: psycopg2.extensions.connection
) -> dict:
    """
    Recalculates and updates GPA and CGPA for a student after score approval.
    Fetches all approved scores across all semesters, computes results,
    and upserts into semester_results table.
    Does NOT call conn.commit() — the calling router owns the transaction.

    Parameters:
        student_id (int): The student's database ID
        conn: Active psycopg2 connection from the calling router

    Returns:
        dict with keys:
            student_id (int): The student's ID
            semesters_updated (int): How many semester results were updated
            current_cgpa (float): The student's latest CGPA after recalculation
    """
    from psycopg2.extras import RealDictCursor

    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # fetch all approved scores for this student across every semester
        # joins through registrations -> course_offerings -> semesters
        # to get the semester context for each score
        cursor.execute(
            """
            SELECT
                s.id AS score_id,
                s.ca_score,
                s.exam_score,
                s.total_score,
                s.grade,
                s.grade_point,
                c.credit_units,
                c.code AS course_code,
                sem.id AS semester_id,
                sem.session_id,
                sem.semester_number
            FROM scores s
            JOIN registrations r ON s.registration_id = r.id
            JOIN course_offerings co ON r.course_offering_id = co.id
            JOIN courses c ON co.course_id = c.id
            JOIN semesters sem ON co.semester_id = sem.id
            WHERE r.student_id = %s
            AND s.approval_status = 'approved'
            ORDER BY sem.session_id, sem.semester_number
        """,
            (student_id,),
        )

        all_scores = cursor.fetchall()

        if not all_scores:
            logger.warning(f"No approved scores found for student {student_id}")
            return {
                "student_id": student_id,
                "semesters_updated": 0,
                "current_cgpa": 0.0,
            }
        # group scores by semester_id | key(semester_id), value(list of scores for that semester)
        semesters_map = {}
        for score in all_scores:
            sem_id = score["semester_id"]
            if sem_id not in semesters_map:
                semesters_map[sem_id] = []
            semesters_map[sem_id].append(dict(score))

        # build the full list of all courses across all semesters
        # used to calculate CGPA — needs every course ever taken
        all_courses_flat = [dict(score) for score in all_scores]

        cgpa = calculate_cgpa(all_courses_flat)
        academic_standing = get_academic_standing(cgpa)

        semesters_updated = 0

        for semester_id, courses in semesters_map.items():
            semester_summary = compute_semester_result(courses)

            # upsert semester result — create if not exists, update if it does
            cursor.execute(
                """
                INSERT INTO semester_results (
                    student_id,
                    semester_id,
                    total_units_registered,
                    total_units_passed,
                    total_grade_points,
                    gpa,
                    cgpa,
                    academic_standing,
                    computed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (student_id, semester_id)
                DO UPDATE SET
                    total_units_registered = EXCLUDED.total_units_registered,
                    total_units_passed = EXCLUDED.total_units_passed,
                    total_grade_points = EXCLUDED.total_grade_points,
                    gpa = EXCLUDED.gpa,
                    cgpa = EXCLUDED.cgpa,
                    academic_standing = EXCLUDED.academic_standing,
                    computed_at = CURRENT_TIMESTAMP
            """,
                (
                    student_id,
                    semester_id,
                    semester_summary["total_units_registered"],
                    semester_summary["total_units_passed"],
                    sum(c["credit_units"] * c["grade_point"] for c in courses),
                    semester_summary["gpa"],
                    cgpa,
                    academic_standing,
                ),
            )

            semesters_updated += 1

        if academic_standing == "probation":
            cursor.execute(
                "UPDATE students SET status = 'probation' WHERE id = %s", (student_id,)
            )
        elif academic_standing == "good_standing":
            cursor.execute(
                "UPDATE students SET status = 'active' WHERE id = %s", (student_id,)
            )

        logger.info(
            f"GPA recalculated for student {student_id} — "
            f"CGPA: {cgpa}, standing: {academic_standing}, "
            f"semesters updated: {semesters_updated}"
        )

        return {
            "student_id": student_id,
            "semesters_updated": semesters_updated,
            "current_cgpa": cgpa,
        }

    finally:
        cursor.close()
