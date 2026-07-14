"""7주차 정답 — mymodel.py 대체용."""

import mybs


def build_pi_loop():
    bd = mybs.Diagram()
    ref = bd.add(mybs.Step(t_on=1.0, height=1.0, name="ref"))
    err = bd.add(mybs.Sum("+-", name="err"))
    kp = bd.add(mybs.Gain(3.0, name="Kp"))
    integ = bd.add(mybs.Integrator(name="err_int"))
    ki = bd.add(mybs.Gain(2.0, name="Ki"))
    pi = bd.add(mybs.Sum("++", name="PI"))
    sp = bd.add(mybs.Sum("+--", name="plant_sum"))
    xd = bd.add(mybs.Integrator(name="xd"))
    x = bd.add(mybs.Integrator(name="x"))
    damp = bd.add(mybs.Gain(2.0, name="damp"))
    sc = bd.add(mybs.Scope(n_in=1, labels=["y"], name="scope"))
    bd.connect(ref, err[0]); bd.connect(x, err[1])
    bd.connect(err, kp); bd.connect(err, integ); bd.connect(integ, ki)
    bd.connect(kp, pi[0]); bd.connect(ki, pi[1])
    bd.connect(pi, sp[0]); bd.connect(xd, damp); bd.connect(damp, sp[1])
    bd.connect(x, sp[2])
    bd.connect(sp, xd); bd.connect(xd, x)
    bd.connect(x, sc)
    return bd, sc


def build_pendulum():
    bd = mybs.Diagram()
    ref = bd.add(mybs.Step(t_on=1.0, height=0.8, name="ref"))
    ctrl = bd.add(mybs.PyFunction("6.0*(u0-u1) - 2.0*u2", n_in=3, name="PD"))
    dyn = bd.add(mybs.PyFunction("-(9.81/1.0)*sin(u0) - 0.3*u1 + u2", n_in=3,
                                 name="pendulum"))
    omega = bd.add(mybs.Integrator(name="omega"))
    theta = bd.add(mybs.Integrator(name="theta"))
    sc = bd.add(mybs.Scope(n_in=1, labels=["theta"], name="scope"))
    bd.connect(ref, ctrl[0]); bd.connect(theta, ctrl[1]); bd.connect(omega, ctrl[2])
    bd.connect(theta, dyn[0]); bd.connect(omega, dyn[1]); bd.connect(ctrl, dyn[2])
    bd.connect(dyn, omega); bd.connect(omega, theta)
    bd.connect(theta, sc)
    return bd, sc
