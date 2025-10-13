from django.shortcuts import render
from django.http import HttpResponse
from datetime import date
from .models import Orders, OrderInApplication
from .models import Application
from django.db import connection
from django.contrib.auth.models import User
from django.shortcuts import redirect, get_object_or_404
from django.http import Http404

orders = [{'title': 'Древний город', 'image': 'http://localhost:9000/static/img/town.png', 'main_information': 'плотность ≈ 110 ч/га', 'more_information': '    Это основная жилая зона с усадебной застройкой. Плотность здесь была заметно ниже.\n\n    плотность населения ≈ 110 ч/га\n    плотность застройки ≈ 17 усадеб/га\n    количество жильцов в усадьбе ≈ 6 ч/ус', 'id': 1, 'app_flag': False},
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
'''
def GetOrders(request):
    return render(request, 'orders.html', {'data': {
        'orders': orders,
    }})

def GetApplication(request, id):
    return render(request, 'application_page.html', {'data': {
        'orders': orders,
    }})
    '''


def GetApplication(request, id):
    # Получаем текущего пользователя (временно используем фиксированного пользователя)
    user = User.objects.get(username="Admin1")

    # Получаем заявку по ID и проверяем, что она принадлежит пользователю
    try:
        application = Application.objects.get(id=id, client=user)

        if application.status == Application.ApplicationStatus.DELETED:
            raise Http404("Заявка не найдена")
    except Application.DoesNotExist:
        # Если заявка не найдена, возвращаем пустой список
        order_in_application_list = []
    else:
        # Получаем все записи OrderInApplication для этой заявки
        order_in_application_list = OrderInApplication.objects.filter(application=application)

    # Подсчитываем количество товаров в корзине для других целей
    orders_in_draft_application = OrderInApplication.objects.filter(
        application__client=user,
        application__status=Application.ApplicationStatus.DRAFT
    ).count()

    return render(request,
                  'application_page.html',
                  {
                      "data": {
                          "application_id": get_current_application_id("Admin1"),
                          "order_in_application_list": order_in_application_list,
                      }
                  })
'''
def GetOrder(request, id):
    order={}
    for i in orders:
        if i['id']==id:
            order=i
    return render(request, 'order.html', {'data' : {
        'order': order,
        'current_id': 1,
    }})'''

def get_order_page(request, id):

    query = "SELECT title, image, more_information FROM bmstu_lab_orders WHERE id = %s"

    with connection.cursor() as cursor:
        cursor.execute(query, [id])
        row = cursor.fetchone()

    if not row:
        return render(request, 'order_information_page.html')

    return render(request,
                  "order_information_page.html",
                  {
                      "data": {
	                      "id": id,
                          "title": row[0],
                          'image': row[1],
                          "more_information": row[2],
                      },
                  })

def get_orders_list_page(request):
    order_title = request.GET.get('title', '')
    orders_in_draft_application = OrderInApplication.objects.filter(
        application__client=User.objects.get(username="Admin1"),
        application__status=Application.ApplicationStatus.DRAFT
    ).count()
    return render(request,
                  'orders_page.html',
                  {
                      "data": {
                          "orders": Orders.objects.filter(title__istartswith=order_title),
                          "items_in_cart": orders_in_draft_application,
                          "product_title": order_title,
                          "application_id": get_current_application_id("Admin1")
                      }
                  })


def add_to_application(request, order_id):
    # Получаем услугу по ID
    order = get_object_or_404(Orders, id=order_id)

    # Получаем или создаем заявку со статусом DRAFT
    # Временно используем фиксированного пользователя
    user = User.objects.get(username="Admin1")
    application, created = Application.objects.get_or_create(
        client=user,
        status=Application.ApplicationStatus.DRAFT,
        defaults={
            'client_id': 1,  # Явно указываем client
            'status': Application.ApplicationStatus.DRAFT,
        }
    )

    # Создаем связь между заявкой и услугой
    OrderInApplication.objects.get_or_create(
        application=application,
        order=order,
        defaults={'comment': ''}  # Пустой комментарий по умолчанию
    )

    # Перенаправляем обратно на страницу услуг
    return redirect('orders_url')

def delete_application(request, application_id):
    # Проверяем существование заявки
    application = get_object_or_404(Application, id=application_id)

    # Прямой SQL UPDATE
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE bmstu_lab_application SET status = 'DELETED' WHERE id = %s",
            [application_id]
        )

    application, created = Application.objects.get_or_create(
        client_id=1,
        status=Application.ApplicationStatus.DRAFT,
        defaults={
            'client_id': 1,  # Явно указываем client
            'status': Application.ApplicationStatus.DRAFT,
        }
    )

    return redirect('orders_url')

def sendText(request):
    if request.method == 'GET':
        input_text = request.GET.get('search', '')

        query = "SELECT title, image, main_information FROM bmstu_lab_orders WHERE title = %s"

        with connection.cursor() as cursor:
            cursor.execute(query, [input_text])
            row = cursor.fetchone()

        if not row:
            return render(request, 'orders_page.html')

        return render(request,
                      "orders_page.html",
                      {
                          "data": {
                              "id": id,
                              "title": row[0],
                              'image': row[1],
                              "main_information": row[2],
                          },
                      })
    return HttpResponse("Method not allowed", status=405)

def get_current_application_id(user):
    application = get_object_or_404(Application, status=Application.ApplicationStatus.DRAFT)
    return application.id
'''
        ans_search = []
        if input_text and input_text != 'ПОИСК':
            for order in orders:
                if input_text.lower() in order['title'].lower():
                    ans_search.append(order)
        else:
            ans_search = []

        return render(request, 'orders_page.html', {'data': {
            'orders': ans_search
        }})
    '''