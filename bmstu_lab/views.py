from django.shortcuts import render
from django.http import HttpResponse
from datetime import date
from .models import Orders, OrderInApplication
from .models import Application
from django.db import connection
from django.contrib.auth.models import User
from django.shortcuts import redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth.decorators import login_required

populations = [{'title': 'Древний город', 'image': 'http://localhost:9000/static/img/town.png', 'main_information': 'плотность ≈ 110 ч/га', 'more_information': '    Это основная жилая зона с усадебной застройкой. Плотность здесь была заметно ниже.\n\n    плотность населения ≈ 110 ч/га\n    плотность застройки ≈ 17 усадеб/га\n    количество жильцов в усадьбе ≈ 6 ч/ус', 'id': 1, 'app_flag': False},
            {'title': 'Крепость', 'image': 'http://localhost:9000/static/img/tower.png', 'main_information': 'плотность ≈ 135 ч/га', 'more_information': '    Здесь наблюдалась максимальная плотность, обусловленная дефицитом защищенного пространства. \n \n    плотность населения ≈ 135 ч/га\n    плотность застройки ≈ 25 усадеб/га\n    количество жильцов в усадьбе ≈ 5 ч/ус', 'id': 2, 'app_flag': True},
            {'title': 'Село', 'image': 'http://localhost:9000/static/img/village.png', 'main_information': 'плотность ≈ 75 ч/га', 'more_information': '    Плотность застройки в сельских поселениях была низкой и определялась сельскохозяйственными потребностями.\n \n    плотность населения ≈ 75 ч/га\n    плотность застройки ≈ 10 усадеб/га\n    количество жильцов в усадьбе ≈ 8 ч/ус', 'id': 3, 'app_flag': True},]
application = {1: [2, 3]}
ans_search=[]
ITEMS_IN_CART = 2

def hello(request):
    return render(request, 'index.html', { 'data' : {
        'current_date': date.today(),
        'list': ['python', 'django', 'html']
    }})

@login_required
def GetDensityCalculation(request, id):
    user = request.user

    try:
        density_calculation = Application.objects.get(id=id, client=user)

        if density_calculation.status == Application.ApplicationStatus.DELETED:
            raise Http404("Расчет плотности не найден")
    except Application.DoesNotExist:
        population_in_density_calculation_list = []
    else:
        population_in_density_calculation_list = OrderInApplication.objects.filter(application=density_calculation)

    populations_in_draft_density_calculation = OrderInApplication.objects.filter(
        application__client=user,
        application__status=Application.ApplicationStatus.DRAFT
    ).count()

    return render(request,
                  'calculate_of_population.html',
                  {
                      "data": {
                          "density_calculation_id": get_current_density_calculation_id("Admin1"),
                          "population_in_density_calculation_list": population_in_density_calculation_list,
                      }
                  })

def get_population_page(request, id):

    query = "SELECT title, image, more_information FROM bmstu_lab_orders WHERE id = %s"

    with connection.cursor() as cursor:
        cursor.execute(query, [id])
        row = cursor.fetchone()

    if not row:
        return render(request, 'information_about_object.html')

    return render(request,
                  "information_about_object.html",
                  {
                      "data": {
	                      "id": id,
                          "title": row[0],
                          'image': row[1],
                          "more_information": row[2],
                      },
                  })


# Обновите функции для использования request.user
def get_populations_list_page(request):
    user = request.user
    population_title = request.GET.get('title', '')

    if user.is_authenticated:
        populations_in_draft_density_calculation = OrderInApplication.objects.filter(
            application__client=user,
            application__status=Application.ApplicationStatus.DRAFT
        ).count()
    else:
        populations_in_draft_density_calculation = 0

    return render(request,
                  'archaeological_objects.html',
                  {
                      "data": {
                          "populations": Orders.objects.filter(title__istartswith=population_title),
                          "items_in_cart": populations_in_draft_density_calculation,
                          "product_title": population_title,
                          "density_calculation_id": get_current_density_calculation_id(user) if user.is_authenticated else None,
                          "user": user
                      }
                  })


def add_to_density_calculation(request, population_id):
    population = get_object_or_404(Orders, id=population_id)

    user = User.objects.get(username="Admin1")
    density_calculation, created = Application.objects.get_or_create(
        client=user,
        status=Application.ApplicationStatus.DRAFT,
        defaults={
            'client_id': 1,
            'status': Application.ApplicationStatus.DRAFT,
        }
    )

    OrderInApplication.objects.get_or_create(
        application=density_calculation,
        order=population,
        defaults={'comment': ''}
    )

    return redirect('populations_url')

def delete_density_calculation(request, density_calculation_id):
    density_calculation = get_object_or_404(Application, id=density_calculation_id)

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE bmstu_lab_application SET status = 'DELETED' WHERE id = %s",
            [density_calculation_id]
        )

    density_calculation, created = Application.objects.get_or_create(
        client_id=1,
        status=Application.ApplicationStatus.DRAFT,
        defaults={
            'client_id': 1,
            'status': Application.ApplicationStatus.DRAFT,
        }
    )

    return redirect('populations_url')

def sendText(request):
    if request.method == 'GET':
        input_text = request.GET.get('search', '')

        query = "SELECT title, image, main_information FROM bmstu_lab_orders WHERE title = %s"

        with connection.cursor() as cursor:
            cursor.execute(query, [input_text])
            row = cursor.fetchone()

        if not row:
            return render(request, 'archaeological_objects.html')

        return render(request,
                      "archaeological_objects.html",
                      {
                          "data": {
                              "id": id,
                              "title": row[0],
                              'image': row[1],
                              "main_information": row[2],
                          },
                      })
    return HttpResponse("Method not allowed", status=405)

def get_current_density_calculation_id(user):
    density_calculation = get_object_or_404(Application, status=Application.ApplicationStatus.DRAFT)
    return density_calculation.id

def update_comment(request, population_in_density_calculation_id):
    if request.method == 'POST':
        population_in_density_calculation = get_object_or_404(OrderInApplication, id=population_in_density_calculation_id)
        new_comment = request.POST.get('comment', '')

        # Обновляем комментарий через ORM
        population_in_density_calculation.comment = new_comment
        population_in_density_calculation.save()

        return redirect('density_calculation_url', id=population_in_density_calculation.application.id)