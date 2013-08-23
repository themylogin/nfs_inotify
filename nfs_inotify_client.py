import argparse
import logging
import os
import socket
import sys

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

def touch_file(filename):
    try:
        ignore_filename = filename + ".ignore_IN_CLOSE_WRITE.nfs_inotify"
        
        logger.debug("Creating ignore file: %s", ignore_filename)
        open(ignore_filename, "w").close()

        logger.debug("Performing touch: %s", filename)
        try:
            os.utime(filename, None)
        except Exception as e:
            logger.exception("Error performing touch %s", filename)

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

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((args.addr, args.port))
    s.send("%s\n" % args.remote_path)
    while True:
        event_type, relative_path = socket_readline(s).split(" ", 1)
        absolute_path = os.path.join(args.local_path, relative_path)

        if event_type == "file":
            logger.debug("Touch file: %s", absolute_path)
            touch_file(absolute_path)
        elif event_type == "directory":
            logger.debug("Touch directory: %s", absolute_path)
            touch_directory(absolute_path)
        else:
            logger.warning("Unknown event type received: %s", event_type)
