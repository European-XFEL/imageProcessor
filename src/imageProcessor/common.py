import time


class FrameRate:
    def __init__(self, type='input'):
        self.counter = 0
        self.lastTime = time.time()
        self.type = type

    def update(self):
        self.counter += 1

    def elapsedTime(self):
        return time.time() - self.lastTime

    def reset(self):
        self.counter = 0
        self.lastTime = time.time()

    def rate(self):
        if self.counter > 0:
            return self.counter / self.elapsedTime()
        else:
            return 0.
