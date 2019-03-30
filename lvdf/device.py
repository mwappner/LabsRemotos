from delegator import run

rangos = {
    'frecuencia': (20, 2000),
    'amplitud': (0, 1),
    'fase': (-180, 180),
    'duracion': (0,36000), 
    'exposicion': (100, 5000000)
    }
replay_when_changed = ['frecuencia',
                       #'amplitud',
                       #'fase',
                       'duracion',
                       ]

def clip_between(value, lower=0, upper=100):
    '''Clips value to the (lower, upper) interval, i.e. if value
    is less than lower, it return lower, if its grater than upper,
    it return upper, else, it returns value unchanged.'''
    if value<lower:
        return lower
    if value>upper:
        return upper
    return value

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
        if name in replay_when_changed and self.initiated:
            self.play()

    def __init__(self, debug=False):
        #Por default, arranca con los valores mínimos del
        #rango permitido
        self.initiated = False
        
        for key, val in rangos.items():
            self.__setattr__(key, val[0])
        self.duracion = 300 #default de la duración es 5 minutos
        
        self.initiated = True
        self._debug = debug
        
        self.proc_running = ProcRunning()

    def _debugrun(self, command):
        if self._debug:
            print(command)
        else:
            self.proc_running.run_new(command)        

    def play(self):
        #play with current values
        command = 'play -n -c1 synth {} sine {}'.format(self.duracion, self.frecuencia)
        self._debugrun(command)
            
    def sweep(self, time, freq_start, freq_end):
        command = 'play -n -c1 synth {} sine {}:{}'.format(time, freq_start, freq_end)
        self._debugrun(command)

    def snapshot(self, delay):
        command = 'raspistill -t {delay} -ss {shutterspeed} -o static/cuerda.jpg'.format(
                delay = delay, shutterspeed = self.exposicion)
        self._debugrun(command)

    def video(self, duration):
        command = ('raspivid -o {file} -w 960 -h 516 -roi 0,0.5,1,1 -fps 30 ' 
                   '-ex off -n -br 70 -co 50 -t {dur} -v&').format(
                           file = 'video/filmacion.h264', dur = duration)
        self._debugrun(command)