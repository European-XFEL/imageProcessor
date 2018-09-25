import time


class FrameRate:
    def __init__(self, type='input', refresh_interval=1.0):
        self.counter = 0
        self.lastTime = time.time()
        self.type = type
        self.refresh_interval = refresh_interval

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

    def refresh(self):
        fps = None
        if self.elapsedTime() >= self.refresh_interval:
            fps = self.rate()
            self.reset()
        return fps
