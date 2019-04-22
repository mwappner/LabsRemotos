from time import sleep, time
from numpy import linspace
from threading import Thread
from os import listdir, remove, path, makedirs
from shutil import rmtree
from queue import Empty
from delegator import run
from .utils import DeleterQueue, ProcRunning, clip_between, nuevo_nombre

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
    'timelapse' : ('/home/pi/jauretche/LabsRemotos/lvdf/staic/timelapses/', ''),
    }


class Oscilator:
    '''A class containing the parameters of the device.'''

    def __setattr__(self, name, value):
        #Me aseguro de que los valores que deen tener límite 
        #caigan en el rango adecuado
        if name in rangos:  
            value = clip_between(value, *rangos[name])    
        super().__setattr__(name, value)
        if name in replay_when_changed and self._initialized:
            self.play()

    def __init__(self, debug=False):
        self._initialized = False
        
        for key, val in iniciales.items():
            self.__setattr__(key, val)
        
        self._initialized = True
        self._debug = debug
        
        self.proc_running = dict(cam=ProcRunning(), sound=ProcRunning())
        self.stopqueue = DeleterQueue(maxsize=1) #acepta cosas per guarda una sola

        self.filequeues = {k:DeleterQueue(accion=remove) for k in nombres}
        self.filequeues['timelapse'].accion = rmtree #para timelapses necesito otra acción
        self._existentes() #inicializo las colas con los archivos existentes

        self._timestart_sound = time() #la primera vez, is_on no va a dar bien, pero por lo menos no tira error.
        self._isplaying = False
        #self._timestart_cam = time()

    def _existentes(self):
        #Si estoy en modo debug, no cargo los archivos (suele ser en otro SO)
        if self._debug:
            return

        #Inicializo las colas con los archivos existentes, ordenados
        for cat, cola in self.filequeues.items():
            #Recupero archivos, ordenados por fecha de creación
            base = nombres[cat][0]
            contenido = [path.join(base,f) for f in listdir(base)]
            contenido.sort(key=lambda f:path.getmtime(f))
            
            #Meto todos los archivos en la cola correspondiente
            for c in contenido:
                cola.put(c)

    @property
    def ison_sound(self):
        return self._timestart_sound + self.duracion > time() and self._isplaying

#    @property
#    def ison_cam(self):
#        return self._timestart_cam + self.duration > time()

    def _debugrun(self, command, cat, **kwargs):
        if self._debug:
            print(cat, command)
        else:
            self.proc_running[cat].run_new(command, **kwargs)

    def play(self):
        #play with current values
        self.stopqueue.put(1)
        run('amixer set PCM -- {}%'.format(self.amplitud*100))
        command = 'play -n -c1 synth {} sine {}'.format(self.duracion, self.frecuencia)
        self._debugrun(command, 'sound')
        self._timestart_sound = time()
        self._isplaying = True

    def stop(self):
        for proc in self.proc_running.values():
            proc.kill()
        self.stopqueue.put(1)
        self._isplaying = False

    def get_params(self):
        return {k:getattr(self, k) for k in rangos}
            
    def sweep(self, time, freq_start, freq_end):
        if freq_start >= freq_end:
            raise ValueError('Frecuencias incompatibles.')
        self.stopqueue.put(1)
        command = 'play -n -c1 synth {} sine {}:{}'.format(time, freq_start, freq_end)
        self._debugrun(command, 'sound')

    def snapshot(self, file=nuevo_nombre(*nombres['foto']), **kwargs):
        command = 'raspistill -ss {shutterspeed} -o {file}'.format(
            shutterspeed = self.exposicion, file = file)
        self._debugrun(command, 'cam', **kwargs)
        self.filequeues['foto'].put(file)
        return path.basename(file)

    def video(self, duration):
        file = nuevo_nombre(*nombres['video'])
        command = ('raspivid -o {file} -w 960 -h 516 -roi 0,0.5,1,1 -fps 30 ' 
                   '-ex off -n -br 70 -co 50 -t {dur} -v&').format(
                           file = file,
                           dur = duration)
        self._debugrun(command, 'cam')
        self.filequeues['video'].put(file)
        return path.basename(file)
        
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
        makedirs(nombre_base)
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

            #AGREGAR UN ELSE ZIP Y MODIFICAR ADECUADAMENTE __init__
            
            #vuelvo a los valores previos del device
            for name, value in d.items():
                setattr(self, name, value)
        
        #vacío la cola por si acaso
        if not self.stopqueue.empty():
            self.stopqueue.get(block=False)

        #inicializo y prendo el thread
        fotos_thread = Thread(target=accion)
        fotos_thread.start()

        self.filequeues['timelapse'].put(nombre_base)
        return path.basename(nombre_base)
