# -*- test-case-name: twisted.test.test_issues -*-
# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
# 

from twisted.spread import pb
from twisted.internet import defer
from twisted.issues.issue import Issue, IssueQueue, InQueue, PendingFixerAnalysis
from twisted.issues.task import Task
from twisted.python.components import Interface

class IssueException(Exception):
    """An error occurred within twisted.issues.
    """

class CouldNotNotify(IssueException):
    """I could not notify for some reason.
    """

class CouldNotTranscribe(IssueException):
    """I could not begin a transcript between two notifiers.
    """

class IIssueNotifier(Interface):
    """A way to notify a user that various things have happened in
    twisted.issues.
    """
    def contactInformation(self):
        """Return a human-readable string which shows how to contact this notifier.
        """

    def beginTranscribing(self, otherNotifier):
        """Begin a transcript of a conversation between this and another notifier.

        This is useful in real-time chat systems.  Raises CouldNotTranscribe if
        these notifiers are incompatible or there is no way to track
        communications between them.

        Returns: (currently, a twisted.words.service.Transcript; this needs to
        be interfaced out as well.)

        Notes: If only there were some way of tracking all these people.
        """

    def notifyText(self, message):
        """Send a text notification message to me.

        Raises CouldNotNotify if the user is not available.
        """

    def notifyFixerReady(self, issueFixer, issue):
        """Notify me that a fixer is ready to fix an issue that I brought up.

        @param issueFixer: the IssuePerson who is now ready to deal with my
                           issue
        @param issue: the Issue that is being resolved
        """

    def notifyFinderReady(self, issueFinder, issue):
        """Notify me that a finder is ready for me to start talking to them
        about an issue.

        This notification is sent when the conversation begins, in order to
        give the fixer a frame of reference for the conversation. (In most chat
        clients, this should pop up a new window with the finder's name in it.)
        """
        
    def notifyFinderGone(self, issueFinder, issue):
        """Notify me that the finder who I was talking to has reclassified the
        issue.
        """

    def notifyFixerGone(self, issueFixer, issue):
        """Notify me that the fixer who I was talking to has reclassified the
        issue.
        """

class IssuePerson(pb.Perspective):
    """A person who interacts with issues.

    We refer to the two kinds of people who interact with issues as follows:

      - B{issueFinder}: A person who finds issues.  This may be a customer, a
        developer in their capacity as a bug-hunter, or a user who has found a
        problem.

      - B{issueFixer}: A person who can fix the problems that are found.  These
        people may be allocated in some manner associated with tasks.  Managers
        are special instances of issue fixers with particular permissions.
    
    """

    notifier = None

    def __init__(self, perspectiveName, identityName="Nobody"):
        pb.Perspective.__init__(self, perspectiveName, identityName)
        self.notifier = None
        # dicts of number:issue currently in conversation.
        self.currentlyFinding = {}
        self.currentlyFixing = {}

    def setNotifier(self, newNotifier):
        self.notifier = newNotifier

    def beginTranscribing(self, otherPerson):
        if self.notifier and otherPerson.notifier:
            return self.notifier.beginTranscribing(otherPerson.notifier)
        else:
            raise CouldNotTranscribe("One of the parties was not logged in.")

    def notifyText(self, text):
        if self.notifier:
            self.notifier.notifyText(text)
    def notifyFixerReady(self, issueFixer, issue):
        if self.notifier:
            self.notifier.notifyFixerReady(issueFixer, issue)
    def notifyFinderReady(self, issueFinder, issue):
        if self.notifier:
            self.notifier.notifyFinderReady(issueFinder, issue)
    def notifyFinderGone(self, issueFinder, issue):
        if self.notifier:
            self.notifier.notifyFinderGone(issueFinder, issue)
    def notifyFixerGone(self, issueFixer, issue):
        if self.notifier:
            self.notifier.notifyFixerGone(issueFixer, issue)

class IssueRepository(pb.Service):
    """I am a repository for issues, their tasks, fixers, and finders.

    This is the Service object in the twisted.issues universe.
    """

    perspectiveClass = IssuePerson

    def __init__(self, serviceName, serviceParent=None, authorizer=None):
        pb.Service.__init__(self, serviceName, serviceParent, authorizer)
        self.currentIssueNumber = 0
        self.issues = {}               # issueNumber: issue
        self.tasks = {}                # taskNumber: task
        self.queues = {}               # name: queue
        self.buildQueue("default")

    def getQueue(self, name):
        return self.queues[name]

    def buildQueue(self, name):
        q = IssueQueue(name)
        self.queues[name] = q
        return q

    # Some utility methods for initial state information.

    def buildIssue(self, issueFinder, description, initialState):
        n = self.getIssueNumber()
        issue = Issue(issueFinder, description, initialState, n)
        self.issues[n] = issue
        return issue

    def buildTask(self, issuePerson, description):
        n = self.getIssueNumber()
        t = Task(issuePerson, description, n)
        self.tasks[n] = t
        return t

    def queueIssue(self, issueFinder, description, queueName="default"):
        """Insert a new issue into an existing queue. Raises KeyError if queue
        does not exist."""
        
        return self.buildIssue(issueFinder, description, InQueue(self.queues[queueName]))

    def reportBug(self, issueFinder, description):
        """A traditional 'report bug' interface, with *no required fields*.
        The quickest way to get an issue into the system.
        """
        return self.buildIssue(issueFinder, description, PendingFixerAnalysis())

    def getIssueNumber(self):
        self.currentIssueNumber = self.currentIssueNumber + 1
        return self.currentIssueNumber


    def loadIssue(self, issueNumber):
        """Load an issue from this repository.
        """
        try:
            issue = self.issues[issueNumber]
        except KeyError:
            return defer.fail()
        else:
            return defer.succeed(issue)


    def loadTask(self, taskNumber):
        """Load an issue from this repository.
        """
        try:
            task = self.tasks[taskNumber]
        except KeyError:
            return defer.fail()
        else:
            return defer.succeed(task)
