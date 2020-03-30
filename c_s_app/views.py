from time import sleep
from requests.auth import HTTPDigestAuth
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
import threading
import requests
import schedule
import xlwt
from django.db.models import Q

from c_s_app.forms import *
from c_s_app.models import *


def get_cams_list():
    login = 'api'
    password = r'1iGcg/AxRYPVAYRoasddSD9aKZCFdYT+yVphmSKtQ'
    url_address = 'http://10.32.2.24:3030/list'
    api_request = requests.get(url_address, auth=HTTPDigestAuth(login, password))

    if api_request.status_code == 200:
        cams_list = api_request.json()
        print(cams_list)
        for cam in cams_list:
            name = cam['name']
            cam_id = cam['id']
            address = cam['path']
            lat = cam['lat']
            long = cam['long']
            azimuth = cam['azimuth']
            cam_obj = Camera.objects.filter(cam_id=cam_id)

            if len(cam_obj) == 0:
                new_cam = Camera.objects.create(name=name,
                                                cam_id=cam_id,
                                                address=address,
                                                lat=lat,
                                                long=long,
                                                azimuth=azimuth)
    else:
        print('WARNING! API response with code: ', api_request.status_code)


def starter():
    """
    runs func get_cams_list every 24h
    :return:
    """
    schedule.every(24).hours.do(get_cams_list)
    while True:
        schedule.run_pending()
        sleep(60*60*5)  # sleeps 5h


# runs func 'starter' in Thread
# threading.Thread(target=starter).start()


class CamerasRequest(View):
    def get(self, request):
        # get_cams_list()  # runs func to update Cameras list in DB
        form = CamsRequestForm()
        return render(request, 'c_s_app/index.html', {'form': form, 'submit_value': 'Отправить запрос'})

    def post(self, request):
        form = CamsRequestForm(request.POST)

        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            start_time = form.cleaned_data['start_time']
            finish_date = form.cleaned_data['finish_date']
            finish_time = form.cleaned_data['finish_time']

            start = datetime.combine(start_date, start_time)
            finish = datetime.combine(finish_date, finish_time)

            cams_list = request.POST.getlist('cams')  # there may be a check on the number (20) of cameras

            cameras_array = [Camera.objects.get(pk=cam) for cam in cams_list]
            request_object = Request.objects.create(start=start, finish=finish)

            # API request for URL
            def get_url(cam_id_request, start_request, finish_request):
                login = 'api'
                password = '1iGcg/AxRYPVAYRoasddSD9aKZCFdYT+yVphmSKtQ'
                url_address = 'http://10.32.2.24:3030/archive'
# ------------------------------ block to work with real API -----------------------------------------------------------
                api_request = requests.get(url_address, auth=HTTPDigestAuth(login, password),
                                           params={'id': cam_id_request, 'start': start_request, 'end': finish_request})
                print(api_request.url)
                print(start_request, finish_request)

                if api_request.status_code == 200:
                    api_response = api_request.json()  # response converted to Python dictionary
                    if api_response is not None:
                        url = api_response['url']
# ------------------------------ end of block "to work with real API" --------------------------------------------------


# ------------------------------ block to test without real API --------------------------------------------------------
#                 if True:
#                     camera_obj = Camera.objects.get(cam_id=cam_id_request)
#                     url = 'Test_URL:_request_pk:{}/cam_id:{}/cam_address:{}'.format(request_object.pk,
#                                                                                     camera_obj.cam_id,
#                                                                                     camera_obj.address)
#                         if True:
# ------------------------------ end of block to test without real API ------------------------------------------------------------

                # URL record to DB
                        camera_obj = Camera.objects.get(cam_id=cam_id_request)
                        obj_for_url = RequestCameraURL.objects.get(request=request_object, camera=camera_obj)
                        obj_for_url.url = url
                        obj_for_url.save()

                    # отправка URL в DeepStream
                    # здесь будет redirect на страницу с результатом обработки через DeepStream

            for cam in cameras_array:
                request_object.cameras.add(cam)

                # URL requests in different Threads
                strt = request_object.start.astimezone().isoformat(timespec='milliseconds')
                fnsh = request_object.finish.astimezone().isoformat(timespec='milliseconds')
                threading.Thread(target=get_url, args=(cam.cam_id, strt, fnsh)).start()

            return redirect("/cam_request/{}".format(request_object.pk))  # здесь будет redirect на страницу с ожиданием обработки

        return render(request, 'c_s_app/index.html', {'form': form})


class CamerasRequestProgress(View):
    def get(self, request, request_id):
        top_form = TopBarSearchForm()  # , 'top_form': top_form
        # в цикле проверяет статус обработки
        # когда все ссылки обработаны на 100%, то перенаправляет на ссылку с результатом
        form = CamsRequestForm()
        cameras_request_obj = get_object_or_404(Request, pk=request_id)
        progress = 0
        return render(request, 'c_s_app/request_progress.html', {'cameras_request_obj': cameras_request_obj,
                                                                 'form': form,
                                                                 'progress': progress,
                                                                 'top_form': top_form})

def progress(request):
    print('Вход в Django AJAX')
    request_pk = request.GET.get('request_pk', None)
    # берем статус Запроса из БД и отправляем в JS
# ----------- temporary block for testing Progress AJAX -------------------------------
    # симуляция прогресса
    curr_progress = request.GET.get('curr_progress', None)
    sleep(1)
    prgrss = 100
    data = {'progress': prgrss}
    return JsonResponse(data)


class RequestResultView(View):
    def get(self, request, request_id):
        request_id = 51  # пока для тестирования берем только Request pk=51
        request_obj = get_object_or_404(Request, pk=request_id)
        results_objs = request_obj.resultdeepstream_set.all().order_by('pk')
        top_form = TopBarSearchForm()  # , 'top_form': top_form
        return render(request,
                      'c_s_app/request_result.html',
                      {'request_results': results_objs, 'request_obj': request_obj, 'top_form': top_form})


class RequestsListView(View):
    def get(self, request):
        request_objs = Request.objects.all().order_by('-pk')
        top_form = TopBarSearchForm()  # , 'top_form': top_form
        return render(request, 'c_s_app/requests_list.html', {'request_objs': request_objs, 'top_form': top_form})


class CarSearchView(View):
    def get(self, request):
        form = CarSearchForm()
        top_form = TopBarSearchForm()  # , 'top_form': top_form
        return render(request, 'c_s_app/car_search.html', {'form': form, 'top_form': top_form})

    def post(self, request):
        form_search = CarSearchForm()
        form_result = CarSearchForm(request.POST)
        top_form = TopBarSearchForm()  # , 'top_form': top_form


        form_topsearch = TopBarSearchForm(request.POST)
        if form_topsearch.is_valid():
            top_text = form_topsearch.cleaned_data['search_text']
            first_word = top_text.split(' ')[0].lower()
            objects_from_db = ResultDeepstream.objects.filter(Q(car_number__contains=first_word.upper())
                                                              | Q(car_obj__model__mark__name__contains=first_word)
                                                              | Q(car_obj__model__name__contains=first_word)
                                                              | Q(car_obj__name__name__contains=first_word)
                                                              | Q(car_color__name__contains=first_word)
                                                              )

            return render(request, 'c_s_app/car_search.html', {'form': form_search,
                                                               'search_results': objects_from_db,
                                                               'top_form': top_form})

        if form_result.is_valid():
            car_num = form_result.cleaned_data['car_number'].upper()
            car_brand = form_result.cleaned_data['car_brand'].lower()
            car_model = form_result.cleaned_data['car_model'].lower()
            car_gen = form_result.cleaned_data['car_generation'].lower()
            car_color = form_result.cleaned_data['car_color'].lower()

            search_results = ResultDeepstream.objects.all()
            if len(car_num) != 0:
                search_results = search_results.filter(car_number__contains=car_num)
            if len(car_brand) != 0:
                search_results = search_results.filter(car_obj__model__mark__name=car_brand)
            if len(car_model) != 0:
                search_results = search_results.filter(car_obj__model__name=car_model)
            if len(car_gen) != 0:
                search_results = search_results.filter(car_obj__name=car_gen)
            if len(car_color) != 0:
                search_results = search_results.filter(car_color__name=car_color)

            return render(request, 'c_s_app/car_search.html', {'form': form_search,
                                                               'search_results': search_results,
                                                               'top_form': top_form})

        return render(request, 'c_s_app/car_search.html', {'form': form_search, 'top_form': top_form})

class EmptyView(View):
    def get(self, request):
        return render(request, 'c_s_app/emty_page.html')


def export_results_xls(request, request_id):
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="results.xls"'

    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Results')

    # Sheet header, first row
    row_num = 0

    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    columns = ['ID', 'Время', 'Адрес', 'Номер', 'Марка', 'Модель', 'Поколение', '%', 'Цвет', '%']

    for col_num in range(len(columns)):
        ws.write(row_num, col_num, columns[col_num], font_style)

    # Sheet body, remaining rows
    font_style = xlwt.XFStyle()

    # for testing we get all objects with request_id=27
# !!!!!!!!! ИСПРАВИТЬ ПОИСК, Т.К. ИЗМЕНИЛАСЬ ТАБЛИЦА В БД
    rows = ResultDeepstream.objects.filter(request_id=request_id).values_list('pk', 'timestamp', 'camera__address', 'car_number',
                                                                      'car_brand', 'car_model', 'car_generation',
                                                                      'car_probability', 'car_color',
                                                                      'color_probability')
    rows = [[x.strftime("%Y-%m-%d %H:%M") if isinstance(x, datetime) else x for x in row] for row in rows]
    for row in rows:
        row_num += 1
        for col_num in range(len(row)):
            ws.write(row_num, col_num, row[col_num], font_style)

    wb.save(response)
    return response


class FAQView(View):
    def get(self, request):
        top_form = TopBarSearchForm()  # , 'top_form': top_form
        return render(request, 'c_s_app/faq.html', {'top_form': top_form})


class FeedbackView(View):
    def get(self, request):
        form = FeedbackForm()
        top_form = TopBarSearchForm()  # , 'top_form': top_form
        return render(request, 'c_s_app/feedback.html', {'form': form, 'top_form': top_form})

    def post(self, request):
        form_result = FeedbackForm(request.POST)
        if form_result.is_valid():
            text = form_result.cleaned_data['text']
            new_question = Feedback.objects.create(text=text)
            return render(request, 'c_s_app/feedback.html', {'success': 'Запрос отправлен успешно!'})
