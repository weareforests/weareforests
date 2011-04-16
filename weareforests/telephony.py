# We Are Forests
# http://weareforests.com/
#
# a project by Duncan Speakman and Emilie Grenier
# -----------------------------------------------
#
# supported by Nederlands Instituut voor de Mediakunst - http://www.nimk.nl/
#
# Source code (c) 2011 Arjan Scherpenisse <arjan@scherpenisse.net>
# This code is released under the MIT license. See LICENSE for details.

import hashlib
import random
import time

from epsilon.extime import Time
from datetime import timedelta

from twisted.internet import reactor

from axiom.item import Item
from axiom.attributes import text, timestamp, integer

from sparked import application



class Recording (Item):
    """
    A certain recording.
    """

    created = timestamp() 
    caller_id = text()
    filename = text()
    duration = integer() # in frames



class CallerSession (object):
    digit = ord("1")

    app = None
    agi = None
    queue = None

    # info
    channel = None
    callerId = None
    timeStarted = None

    # conference user id
    conferenceUserId = None
    isLivePhone = False

    # state machine
    state = None


    def __init__(self, app, agi):
        self.app = app
        self.agi = agi
        self.queue = []
        print self.agi.variables
        self.callerId = unicode(self.agi.variables['agi_callerid'])
        self.channel = self.agi.variables['agi_channel']
        self.timeStarted = time.time()
        print "New session from", self.callerId
        self.state = application.StateMachine(self, verbose=1)
        self.state.set("start")


    def reEntry(self, agi):
        self.agi = agi
        if self.state.get == 'to_recording':
            self.setStateAfterSample("recording", "weareforests-audio/record")
        if self.state.get == 'to_play':
            self.state.set('play')
        if self.state.get == 'to_admin':
            self.setStateAfterSample("admin", "digits/0")


    def queueAdd(self, r):
        self.queue.append(r)


    def queueAddFirst(self, r):
        self.queue.insert(0, r)


    def enter_start(self):
        timePoint = Time() - timedelta(minutes=15)

        if self.app.baseOpts['debug']:
            self.queue = ["weareforests-audio/silent"]
        else:
            self.queue = ["weareforests-audio/intro"] + [r.filename for r in self.app.store.query(Recording, Recording.created >= timePoint, sort=Recording.created.ascending)]
        self.state.set("play")


    def enter_play(self, recording=None, offset=0):
        """
        A recording has finished or a previous sample has finished;
        choose a new recording to play.
        """
        self.app.pingWebSessions()

        # look up the next recording
        if not recording:
            if not self.queue:
                # if no recording, transfer to conference
                self.app.transferToConference(self)
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
                self.setStateAfterSample("recording", "weareforests-audio/record", current, offset)
            elif digit == ord("0"):
                if self.app.isAdmin(self):
                    self.setStateAfterSample("admin", "digits/0")
                else:
                    print "not authorized to enter admin mode from " + self.callerId
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
        self.app.pingWebSessions()

        start = Time()
        filename = "weareforests-recordings/%s" % hashlib.sha1(str(time.time())).hexdigest()
        d = self.agi.recordFile(filename, "gsm", chr(self.digit), 45)

        def save(r):
            digit, tpe, duration = r
            rec = Recording(store=self.app.store, filename=unicode(filename), created=start, caller_id=self.callerId, duration=duration)
            print "saved!"
            if tpe == 'hangup':
                print "user hung up during recording."
                self.app.sessionEnded(self.channel)

            # add it to everybody's queue
            self.app.recordingAdded(rec)
            # resume play where we stopped
            self.setStateAfterSample("play", "weareforests-audio/listen", currentlyPlaying, offset)

        d.addCallback(save)
        d.addErrback(self.catchHangup)


    def setStateAfterSample(self, state, sample, *args):
        d = self.agi.streamFile(str(sample), "", 0)
        def audioDone(r):
            print "audio done"
            self.state.set(state, *args)
        d.addCallback(audioDone)


    def enter_admin(self):
        self.app.pingWebSessions()
        d = self.agi.getOption("weareforests-audio/silent", "0123456789#")

        def handle(r):
            digit, endpos = r
            print digit
            if digit == "0":
                self.setStateAfterSample("play", "weareforests-audio/listen")
                return
            filename = "weareforests-audio/%s" % digit
            print "queueing to all: %s" % filename
            self.app.queueAll(filename)
            d = self.agi.sayDigits(digit)
            d.addCallback(lambda _: self.state.set("admin"))
        d.addCallback(handle)
        d.addErrback(self.catchHangup)


    def catchHangup(self, f):
        if self.state.get == 'to_conference':
            return

        print "***", f
        self.app.sessionEnded(self.channel)
