from django.shortcuts import render
from django.http import HttpResponse
from datetime import date

orders = [{'title': 'Древний город', 'image': 'http://localhost:9000/static/img/town.png', 'main_information': 'плотность ≈ 110 ч/га', 'more_information': '    Это основная жилая зона с усадебной застройкой. Плотность здесь была заметно ниже.\n\n    плотность населения ≈ 110 ч/га\n    плотность застройки ≈ 17 усадеб/га\n    количество жильцов в усадьбе ≈ 6 ч/ус', 'id': 1, 'app_flag': False},
            {'title': 'Крепость', 'image': 'http://localhost:9000/static/img/tower.png', 'main_information': 'плотность ≈ 135 ч/га', 'more_information': '    Здесь наблюдалась максимальная плотность, обусловленная дефицитом защищенного пространства. \n \n    плотность населения ≈ 135 ч/га\n    плотность застройки ≈ 25 усадеб/га\n    количество жильцов в усадьбе ≈ 5 ч/ус', 'id': 2, 'app_flag': True},
            {'title': 'Село', 'image': 'http://localhost:9000/static/img/village.png', 'main_information': 'плотность ≈ 75 ч/га', 'more_information': '    Плотность застройки в сельских поселениях была низкой и определялась сельскохозяйственными потребностями.\n \n    плотность населения ≈ 75 ч/га\n    плотность застройки ≈ 10 усадеб/га\n    количество жильцов в усадьбе ≈ 8 ч/ус', 'id': 3, 'app_flag': True},]
application = {1: [2, 3]}
def hello(request):
    return render(request, 'index.html', { 'data' : {
        'current_date': date.today(),
        'list': ['python', 'django', 'html']
    }})

def GetOrders(request):
    return render(request, 'orders.html', {'data': {
        'orders': orders
    }})

def GetApplication(request, id):
    return render(request, 'application.html', {'data': {
        'orders': orders
    }})

def GetOrder(request, id):
    order={}
    for i in orders:
        if i['id']==id:
            order=i
    return render(request, 'order.html', {'data' : {
        'order': order,
        'application': application,
        'current_id': 1,
    }})

def sendText(request):
    input_text = request.GET.get('search')
    ans_search=[]
    if input_text != 'ПОИСК':
        for order in orders:
            if input_text in order.title:
                ans_search.append(order)
        return render(request, 'orders.html', {'data': {
            'orders': ans_search
        }})