from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Frontend Views"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/login", include_in_schema=False)
def login_page(request: Request):
    """Renders the login HTML page."""
    return templates.TemplateResponse(request=request, name="auth/login.html")


# When Jinja2 renders an HTML template, it needs the request object to know the "context" of the web page


@router.get("/dashboard/registrar", include_in_schema=False)
def registrar_dashboard(request: Request):
    """Renders the registrar dashboard."""
    return templates.TemplateResponse(request=request, name="dashboard/registrar.html")


@router.get("/dashboard/lecturer", include_in_schema=False)
def lecturer_dashboard(request: Request):
    """Renders the lecturer dashboard."""
    return templates.TemplateResponse(request=request, name="dashboard/lecturer.html")


@router.get("/dashboard/hod", include_in_schema=False)
def hod_dashboard(request: Request):
    """Renders the HOD dashboard."""
    return templates.TemplateResponse(request=request, name="dashboard/hod.html")


@router.get("/dashboard/student", include_in_schema=False)
def student_dashboard(request: Request):
    """Renders the student dashboard."""
    return templates.TemplateResponse(request=request, name="dashboard/student.html")


@router.get("/dashboard/exam-officer", include_in_schema=False)
def exam_officer_dashboard(request: Request):
    """Renders the exam officer dashboard."""
    return templates.TemplateResponse(
        request=request, name="dashboard/exam_officer.html"
    )
