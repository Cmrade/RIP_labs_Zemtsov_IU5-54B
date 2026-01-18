from typing import List, Optional, Dict, Any


# Простые модели без pydantic
class OrderData:
    def __init__(self, building_density: float, people_per_building: float):
        self.building_density = building_density
        self.people_per_building = people_per_building
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            building_density=data.get("building_density", 0.0),
            people_per_building=data.get("people_per_building", 0.0)
        )


# Простые функции для работы с JSON
def success_response(data: dict = None) -> dict:
    return {"status": "success", "data": data or {}}


def error_response(message: str, details: str = None) -> dict:
    return {
        "status": "error",
        "message": message,
        "details": details
    }