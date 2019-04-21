from datetime import datetime
from time import time
from queue import Queue
from warnings import warn
from uuid import uuid4
from os import path
from delegator import run

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
    sobre el elemento descartado. Por defecto, accion() es hacer nada.'''
    def __init__(self, *args, maxsize=3, accion=lambda *a, **k: None, **kwargs):
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

    def run_new(self, command, block=False):
        #Kill prevoius process
        self.kill() #killing a dead subproc raises no error
        self.subprocess = run(command, block=block)

    def kill(self):
        if not self.subprocess is None:
            self.subprocess.kill()
