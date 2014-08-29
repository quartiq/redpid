# Robert Jordens <jordens@gmail.com> 2014

from migen.fhdl.std import *
from migen.genlib.record import *
from migen.bus import csr
from migen.bank import csrgen

# https://github.com/RedPitaya/RedPitaya/blob/master/FPGA/release1/fpga/code/rtl/red_pitaya_daisy.v

from .pitaya_ps import SysCDC, Sys2CSR, SysInterconnect, PitayaPS, sys_layout
from .crg import CRG
from .analog import PitayaAnalog
from .pid import FastChain, SlowChain, cross_connect
from .slow import Gpio
from .xadc import XADC
from .delta_sigma import DeltaSigma
from .dna import DNA


#     tcl.append("read_xdc -ref processing_system7_v5_4_processing_system7 ../verilog/ system_processing_system7_0_0.xdc")


class Pid(Module):
    def __init__(self, platform):
        csr_map = {}

        self.submodules.analog = PitayaAnalog(
                platform.request("adc"),
                platform.request("dac"))
        self.submodules.xadc = XADC(platform.request("xadc"))
        csr_map["xadc"] = 29
        for i in range(4):
            pwm = platform.request("pwm", i)
            ds = RenameClockDomains(DeltaSigma(width=16), "sys_double")
            self.comb += pwm.eq(ds.out)
            setattr(self.submodules, "ds%i" % i, ds)
        exp = platform.request("exp")
        self.submodules.gpio_n = Gpio(exp.n)
        csr_map["gpio_n"] = 30
        self.submodules.gpio_p = Gpio(exp.p)
        csr_map["gpio_p"] = 31

        leds = Cat(*(platform.request("user_led", i) for i in range(8)))
        self.comb += leds.eq(self.gpio_p.o)

        self.asg = [Signal((14, True)) for i in range(2)]

        #self.submodules.dna = DNA()

        w, s, c = 14, 25, 18
        self.submodules.fast_a = FastChain(w, s, c)
        csr_map["fast_a"] = 0
        self.submodules.fast_b = FastChain(w, s, c)
        csr_map["fast_b"] = 1
        w = 16
        self.submodules.slow_a = SlowChain(w, s, c)
        csr_map["slow_a"] = 2
        self.submodules.slow_b = SlowChain(w, s, c)
        csr_map["slow_b"] = 3
        self.submodules.slow_c = SlowChain(w, s, c)
        csr_map["slow_c"] = 4
        self.submodules.slow_d = SlowChain(w, s, c)
        csr_map["slow_d"] = 5

        cross_connect(self.gpio_p, [
            self.fast_a, self.fast_b,
            self.slow_a, self.slow_b,
            self.slow_c, self.slow_d,
        ])

        self.comb += [
                self.fast_a.dy.eq(self.asg[0] << (25 - 14)),
                self.fast_b.dy.eq(self.asg[1] << (25 - 14)),
                self.fast_a.adc.eq(self.analog.adc_a),
                self.fast_b.adc.eq(self.analog.adc_b),
                self.analog.dac_a.eq(self.fast_a.dac),
                self.analog.dac_b.eq(self.fast_b.dac),
                self.slow_a.adc.eq(self.xadc.adc[10] << 4),
                self.ds0.data.eq(self.slow_a.dac),
                self.slow_b.adc.eq(self.xadc.adc[8] << 4),
                self.ds1.data.eq(self.slow_b.dac),
                self.slow_c.adc.eq(self.xadc.adc[9] << 4),
                self.ds2.data.eq(self.slow_c.dac),
                self.slow_d.adc.eq(self.xadc.adc[11] << 4),
                self.ds3.data.eq(self.slow_d.dac),
        ]

        self.submodules.csrbanks = csrgen.BankArray(self,
                    lambda name, mem: csr_map[name if mem is None
                        else name + "_" + mem.name_override])
        self.submodules.sys2csr = Sys2CSR()
        self.submodules.csrcon = csr.Interconnect(self.sys2csr.csr,
                self.csrbanks.get_buses())
        self.submodules.syscdc = SysCDC()
        self.comb += self.syscdc.target.connect(self.sys2csr.sys)


class RedPid(Module):
    def __init__(self, platform):
        self.submodules.ps = PitayaPS(platform.request("cpu"))
        self.submodules.crg = CRG(platform.request("clk125"), ~self.ps.frstn[0])
        self.submodules.pid = Pid(platform)

        asg_trig = Signal()
        scope_sys = Record(sys_layout)
        self.specials.scope = Instance("red_pitaya_scope",
                i_adc_a_i=self.pid.analog.adc_a,
                i_adc_b_i=self.pid.analog.adc_b,
                i_adc_clk_i=ClockSignal(),
                i_adc_rstn_i=~ResetSignal(),
                i_trig_ext_i=self.pid.gpio_p.i[0],
                i_trig_asg_i=asg_trig,

                i_sys_clk_i=scope_sys.clk,
                i_sys_rstn_i=scope_sys.rstn,
                i_sys_addr_i=scope_sys.addr,
                i_sys_wdata_i=scope_sys.wdata,
                i_sys_sel_i=scope_sys.sel,
                i_sys_wen_i=scope_sys.wen,
                i_sys_ren_i=scope_sys.ren,
                o_sys_rdata_o=scope_sys.rdata,
                o_sys_err_o=scope_sys.err,
                o_sys_ack_o=scope_sys.ack,
        )


        asg_sys = Record(sys_layout)
        self.specials.asg = Instance("red_pitaya_asg",
                o_dac_a_o=self.pid.asg[0],
                o_dac_b_o=self.pid.asg[1],
                i_dac_clk_i=ClockSignal(),
                i_dac_rstn_i=~ResetSignal(),
                i_trig_a_i=self.pid.gpio_p.i[0],
                i_trig_b_i=self.pid.gpio_p.i[0],
                o_trig_out_o=asg_trig,

                i_sys_clk_i=asg_sys.clk,
                i_sys_rstn_i=asg_sys.rstn,
                i_sys_addr_i=asg_sys.addr,
                i_sys_wdata_i=asg_sys.wdata,
                i_sys_sel_i=asg_sys.sel,
                i_sys_wen_i=asg_sys.wen,
                i_sys_ren_i=asg_sys.ren,
                o_sys_rdata_o=asg_sys.rdata,
                o_sys_err_o=asg_sys.err,
                o_sys_ack_o=asg_sys.ack,
        )

        hk_sys = Record(sys_layout)
        self.submodules.ic = SysInterconnect(self.ps.axi.sys,
                hk_sys, scope_sys, asg_sys, self.pid.syscdc.source)
