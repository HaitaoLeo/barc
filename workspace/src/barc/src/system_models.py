#!/usr/bin/env python

# ---------------------------------------------------------------------------
# Licensing Information: You are free to use or extend these projects for 
# education or reserach purposes provided that (1) you retain this notice
# and (2) you provide clear attribution to UC Berkeley, including a link 
# to http://barc-project.com
#
# Attibution Information: The barc project ROS code-base was developed
# at UC Berkeley in the Model Predictive Control (MPC) lab by Jon Gonzales
# (jon.gonzales@berkeley.edu). The cloud services integation with ROS was developed
# by Kiet Lam  (kiet.lam@berkeley.edu). The web-server app Dator was 
# based on an open source project by Bruce Wootton
# ---------------------------------------------------------------------------

from numpy import sin, cos, tan, arctan, array, dot
from numpy import sign, argmin, sqrt
import rospy

# discrete non-linear bicycle model dynamics
def f_2s(z, u, vhMdl, trMdl, dt, v_x): 
    """
    process model
    input: state z at time k, z[k] := [beta[k], r[k]], (i.e. slip angle and yaw rate)
    output: state at next time step (k+1)
    """
    
    # get states / inputs
    beta    = z[0]
    r       = z[1]
    d_f     = u
    
    # extract parameters
    (a,b,m,I_z) = vhMdl
    (trMdlFront, trMdlRear) = trMdl

    # comptue the front/rear slip  [rad/s]
    # ref: Hindiyeh Thesis, p58
    a_F     = arctan(beta + a*r/v_x) - d_f
    a_R     = arctan(beta - b*r/v_x)

    # compute tire force
    FyF     = f_pacejka(trMdlFront, a_F)
    FyR     = f_pacejka(trMdlRear, a_R)

    # compute next state
    beta_next   = beta  + dt*(-r + (1/(m*v_x))*(FyF*cos(d_f)+FyR))
    r_next      = r    + dt/I_z*(a*FyF*cos(d_f) - b*FyR);
    return array([beta_next, r_next])

# discrete non-linear bicycle model dynamics
def f_3s(z, u, vhMdl, trMdl, F_ext, dt): 
    """
    process model
    input: state z at time k, z[k] := [v_x[k], v_y[k], r[k]])
    output: state at next time step z[k+1]
    """
    
    # get states / inputs
    v_x     = z[0]
    v_y     = z[1]
    r       = z[2]
    d_f     = u[0]
    FxR     = u[1]

    # extract parameters
    (a,b,m,I_z)             = vhMdl
    (a0, Ff)                = F_ext
    (trMdlFront, trMdlRear) = trMdl
    (B,C,mu)                = trMdlFront
    g                       = 9.81
    Fn                      = m*g/2.0         # assuming a = b (i.e. distance from CoG to either axel)

    # limit force to tire friction circle
    if FxR >= mu*Fn:
        FxR = mu*Fn

    # comptue the front/rear slip  [rad/s]
    # ref: Hindiyeh Thesis, p58
    a_F     = arctan((v_y + a*r)/v_x) - d_f
    a_R     = arctan((v_y - b*r)/v_x)

    # compute lateral tire force at the front
    TM_param    = [B, C, mu*Fn]
    FyF         = -f_pacejka(TM_param, a_F)

    # compute lateral tire force at the rear
    # ensure that magnitude of longitudinal/lateral force lie within friction circle
    FyR_paj     = -f_pacejka(TM_param, a_R)
    FyR_max     = sqrt((mu*Fn)**2 - FxR**2)
    FyR         = min(FyR_max, max(-FyR_max, FyR_paj))

    # compute next state
    v_x_next    = v_x + dt*(r*v_y +1/m*(FxR - FyF*sin(d_f)) - a0*v_x**2 - Ff)
    v_y_next    = v_y + dt*(-r*v_x +1/m*(FyF*cos(d_f) + FyR))
    r_next      = r    + dt/I_z*(a*FyF*cos(d_f) - b*FyR)

    return array([v_x_next, v_y_next, r_next])

# discrete non-linear bicycle model dynamics 6-dof
def f_6s(z, u, vhMdl, trMdl, F_ext, dt): 
    """
    process model
    input: state z at time k, z[k] := [X[k], Y[k], phi[k], v_x[k], v_y[k], r[k]])
    output: state at next time step z[k+1]
    """
    
    # get states / inputs
    X       = z[0]
    Y       = z[1]
    phi     = z[2]
    v_x     = z[3]
    v_y     = z[4]
    r       = z[5]

    d_f     = u[0]
    FxR     = u[1]

    # extract parameters
    (a,b,m,I_z)             = vhMdl
    (a0, Ff)                = F_ext
    (trMdlFront, trMdlRear) = trMdl
    (B,C,mu)                = trMdlFront
    g                       = 9.81
    Fn                      = m*g/2.0         # assuming a = b (i.e. distance from CoG to either axel)

    # limit force to tire friction circle
    if FxR >= mu*Fn:
        FxR = mu*Fn

    # comptue the front/rear slip  [rad/s]
    # ref: Hindiyeh Thesis, p58
    a_F     = arctan((v_y + a*r)/v_x) - d_f
    a_R     = arctan((v_y - b*r)/v_x)

    # compute lateral tire force at the front
    TM_param    = [B, C, mu*Fn]
    FyF         = -f_pacejka(TM_param, a_F)

    # compute lateral tire force at the rear
    # ensure that magnitude of longitudinal/lateral force lie within friction circle
    FyR_paj     = -f_pacejka(TM_param, a_R)
    FyR_max     = sqrt((mu*Fn)**2 - FxR**2)
    Fy          = array([FyR_max, FyR_paj])
    idx         = argmin(abs(Fy))
    FyR         = Fy[idx]

    # compute next state
    X_next      = X + dt*(v_x*cos(phi) - v_y*sin(phi))
    Y_next      = Y + dt*(v_x*sin(phi) + v_y*cos(phi))
    phi_next    = phi + dt*r
    v_x_next    = v_x + dt*(r*v_y +1/m*(FxR - FyF*sin(d_f)) - a0*v_x**2 - Ff)
    v_y_next    = v_y + dt*(-r*v_x +1/m*(FyF*cos(d_f) + FyR))
    r_next      = r    + dt/I_z*(a*FyF*cos(d_f) - b*FyR)

    return array([X_next, Y_next, phi_next, v_x_next, v_y_next, r_next])

def h_2s(x):
    """
    measurement model
    state: z := [beta, r], (i.e. slip angle and yaw rate)
    output h := r (yaw rate)
    """
    C = array([[0, 1]])
    return dot(C, x)

def h_3s(x):
    """
    measurement model
    input   := state z at time k, z[k] := [v_x[k], v_y[k], r[k]])
    output  := [v_x, r] (yaw rate)
    """
    C = array([[1, 0, 0],
               [0, 0, 1]])
    return dot(C, x)

def f_pacejka(trMdl, alpha):
    """
    f_pacejka = d*sin(c*atan(b*alpha))
    
    inputs :
        * trMdl := tire model, a list or tuple of parameters (b,c,d)
        * alpha := tire slip angle [radians]
    outputs :
        * Fy := lateral force from tire [Newtons]
    """
    (b,c,d) = trMdl
    return  d*sin(c*arctan(b*alpha))


def f_KinBkMdl(z,u,vhMdl, dt):
    """
    process model
    input: state z at time k, z[k] := [x[k], y[k], psi[k], v[k]]
    output: state at next time step z[k+1]
    """
    #c = array([0.5431, 1.2767, 2.1516, -2.4169])

    # get states / inputs
    x       = z[0]
    y       = z[1]
    psi     = z[2]
    v       = z[3]

    d_f     = u[0]
    a       = u[1]

    # extract parameters
    (L_a, L_b)             = vhMdl

    # compute slip angle
    bta         = arctan( L_a / (L_a + L_b) * tan(d_f) )

    # compute next state
    x_next      = x + dt*( v*cos(psi + bta) )
    y_next      = y + dt*( v*sin(psi + bta) )
    psi_next    = psi + dt*v/L_b*sin(bta)
    v_next      = v + dt*(a - 0.63*sign(v)*v**2)

    return array([x_next, y_next, psi_next, v_next])

def pacejka(a):
    B = 0.3#20
    C = 1.25
    mu = 0.234
    m = 1.98
    g = 9.81
    D = mu * m * g/2
    D = D*10

    C_alpha_f = D*sin(C*arctan(B*a))
    return C_alpha_f

def f_DynBkMdl_exact(z,u,vhMdl,trMdl,dt):
    zNext = z
    dtn = dt / 10
    for i in range(0,10):
        zNext = f_DynBkMdl(zNext,u,vhMdl,trMdl,dtn)

    return zNext

def f_DynBkMdl(z,u,vhMdl,trMdl,dt):
    x_I      = z[0]
    y_I      = z[1]
    v_x      = z[2]
    v_y      = z[3]
    psi      = z[4]
    psi_dot  = z[5]
    x_I_pred      = z[6]
    y_I_pred      = z[7]
    v_x_pred      = z[8]
    v_y_pred      = z[9]
    psi_pred      = z[10]
    psi_dot_pred  = z[11]

    d_f      = u[0]
    a        = u[1]

    dt_pred = 0.15

    # extract parameters
    (L_f,L_r,m,I_z)         = vhMdl
    (trMdlFront, trMdlRear) = trMdl
    (B,C,mu)                = trMdlFront
    g                       = 9.81
    Fn                      = m*g/2.0         # assuming a = b (i.e. distance from CoG to either axel)

    # comptue the front/rear slip  [rad/s]
    # ref: Hindiyeh Thesis, p58
    a_F = 0
    a_R = 0
    if abs(v_x) > 0.1:
        a_F     = arctan((v_y + L_f*psi_dot)/v_x) - d_f
        a_R     = arctan((v_y - L_r*psi_dot)/v_x)

    FyF = -pacejka(a_F)
    FyR = -pacejka(a_R)

    if abs(a_F) > 30/180*3.1416 or abs(a_R) > 30/180*3.1416:
        print("WARNING: Large slip angles in estimation")

    # compute next state
    x_I_next             = x_I       + dt * (cos(psi)*v_x - sin(psi)*v_y)
    y_I_next             = y_I       + dt * (sin(psi)*v_x + cos(psi)*v_y)
    v_x_next             = v_x       + dt * (a + v_y*psi_dot - 0.63*v_x**2*sign(v_x))
    v_y_next             = v_y       + dt * (2/m*(FyF*cos(d_f) + FyR) - psi_dot*v_x)
    psi_next             = psi       + dt * (psi_dot)
    psi_dot_next         = psi_dot   + dt * (2/I_z*(L_f*FyF - L_r*FyR))

    x_I_next_pred        = x_I       + dt_pred * (cos(psi)*v_x - sin(psi)*v_y)
    y_I_next_pred        = y_I       + dt_pred * (sin(psi)*v_x + cos(psi)*v_y)
    v_x_next_pred        = v_x       + dt_pred * (a + v_y*psi_dot - 0.63*v_x**2*sign(v_x))
    v_y_next_pred        = v_y       + dt_pred * (2/m*(FyF*cos(d_f) + FyR) - psi_dot*v_x)
    psi_next_pred        = psi       + dt_pred * (psi_dot)
    psi_dot_next_pred    = psi_dot   + dt_pred * (2/I_z*(L_f*FyF - L_r*FyR))

    return array([x_I_next,y_I_next,v_x_next,v_y_next,psi_next,psi_dot_next,x_I_next_pred,y_I_next_pred,v_x_next_pred,v_y_next_pred,psi_next_pred,psi_dot_next_pred])

def f_KinBkMdl_predictive(z,u,vhMdl, dt):
    """
    process model
    input: state z at time k, z[k] := [x[k], y[k], psi[k], v[k]]
    output: state at next time step z[k+1]
    """
    #c = array([0.5431, 1.2767, 2.1516, -2.4169])

    # get states / inputs
    x       = z[0]
    y       = z[1]
    psi     = z[2]
    v       = z[3]

    x_pred  = z[4]
    y_pred  = z[5]
    psi_pred= z[6]
    v_pred  = z[7]

    d_f     = u[0]
    a       = u[1]

    # extract parameters
    (L_a, L_b)             = vhMdl

    # compute slip angle
    bta         = arctan( L_a / (L_a + L_b) * tan(d_f) )

    # compute next state
    x_next      = x + dt*( v*cos(psi + bta) )
    y_next      = y + dt*( v*sin(psi + bta) )
    psi_next    = psi + dt*v/L_b*sin(bta)
    v_next      = v + dt*(a - 0.63*sign(v)*v**2)

    x_next_pred      = x_next   + 0.1*( v*cos(psi + bta) )
    y_next_pred      = y_next   + 0.1*( v*sin(psi + bta) ) 
    psi_next_pred    = psi_next + 0.1*v/L_b*sin(bta)
    v_next_pred      = v_next   + 0.1*(a - 0.63*sign(v)*v**2)

    return array([x_next, y_next, psi_next, v_next, x_next_pred, y_next_pred, psi_next_pred, v_next_pred])

def h_DynBkMdl(x):
    # For GPS only:
    C = array([[1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
               [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
               [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
               [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0]])
    return dot(C, x)

def h_KinBkMdl(x):
    """
    measurement model
    """
    # For GPS, IMU and encoders:
    # C = array([[1, 0, 0, 0],
    #            [0, 1, 0, 0],
    #            [0, 0, 1, 0],
    #            [0, 0, 0, 1]])
    # For GPS only:
    C = array([[1, 0, 0, 0],
               [0, 1, 0, 0]])
    return dot(C, x)

def h_KinBkMdl_predictive(x):
    """
    measurement model
    """
    # For GPS, IMU and encoders:
    # C = array([[1, 0, 0, 0],
    #            [0, 1, 0, 0],
    #            [0, 0, 1, 0],
    #            [0, 0, 0, 1]])
    # For GPS only:
    C = array([[1, 0, 0, 0, 0, 0, 0, 0],
               [0, 1, 0, 0, 0, 0, 0, 0]])
    return dot(C, x)
