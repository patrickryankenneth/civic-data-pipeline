from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, UTC

class Vendor(BaseModel):
    name: str = Field(..., description="Local Vendor Name")
    local_contract_count: int
    total_spend: float

class FederalContractRecord(BaseModel):
    recipient_id: str
    award_amount: float
    fiscal_year: int
    agency: str

class UnifiedVendorProfile(BaseModel):
    vendor_name: str
    recipient_id: Optional[str]
    total_local_spend: float
    total_federal_spend: float
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
