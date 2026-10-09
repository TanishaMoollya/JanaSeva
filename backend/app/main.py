from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.ai import analyze, find_duplicates, guidance, resolution_support
from app.core.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.models import Attachment, AuditLog, Complaint, Department, Notification, StatusHistory, User
from app.schemas import AIAnalysisIn, AssignIn, ComplaintCreate, ComplaintOut, DepartmentCreate, DuplicateCheckIn, GuidanceIn, LoginIn, RegisterIn, RoleUpdate, StatusUpdate, UserOut
from app.security import create_token, current_user, hash_password, require_roles, verify_password

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        for name in ["Roads Department", "Sanitation Department", "Electrical Department", "Water Department", "Public Works Department", "Municipal Services"]:
            if not db.scalar(select(Department).where(Department.name == name)):
                db.add(Department(name=name))
        db.commit()
    yield

app = FastAPI(title=settings.app_name, description="Public grievance reporting and tracking portal", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type"])

def can_access(user: User, complaint: Complaint):
    if user.role == "admin" or complaint.citizen_id == user.id:
        return True
    return user.role == "official" and user.department_id == complaint.department_id

@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}

@app.post("/api/auth/register", response_model=UserOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "An account with this email already exists")
    user = User(name=data.name.strip(), email=data.email.lower(), password_hash=hash_password(data.password), role="citizen")
    db.add(user); db.commit(); db.refresh(user)
    return user

@app.post("/api/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    return {"access_token": create_token(user), "token_type": "bearer", "user": UserOut.model_validate(user)}

@app.get("/api/users/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

@app.get("/api/departments")
def departments(db: Session = Depends(get_db)):
    return db.scalars(select(Department).order_by(Department.name)).all()

@app.post("/api/departments", status_code=201)
def create_department(data: DepartmentCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    if db.scalar(select(Department).where(Department.name == data.name.strip())):
        raise HTTPException(409, "That department already exists")
    department = Department(name=data.name.strip(), description=data.description.strip())
    db.add(department); db.commit(); db.refresh(department)
    return department

@app.get("/api/admin/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    return db.scalars(select(User).order_by(User.created_at.desc()).limit(200)).all()

@app.patch("/api/admin/users/{user_id}/role", response_model=UserOut)
def update_user_role(user_id: int, data: RoleUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    target = db.get(User, user_id)
    if not target: raise HTTPException(404, "User not found")
    if target.id == user.id and data.role != "admin": raise HTTPException(409, "You cannot remove your own administrator access")
    if data.role == "official":
        if data.department_id is None or not db.get(Department, data.department_id): raise HTTPException(422, "An existing department is required for officials")
        target.department_id = data.department_id
    else:
        target.department_id = None
    target.role = data.role
    db.commit(); db.refresh(target)
    return target

@app.post("/api/complaints", response_model=ComplaintOut, status_code=201)
def create_complaint(data: ComplaintCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("citizen", "admin"))):
    suggestion = analyze(data.title, data.description, data.category)
    department = db.scalar(select(Department).where(Department.name == suggestion["department"]))
    complaint = Complaint(reference=f"JS-{uuid4().hex[:8].upper()}", citizen_id=user.id, title=data.title.strip(), description=data.description.strip(), category=suggestion["category"], address=data.address.strip(), latitude=data.latitude, longitude=data.longitude, department_id=department.id if department else None, priority=suggestion["priority"])
    db.add(complaint); db.flush()
    db.add(StatusHistory(complaint_id=complaint.id, actor_id=user.id, new_status="Submitted", note="Complaint submitted"))
    db.commit(); db.refresh(complaint)
    return complaint

@app.get("/api/complaints", response_model=list[ComplaintOut])
def list_complaints(status: str | None = None, category: str | None = None, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Complaint).order_by(Complaint.created_at.desc()).offset(skip).limit(limit)
    if user.role == "citizen": query = query.where(Complaint.citizen_id == user.id)
    elif user.role == "official": query = query.where(Complaint.department_id == user.department_id)
    if status: query = query.where(Complaint.status == status)
    if category: query = query.where(Complaint.category == category)
    return db.scalars(query).all()

@app.get("/api/complaints/{complaint_id}", response_model=ComplaintOut)
def complaint_detail(complaint_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Complaint, complaint_id)
    if not item: raise HTTPException(404, "Complaint not found")
    if not can_access(user, item): raise HTTPException(403, "You cannot access this complaint")
    return item

@app.get("/api/complaints/{complaint_id}/history")
def complaint_history(complaint_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Complaint, complaint_id)
    if not item: raise HTTPException(404, "Complaint not found")
    if not can_access(user, item): raise HTTPException(403, "You cannot access this complaint")
    return db.scalars(select(StatusHistory).where(StatusHistory.complaint_id == complaint_id).order_by(StatusHistory.created_at)).all()

@app.patch("/api/complaints/{complaint_id}/status", response_model=ComplaintOut)
def update_status(complaint_id: int, data: StatusUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("official", "admin"))):
    item = db.get(Complaint, complaint_id)
    if not item: raise HTTPException(404, "Complaint not found")
    if user.role == "official" and item.department_id != user.department_id: raise HTTPException(403, "This complaint is outside your department")
    allowed = {"Submitted", "Under Review", "Assigned", "In Progress", "Resolved", "Closed", "Reopened"}
    transitions = {"Submitted": {"Under Review", "Assigned"}, "Under Review": {"Assigned", "In Progress"}, "Assigned": {"In Progress"}, "In Progress": {"Resolved"}, "Resolved": {"Closed", "Reopened"}, "Closed": {"Reopened"}, "Reopened": {"Under Review", "Assigned", "In Progress"}}
    if data.status not in allowed: raise HTTPException(422, "Unknown complaint status")
    if data.status != item.status and data.status not in transitions.get(item.status, set()): raise HTTPException(409, f"Cannot move from {item.status} to {data.status}")
    if data.status == "Resolved" and not (data.resolution_details and data.resolution_details.strip()): raise HTTPException(422, "Resolution details are required")
    if data.status == "Resolved" and not item.attachments: raise HTTPException(422, "Upload resolution evidence before resolving this complaint")
    if data.status != item.status:
        old = item.status; item.status = data.status
        if data.resolution_details: item.resolution_details = data.resolution_details.strip()
        db.add(StatusHistory(complaint_id=item.id, actor_id=user.id, old_status=old, new_status=item.status, note=data.note.strip()))
        db.add(Notification(user_id=item.citizen_id, complaint_id=item.id, message=f"{item.reference} status changed to {item.status}"))
        db.commit(); db.refresh(item)
    return item

@app.post("/api/complaints/{complaint_id}/assign", response_model=ComplaintOut)
def assign_complaint(complaint_id: int, data: AssignIn, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    item = db.get(Complaint, complaint_id); department = db.get(Department, data.department_id)
    if not item or not department: raise HTTPException(404, "Complaint or department not found")
    item.department_id = department.id
    db.add(AuditLog(complaint_id=item.id, actor_id=user.id, action="assignment", detail=f"Assigned to {department.name}"))
    db.commit(); db.refresh(item); return item

@app.get("/api/map/complaints")
def map_complaints(db: Session = Depends(get_db)):
    items = db.scalars(select(Complaint).where(Complaint.latitude.is_not(None), Complaint.longitude.is_not(None)).order_by(Complaint.created_at.desc()).limit(500)).all()
    # Grid rounding reduces precision; no citizen identity or street address is returned.
    return [{"reference": x.reference, "category": x.category, "status": x.status, "latitude": round(x.latitude, 2), "longitude": round(x.longitude, 2)} for x in items]

@app.get("/api/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db), user: User = Depends(require_roles("official", "admin"))):
    q = select(Complaint)
    if user.role == "official": q = q.where(Complaint.department_id == user.department_id)
    items = db.scalars(q).all()
    return {"total": len(items), "open": sum(i.status not in {"Resolved", "Closed"} for i in items), "resolved": sum(i.status in {"Resolved", "Closed"} for i in items), "by_status": {s: sum(i.status == s for i in items) for s in ["Submitted", "Under Review", "Assigned", "In Progress", "Resolved", "Closed", "Reopened"]}}

@app.post("/api/complaints/{complaint_id}/attachments", status_code=201)
async def upload_attachment(complaint_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Complaint, complaint_id)
    if not item: raise HTTPException(404, "Complaint not found")
    if not can_access(user, item): raise HTTPException(403, "You cannot access this complaint")
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if file.content_type not in allowed: raise HTTPException(415, "Upload a JPEG, PNG, or WebP image")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024: raise HTTPException(413, "Image exceeds the upload size limit")
    valid_signature = ((file.content_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff")) or
                       (file.content_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n")) or
                       (file.content_type == "image/webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP"))
    if not valid_signature: raise HTTPException(415, "File content is not a supported image")
    stored = f"{uuid4().hex}{allowed[file.content_type]}"
    Path(settings.upload_dir, stored).write_bytes(content)
    row = Attachment(complaint_id=item.id, uploader_id=user.id, filename=(file.filename or "image")[:255], stored_name=stored, content_type=file.content_type)
    db.add(row); db.commit()
    return {"id": row.id, "filename": row.filename}

@app.get("/api/complaints/{complaint_id}/attachments")
def list_attachments(complaint_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Complaint, complaint_id)
    if not item: raise HTTPException(404, "Complaint not found")
    if not can_access(user, item): raise HTTPException(403, "You cannot access this complaint")
    return [{"id": row.id, "filename": row.filename, "content_type": row.content_type, "created_at": row.created_at} for row in item.attachments]

@app.get("/api/attachments/{attachment_id}")
def get_attachment(attachment_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.get(Attachment, attachment_id)
    if not row or not can_access(user, row.complaint): raise HTTPException(404, "Attachment not found")
    path = Path(settings.upload_dir, row.stored_name)
    if not path.exists(): raise HTTPException(404, "Attachment file not found")
    return FileResponse(path, media_type=row.content_type, filename=row.filename)

@app.get("/api/notifications")
def notifications(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50)).all()

@app.patch("/api/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.get(Notification, notification_id)
    if not item or item.user_id != user.id: raise HTTPException(404, "Notification not found")
    item.is_read = True
    db.commit()
    return {"id": item.id, "is_read": item.is_read}

@app.post("/api/ai/analyze")
def ai_analyze(data: AIAnalysisIn, user: User = Depends(current_user)):
    return analyze(data.title, data.description, data.category)

@app.post("/api/ai/possible-duplicates")
def possible_duplicates(data: DuplicateCheckIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Complaint).order_by(Complaint.created_at.desc()).limit(300)
    if data.category: query = query.where(Complaint.category == data.category)
    candidates = db.scalars(query).all()
    return {"matches": find_duplicates(data.title, data.description, data.category, data.latitude, data.longitude, candidates),
            "notice": "Possible matches are advisory. Your report will not be rejected automatically."}

@app.post("/api/ai/guidance")
def ai_guidance(data: GuidanceIn, user: User = Depends(current_user)):
    return guidance(data.question)

@app.get("/api/complaints/{complaint_id}/resolution-support")
def complaint_resolution_support(complaint_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("official", "admin"))):
    item = db.get(Complaint, complaint_id)
    if not item: raise HTTPException(404, "Complaint not found")
    if user.role == "official" and item.department_id != user.department_id: raise HTTPException(403, "This complaint is outside your department")
    return resolution_support(item.title, item.description, item.status)
