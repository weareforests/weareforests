Installation
------------


Installation of dependencies

    sudo add-apt-repository ppa:arjan-scherpenisse/spark
    sudo apt-get update && sudo apt-get install python-sparked

Add to extensions.conf:

    exten => 502,1,AGI(agi://127.0.0.1:4573)


Debug mode
----------

    sparkd agi_queue.py

Asterisk permissions:

    sudo ln -s /tmp/agi_queue/db/audio/ /usr/share/asterisk/sounds/
    sudo chown asterisk:asterisk /tmp/agi_queue/db/audio/


Running in system mode
----------------------

Use the /usr/share/sparked/sparked-init script

Asterisk permissions:

    sudo ln -s /var/lib/agi_queue/db/audio/ /usr/share/asterisk/sounds/
    sudo chown asterisk:asterisk /var/lib/agi_queue/db/audio/
