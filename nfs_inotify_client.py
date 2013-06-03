import argparse
import logging
import os
import socket
import sys

logger = logging.getLogger("nfs_inotify_client")
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(__file__.replace(".py", ".%s.log" % socket.gethostname()))
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

def socket_readline(s):
    ret = ""
    while True:
        c = s.recv(1)

        if c == "\n" or c == "":
            break
        else:
            ret += c

    return ret

def touch(to_touch):
    if os.path.isdir(to_touch):
        dummy = os.path.join(to_touch, ".nfs_inotify_client_dummy")

        logger.debug("create %s", dummy)
        open(dummy, "w").close()

        logger.debug("unlink %s", dummy)
        os.unlink(dummy)
    else:
        logger.debug("touch %s", to_touch)
        os.utime(to_touch, None)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NFS inotify client")
    parser.add_argument("addr", action="store")
    parser.add_argument("port", action="store", type=int)
    parser.add_argument("remote_path", action="store")
    parser.add_argument("local_path", action="store")
    args = parser.parse_args(sys.argv[1:])

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((args.addr, args.port))
    s.send("%s\n" % args.remote_path)
    while True:
        to_touch = os.path.join(args.local_path, socket_readline(s))
        try:
            touch(to_touch)
        except Exception, e:
            logger.exception(e)
            pass
