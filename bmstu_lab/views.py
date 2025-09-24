from django.shortcuts import render
from django.http import HttpResponse
from datetime import date
from .models import Orders, OrderInApplication, Application
from django.db import connection
from django.contrib.auth.models import User

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
    }})'''

def GetApplication(request, id):
    return render(request, 'application_page.html', {'data': {
        'orders': orders,
    }})
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
                      }
                  })



def sendText(request):
    if request.method == 'GET':
        input_text = request.GET.get('search', '')
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
    return HttpResponse("Method not allowed", status=405)