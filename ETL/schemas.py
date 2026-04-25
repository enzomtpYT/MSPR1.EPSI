from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class DailyFoodRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    Food_Item: str = Field(alias="Food_Item")
    Calories: float = Field(alias="Calories (kcal)")
    Protein: float = Field(alias="Protein (g)")
    Carbohydrates: float = Field(alias="Carbohydrates (g)")
    Fat: float = Field(alias="Fat (g)")
    Fiber: float = Field(alias="Fiber (g)")
    Sugars: float = Field(alias="Sugars (g)")
    Sodium: float = Field(alias="Sodium (mg)")
    Cholesterol: float = Field(alias="Cholesterol (mg)")
    Category: Optional[str] = Field(None, alias="Category")
    Meal_Type: Optional[str] = Field(None, alias="Meal_Type")

class DietRecRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    Patient_ID: str = Field(alias="Patient_ID")
    Age: int = Field(alias="Age")
    Gender: str = Field(alias="Gender")
    Weight_kg: float = Field(alias="Weight_kg")
    Height_cm: float = Field(alias="Height_cm")
    Allergies: Optional[str] = Field(None, alias="Allergies")
    Dietary_Restrictions: Optional[str] = Field(None, alias="Dietary_Restrictions")
    Diet_Recommendation: Optional[str] = Field(None, alias="Diet_Recommendation")

class ExerciseRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    Age: int = Field(alias="Age")
    Gender: str = Field(alias="Gender")
    Weight: float = Field(alias="Weight (kg)")
    Height: float = Field(alias="Height (m)")
    Max_BPM: int = Field(alias="Max_BPM")
    Avg_BPM: int = Field(alias="Avg_BPM")
    Resting_BPM: int = Field(alias="Resting_BPM")
    Session_Duration: float = Field(alias="Session_Duration (hours)")
    Workout_Type: str = Field(alias="Workout_Type")