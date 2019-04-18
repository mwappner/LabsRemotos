from time import sleep, time
from datetime.datetime import fromtimestamp 
from numpy import linspace
from threading import Thread
from queue import Queue, Empty
from warnings import warn
from os import listdir, remove, path, makedirs
from shutil import rmtree
from uuid import uuid4
from delegator import run

#paro el streaming de la cámara al comienzo, hackfix
run('sudo service motion stop') 

rangos = {
    'frecuencia': (20, 2000), #Hz
    'amplitud': (.6, .96), #en escala [0,1]
    'fase': (-180, 180), #grados
    'duracion': (0,36000), #segundos
    'exposicion': (10000, 5000000) #microsegundos
    }
iniciales = {
    'frecuencia': 100, #Hz
    'amplitud': rangos['amplitud'][-1], #en escala [0,1]
    'fase': 0, #grados
    'duracion': rangos['duracion'][-1], #segundos
    'exposicion': 30000, #microsegundos
    }
replay_when_changed = ['frecuencia',
                       'amplitud',
                       #'fase',
                       'duracion',
                       ]
nombres = {
    'video' : ('/home/pi/jauretche/LabsRemotos/lvdf/static/videos/', '.h264'),
    'foto' : ('/home/pi/jauretche/LabsRemotos/lvdf/static/fotos/', '.jpg'),
    'timelapse' : ('/home/pi/jauretche/LabsRemotos/lvdf/staic/timelapses', ''),
    }

def clip_between(value, lower=0, upper=100):
    '''Clips value to the (lower, upper) interval, i.e. if value
    is less than lower, it return lower, if its grater than upper,
    it return upper, else, it returns value unchanged.'''
    if value<lower:
        warn('Value out of bounds', SyntaxWarning)
        return lower
    if value>upper:
        warn('Value out of bounds', SyntaxWarning)
        return upper
    return value

def utc_later(delay):
    '''Devuelve la el tiempo UTC dentro de delay segundos.'''
    return str(datetime.fromtimestamp(time()+delay))

def nuevo_nombre(directorio, extension):
    '''Devuelve un nuevo nombre unico de un archivo en el directorio y con
    la extensión dados.'''
    return path.join(directorio, uuid4().hex + extension)

class DeleterQueue(Queue):
    '''Una subclase de Queue que agrega una funcionalidad: cuando la cola se llena,
    puede meter otro elemento, descartando el más antiguo. Además, ejecuta accion()
    sobre el elemento descartado.'''
    def __init__(self, *args, maxsize=3, accion=None, **kwargs):
        #Accion es lo que se debe hacer cuando un elemento se cae de la cola
        if accion is None:
            def accion(*args, **kwargs):
                pass
        self.accion = accion
        super().__init__(*args, maxsize=maxsize, **kwargs)
        
    def put(self, *args, **kwargs):
        #Si está llena, saco uno y lo borro a mano
        if self.full():
           cosa = self.get()
           self.accion(cosa)
           
        #Meto el nuevo
        super().put(*args, **kwargs)

class ProcRunning:
    '''A delegator subprocess with an extra layer to always run
    non blocking mode and always run only one thing at a time.'''
    def __init__(self):
        self.subprocess = None

    def run_new(self, command):
        #Kill prevoius process
        self.kill() #killing a dead subproc raises no error
        self.subprocess = run(command, block=False)

    def kill(self):
        if not self.subprocess is None:
            self.subprocess.kill()

class Oscilator:
    '''A class containing the parameters of the device.'''

    def __setattr__(self, name, value):
        #Me aseguro de que los valores que deen tener límite 
        #caigan en el rango adecuado
        if name in rangos:  
            value = clip_between(value, *rangos[name])    
        super().__setattr__(name, value)
        if name in replay_when_changed and self.initialized:
            self.play()

    def __init__(self, debug=False):
        self.initialized = False
        
        for key, val in iniciales.items():
            self.__setattr__(key, val)
        
        self.initialized = True
        self._debug = debug
        
        self.proc_running = ProcRunning()
        self.stopqueue = Queue()
        self.filequeues = {k:DeleterQueue(accion=remove) for k in nombres}
        self.filequeues['timelapse'].accion = rmtree #para timelapses necesito otra acción


    def _debugrun(self, command):
        if self._debug:
            print(command)
        else:
            self.proc_running.run_new(command)

    def play(self):
        #play with current values
        self.stopqueue.put(1)
        run('amixer set PCM -- {}%'.format(self.amplitud*100))
        command = 'play -n -c1 synth {} sine {}'.format(self.duracion, self.frecuencia)
        self._debugrun(command)

    def stop(self):
        self.proc_running.kill()
        self.stopqueue.put(1)

    def get_params(self):
        return {k:getattr(self, k) for k in rangos}
            
    def sweep(self, time, freq_start, freq_end):
        if freq_start >= freq_end:
            raise ValueError('Frecuencias incompatibles.')
        self.stopqueue.put(1)
        command = 'play -n -c1 synth {} sine {}:{}'.format(time, freq_start, freq_end)
        self._debugrun(command)

    def snapshot(self, file=nuevo_nombre(*nombres['foto']), block=False):
        command = 'raspistill -ss {shutterspeed} -o {file}'.format(
            shutterspeed = self.exposicion, file = file)
        run(command, block=block)
        self.filequeues['foto'].put(file)
        return file

    def video(self, duration):
        file = nuevo_nombre(*nombres['video'])
        command = ('raspivid -o {file} -w 960 -h 516 -roi 0,0.5,1,1 -fps 30 ' 
                   '-ex off -n -br 70 -co 50 -t {dur} -v&').format(
                           file = file,
                           dur = duration)
        run(command, block=False)
        self.filequeues['video'].put(file)
        return file
        
    def fotos(self, freq_start, freq_end):
        '''Barre cien frecuencais entre freq_start y freq_end. Saca una foto 
        de larga exposicion a cada frecuencia.'''
        
        if freq_start >= freq_end:
            raise ValueError('Frecuencias incompatibles.')

        #me guardo el estado actual del device
        d = self.__dict__.copy()
        
        self.duracion = 3
        self.amplitud = 1
        frecuencias = linspace(freq_start, freq_end, 100)
        
        #creo carpeta donde voy a guardar el timelapse y una función para los archivos
        nombre_base = nuevo_nombre(*nombres['timelapse'])
        os.makedirs(nombre_base)
        nombre = lambda freq: path.join(nombre_base,'{:.1f}Hz.jpg'.format(freq))

        #defino funcion a correr en el thread
        def accion():
            for f in frecuencias:
                self.frecuencia = f #esto pone a andar por 1 segundo
                sleep(0.1)
                self.snapshot(1, nombre(f), block=True)
                
                #veo si me indicaron que pare
                try:
                    self.stopqueue.get(block=False)
                except Empty:
                    continue
                else:
                    break
            
            #vuelvo a los valores previos del device
            for name, value in d.items():
                setattr(self, name, value)
        
        #vacío la cola por si acaso
        while not self.stopqueue.empty():
            self.stopqueue.get(block=False)

        #vacío carpeta de fotos
        for f in os.listdir(nombres['timelapse']):
            os.remove(path.join(nombres['timelapse'], f))
        #inicializo y prendo el thread
        fotos_thread = Thread(target=accion)
        fotos_thread.start()

        self.filequeues['timelapse'].put(nombre_base)
        return nombre_base
