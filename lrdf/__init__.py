from os import listdir, remove, path, getcwd, getenv
from zipfile import ZipFile
from warnings import catch_warnings
from flask import Flask, request, send_file, jsonify, Response
from .device import rangos, nombres, Oscilator, clip_between
from .utils import utc_later

# status_key = {0:'Todo OK', -1:'Valor inválido', -2:'Valor fuera de rango', -3:'Archivo inexistente'}

# Some settings taken from environment variables
dev_dryrun = getenv('DRYRUN', 'YES') =='YES'
dev = Oscilator(dryrun=dev_dryrun)

# Create flask app
app = Flask(__name__)

# Security stuff. If no key is given as environment variable, check will be skipped.
key = getenv('JWT_SECRET_KEY') #defaults to None

if key is None:
    def jwt_required(func):
        return func
else:
    from flask_jwt_extended import JWTManager, jwt_required

    app.config['JWT_SECRET_KEY'] = getenv('JWT_SECRET_KEY','') #change this

    jwt = JWTManager(app)
   
    @jwt.expired_token_loader
    def my_expired_token_callback(expired_token):
        token_type = expired_token['type']
        return jsonify({
            'status': 401,
            'sub_status': 42,
            'msg': 'The {} token has expired'.format(token_type)
            }), 401


@app.route('/')
def index():
    return 'LRDF v2019-5-24'


def cambiar_valor(parametro, valor, status=0):
    '''Intenta cambiar el el valor del parámetro dado. Si se levanta una
    advertencia, asume que es porque el valor estuvo fuera del rango dado
    y devuelve el valor correspondiente de status: -2. Faltaría chequear 
    qué warning se levantó.'''
    if valor is not None:
        with catch_warnings(record=True) as w:
            setattr(dev, parametro, valor)
            if w: #Es una lista vacía si no hubo warnings
                status = -2
    return status, getattr(dev, parametro)


def chequear_rango(parametro, valor, status=0, rango=None):
    '''Chequea que el valor dado es´té en el rango adecuado, según el 
    parámetro. Si no lo está, avisa usando status=-2 y lo mete en el
    rango adecuado.'''
    if rango is None:
        rango = rangos[parametro]
    with catch_warnings(record=True) as w:
        valor = clip_between(valor, *rango)
        if w: #Es una lista vacía si no hubo warnings
            status = -2
    return status, valor


@app.route('/rangos')
def view_rangos():
    return jsonify(status=0, valor=rangos)


@app.route('/parametros')
def view_parametros():
    return jsonify(status=0, valor=dev.get_params())


@app.route('/encendido')
def view_encendido():
    return jsonify(status=0, valor=dev.ison_sound)


#@app.route('/enuso_camara')
#def view_camara():
#    return jsonify(status=0, valor=dev.ison_cam)


@app.route('/frecuencia')
@app.route('/frecuencia/<float:valor>')
@app.route('/frecuencia/<int:valor>')
@jwt_required
def view_frecuencia(valor=None):
    status, valor_salida = cambiar_valor('frecuencia', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/fase')
@app.route('/fase/<float:valor>')
@app.route('/fase/<int:valor>')
@jwt_required
def view_fase(valor=None):
    status, valor_salida = cambiar_valor('fase', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/amplitud')
@app.route('/amplitud/<float:valor>')
@app.route('/amplitud/<int:valor>')
@jwt_required
def view_amplitud(valor=None):
    status, valor_salida = cambiar_valor('amplitud', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/duracion')
@app.route('/duracion/<float:valor>')
@app.route('/duracion/<int:valor>')
@jwt_required
def view_duracion(valor=None):
    status, valor_salida = cambiar_valor('duracion', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/exposicion')
@app.route('/exposicion/<float:valor>')
@app.route('/exposicion/<int:valor>')
@jwt_required
def view_exposicion(valor=None):
    status, valor_salida = cambiar_valor('exposicion', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/foto')
@jwt_required
def view_foto():
    file = dev.snapshot()
    mandar = dict(file=file,
                 tiempo_estimado=utc_later(10)) #lo hago esperar al menos diez segundos.
    return jsonify(status=0, valor=mandar)


@app.route('/barrido/<int:duracion>/<int:frec_i>/<int:frec_f>')
@app.route('/barrido/<int:duracion>/<float:frec_i>/<int:frec_f>')
@app.route('/barrido/<int:duracion>/<int:frec_i>/<float:frec_f>')
@app.route('/barrido/<int:duracion>/<float:frec_i>/<float:frec_f>')
@jwt_required
def hacer_barrido(duracion, frec_i, frec_f):
    # Chequeo que los valores estén en el rango admitido
    status, frec_i = chequear_rango('frecuencia', frec_i)
    status, frec_f = chequear_rango('frecuencia', frec_f, status=status)
    status, duracion = chequear_rango('duracion', duracion, status=status, rango=(0,60))
    try:
        file = dev.video(duracion)
        dev.sweep(duracion, frec_i, frec_f)
        mandar = dict(file=file,
                         tiempo_estimado=utc_later(duracion),
                         barriendo_entre=[frec_i, frec_f])
        return jsonify(status=status, valor=mandar)

    except ValueError: #las frecuencias eran incompatibles
        msg = ('Valores de frecuencias incompatibles. Tal vez frec_i={} igual o más grande que '
            'frec_f={}, o ambas fuera del rango permitido, en cuyo caso frec_i=frec_f.'
            ).format(frec_i, frec_f)
        if status == -2:
            msg += '\n Frecuencias estaban fuera del rango permitido (status=-2).'
        return jsonify(status=-1, mensaje=msg)


@app.route('/timelapse/<int:frec_i>/<int:frec_f>')
@app.route('/timelapse/<int:frec_i>/<float:frec_f>')
@app.route('/timelapse/<float:frec_i>/<int:frec_f>')
@app.route('/timelapse/<float:frec_i>/<float:frec_f>')
@jwt_required
def sacar_timelapse(frec_i, frec_f):

    # Chequeo que los valores estén en el rango admitido
    status, frec_i = chequear_rango('frecuencia', frec_i)
    status, frec_f = chequear_rango('frecuencia', frec_f, status)

    try:
        file = dev.fotos(frec_i, frec_f)
        mandar = dict(file=file,
                         tiempo_estimado=utc_later(200), #mucho tiempo extra (debería tardar 100)
                         barriendo_entre=[frec_i, frec_f])
        return jsonify(status=status, valor=mandar)

    except ValueError: #las frecuencias eran incompatibles
        msg = ('Valores de frecuencias incompatibles. Tal vez frec_i={} igual o más grande que '
            'frec_f={}, o ambas fuera del rango permitido, en cuyo caso frec_i=frec_f.'
            ).format(frec_i, frec_f)
        if status == -2:
            msg += '\n Frecuencias estaban fuera del rango permitido (status=-2).'
        return jsonify(status=-1, mensaje=msg)


@app.route('/getfoto/<path:file>')
@jwt_required
def get_ultima_foto(file):
    if dev_dryrun:
        return jsonify('File sent: {}'.format(file))
    
    try:
        return send_file(path.join(nombres['foto'][0],file))
    except FileNotFoundError:
        msg = 'Archivo {} no existente.'.format(file)
        return jsonify(status=-3, mensaje=msg)


@app.route('/getvideo/<path:file>')
@jwt_required
def get_video(file):
    if dev_dryrun:
        return jsonify('File sent: {}'.format(file))

    try:
        return send_file(path.join(nombres['video'][0],file))
    except FileNotFoundError:
        msg = 'Archivo {} no existente.'.format(file)
        return jsonify(status=-3, mensaje=msg)


@app.route('/gettimelapse/<path:file>')
@jwt_required
def get_timelapse(file):
    file = path.join(nombres['timelapse'][0], file)
    try:
        lista = [path.join(file, f) for f in listdir(file)]
    except FileNotFoundError:
        msg = 'Archivo {} no existente.'.format(file)
        return jsonify(status=-3, mensaje=msg)

    if lista:
        dev.stop() #para que no siga creando fotos mientras intento mandarlas
        with ZipFile('send.zip', 'w') as zf:
            for f in lista:
                zf.write(f)
                remove(f)

        dev.play() #vuelvo a arrancar
        if dev_dryrun:
            return jsonify('File sent: {}'.format(filename))
        return send_file('send.zip')
    else:
        msg = 'Archivo no existente.'
        return jsonify(status=-3, mensaje=msg)


@app.route('/live')
@app.route('/live/<float:delay1>/<float:delay2>')
@jwt_required
def live(delay1=None, delay2=None):
    if delay1 is None:
        delay1 = 1
    if delay2 is None:
        delay2 = 1
        
    file = dev.live(delay1, delay2)

    if dev_dryrun:
        return jsonify('File sent: {}'.format(path.basename(file)))
    
    return send_file(file)


@app.route('/stop')
@jwt_required
def stop():
    dev.stop()
    return jsonify(status=0)


@app.route('/play')
@jwt_required
def play():
    dev.play()
    return jsonify(status=0)



def main(debug=True, browser=False, port=5000):
    if debug:
        print(getcwd())

    if browser:
        import threading, webbrowser
        url = "http://127.0.0.1:{0}".format(port)
        threading.Timer(3, lambda: webbrowser.open(url)).start()
    #app.run(port=port, debug=debug)
    app.run(host = '0.0.0.0', port=5000, debug=debug)
