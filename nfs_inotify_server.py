import argparse
import logging
import os
import pyinotify
from Queue import Queue
import socket
import SocketServer
import sys
import threading

logger = logging.getLogger("nfs_inotify_server")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(__file__.replace(".py", ".%s.log" % socket.gethostname()))
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class TouchProducer(object):
    def __init__(self, root_full_path, handler):
        self.root_full_path = root_full_path
        self.handler = handler

        self.watch_manager = pyinotify.WatchManager()
        self.notifier = pyinotify.Notifier(self.watch_manager, self.handle_event)

        self.add_watch_recursive(self.root_full_path)

    def process(self):
        while True:
            self.notifier.process_events()
            if self.notifier.check_events():
                self.notifier.read_events()

    def add_watch(self, full_path):
        logger.debug("add_watch: %s", full_path)

        self.watch_manager.add_watch(full_path,
            pyinotify.IN_CREATE |
            pyinotify.IN_DELETE |
            pyinotify.IN_MOVED_FROM |
            pyinotify.IN_MOVED_TO | 
            pyinotify.IN_CLOSE_WRITE |
            0
        )

    def add_watch_recursive(self, full_path):
        self.add_watch(full_path)
        if os.path.isdir(full_path):
            for i in os.listdir(full_path):
                self.add_watch_recursive(os.path.join(full_path, i))

    def handle_event(self, event):
        logger.debug("received event: %s", event)

        if event.pathname.endswith(".nfs_inotify_client_dummy"):
            return

        full_path = self.what_to_touch(event)
        if full_path is not None:
            self.handler(os.path.relpath(full_path, self.root_full_path))

        self.add_new_watches(event)

    def what_to_touch(self, event):
        if event.maskname == pyinotify.IN_CLOSE_WRITE:
            return event.pathname
        else:
            return event.path

    def add_new_watches(self, event):
        if event.mask & (pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO):
            self.add_watch_recursive(event.pathname)

def create_touch_producer_event_handler(queues_list):
    def touch_producer_event_handler(path):
        logger.debug("touch %s", path)

        for queue in queues_list:
            queue.put(path)

    return touch_producer_event_handler

class TouchEventsRequestHandler(SocketServer.StreamRequestHandler, object):
    def __init__(self, queues, *args, **kwargs):
        self.queues = queues
        super(TouchEventsRequestHandler, self).__init__(*args, **kwargs)

    def handle(self):
        path = self.rfile.readline().strip()
        if path not in self.queues:
            return

        queue = Queue()
        self.queues[path].append(queue)
        while True:
            self.wfile.write("%s\n" % queue.get())

class TouchEventsRequestHandlerFactory:
    def __init__(self, queues):
        self.queues = queues

    def __call__(self, *args, **kwargs):
        return TouchEventsRequestHandler(self.queues, *args, **kwargs)

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NFS inotify server")
    parser.add_argument("addr", action="store")
    parser.add_argument("port", action="store", type=int)
    parser.add_argument("path", action="append", nargs="+")
    args = parser.parse_args(sys.argv[1:])

    queues = {}
    for path in args.path[0]:
        queues[path] = []
        producer_thread = threading.Thread(target=TouchProducer(path, create_touch_producer_event_handler(queues[path])).process)
        producer_thread.daemon = True
        producer_thread.start()

    ThreadedTCPServer((args.addr, args.port), TouchEventsRequestHandlerFactory(queues)).serve_forever()
