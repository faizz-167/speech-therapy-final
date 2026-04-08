from pydantic import BaseModel, Field, field_validator
from typing import Optional


class DefectItem(BaseModel):
    defect_id: str
    code: str
    name: str
    category: str


class NotificationOut(BaseModel):
    id: str
    notification_type: str
    message: str
    is_read: bool
    created_at: str
    patient_id: Optional[str]
    attempt_id: Optional[str]


class PatientListItem(BaseModel):
    patient_id: str
    full_name: str
    email: str
    status: str
    date_of_birth: str
    gender: Optional[str]
    pre_assigned_defect_ids: Optional[dict]
    created_at: str

    model_config = {"from_attributes": True}


class ApprovePatientRequest(BaseModel):
    defect_ids: list[str] = Field(min_length=1)
    primary_diagnosis: Optional[str] = Field(default=None, max_length=200)
    clinical_notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("defect_ids")
    @classmethod
    def validate_defect_ids(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for defect_id in value:
            normalized = defect_id.strip()
            if not normalized:
                raise ValueError("defect_ids cannot contain blank values")
            if normalized not in seen:
                seen.add(normalized)
                cleaned.append(normalized)
        if not cleaned:
            raise ValueError("At least one defect must be selected")
        return cleaned

    @field_validator("primary_diagnosis", "clinical_notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class DashboardResponse(BaseModel):
    total_patients: int
    approved_patients: int
    pending_patients: int
    patients_without_baseline: int = 0
    patients_without_approved_plan: int = 0
    plans_pending_approval: int = 0
    unread_notification_count: int = 0


class TherapistProfileResponse(BaseModel):
    therapist_id: str
    full_name: str
    email: str
    therapist_code: str
    license_number: Optional[str]
    specialization: Optional[str]
    years_of_experience: Optional[int]
