import asyncio
import random
import logging


logger = logging.getLogger(__name__)


class PopulationCalculator:
    """Сервис расчета населения"""
    
    def __init__(self, min_delay: int = 5, max_delay: int = 10):
        self.min_delay = min_delay
        self.max_delay = max_delay
    
    async def calculate_total_population(self, territory_area: float, orders: list) -> int:
        """Расчет общего населения"""
        total = 0
        
        for order in orders:
            building_density = int(order.get("building_density", 0))
            people_per_building = int(order.get("people_per_building", 0))
            
            if building_density > 0 and people_per_building > 0:
                population = territory_area * building_density * people_per_building
                total += int(population)
        
        # Добавляем случайное отклонение (±10%)
        deviation = 0.9 + random.random() * 0.2
        final_population = int(total * deviation)
        
        logger.info(f"Calculated population: {total} -> {final_population} (deviation: {deviation:.2f})")
        return final_population
    
    async def simulate_calculation(self) -> None:
        """Имитация задержки расчета"""
        delay = random.randint(self.min_delay, self.max_delay)
        logger.info(f"Simulating calculation delay: {delay} seconds")
        await asyncio.sleep(delay)


calculator = PopulationCalculator()