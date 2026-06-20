from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Template
from app.schemas import TemplateCreate, TemplateOut

router = APIRouter(tags=["templates"])


@router.post("/templates", response_model=TemplateOut, status_code=201)
def create_template(payload: TemplateCreate, db: Session = Depends(get_db)):
    """Create a reusable message template. Use {{variable}} placeholders in the body/subject."""
    existing = db.query(Template).filter(Template.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Template named '{payload.name}' already exists")

    template = Template(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/templates/{template_id}", response_model=TemplateOut)
def get_template(template_id: str, db: Session = Depends(get_db)):
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template
