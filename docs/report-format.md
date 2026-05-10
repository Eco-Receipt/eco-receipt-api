```python
class GreenReport(BaseModel):
    productName: str
    brand: str
    score: int = Field(ge=0, le=100)
    grade: str
    summary: str
    positiveSignals: list[str] = []
    riskSignals: list[str] = []
    greenwashingRisk: Literal["Low", "Medium", "High", "Critical"] = "Medium"
    findings: list[str] = []
    evidences: list[Evidence] = []
    alternatives: list[str] = []
    createdAt: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
```