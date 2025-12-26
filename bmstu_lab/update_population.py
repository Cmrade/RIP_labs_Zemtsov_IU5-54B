#!/usr/bin/env python
import sys
import os
import django
import time
import random

# Настройка Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoProject.settings')
django.setup()

from bmstu_lab.models import Application, Orders  # Orders все еще существует как модель


def update_population(density_calculation_id):  # application_id -> density_calculation_id
    """Обновляет поле calculated_population для расчета плотности"""
    try:
        print(f"[UPDATE_POPULATION] Начало обновления для расчета плотности {density_calculation_id}")

        # Имитируем долгую операцию (5-10 секунд)
        delay = 5 + random.randint(0, 5)
        print(f"[UPDATE_POPULATION] Задержка: {delay} секунд")
        time.sleep(delay)

        # Получаем расчет плотности
        density_calculation = Application.objects.get(id=density_calculation_id)

        # Проверяем данные
        if not density_calculation.territory_area or density_calculation.territory_area <= 0:
            print(f"[UPDATE_POPULATION] Ошибка: не указана площадь территории")
            return False

        if not density_calculation.orderinapplication_set.exists():
            print(f"[UPDATE_POPULATION] Ошибка: в расчете плотности нет типов населения")
            return False

        # Рассчитываем численность населения
        total_population = 0

        for population_in_calc in density_calculation.orderinapplication_set.all():
            population = population_in_calc.order
            if population.building_density and population.people_per_building:
                # Формула: площадь × плотность × человек
                population_calc = float(density_calculation.territory_area) * population.building_density * population.people_per_building
                total_population += population_calc

        # Добавляем случайное отклонение (±10%)
        deviation = 0.9 + random.random() * 0.2  # от 0.9 до 1.1
        final_population = int(total_population * deviation)

        # Обновляем запись в базе данных
        Application.objects.filter(id=density_calculation_id).update(
            calculated_population=final_population
        )

        print(f"[UPDATE_POPULATION] Успех! Расчет плотности {density_calculation_id} обновлен: {final_population} человек")
        return True

    except Application.DoesNotExist:
        print(f"[UPDATE_POPULATION] Ошибка: расчет плотности {density_calculation_id} не найден")
        return False
    except Exception as e:
        print(f"[UPDATE_POPULATION] Ошибка: {str(e)}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python update_population.py <density_calculation_id>")
        sys.exit(1)

    try:
        density_calculation_id = int(sys.argv[1])
        success = update_population(density_calculation_id)
        sys.exit(0 if success else 1)
    except ValueError:
        print("Ошибка: density_calculation_id должен быть числом")
        sys.exit(1)