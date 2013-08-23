nfs_inotify
===========

Transfers inotify events from NFS server to client (for [theMediaShell](https://github.com/themylogin/theMediaShell), MPD library auto-update, etc.)

### How to use it
This software consists from server (one instance ran on NFS server) and client (one instance per share ran on NFS client); server captures inotify event and client simulates them:

    [server] ~> python2 nfs_inotify_server.py 192.168.0.1 2050 /media/storage/Music /media/storage/Torrent/downloads
    [mediacenter] ~> python2 nfs_inotify_client.py 192.168.0.1 2050 /media/storage/Music /home/themylogin/Storage/Music
    [mediacenter] ~> python2 nfs_inotify_client.py 192.168.0.1 2050 /media/storage/Torrent/downloads /home/themylogin/Storage/Torrent/downloads

In this example two directories are being inotified on my media PC: music one and torrent downloads (movies).

### Usage tips

Put

    fs.inotify.max_user_watches=262144

to `/etc/sysctl.conf`

### Upstart .conf's
/etc/init/nfs_inotify_server.conf

    ########################################
    ##### install in /etc/init         #####
    ########################################
     
    description "NFS inotify server"

    env PYTHON_HOME=/home/themylogin/www/apps/virtualenv

    start on runlevel [2345]
    stop on runlevel [!2345]

    setuid themylogin
    setgid themylogin

    exec $PYTHON_HOME/bin/python /media/storage/Shared/nfs_inotify/nfs_inotify_server.py 192.168.0.1 2050 /media/storage/Music /media/storage/Torrent/downloads --log-file=/tmp/nfs_inotify_server.log

    respawn
    respawn limit 10 5

/etc/init/nfs_inotify_client.conf 

    ########################################
    ##### install in /etc/init         #####
    ########################################
     
    description "NFS inotify server"
    
    start on runlevel [2345]
    stop on runlevel [!2345]
    
    setuid themylogin
    setgid themylogin
    
    exec python2 /home/themylogin/Storage/Shared/nfs_inotify/nfs_inotify_client.py 192.168.0.1 2050 /media/storage/Torrent/downloads /home/themylogin/Storage/Torrent/downloads --log-file=/tmp/nfs_inotify_client_torrent.log
    
    respawn
    respawn limit 10 5
