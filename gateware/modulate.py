# Copyright 2014-2015 Robert Jordens <jordens@gmail.com>
#
# This file is part of redpid.
#
# redpid is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# redpid is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with redpid.  If not, see <http://www.gnu.org/licenses/>.

from migen import *
from misoc.interconnect.csr import CSRStorage

from .cordic import Cordic
from .filter import Filter


class Demodulate(Filter):
    def __init__(self, **kwargs):
        Filter.__init__(self, **kwargs)

        width = len(self.y)
        self.delay = CSRStorage(width)
        self.phase = Signal(width)

        self.submodules.cordic = Cordic(
            width=width + 1, stages=width + 1, guard=2,
            eval_mode="pipelined", cordic_mode="rotate",
            func_mode="circular")
        self.comb += [
            self.cordic.xi.eq(self.x),
            self.cordic.zi.eq((self.phase + self.delay.storage) << 1),
            self.y.eq(self.cordic.xo >> 1)
        ]


class Modulate(Filter):
    def __init__(self, freq_width=32, **kwargs):
        Filter.__init__(self, **kwargs)

        width = len(self.y)
        self.amp = CSRStorage(width)
        self.freq = CSRStorage(freq_width)
        self.phase = Signal(width)

        z = Signal(freq_width)
        stop = Signal()
        self.sync += [
            stop.eq(self.freq.storage == 0),
            If(stop,
                z.eq(0)
            ).Else(
                z.eq(z + self.freq.storage)
            )
        ]

        self.submodules.cordic = Cordic(
            width=width + 1, stages=width + 1, guard=2,
            eval_mode="pipelined", cordic_mode="rotate",
            func_mode="circular")
        self.comb += [
            self.phase.eq(z[-len(self.phase):]),
            self.cordic.xi.eq(self.amp.storage + self.x),
            self.cordic.zi.eq(self.phase << 1),
            self.y.eq(self.cordic.xo >> 1)
        ]
