from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    department_id: int | None
    model_config = ConfigDict(from_attributes=True)


class ComplaintCreate(BaseModel):
    title: str = Field(min_length=5, max_length=180)
    description: str = Field(min_length=10, max_length=5000)
    category: Literal["Roads", "Sanitation", "Streetlights", "Water & Drainage", "Public Infrastructure", "Other"]
    address: str = Field(min_length=3, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class ComplaintOut(BaseModel):
    id: int
    reference: str
    citizen_id: int
    department_id: int | None
    department_name: str
    title: str
    description: str
    category: str
    address: str
    latitude: float | None
    longitude: float | None
    priority: str
    status: str
    resolution_details: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StatusUpdate(BaseModel):
    status: str
    note: str = Field(default="", max_length=500)
    resolution_details: str | None = Field(default=None, max_length=5000)


class AssignIn(BaseModel):
    department_id: int


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)


class RoleUpdate(BaseModel):
    role: Literal["citizen", "official", "admin"]
    department_id: int | None = None


class AIAnalysisIn(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=5, max_length=5000)
    category: Literal["Roads", "Sanitation", "Streetlights", "Water & Drainage", "Public Infrastructure", "Other"] | None = None


class DuplicateCheckIn(AIAnalysisIn):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class GuidanceIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
