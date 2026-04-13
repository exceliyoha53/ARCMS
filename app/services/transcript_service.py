import os
import asyncio
import logging
from datetime import datetime
from jinja2 import Environment, FileSystemLoader  # renders HTML templates
from weasyprint import HTML  # converts HTML to PDF

logger = logging.getLogger(__name__)

OUTPUT_DIR = "generated_transcripts"
os.makedirs(OUTPUT_DIR, exist_ok=True)  # create folder if it doesn't exist

template_env = Environment(loader=FileSystemLoader("app/templates/transcript"))


def generate_transcript_pdf(transcript_data: dict) -> str:
    """
    Async wrapper for the transcript generation process.

    Pushes the heavy WeasyPrint CPU-bound task to a background thread using
    asyncio.to_thread. This prevents the FastAPI event loop from being blocked,
    ensuring the server remains responsive to other requests while the PDF
    is being rendered.

    Parameters:
        transcript_data (dict): The complete dataset required for the transcript.

    Returns:
        str: Absolute file path to the generated PDF.
    """
    return _build_pdf_sync(transcript_data)


def _build_pdf_sync(transcript_data: dict) -> str:
    """
    The actual synchronous function that renders the PDF.
    Renders an HTML template with Jinja2 then converts to PDF with WeasyPrint.
    The PDF is saved temporarily and the file path is returned.
    The calling router deletes the file after sending it to the client.

    Parameters:
        transcript_data (dict): Contains:
            student (dict): Student profile — name, matric, department, programme
            results (list[dict]): All approved course results
            semester_gpas (dict): GPA summary keyed by semester_id
            final_cgpa (float): Overall CGPA
            degree_classification (str): e.g. First Class Honours
            purpose (str): Reason for transcript request

    Returns:
        str: Absolute file path to the generated PDF.
    """
    student = transcript_data["student"]
    results = transcript_data["results"]
    semester_gpas = transcript_data["semester_gpas"]
    final_cgpa = transcript_data["final_cgpa"]
    degree_classification = transcript_data["degree_classification"]

    # group course results by semester for template rendering
    # {(session_name, semester_number, level): [list of courses]}
    semesters = {}
    for result in results:
        key = (
            result["session_name"],
            result["semester_number"],
            result.get("level", "N/A"),
        )
        if key not in semesters:
            semesters[key] = []
        semesters[key].append(result)

        # sort semesters chronologically | lambda is creating a sorting priority
        sorted_semesters = sorted(semesters.items(), key=lambda x: (x[0][0], x[0][1]))

        semester_blocks = []
        for (session_name, semester_number, level), courses in sorted_semesters:
            semester_id = courses[0]["semester_id"]
            gpa_data = semester_gpas.get(semester_id, {})

            semester_blocks.append(
                {
                    "session_name": session_name,
                    "semester_number": semester_number,
                    "level": level,
                    "courses": courses,
                    "gpa": gpa_data.get("gpa", 0.0),
                    "cgpa": gpa_data.get("cgpa", 0.0),
                    "total_units": gpa_data.get("total_units_registered", 0),
                }
            )

        template = template_env.get_template("transcript.html")
        html_content = template.render(
            student=student,
            semester_blocks=semester_blocks,
            final_cgpa=final_cgpa,
            degree_classification=degree_classification,
            generated_at=datetime.now().strftime("%B %d, %Y at %I:%M %p"),
            institution_name=os.getenv(
                "INSTITUTION_NAME", "Air Force Institute of Technology"
            ),
            institution_address=os.getenv(
                "INSTITUTION_ADDRESS", "PMB 2104, Kaduna, Nigeria"
            ),
        )

    # generate unique filename using matric number and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"transcript_{student['matric_number']}_{timestamp}.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)

    HTML(string=html_content).write_pdf(output_path)

    logger.info(f"Transcript PDF generated: {output_path}")
    return output_path
