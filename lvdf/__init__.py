
from flask import Flask, request, send_file, jsonify, Response
from device import Oscilator
from time import sleep


app = Flask(__name__)


API_KEY = '17a1240802ec4726fe6c8e174d144dbe3b5c4d05'
SESSION_TOKEN = '9363191fb9f973f9af3b0d1951b569ddbf3eacb2'


# def require_api_key(view_function):
#     @wraps(view_function)
#     # the new, post-decoration function. Note *args and **kwargs here.
#     def decorated_function(*args, **kwargs):
#         if request.args.get('x-api-key') and request.args.get('x-api-key') == API_KEY:
#             return view_function(*args, **kwargs)
#         else:
#             return Response('El API Key es inválido', 401,
#                             {'WWWAuthenticate': 'Basic realm="Login Required"'})
#     return decorated_function
#
#
# def require_user_token(view_function):
#     @wraps(view_function)
#     # the new, post-decoration function. Note *args and **kwargs here.
#     def decorated_function(*args, **kwargs):
#         if request.args.get('x-user-token') and request.args.get('x-user-token') == USER_TOKEN:
#             return view_function(*args, **kwargs)
#         else:
#             return Response('El USER Token es inválido', 401,
#                             {'WWWAuthenticate': 'Basic realm="Login Required"'})
#     return decorated_function

dev = Oscilator()

@app.route('/')
def index():
    return 'LVDF'

# # @app.before_request
# def _check():
#
#     valid_key = request.headers.get('x-api-key') and request.headers.get('x-api-key') == API_KEY
#     if not valid_key:
#         return Response('El API Key es inválido', 401,
#                         {'WWWAuthenticate': 'Basic realm="Login Required"'})
#
#     valid_token = request.headers.get('x-session-token') and request.headers.get('x-session-token') == SESSION_TOKEN
#     if not valid_token:
#         return Response('El session Token es inválido', 401,
#                         {'WWWAuthenticate': 'Basic realm="Login Required"'})
#

@app.route('/frecuencia')
@app.route('/frecuencia/<float:valor>')
def view_frecuencia(valor=None):

    if valor:
        dev.change_freq = valor
        return jsonify(status=0)

    return jsonify(status=0, valor=dev.frecuencia)


@app.route('/fase')
@app.route('/fase/<float:valor>')
def view_fase(valor=None):

    if valor:
        dev.change_phase = valor
        return jsonify(status=0) #devuelve status=0 dos veces?

    return jsonify(status=0, valor=dev.fase)


@app.route('/amplitud')
@app.route('/amplitud/<float:valor>')
def view_amplitud(valor=None):

    if valor:
        dev.change_amp = valor
        return jsonify(status=0)

    return jsonify(status=0, valor=dev.amplitud)


@app.route('/foto/<float:delay>')
def view_foto(delay=None):

    if not delay:
        delay=1
    dev.snapshot(delay)
    return send_file('static/cuerda.jpg')


@app.route('/barrido/<valores>')
def hacer_barrido(valores=None):
    #falta un check para ver que valores sea lo que creo que es
    #espero algo de la forma 'tiempo_frecini_frecfin'
    valores = valores.split('_')
    dev.sweep(*valores)
    sleep(valores[0]) #esperar a que termine el barrido, bloquea todo
    return send_file('video/filmacion.h264')


def main(debug=True, browser=False, port=5000):
    if browser:
        import threading, webbrowser
        url = "http://127.0.0.1:{0}".format(port)
        threading.Timer(3, lambda: webbrowser.open(url)).start()
    app.run(port=port, debug=debug)
