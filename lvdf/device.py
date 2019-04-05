from delegator import run

rangos = {
	'frecuencia': (20, 2000),
	'amplitud': (0, 1),
	'fase': (-180, 180),
	'duracion': (0,36000), 
	}

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

	def __init__(self):
		#Por default, arranca con los valores mínimos del
		#rango permitido
		for key, val in rangos.items():
			self.__setattr__(key, val[0])
		self.proc_running = ProcRunning()
		self.ison = False
		self.duracion = 300 #default de la duración es 5 minutos

	def play(self):
		#play with current values
		command = 'play -n -c1 synth {} sine {}'.format(self.duracion, self.frecuencia)
		self.proc_running.run_new(command)

	def sweep(self, time, freq_start, freq_end):
		command = 'barrido.sh {} {} {}'.format(time, freq_start, freq_end)
		self.proc_running.run_new(command)

	def snapshot(self, delay):
		command = 'raspistill -t {} -o static/cuerda.jpg'.format(delay)
		run(command, block=False)

	def change_freq(self, value):
		self.frecuencia = value
		self.play()

	def change_duration(self, value):
		self.duracion = value
		self.play()

	def change_amp(self, value):
		self.amplitud = value

	def change_phase(self, value):
		self.fase = value