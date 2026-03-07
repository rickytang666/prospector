from pydantic import BaseModel
from typing import Optional

# data schemas - normalized

class RawCompany(BaseModel):
    name: str
    url: Optional[str] = None
    source_url: str
    source_type: str


class AffinityEvidence(BaseModel):
    type: str
    text: str
    source_url: str


class ContactRoute(BaseModel):
    type: str
    value: str


class RawDocument(BaseModel):
    url: str
    title: str
    raw_text: str
    fetched_at: str


class Entity(BaseModel):
    id: str
    name: str
    entity_type: str = "provider"
    canonical_url: Optional[str] = None
    summary: Optional[str] = None
    source_urls: list[str] = []
    raw_documents: list[RawDocument] = []
    tags: list[str] = []
    support_types: list[str] = []
    waterloo_affinity_evidence: list[AffinityEvidence] = []
    contact_routes: list[ContactRoute] = []
