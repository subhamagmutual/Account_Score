"""FastAPI request/response models."""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    """Request for single physician score."""

    npi: int = Field(..., description="National Provider Identifier")
    specialty: str = Field(..., description="Medical specialty")
    state: str = Field(..., description="State code")
    **kwargs  # Additional clinical features as needed

    class Config:
        schema_extra = {
            "example": {
                "npi": 1234567890,
                "specialty": "Surgery",
                "state": "CA",
            }
        }


class BatchScoreRequest(BaseModel):
    """Request for batch scoring."""

    physicians: List[ScoreRequest] = Field(
        ..., description="List of physicians to score"
    )
    max_records: Optional[int] = Field(
        None, description="Maximum records to process"
    )


class ComponentScores(BaseModel):
    """Component scores breakdown."""

    adequacy: float = Field(..., description="Adequacy score (1-10)")
    capacity: float = Field(..., description="Capacity score (1-10)")
    appetite: float = Field(..., description="Appetite score (1-10)")
    environment: float = Field(..., description="Environment score (1-10)")


class ScoreResponse(BaseModel):
    """Response with physician score."""

    npi: int
    composite_score: float = Field(..., description="Overall composite score (1-10)")
    components: ComponentScores
    credibility_z_factor: Optional[float] = Field(
        None, description="Credibility weighting factor (0-1)"
    )
    scoring_timestamp: str
    model_version: str

    class Config:
        schema_extra = {
            "example": {
                "npi": 1234567890,
                "composite_score": 5.5,
                "components": {
                    "adequacy": 5.2,
                    "capacity": 5.8,
                    "appetite": 5.6,
                    "environment": 5.0,
                },
                "credibility_z_factor": 0.95,
                "scoring_timestamp": "2026-07-28T10:30:00Z",
                "model_version": "1.0.0",
            }
        }


class BatchScoreResponse(BaseModel):
    """Response with batch scores."""

    total_records: int
    successful: int
    failed: int
    scores: List[ScoreResponse]
    processing_time_ms: float


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status (healthy/degraded/unhealthy)")
    version: str = Field(..., description="API version")
    model_version: str = Field(..., description="Scoring model version")
    uptime_seconds: int = Field(..., description="Uptime in seconds")
    last_scoring_timestamp: Optional[str] = Field(
        None, description="Timestamp of last scoring operation"
    )
    total_scores_generated: int = Field(
        ..., description="Total scores generated since startup"
    )


class MonitoringMetrics(BaseModel):
    """Current monitoring metrics."""

    mean_score: float
    median_score: float
    std_dev: float
    gini_coefficient: float
    null_rate: float = Field(..., description="Percentage of null scores")
    psi_vs_baseline: Optional[float] = Field(
        None, description="PSI vs baseline distribution"
    )
    anomalies_detected: int = Field(..., description="Number of anomalies detected")
    data_quality_issues: int = Field(..., description="Number of data quality issues")


class ConfigResponse(BaseModel):
    """Current configuration."""

    version: str
    scoring_weights: Dict[str, Any] = Field(..., description="Component weights")
    monitoring_config: Dict[str, Any] = Field(..., description="Monitoring configuration")
    model_date: str = Field(..., description="Model/configuration date")


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Additional details")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
