from time import sleep, time
from threading import Thread
from os import listdir, remove, path, makedirs, getenv
from shutil import rmtree
from queue import Empty
from delegator import run
from .utils import DeleterQueue, ProcRunning, clip_between, nuevo_nombre, toggle_streaming_concatenar, linspace


rangos = {
    'frecuencia': (20, 2000), #Hz
    'amplitud': (0, 100), #en %
    'fase': (-180, 180), #grados
    'duracion': (0,3600), #segundos
    'exposicion': (10000, 5000000) #microsegundos
    }

iniciales = {
    'frecuencia': 100, #Hz
    'amplitud': rangos['amplitud'][-1], #valor máximo
    'fase': 0, #grados
    'duracion': 1800, #segundos
    'exposicion': 30000, #microsegundos
    }

replay_when_changed = (
    'frecuencia',
    'amplitud',
    #'fase',
    'duracion',
    )

# Construye rutas completas donde guardar cada tipo de archivo
store_directory = getenv('STORE_FOLDER', '/home/pi/lrdf_use/temporary')
constructor = lambda name: path.join(store_directory, name)
nombres = {
    'video' : (constructor('videos'), '.h264'),
    'foto' : (constructor('fotos'), '.jpg'),
    'timelapse' : (constructor('timelapses'), ''),
    'live' : (constructor('live'), '.jpg'),
    }
# Si no existen las carpetas, las crea
for d, _ in nombres.values():
    makedirs('d', exist_ok=True)

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

    def __init__(self, dryrun=False):
        self._initialized = False
        
        for key, val in iniciales.items():
            self.__setattr__(key, val)
        
        self._initialized = True
        self._dryrun = dryrun

#        #paro el streaming de la cámara al comienzo, hackfix
#        if not debug:
#            run('sudo service motion stop', block=False) 


        self.proc_running = dict(cam=ProcRunning(), sound=ProcRunning())
        self.stopqueue = DeleterQueue(maxsize=1) #acepta cosas per guarda una sola

        self.filequeues = {k:DeleterQueue(accion=remove) for k in nombres}
        self.filequeues['timelapse'].accion = rmtree #para timelapses necesito otra acción
        self._existentes() #inicializo las colas con los archivos existentes

        self._timestart_sound = time() #la primera vez, is_on no va a dar bien, pero por lo menos no tira error.
        self._isplaying = False
        #self._timestart_cam = time()

    def _existentes(self):
        #Si estoy en modo dryrun, no cargo los archivos (suele ser en otro SO)
        if self._dryrun:
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

    @property
    def amplitud(self):
        amp_rango = (.6, .96)
        return (self._amplitud - amp_rango[0]) * 100 / (amp_rango[1] - amp_rango[0])
    @amplitud.setter
    def amplitud(self, value):
        '''Escala el valor dado del intervalo [0,100] al intervalo <amp_rango>. Value
        viene dado en [0, 100]'''
        amp_rango = (.6, .96)
        self._amplitud = (amp_rango[1] - amp_rango[0])/100 * value + amp_rango[0]
    
#    @property
#    def ison_cam(self):
#        return self._timestart_cam + self.duration > time()

    def _dryrunrun(self, command, cat, **kwargs):
        if self._dryrun:
            print(cat, command)
        else:
            self.proc_running[cat].run_new(command, **kwargs)

    def play(self):
        #play with current values
        self.stopqueue.put(1)
        run('amixer set PCM -- {}%'.format(self.amplitud*100))
        command = 'play -n -c1 synth {} sine {}'.format(self.duracion, self.frecuencia)
        self._dryrunrun(command, 'sound')
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
        self._dryrunrun(command, 'sound')

    def snapshot(self, file='', **kwargs):
        '''Takes a single snapshot and returns a filename under which the picture taken will 
        be saved.'''
        # Assign given name. If no name was given, assign deffault
        file = file or nuevo_nombre(*nombres['foto'])
        command = 'raspistill -ss {shutterspeed} -o {file} -t 1'.format(
            shutterspeed = self.exposicion, file = file)
        #command = toggle_streaming_concatenar(command)
        self._dryrunrun(command, 'cam', **kwargs)
        self.filequeues['foto'].put(file)
        return path.basename(file)

    def video(self, duration):
        file = nuevo_nombre(*nombres['video'])
        command = ('raspivid -o {file} -w 960 -h 516 -roi 0,0.5,1,1 -fps 30 ' 
                   '-ex off -n -br 70 -co 50 -t {dur} -v&').format(
                           file = file,
                           dur = duration)
        #command = toggle_streaming_concatenar(command)
        self._dryrunrun(command, 'cam')
        self.filequeues['video'].put(file)
        return path.basename(file)

    def live(self, delay1, delay2):
        #file = path.join(nombres['live'][0], 'foto.jpg')
        file = nuevo_nombre(*nombres['live'])
        self.filequeues['live'].put(file)
        command = ('raspistill -w 640 -h 480 -o {file} '
            '--nopreview -t 0 -s').format(file=file)
        self._dryrunrun(command, 'cam')
        sleep(delay1)
        run('pkill -SIGUSR1 raspistill')
        sleep(delay2)
        run('pkill -9 raspistill')
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
        makedirs(nombre_base)
        nombre = lambda freq: path.join(nombre_base,'{:.1f}Hz.jpg'.format(freq))

        #defino funcion a correr en el thread
        def accion():
            for f in frecuencias:
                self.frecuencia = f #esto pone a andar por 1 segundo
                sleep(0.1)
                self.snapshot(nombre(f), block=True)
                
                #veo si me indicaron que pare
                try:
                    self.stopqueue.get(block=False)
                except Empty:
                    continue
                else:
                    break

            #AGREGAR UN ELSE ZIP Y MODIFICAR ADECUADAMENTE __init__.py
            
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
