# Copyright 2026 The Radiativity Company
# Licensed under the Apache License, Version 2.0

"""Aerospace formulas."""

import math

from ucon import Dimension, Number, enforce_dimensions
from ucon import units
from ucon.constants import gravitational_constant, standard_gravity
from ucon.tools.mcp.formulas._registry import register_formula

G = gravitational_constant.as_number()
g0 = standard_gravity.as_number()


@register_formula(
    "orbital_velocity",
    description="Circular orbital velocity (v = sqrt(G*M/r))",
)
@enforce_dimensions
def orbital_velocity(
    body_mass: Number[Dimension.mass],
    orbital_radius: Number[Dimension.length],
) -> Number:
    body_mass = body_mass.to_base()
    orbital_radius = orbital_radius.to_base()
    return (G * body_mass / orbital_radius) ** 0.5


@register_formula(
    "escape_velocity",
    description="Escape velocity (v = sqrt(2*G*M/r))",
)
@enforce_dimensions
def escape_velocity(
    body_mass: Number[Dimension.mass],
    radius: Number[Dimension.length],
) -> Number:
    body_mass = body_mass.to_base()
    radius = radius.to_base()
    return (G * body_mass * 2 / radius) ** 0.5


@register_formula(
    "orbital_period",
    description="Orbital period (T = 2*pi*sqrt(a^3/(G*M)))",
)
@enforce_dimensions
def orbital_period(
    semi_major_axis: Number[Dimension.length],
    body_mass: Number[Dimension.mass],
) -> Number:
    semi_major_axis = semi_major_axis.to_base()
    body_mass = body_mass.to_base()
    return Number(2 * math.pi) * ((semi_major_axis ** 3) / (G * body_mass)) ** 0.5


@register_formula(
    "tsiolkovsky_delta_v",
    description="Tsiolkovsky rocket equation (delta_v = Isp*g0*ln(m0/mf))",
)
@enforce_dimensions
def tsiolkovsky_delta_v(
    specific_impulse: Number[Dimension.time],
    wet_mass: Number[Dimension.mass],
    dry_mass: Number[Dimension.mass],
) -> Number:
    wet_mass = wet_mass.to_base()
    dry_mass = dry_mass.to_base()
    m0 = wet_mass.quantity
    mf = dry_mass.quantity
    return specific_impulse * g0 * math.log(m0 / mf)


@register_formula(
    "thrust",
    description="Rocket thrust (F = mass_flow_rate * exhaust_velocity)",
)
@enforce_dimensions
def thrust(
    mass_flow_rate: Number,
    exhaust_velocity: Number[Dimension.velocity],
) -> Number:
    mass_flow_rate = mass_flow_rate.to_base()
    exhaust_velocity = exhaust_velocity.to_base()
    return mass_flow_rate * exhaust_velocity
