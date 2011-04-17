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

class PriorityQueue(object):
    def __init__(self):
        self._q = {}

    def append(self, p, item):
        assert(type(p) == int)
        if p not in self._q:
            self._q[p] = []
        self._q[p].append(item)

    def pop(self):
        for p in sorted(self._q.keys()):
            l = self._q[p]
            if not l:
                continue
            item = l[0]
            del l[0]
            return item
        raise IndexError('Pop from empty priority queue')


    def __iter__(self):
        for p in sorted(self._q.keys()):
            for item in self._q[p]:
                yield item

    def isEmpty(self):
        return not len(list(self))


if __name__ == '__main__':

    p = PriorityQueue()
    p.append(10, 'b1')
    p.append(10, 'b2')
    p.append(5, 'a')
    p.append(11, 'c')

    assert(list(p) == ['a', 'b1', 'b2', 'c'])

    assert(p.pop() == 'a')
    assert(p.pop() == 'b1')
    assert(p.pop() == 'b2')
    assert(p.pop() == 'c')
    print 'ok'

