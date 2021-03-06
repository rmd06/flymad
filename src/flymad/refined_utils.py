import numpy as np
import collections
import threading

import roslib; roslib.load_manifest('flymad')

import rospy
from flymad.msg import HeadDetect

PX = -0.6
PY = -0.6

TTM_NAMES = {HeadDetect.TARGET_HEAD:"head",
             HeadDetect.TARGET_BODY:"body",
}

def target_dx_dy_from_message(msg):
    """returns None,None if the head/body was not detected"""

    dx = dy = None
    tx = ty = HeadDetect.NO_DETECT

    if msg.target_type == HeadDetect.TARGET_HEAD:
        tx = msg.head_x
        ty = msg.head_y
    elif msg.target_type == HeadDetect.TARGET_BODY:
        tx = msg.body_x
        ty = msg.body_y

    if tx != HeadDetect.NO_DETECT:
        dx = msg.target_x - tx
        dy = msg.target_y - ty

    return dx, dy

def predict_position(s, latency):
    """ returns (x,y,vx,vy) """
    if latency > 0:
        #add predict the position based on the current velocity
        return s[0] + s[2]*latency,s[1] + s[3]*latency,s[2],s[3]
    else:
        return s[0],s[1],s[2],s[3]

class ControlManager:

    PX = -0.6
    PY = -0.6
    PV = 0.0
    LATENCY = 0.0

    def __init__(self, enable_latency_correction=False, debug=True):
        self.PX = float(rospy.get_param('ttm/px', ControlManager.PX))
        self.PY = float(rospy.get_param('ttm/py', ControlManager.PY))
        self.PV = float(rospy.get_param('ttm/pv', ControlManager.PV))
        self.LATENCY = float(rospy.get_param('ttm/latency', ControlManager.LATENCY))
        self._debug = debug
        self._timer = rospy.Timer(rospy.Duration(1.0), self._update_params)

    def _update_params(self, evt):
        #get the params in one call for efficiency
        cfg = rospy.get_param('/ttm/', {})
        self.PX = float(cfg.get('px', ControlManager.PX))
        self.PY = float(cfg.get('py', ControlManager.PY))
        self.PV = float(cfg.get('pv', ControlManager.PV))

    def compute_dac_cmd(self, a, b, dx, dy, v=0.0):
        """
        calculates dac values based on position gains (PX,Y), errors dx,dy
        and possibly increases gain if fly is walking fast (another strategy
        to minimise lag
        """
        #in the flymad_dorothea setup
        #left = +ve dx
        #up = +ve dy

        #never less than 1, we don't want to slow tracking
        pv = max(self.PV*abs(v) if self.PV > 0 else 1.0, 1.0)

        cmdA = a+(self.PX*dx*pv)
        cmdB = b+(self.PY*dy*pv)

        if self._debug:
            print "%+.1f,%+.1f -> %+.1f,%+.1f (%+.1f,%+.1f)(v:%+.3f)" % (a,b,cmdA,cmdB,dx,dy,pv)

        return cmdA,cmdB

    def predict_position(self, s):
        return predict_position(s, self.LATENCY)

    def __repr__(self):
        return "<ControlManager PX:%.1f PY:%.1f PV:%.1f LATENCY:%.1f>" % (
                    self.PX,self.PY,self.PV,self.LATENCY)

class StatsManager:
    def __init__(self, secs, fps=100):
        types = (HeadDetect.TARGET_HEAD, HeadDetect.TARGET_BODY)
        self._processingtime = {k:collections.deque(maxlen=secs*fps) for k in types}
        self._accuracy = {k:collections.deque(maxlen=secs*fps) for k in types}
        self._framenumber = 0
        self._lock = threading.Lock()

    def process(self, msg):
        if not (msg.framenumber > self._framenumber):
            return

        try:
            with self._lock:
                self._processingtime[msg.target_type].append(msg.processing_time)
                head_hit = msg.head_x != HeadDetect.NO_DETECT
                body_hit = msg.body_x != HeadDetect.NO_DETECT
                if msg.target_type == HeadDetect.TARGET_HEAD:
                    self._accuracy[HeadDetect.TARGET_HEAD].append(head_hit)
                self._accuracy[HeadDetect.TARGET_BODY].append(body_hit)
        except KeyError:
            pass

    def get_stats(self):
        with self._lock:
            pt = {k:np.mean(v) for k,v in self._processingtime.iteritems()}
            ac = {k:np.mean(v) for k,v in self._accuracy.iteritems()}
        return pt,ac

