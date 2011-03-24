import hashlib
import random
import time

from twisted.internet import reactor, defer, task
from starpy import fastagi
from twisted.python import log

from epsilon.extime import Time
from datetime import timedelta

from axiom.item import Item
from axiom.store import Store
from axiom.attributes import text, timestamp, integer


WHITELIST=["5010", "0653638994", "0641322599", "0653639052"]



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


    def started(self):

        # database handling
        print self.path("db").path
        self.store = Store(self.path("db").child("storage").path)
        p = self.path("db").child("audio")
        if not p.exists(): p.createDirectory()

        # start AGI service
        f = fastagi.FastAGIFactory(self.connected)
        reactor.listenTCP( 4573, f, 50, '127.0.0.1')

        self.sessions = set()


    def connected(self, agi):
        self.sessions.add(CallerSession(self, agi))


    def getIdleRecordings(self):
        r = list(self.store.query(Recording, Recording.filename == u'audio/silent'))
        if r:
            return r
        rec = Recording(store=self.store, filename=u'audio/silent')
        return [rec]


    def sessionEnded(self, session):
        print 'session ended', session
        self.sessions.remove(session)


    def recordingAdded(self, r):
        for session in self.sessions:
            session.queueAdd(r.filename)

    def isAdmin(self, callerId):
        print "Admin request:", callerId
        if str(callerId) in WHITELIST:
            return True
        return False


    def queueAll(self, filename):
        for session in self.sessions:
            session.queueAddFirst(filename)



class CallerSession (object):
    digit = ord("1")

    def __init__(self, app, agi):
        self.app = app
        self.agi = agi
        self.queue = []
        self.callerId = unicode(self.agi.variables['agi_callerid'])
        print "New session from", self.callerId
        self.state = application.StateMachine(self, verbose=1)
        self.state.set("start")


    def queueAdd(self, r):
        self.queue.append(r)

    def queueAddFirst(self, r):
        self.queue.insert(0, r)


    def enter_start(self):
        timePoint = Time() - timedelta(minutes=15)
        self.queue = ["audio/intro"] + [r.filename for r in self.app.store.query(Recording, Recording.created >= timePoint, sort=Recording.created.ascending)]
        self.state.set("play")


    def enter_play(self, recording=None, offset=0):
        """
        A recording has finished or a previous sample has finished;
        choose a new recording to play.
        """
        # look up the next recording
        if not recording:
            if not self.queue:
                current = "audio/silent"
            else:
                current = self.queue[0]
                del self.queue[0]

        else:
            current = recording

        print "Playing recording: %s, offset %d" % (current, offset)
        d = self.agi.streamFile(str(current), chr(self.digit)+"0", offset)
        def audioDone(r):
            digit, offset = r
            if digit == self.digit:
                self.setStateAfterSample("recording", "audio/record", current, offset)
            elif digit == ord("0"):
                print "wow"
                if self.app.isAdmin(self.callerId):
                    self.state.set("admin_start")
                else:
                    # just play the same
                    self.state.set("play", current)
            else:
                self.state.set("play")
        d.addCallback(audioDone)
        d.addErrback(self.catchHangup)


    def enter_recording(self, currentlyPlaying=None, offset=0):
        """
        User has pressed '1' to start the recording.
        """
        start = Time()
        filename = "audio/%s" % hashlib.sha1(str(time.time())).hexdigest()
        d = self.agi.recordFile(filename, "gsm", chr(self.digit))

        def save(r):
            digit, type, duration = r
            rec = Recording(store=self.app.store, filename=unicode(filename), created=start, caller_id=self.callerId, duration=duration)
            print "saved!"
            # add it to everybody's queue
            self.app.recordingAdded(rec)
            # resume play where we stopped
            self.setStateAfterSample("play", "audio/listen", currentlyPlaying, offset)
            #self.state.set("play", currentlyPlaying, offset)
            #self.state.set("play", currentlyPlaying, offset)
        d.addCallback(save)
        d.addErrback(self.catchHangup)



    def setStateAfterSample(self, state, sample, *args):
        d = self.agi.streamFile(str(sample), "", 0)
        def audioDone(r):
            print "audio done"
            self.state.set(state, *args)
        d.addCallback(audioDone)



    def enter_admin_start(self):
        d = self.agi.sayDigits("0")
        def handle(r):
            self.state.set("admin")
        d.addCallback(handle)


    def enter_admin(self):
        d = self.agi.getOption("audio/silent", "0123456789#")

        def handle(r):
            digit, endpos = r
            print digit
            if digit == "0":
                self.setStateAfterSample("play", "audio/listen")
                return
            filename = "audio/%s" % digit
            print "queueing to all: %s" % filename
            self.app.queueAll(filename)
            d = self.agi.sayDigits(digit)
            d.addCallback(lambda _: self.state.set("admin"))
        d.addCallback(handle)
        d.addErrback(self.catchHangup)



    def catchHangup(self, f):
        print "***", f
        self.app.sessionEnded(self)
