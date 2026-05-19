import logging
from datetime import datetime
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from src.db.database import AsyncSessionLocal
from src.db.models import Certificate, CertificateStatus
from src.api.webhooks import router as webhooks_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
)
logger = logging.getLogger("API")

app = FastAPI(title="AMCO Clinic API")


app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])


def render_404_page():
    try:
        with open("src/services/404.html", "r", encoding="utf-8") as f:
            template_str = f.read()
        template = Template(template_str)
        return HTMLResponse(content=template.render(), status_code=404)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>404 Not Found</h1>", status_code=404)
    

@app.get("/api/cert/{cert_id}", response_class=HTMLResponse)
async def view_certificate(cert_id: str):
    """
    Отображает сертификат или страницу 404, если ID неверный или сертификат не найден.
    """
    try:
        uuid.UUID(cert_id)
    except ValueError:
        logger.warning(f"Invalid UUID format accessed: {cert_id}")
        return render_404_page()

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(Certificate).where(Certificate.id == cert_id))
            cert = result.scalar_one_or_none()
        except DBAPIError as e:
            logger.error(f"Database error while fetching cert {cert_id}: {e}")
            return render_404_page()

        if not cert:
            return render_404_page()

        if cert.status != CertificateStatus.issued:

            return HTMLResponse(
                content="<div style='display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif; text-align:center;'>"
                        "<h1>Сертификат еще не оплачен или не активен</h1></div>",
                status_code=403
            )

        try:
            with open("src/services/cert.html", "r", encoding="utf-8") as f:
                template_str = f.read()
        except FileNotFoundError:
            logger.error("Файл шаблона cert.html не найден")
            return HTMLResponse(content="<h1>Template Error</h1>", status_code=500)

        template = Template(template_str)
        
        html_content = template.render(
            amount=f"{cert.amount:,}".replace(",", " "),
            recipient_name=cert.recipient_name or "Счастливчику",
            message=cert.message,
            issued_date=cert.issued_at.strftime("%d.%m.%Y") if cert.issued_at else datetime.now().strftime("%d.%m.%Y"),
            cert_id=str(cert.id).upper()[:8] 
        )

        return HTMLResponse(content=html_content)


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, full_path: str):
    """
    Ловит все неизвестные GET запросы (кроме /api/webhooks...) и отдает страницу 404.
    """
    if full_path.startswith("api/"):
        return render_404_page()
        
    return render_404_page()