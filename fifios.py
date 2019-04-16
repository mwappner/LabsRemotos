from queue import Queue

class Borrable:
    def __del__(self):
        print('borrando')  
    
    def __init__(self, archivo):
        self.archivo = archivo