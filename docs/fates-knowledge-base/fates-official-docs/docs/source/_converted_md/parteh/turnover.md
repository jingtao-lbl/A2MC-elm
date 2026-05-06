# Overview of Turnover

In the turnover phase, biomass is removed from the plant due to turnover
associated with both maintenance and event based processes.

1.  Maintenance turnover is continuous, and typically applies to the
    constant overturn of ageing leaves and fine-roots in evergreens, and
    continuous branchfall in most all species
2.  Event based turnover refers to phenology and/or seasonal losses of
    leaves and fine-roots in deciduous plants, or losses due to the
    damage from storms or fire.

The parameters that govern the rate of turnover are applicable to the
maintenance rates. The severity of losses due to events are governed by
external modules. Since a plant must be exclusively one of evergreen or
deciduous, the parameters that govern retranslocation are applicable in
each context. If a plant is evergreen, the leaf retranslocation
parameter for that functional type is relevant to maintenance turnover
process in leaves. If a plant is deciduous, the leaf retranslocation
parameter is relevant to the seasonal or stress induced drop processes.
The table `turnover_params_table` describes the parameters.

| Symbol | Dimension | Description | Units |
|-------------------|-------------|-------------------------------|--------|
| *τ*<sub>*l*</sub> | pft\* | leaf maintenance turnover timescale | \[years\] |
| *τ*<sub>*f*</sub> | pft\* | fine-root maintenance turnover timescale | \[years\] |
| *τ*<sub>*b*</sub> | pft\* | branch turnover timescale | \[years\] |
| *η*<sub>*c*(*o*)</sub> | pft\* x organ | carbon retranslocation fraction | \[kg/kg\] |
| *η*<sub>*n*(*o*)</sub> | pft\* x organ | nitrogen retranslocation fraction | \[kg/kg\] |
| *η*<sub>*p*(*o*)</sub> | pft\* x organ | phosphorous retranslocation fraction | \[kg/kg\] |

Turnover Parameters

*List of key parameters used for turnover processes. :math:\`*\` Note
that the parameters are specified explicitly for each pft, but the
dimension will be implied in our notation as each plant is already
uniquely asociated with a PFT.\*

# Maintenance Turnover Hypotheses

## Constant Fraction Maintenance Turnover and Retranslocation

Constant fraction turnover can be applied to any arbitrary mass pool.
The loss rates are governed by the turnover parameters for leaves,
fine-roots and branches, as well as the re-translocation fractions. See
`turnover_params_table`

Turnover losses to leaves (organ set *o* = 𝕆<sub>*l*</sub>) and
fineroots (organ set *o* = 𝕆<sub>*f*</sub>) are dictated by their
turnover timescale parameters *τ*<sub>*l*</sub> and *τ*<sub>*f*</sub>
respectively. Branchfall affects the pools of sapwood, structure,
storage and reproduction (if non-zero), which have the branchfall set of
organs *o* = 𝕆<sub>*b*</sub>. Note that with no re-translocation of
nutrients, these rates apply to all nutrient species. The turnover
timescale is in units of \[years-1\], the elapsed time
*Δ*<sub>*y**r*</sub> is in units of years (which in practice is 1/365).
Some amount of nutrient of each species *s* may be re-translocated
directly back into the existing pool as proportions dictated by
*η*<sub>*l*(*s*)</sub> and *η*<sub>*f*(*s*)</sub> in leaves and
fine-root respectively. The turnover flux for carbon *C̃* and nutrient
species *Ñ* are calculated as:

<span label="maint_turn_lossfluxes_eq">
leaves
$$\\tilde{C}\_{(\\mathbb{O}\_l)} &= C\_{(\\mathbb{O}\_l)} \\cdot \\tau\_l \\cdot \\Delta\_{yr}$$
$$\\tilde{N}\_{(\\mathbb{O}\_l,s)} &=  N\_{(\\mathbb{O}\_l,s)} \\cdot \\tau\_l \\cdot  \\Delta\_{yr}  \\cdot (1-\\eta\_{c(ft,\\mathbb{O}\_l )})$$
fine-roots
$$\\tilde{C}\_{(\\mathbb{O}\_f)} &=  C\_{(\\mathbb{O}\_f)}  \\cdot \\tau\_f \\cdot \\Delta\_{yr}$$
$$\\tilde{N}\_{(\\mathbb{O}\_f,s)} &= N\_{(\\mathbb{O}\_f,s)} \\cdot \\tau\_f \\cdot \\Delta\_{yr} \\cdot ((1-\\eta\_{\*(ft,\\mathbb{O}\_f )})$$
branches
$$\\tilde{C}\_{(\\mathbb{O}\_b,s)} &=  C\_{(\\mathbb{O}\_b,s)} \\cdot  \\tau\_{b} \\cdot \\Delta\_{yr}$$
$$\\tilde{N}\_{(\\mathbb{O}\_b,s)} &=  N\_{(\\mathbb{O}\_b,s)} \\cdot  \\tau\_{b} \\cdot \\Delta\_{yr}$$
</span>

Note that as an end-user of the FATES model, the retranslocation factors
are defined in separate arrays by species. The notation we use in the
above equations are simplified to indicate that the nutrient
retranslocation factors specific to the species of interest, e.g.
*η*<sub>\*(*f**t*, 𝕆<sub>*f*</sub>)</sub>. These loss fluxes are
directly removed from the state variables for any organ *o* and species
*s*:

$$C\_{(o)} &= C\_{(o)} - \\tilde{C}\_{(o)}$$
$$N\_{(o,s)} &= N\_{(o,s)} - \\tilde{N}\_{(o,s)}$$

# Event Based Turnover Hypotheses

## Event Based Turnover with Simple Retranslocation Hypotheses

For event-based turnover, the host model must provide PARTEH with the
fractions of the biomass that should be removed from each organ in the
event. Depending on the context, PARTEH will or will-not implement
re-translocation of nutrients.

PARTEH will implement re-translocation for these events:

1.  Deciduous leaf drop

PARTEH will not implement re-translocation for these events:

1.  Fire losses
2.  Herbivory
3.  Storms

The procedures for both contexts are similar, where in the later, the
re-translocation factors can be assumed as zero.

In all situations, when the events are triggered, a fraction mass lost
must be passed in as the argument. As an example, for deciduous leaf
drop, the fraction of dropped leave *f*<sub>*d**r**o**p*</sub> is
assessed from the phenology module and passed into the PARTEH module. We
define a mass *M* which is represented for any carbon or nutrient
species present, (defined by species set *s* = 𝕊), and each organ in
that set *o* = 𝕆<sub>*l*</sub> (perhaps there are multiple leaf organs).
For all species and organs in that set, we define the turnover (or loss)
mass *M⃗*<sub>*l**o**s**s*(𝕊, 𝕆<sub>*l*</sub>)</sub> and the
re-translocated mass *M⃗*<sub>*r**e**t**r*(𝕊, 𝕆<sub>*l*</sub>)</sub>
which is destined for storage *M*<sub>(𝕊, *s**t*)</sub>.

<span label="event_turn_lossfluxes_eq">
$$\\vec{M}\_{loss(\\mathbb{S},\\mathbb{O}\_l)} &= \\quad  (1-\\eta\_{\*(ft,\\mathbb{O}\_l )}) \\cdot M\_{(\\mathbb{S},\\mathbb{O}\_l)} \\cdot f\_{drop}$$
$$\\vec{M}\_{retr(\\mathbb{S},\\mathbb{O}\_l)} &= \\quad  \\eta\_{\*(ft,\\mathbb{O}\_l )}  \\cdot M\_{(\\mathbb{S},\\mathbb{O}\_l)} \\cdot f\_{drop}$$
</span>

Both fluxes decrement the pool of interest, while the loss flux leaves
the live plant's control volume, and the retranslocated mass increments
storage carbon.

<span label="event_turn_incrementfluxes_eq">
$$M\_{(\\mathbb{S},\\mathbb{O}\_l)} &= \\quad M\_{(\\mathbb{S},\\mathbb{O}\_l)} - (\\vec{M}\_{loss(\\mathbb{S},\\mathbb{O}\_l)} + \\vec{M}\_{retr(\\mathbb{S},\\mathbb{O}\_l)})$$
$$M\_{(\\mathbb{S},st)} &=\\quad M\_{(\\mathbb{S},st)} + \\vec{M}\_{retr(\\mathbb{S},\\mathbb{O}\_l)}$$
</span>
