from pydantic import BaseModel
from typing import Optional


class DefectItem(BaseModel):
    defect_id: str
    code: str
    name: str
    category: str


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
    defect_ids: list[str]
    primary_diagnosis: Optional[str] = None
    clinical_notes: Optional[str] = None


class DashboardResponse(BaseModel):
    total_patients: int
    approved_patients: int
    pending_patients: int


class TherapistProfileResponse(BaseModel):
    therapist_id: str
    full_name: str
    email: str
    therapist_code: str
    license_number: Optional[str]
    specialization: Optional[str]
    years_of_experience: Optional[int]
