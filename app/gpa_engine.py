PROBATION_THRESHOLD = 1.00
GRADUATION_MINIMUM = 1.50


def get_grade(total_score: float) -> tuple[str, float]:
    """
    Converts a total score (0-100) into a letter grade point
    using the AFIT 5-point grading scale.

    Parameters:
        total_score (float): The student's total score out of 100

    Returns:
        tuple[str, float]: (letter_grade, grade_point) e.g. ("A", 5.0)

    Raises:
        ValueError: If score is outside the valid 0-100 range
    """
    if not (0 <= total_score <= 100):
        raise ValueError(f"Score {total_score} is outside valid range 0-100")
    
    if total_score >= 70:
        return "A", 5.0
    elif total_score >= 60:
        return "B", 4.0
    elif total_score >= 50:
        return "C", 3.0
    elif total_score >= 45:
        return "D", 2.0
    elif total_score >= 40:
        return "E", 1.0
    else:
        return "F", 0.0
    

def calculate_gpa(courses: list[dict]) -> float:
    """
    Calculates the GPA for a single semester using the AFIT formula.
    Formula: GPA = Σ(credit_units × grade_point) / Σ(credit_units)

    Parameters:
        courses (list[dict]): List of course results for the semester.
            Each dict must have:
                credit_units (int): The credit unit weight of the course
                grade_point (float): The grade point earned (0.0 to 5.0)

    Returns:
        float: The calculated GPA rounded to 2 decimal places.
               Returns 0.0 if no courses provided.

    Example:
        courses = [
            {"credit_units": 3, "grade_point": 5.0},  # A
            {"credit_units": 2, "grade_point": 4.0},  # B
        ]
        GPA = (3×5.0 + 2×4.0) / (3+2) = 23/5 = 4.60
    """
    if not courses:
        return 0.0
    
    total_weighted_points = sum(
        c["credit_units"] * c["grade_point"] for c in courses
    )

    total_units = sum(c["credit_units"] for c in courses)

    if total_units == 0:
        return 0.0

    return round(total_weighted_points / total_units, 2)


def calculate_cgpa(all_semesters: list[dict]) -> float:
    """
    Calculates the Cumulative GPA across all semesters.
    Uses all attempts including repeated courses per AFIT regulations.
    Formula: CGPA = Σ(all grade points) / Σ(all units across all semesters)

    Parameters:
        all_semesters (list[dict]): All course results across every semester.
            Each dict must have:
                credit_units (int): Credit unit weight
                grade_point (float): Grade point earned

    Returns:
        float: The calculated CGPA rounded to 2 decimal places.
               Returns 0.0 if no data provided.
    """
    return calculate_gpa(all_semesters)


def get_degree_classification(cgpa: float) -> str:
    """
    Returns the degree classification string for a given CGPA.
    Based on AFIT official degree classification table.

    Parameters:
        cgpa (float): The student's cumulative GPA

    Returns:
        str: Degree classification e.g. "First Class Honours"
    """
    if cgpa >= 4.50:
        return "First Class Honours"
    elif cgpa >= 3.50:
        return "Second Class Honours (Upper)"
    elif cgpa >= 2.40:
        return "Second Class Honours (Lower)"
    elif cgpa >= 1.50:
        return "Third Class Honours"
    else:
        return "Fail"
    

def get_academic_standing(cgpa: float) -> str:
    """
    Determines a student's academic standing based on their CGPA.
    Per AFIT regulations:
        CGPA < 1.00 → probation (one year to recover)
        CGPA < 1.50 → cannot graduate
        CGPA >= 1.50 → good standing

    Parameters:
        cgpa (float): The student's current CGPA

    Returns:
        str: 'probation', 'poor_standing', or 'good_standing'
    """
    if cgpa < PROBATION_THRESHOLD:
        return "probation"
    if cgpa < GRADUATION_MINIMUM:
        return "poor_standing"
    return "good_standing"


def compute_semester_result(courses: list[dict]) -> dict:
    """
    Computes the full result summary for a single semester.
    Calculates GPA, total units registered, units passed, and carry-overs.

    Parameters:
        courses (list[dict]): Course results for the semester.
            Each dict must have:
                credit_units (int): Credit unit weight
                grade_point (float): Grade point earned
                grade (str): Letter grade

    Returns:
        dict with keys:
            gpa (float): Semester GPA
            total_units_registered (int): All units attempted
            total_units_passed (int): Units where grade is not F
            carry_over_count (int): Number of failed courses
    """
    gpa = calculate_gpa(courses)

    total_units_registered = sum(c["credit_units"] for c in courses)

    total_units_passed = sum(c["credit_units"] for c in courses if c["grade"] != "F")

    carry_over_count = sum(1 for c in courses if c["grade"] == "F")

    return {
        "gpa": gpa,
        "total_units_registered": total_units_registered,
        "total_units_passed": total_units_passed,
        "carry_over_count": carry_over_count,
    }