import argparse
import logging
import os
import pyinotify
from Queue import Queue
import SocketServer
import sys
import threading

logger = logging.getLogger("nfs_inotify_server")

class TouchProducer(object):
    def __init__(self, root_full_path, file_handler, directory_handler):
        self.root_full_path = root_full_path

        self.file_handler = file_handler
        self.directory_handler = directory_handler

        self.watch_manager = pyinotify.WatchManager()
        self.notifier = pyinotify.Notifier(self.watch_manager, self.handle_event)

        self.add_watch_recursive(self.root_full_path)

    def process(self):
        while True:
            self.notifier.process_events()
            if self.notifier.check_events():
                self.notifier.read_events()

    def add_watch(self, full_path):
        if os.path.isdir(full_path):
            logger.debug("Add watch (directory): %s", full_path)
            self.watch_manager.add_watch(full_path,
                pyinotify.IN_CREATE |
                pyinotify.IN_DELETE |
                pyinotify.IN_MOVED_FROM |
                pyinotify.IN_MOVED_TO | 
                0
            )
        else:
            logger.debug("Add watch (file): %s", full_path)
            self.watch_manager.add_watch(full_path,                
                pyinotify.IN_MODIFY |
                pyinotify.IN_CLOSE_WRITE |
                0
            )

    def add_watch_recursive(self, full_path):
        self.add_watch(full_path)
        if os.path.isdir(full_path):
            for i in os.listdir(full_path):
                self.add_watch_recursive(os.path.join(full_path, i))

    def handle_event(self, event):
        logger.debug("Received event: %s", event)

        if event.mask & (pyinotify.IN_IGNORED):
            logger.debug("Ignoring this event")
            return

        if not self.is_own_event(event):
            self.produce_touches(event)
            self.add_new_watches(event)

    def is_own_event(self, event):
        if os.path.basename(event.pathname).endswith(".nfs_inotify"):
            logger.debug("It is event regarding *.nfs_inotify file")
            return True

        if event.mask & (pyinotify.IN_CLOSE_WRITE):
            directory, filename = os.path.split(event.pathname)
            ignore_filename = os.path.join(directory, filename + ".ignore_IN_CLOSE_WRITE.nfs_inotify")
            if os.path.exists(ignore_filename):
                logger.debug("It is IN_CLOSE_WRITE event, but *.ignore_IN_CLOSE_WRITE.nfs_inotify file exists")
                return True

        return False

    def produce_touches(self, event):        
        if event.mask & (pyinotify.IN_MODIFY | pyinotify.IN_CLOSE_WRITE):
            path = os.path.relpath(event.pathname, self.root_full_path)
            logger.info("Touch file: %s", path)
            self.file_handler(path)
        else:
            path = os.path.relpath(event.path, self.root_full_path)
            logger.info("Touch directory: %s", path)
            self.directory_handler(path)

    def add_new_watches(self, event):
        if event.mask & (pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO):
            self.add_watch_recursive(event.pathname)

class TouchProducerEventHandler(object):
    def __init__(self, queues):
        self.queues = queues

    def file_handler(self, filename):
        self.queues_put("file %s" % filename)

    def directory_handler(self, filename):
        self.queues_put("directory %s" % filename)

    def queues_put(self, command):
        for queue in self.queues:
            queue.put(command)

class TouchEventsRequestHandler(SocketServer.StreamRequestHandler, object):
    def __init__(self, queues, *args, **kwargs):
        self.queues = queues
        super(TouchEventsRequestHandler, self).__init__(*args, **kwargs)

    def handle(self):
        path = self.rfile.readline().strip()
        logger.debug("Connected client watching %s", path)

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
    parser.add_argument("--log-file", action="store", type=argparse.FileType("w"), default=sys.stderr)
    parser.add_argument("--log-level", action="store", type=lambda level: getattr(logging, level), default="DEBUG", choices=["DEBUG", "INFO", "WARNING", "ERROR", "FATAL"])
    args = parser.parse_args(sys.argv[1:])

    logging.basicConfig(stream=args.log_file, level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%b %d %H:%M:%S")

    queues = {}
    for path in args.path[0]:
        queues[path] = []
        event_handler = TouchProducerEventHandler(queues[path])
        touch_producer = TouchProducer(path, event_handler.file_handler, event_handler.directory_handler)
        producer_thread = threading.Thread(target=touch_producer.process)
        producer_thread.daemon = True
        producer_thread.start()

    tcp_server = ThreadedTCPServer((args.addr, args.port), TouchEventsRequestHandlerFactory(queues))
    tcp_server.serve_forever()
