import argparse
import logging
import os
import socket
import sys
import threading
import time

logger = logging.getLogger("nfs_inotify_client")

def socket_readline(s):
    ret = ""
    while True:
        c = s.recv(1)

        if c == "\n" or c == "":
            break
        else:
            ret += c

    return ret

tasks = []
tasks_lock = threading.Lock()
last_task_inserted_at = [None]
def schedule_task(task, *args, **kwargs):
    tasks_lock.acquire()
    tasks.append(lambda: task(*args, **kwargs))
    tasks_lock.release()

    last_task_inserted_at[0] = time.time()

def execute_tasks():
    while True:
        if tasks and time.time() - last_task_inserted_at[0] >= 10:
            tasks_lock.acquire()
            map(lambda task: task(), tasks)
            tasks[:] = []
            tasks_lock.release()

        time.sleep(1)

def touch_file(filename):
    try:
        ignore_filename = filename + ".ignore_IN_CLOSE_WRITE.nfs_inotify"
        
        logger.debug("Creating ignore file: %s", ignore_filename)
        open(ignore_filename, "w").close()

        logger.debug("Performing IN_CLOSE_WRITE: %s", filename)
        try:
            if os.path.exists(filename):
                with open(filename, "a") as f:
                    pass
        except Exception as e:
            logger.exception("Error performing IN_CLOSE_WRITE %s", filename)

        logger.debug("Removing ignore file: %s", ignore_filename)
        os.unlink(ignore_filename)
    except Exception as e:
        logger.exception("Error touching %s", filename)

def touch_directory(path):
    try:
        dummy_filename = os.path.join(path, ".dummy.nfs_inotify")

        logger.debug("Creating dummy file: %s", dummy_filename)
        open(dummy_filename, "w").close()

        logger.debug("Removing dummy file: %s", dummy_filename)
        os.unlink(dummy_filename)
    except Exception as e:
        logger.exception("Error touching %s", path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NFS inotify client")
    parser.add_argument("addr", action="store")
    parser.add_argument("port", action="store", type=int)
    parser.add_argument("remote_path", action="store")
    parser.add_argument("local_path", action="store")
    parser.add_argument("--log-file", action="store", type=argparse.FileType("w"), default=sys.stderr)
    parser.add_argument("--log-level", action="store", type=lambda level: getattr(logging, level), default="DEBUG", choices=["DEBUG", "INFO", "WARNING", "ERROR", "FATAL"])
    args = parser.parse_args(sys.argv[1:])

    logging.basicConfig(stream=args.log_file, level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%b %d %H:%M:%S")

    execute_tasks_thread = threading.Thread(target=execute_tasks)
    execute_tasks_thread.daemon = True
    execute_tasks_thread.start()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((args.addr, args.port))
    s.send("%s\n" % args.remote_path)
    while True:
        event_type, relative_path = socket_readline(s).split(" ", 1)
        absolute_path = os.path.join(args.local_path, relative_path)

        if event_type == "file":
            logger.debug("Schedule touch file: %s", absolute_path)
            schedule_task(touch_file, absolute_path)
        elif event_type == "directory":
            logger.debug("Schedule touch directory: %s", absolute_path)
            schedule_task(touch_directory, absolute_path)
        else:
            logger.warning("Unknown event type received: %s", event_type)
