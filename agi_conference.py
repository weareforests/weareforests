import hashlib
import random
import time

from twisted.internet import reactor, defer, task
from starpy import fastagi, manager
from twisted.python import log

from epsilon.extime import Time
from datetime import timedelta

from axiom.item import Item
from axiom.store import Store
from axiom.attributes import text, timestamp, integer


class Recording (Item):
    """
    A certain recording.
    """

    created = timestamp() 
    caller_id = text()
    filename = text()
    duration = integer() # in frames


from sparked import application


class Application (application.Application):

    admin = None
    meetme = '1234'
    
    def started(self):

        # start AGI service
        f = fastagi.FastAGIFactory(self.connected)
        reactor.listenTCP( 4573, f, 50, '127.0.0.1')

        self.sessions = set()

        # establish AMI admin connection
        f = manager.AMIFactory('admin', 'admin')
        def r(proto):
            self.admin = proto
            self.admin.registerEvent("ConferenceDTMF", log.msg)
            self.admin.registerEvent("MeetmeJoin", self.joined)
            self.admin.registerEvent("MeetmeLeave", self.left)
            self.admin.originate("SIP/5010", context="default", exten="503", priority="1")
        f.login("127.0.0.1", 5038).addCallback(r)

        self.chan2user = {}


    def joined(self, manager, userinfo):
        self.chan2user[userinfo['channel']] = userinfo['usernum']
        #print self.chan2user
        print "User %s joined (%s)" % (userinfo['usernum'], userinfo['channel'])


    def left(self, manager, userinfo):
        print "left", userinfo
        print userinfo
        # self.chan2user[userinfo['channel']] = userinfo['usernum']
        # print self.chan2user
        # print "User %d joined (%s)" % (userinfo['channel'], userinfo['usernum'])


    def connected(self, agi):
        print "!!!!!!!"
        return
        import pprint
        #pprint.pprint(agi.variables)
        #agi.finish()
        def wait():
            d = agi.waitForDigit(2)
            d.addCallback(log.msg)
            d.addCallback(self.handleDigit, agi)
            d.addCallback(lambda _: wait())
            d.addErrback(self.catchHangup, agi)
        wait()
        #self.sessions.add(CallerSession(self, agi))

    def handleDigit(self, digit, agi):
        print digit
        print agi.variables['agi_channel']
        #return self.admin.playDTMF(agi.variables['agi_channel'], chr(digit))
        # redirect to another extension. easy peasy :)
        #d = self.admin.redirect(agi.variables['agi_channel'], "default", "501", "1")
        #d.addCallback(lambda _: agi.finish())
        return 


    def catchHangup(self, f, agi):
        print "***", f
        agi.finish()
        #self.app.sessionEnded(self)
