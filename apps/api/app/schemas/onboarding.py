from pydantic import BaseModel


class OnboardingAnswers(BaseModel):
    learning_challenge: str
    preferred_method: str
    obstacle: str
    goal: str


class OnboardingResponse(BaseModel):
    success: bool = True
