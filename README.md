Installation
------------

Installation of dependencies

    sudo apt-get install sox lame asterisk

    sudo add-apt-repository ppa:arjan-scherpenisse/spark
    sudo apt-get update && sudo apt-get install python-sparked

    git clone git://github.com/weareforests/appkonference.git
    cd appkonference/conference
    make && cp app_konference.so /usr/lib/asterisk/modules/

Add to asterisk's extensions.conf:

    [default]
    exten => 501,1,Answer
    exten => 501,n,AGI(agi://127.0.0.1:4573/DialOut)

    exten => 502,1,Answer
    exten => 502,n,AGI(agi://127.0.0.1:4573)

    exten => 503,1,Answer
    exten => 503,n,Konference(weareforests,R)


Debug mode
----------

    sparkd -d weareforests

Asterisk permissions:

    sudo ln -s /tmp/weareforests/db/audio/ /usr/share/asterisk/sounds/
    sudo chown asterisk:asterisk /tmp/weareforests/db/recordings/
    sudo chmod 777 /tmp/weareforests/db/recordings/


Running in system mode
----------------------

Put the following script in /etc/init.d/weareforests:

    #!/bin/sh
    ### BEGIN INIT INFO
    # Provides:          weareforests
    # Required-Start:    $all
    # Required-Stop:     $all
    # Default-Start:     2 3 4 5
    # Default-Stop:      0 1 6
    # Short-Description: Starts a service for the Sparked plugin 'weareforests'
    # Description:       Generic plugin starter for sparkd plugins
    ### END INIT INFO
    # Author: Arjan Scherpenisse <arjan@scherpenisse.net>
    
    APPLICATION="weareforests"
    . /usr/lib/sparked/sparked-init

Asterisk permissions:

    sudo ln -s /var/lib/weareforests/db/audio/ /usr/share/asterisk/sounds/
    sudo chown asterisk:asterisk /var/lib/weareforests/db/recordings/
    sudo chmod 777 /var/lib/weareforests/db/recordings/
