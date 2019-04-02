
from flask import Flask, request, send_file, jsonify, Response
from device import Oscilator, rangos
from threading import Timer
from os import listdir, remove, path
from zipfile import ZipFile
from warnings import catch_warnings


app = Flask(__name__)


API_KEY = '17a1240802ec4726fe6c8e174d144dbe3b5c4d05'
SESSION_TOKEN = '9363191fb9f973f9af3b0d1951b569ddbf3eacb2'

 # status_key = {0:'Todo OK', -1:'Valor inválido', -2:'Valor fuera de rango'}


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

def cambiar_valor(parametro, valor):
	'''Intenta cambiar el el valor del parámetro dado. Si se levanta una
	advertencia, asume que es porque el valor estuvo fuera del rango dado
	y devuelve el valor correspondiente de status: -2. Faltaría chequear 
	qué warning se levantó.'''
	status = 0
	if valor is not None:
		with catch_warnings(record=True) as w:
			setattr(dev, parametro, valor)
			if w: #Es una lista vacía si no hubo warnings
				status = -2
	return status, getattr(dev, parametro)


@app.route('/rangos/')
def view_rangos():
    return jsonify(status=0, valor=rangos)


@app.route('/frecuencia')
@app.route('/frecuencia/<float:valor>')
def view_frecuencia(valor=None):
    status, valor_salida = cambiar_valor('frecuencia', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/fase')
@app.route('/fase/<float:valor>')
def view_fase(valor=None):
    status, valor_salida = cambiar_valor('fase', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/amplitud')
@app.route('/amplitud/<float:valor>')
def view_amplitud(valor=None):
    status, valor_salida = cambiar_valor('amplitud', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/duracion')
@app.route('duracion/<float:valor>')
def view_duracion(valor=None):
    status, valor_salida = cambiar_valor('duracion', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/foto/<float:delay>')
def view_foto(delay=None):

    if not delay:
        delay=1
    dev.snapshot(delay)
    return send_file('static/cuerda.jpg')


@app.route('/barrido/<valores>')
def hacer_barrido(valores=None):
    #falta un check bonito para ver que valores sea lo que 
    #creo que es. Espero algo de la forma 'tiempo_frecini_frecfin'
    valores = valores.split('_')

    try:
    	if len(valores)!=2:
    		raise ValueError()
        valores = [float(v) for v in valores]
    except ValueError: #alguno no era convetible
    	msg = 'Valor inválido. Debe ser "tiempo_frecini_frecfin".' 
        return jsonify(status=-1, mensaje=msg)

    dev.video(valores[0])
    dev.sweep(*valores)
    mandar = dict(file='video',
    				 tiempo_estimado=valores[0],
    				 unidades='segundos')
    return jsonify(status=0, valor=mandar)


@app.route('/fotos/<valores>')
def sacar_fotos(valores=None):
    #falta un check bonito para ver que valores sea lo que 
    #creo que es. Espero algo de la forma 'frecini_frecfin'
    valores = valores.split('_')
    
    try:
    	if len(valores)!=2:
    		raise ValueError()
        valores = [float(v) for v in valores]
    except ValueError: #alguno no era convetible
        msg = 'Valor inválido. Debe ser "frecini_frecfin".' 
        return jsonify(status=-1, mensaje=msg)

    mandar = dict(file='timelapse',
					 tiempo_estimado=200, #mucho tiempo extra (debería tardar 100)
					 unidades='segundos')
    return jsonify(status=0, valor=mandar)


@app.route('/getvideo/')
def get_video()

	#chequear qué pasa si no existe el archivo!!!!
	return send_file('video/filmacion.h264')


@app.route('/getfotos/')
def get_fotos()
	lista = ['timelapse/'+f for f in os.listdir()]
	with ZipFile('send.zip', 'w') as zf:
		for f in lista:
			zf.write(f)
			remove(f)

	return send_file('send.zip')


@app.route('/stop')
def stop():
    dev.stop()
    return jsonify(status=0)


def main(debug=True, browser=False, port=5000):
    if browser:
        import threading, webbrowser
        url = "http://127.0.0.1:{0}".format(port)
        threading.Timer(3, lambda: webbrowser.open(url)).start()
    #app.run(port=port, debug=debug)
    app.run(host = '0.0.0.0',port=5000)
