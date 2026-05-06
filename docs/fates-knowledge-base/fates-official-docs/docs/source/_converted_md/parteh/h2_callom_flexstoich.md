# Allocation Hypothesis 2: Allometrically Guided, Carbon and Nutrients with Prioritization and Flexible Target Stoichiometry

This hypothesis assumes there is a single carbon species, and an
arbitrary number of nutrient species for each of the six plant organ
pools:

1.  Leaf
2.  Fine-root
3.  Sapwood
4.  Structural wood
5.  Storage
6.  Reproductive

The PARTEH code for hypothesis two currently only enables Nitrogen and
Phosphorous. The code can be easily extended to handle other nurtient
species, however this would increase the number of parameters used and
complicate things for a broader user base. Without an imediate need for
other species, they have been left out. This documentation will use the
generic symbol *N* for all nutrients of any species indexed by *s* in
organs indexed by *o*.

The state variables, boundary conditions and parameters for hypothesis 2
are described in `h2_variable_table`.

<table style="width:98%;">
<caption>Table H2-1</caption>
<colgroup>
<col style="width: 26%" />
<col style="width: 26%" />
<col style="width: 35%" />
<col style="width: 10%" />
</colgroup>
<thead>
<tr>
<th>Symbol</th>
<th>Dimension</th>
<th>Description</th>
<th>Units</th>
</tr>
</thead>
<tbody>
<tr>
<td colspan="4">State Variables</td>
</tr>
<tr>
<td><span
class="math inline"><em>C</em><sub>(<em>o</em>)</sub></span></td>
<td>organ</td>
<td>carbon mass</td>
<td>[kg]</td>
</tr>
<tr>
<td><span
class="math inline"><em>N</em><sub>(<em>o</em>, <em>s</em>)</sub></span></td>
<td>organ x species</td>
<td>nutrient mass</td>
<td>[kg]</td>
</tr>
<tr>
<td colspan="4">Input/Output Boundary Conditions</td>
</tr>
<tr>
<td><span
class="math inline"><em>R</em><sub><em>m</em><em>d</em></sub></span></td>
<td>scalar</td>
<td>Maint. Resp. Deficit</td>
<td>[kg]</td>
</tr>
<tr>
<td><span class="math inline"><em>d</em></span></td>
<td>scalar</td>
<td>Reference Stem Diameter</td>
<td>[cm]</td>
</tr>
<tr>
<td colspan="4">Input Boundary Conditions</td>
</tr>
<tr>
<td><span
class="math inline"><em>f</em><sub><em>t</em><em>r</em><em>i</em><em>m</em></sub></span></td>
<td>scalar</td>
<td>Canopy Trim Fraction</td>
<td>[0-1]</td>
</tr>
<tr>
<td><span
class="math inline"><em>C</em><sub><em>g</em><em>a</em><em>i</em><em>n</em></sub></span></td>
<td>scalar</td>
<td>Daily carbon gain</td>
<td>[kg]</td>
</tr>
<tr>
<td><span
class="math inline"><em>N</em><sub><em>g</em><em>a</em><em>i</em><em>n</em>(<em>s</em>)</sub></span></td>
<td>species</td>
<td>Daily nutrient gain</td>
<td>[kg]</td>
</tr>
<tr>
<td colspan="4">Output Boundary Conditions</td>
</tr>
<tr>
<td><span
class="math inline"><em>C</em><sub><em>e</em><em>x</em><em>u</em></sub></span></td>
<td>scalar</td>
<td>Daily carbon exudation</td>
<td>[kg]</td>
</tr>
<tr>
<td><span
class="math inline"><em>N</em><sub><em>e</em><em>x</em><em>u</em>(<em>s</em>)</sub></span></td>
<td>species</td>
<td>Daily nutrient exudation</td>
<td>[kg]</td>
</tr>
<tr>
<td><span
class="math inline"><em>R</em><sub><em>g</em></sub></span></td>
<td>scalar</td>
<td>Growth Respiration</td>
<td>[kg]</td>
</tr>
<tr>
<td colspan="4">Parameters</td>
</tr>
<tr>
<td><span
class="math inline"><em>α</em><sub>(<em>o</em>, <em>s</em>)</sub></span></td>
<td>pft* x organ x species</td>
<td>ideal stoichiometric ratios</td>
<td>[kg/kg]</td>
</tr>
<tr>
<td><span
class="math inline"><em>β</em><sub>(<em>o</em>, <em>s</em>)</sub></span></td>
<td>pft* x organ x species</td>
<td>minimum stoichiometric ratios</td>
<td>[kg/kg]</td>
</tr>
<tr>
<td><span
class="math inline"><em>p</em><sub><em>t</em><em>m</em></sub></span></td>
<td>pft*</td>
<td>tissue vs. resp. prioritization</td>
<td>[0-1]</td>
</tr>
<tr>
<td><span
class="math inline"><em>ω</em><sub>(<em>o</em>)</sub></span></td>
<td>pft* x organ</td>
<td>prioritization level</td>
<td>[1-6]</td>
</tr>
<tr>
<td><span
class="math inline"><em>r</em><sub><em>g</em>(<em>o</em>)</sub></span></td>
<td>pft* x organ</td>
<td>unit growth respiration rate</td>
<td>[kg/kg]</td>
</tr>
</tbody>
</table>

*List of key states, boundary conditions and parameters in hypothesis 2,
allometric multi-nutrient species with fixed target stoichiometry. In
this notation, o and s are used to index the organ and species
(nutrient) dimensions. :math:\`*\` Note that the parameters are
specified explicitly for each pft, but the dimension will be implied in
our notation as each plant is already uniquely asociated with a PFT.\*

## Order of Operations

It is assumed that over the sub-daily time-steps, photosynthesis,
respiration and nutrient uptake has been accumulated. These provide net
carbon and nutrient gains at the end of the day to drive allocations.
The first daily procedure is the removal of biomass from the plant due
to turnover coming from leaf-fall, branchfall and turnover of
fine-roots. The second daiy procedure seeks to replenish the plants
existing pools with respect to a target mass that is defined by the
stature (size) of the plant (this may be thought of of bringing the
plant back to allometric targets). Next, if resources are still
available the plant will grow in stature, where allocation seeks to grow
the pools out concurrently with each other. If any nutrient resources
remain, they will be allocated towards ideal stoichiometric proportions,
which may or may not be greater than the proportionalities needed during
stature growth. And finally, all excess materials are sent to storage
pools (if not full) and then exuded through roots.

1.  (sub-daily) `h2_accumulate_cn_section`
2.  (daily) Perform Allocations to Pools
    1.  `h2_turnover_section`
    2.  `h2_replenish_targets_section`
    3.  `h2_grow_stature_section`
    4.  `h2_transfer_ideal_nutrients_section`
    5.  `h2_exude_section`

VISUALIZATION

## Accumulate Carbon and Nutrients

Photosynthesis and maintenance respiration are sensitive to light levels
and tissue temperatures, which vary over sub-daily timescales. In
CLM/ELM, this "fast" time-step is 30 minutes. It is assumed that the
host-model (e.g. FATES) will handle the calculation of GPP and
maintenance respiration, and integrate these quantities over the course
of the day. There is some flexibility in how PARTEH handles allocations
with these two constraints. Along with nutrient inputs, the host model
must provide the boundary conditions of daily carbon gain
*C*<sub>*g**a**i**n*</sub>, and optionally, the maintenance respiration
deficit *R*<sub>*m**d*</sub>.

There are two scenarios that this hypothesis accomodates:

1.  The host model calculates the difference between daily integrated
    GPP and maintenance respiration and passes it as
    *C*<sub>*g**a**i**n*</sub>, which may be positive or negative. No
    maintenance respiration is tracked, because it is paid instantly,
    and thus *R*<sub>*m**d*</sub> = 0.
2.  The host model passes GPP as *C*<sub>*g**a**i**n*</sub> (always
    positive), and maintains a running account of maintenance
    respiration deficit, thereby adding the daily integrated maintenance
    respiration to *R*<sub>*m**d*</sub>. The PARTEH model will then
    attempt to pay for *R*<sub>*m**d*</sub>, and passing back the
    updated deficit to the host.

The third key boundary condition provided by the host, is the daily
integrated flux of nutrients from soil to fine-roots,
*N*<sub>*g**a**i**n*(*s*)</sub>, for each nutrient species *s*.
Depending on the soil biogeochemistry model in use, PARTEH can provide
information about the state of the plant, to help the soil
biogeochemistry module determine the plant's affinity in a competitive
nutrient environment.

## Remove Biomass From All Pools as Turnover

Different methodologies for calculating turnover exist, and are executed
prior to allocations. Event based turnover is covered in
`event_turnover_section`, and maintenance turnover is covered in
`maintenance_turnover_section`.

## Replenish Pools with Respect to Target Levels

The organs of each plant have target masses for carbon
*C̀*<sub>(*o*)</sub> and nutrients *Ǹ*<sub>(*o*, *s*)</sub>. These
targets are goverened by the stature of the plant, and can be thought of
as the desireable pool sizes that the plant would like to have to be
ready for further growth in stature. Turnover, as described in the
previous section, draws down the masses away from the target values
associated with their current stature. Sometimes this is considered
being "off allometry". In this hypothesis, the base assumption is that
the targets are dictated by allometry, but other methods of determining
these targets are possible as well. Allometric targets are typically a
function of plant diameter dbh , plant functional type pft, and an
indicator of how much trimming of unproductive lower boughs a plant has
executed trimming.

<span label="h2_c_target_eq">
$$\\grave{C}\_{(o)} &= \\text{func}(\\text{dbh},\\text{pft},\\text{trimming})$$
</span>

For nutrient species, the targets are based on a parameter that
describes the minimum stoichiometric ratios with carbon
*β*<sub>(*o*, *s*)</sub> that are required for the plant to grow in
stature.

<span label="h2_n_target_eq">
$$\\grave{N}\_{(o,s)} &= \\quad \\grave{C}\_{(o)} \\cdot \\beta\_{(o,s)}$$
</span>

In this step, the plant must allocate resources to bring its pools up to
the targets before growing out the plant's stature again. This process
relies on calculating the targets, and then the carbon
*Č*<sub>(*o*)</sub> and nutrient *Ň*<sub>(*o*, *s*)</sub> demands to
reach those targets.

Given these targets, the demands for each carbon *Č*<sub>(*o*)</sub> and
nutrient *Ň*<sub>(*o*, *s*)</sub> pool are calculated. In the case of
carbon, a growth tax is applied to allocation, which contributes to the
demand. Here, that tax is governed by a unit growth parameter
*r*<sub>*g*(*o*)</sub>, however more complicated growth tax functions
could be used as well. Likewise, a pool may already be at or above its
current target. Only positive demands are used, so a floor of 0 is
imposed on the demand.

<span label="h2_c_demand_eq">
$$\\check{C}\_{(o)} &=  \\quad \\text{max}(0,(\\grave{C}\_{(o)} - C\_{(o)}) \\cdot (1+r\_{g(o)}))$$
</span>

<span label="h2_n_demand_eq">
$$\\check{N}\_{(o,s)} &=  \\quad \\text{max}(0,\\grave{N}\_{(o,s)} - N\_{(o,s)} )$$
</span>

Each plant organ is then associated with any priority level, 0 through
6. Organs associated with priority 1 will get first access to carbon and
nutrients and organs associated with priority order will get the
remainder. The priority order levels are ascended sequentially, we
indicate the valid set of organ indices in the current priority order
level *p**r* as set 𝕆<sub>*p**r*</sub>. Note that priority level 0 is a
special bypass level. This is used for reproductive allocation, which
currently is only generated during the stature growth step. Note, it is
not required that ANY organs are classified as priority 1.

The first priority level (*p**r* = 1, 𝕆<sub>1</sub>) has two approaches
based on the boundary conditions provided.

1.  It is assumed that maintenance respiration costs have not been paid
    yet by the host model, and thus the maintenance respiration deficit
    *R*<sub>*m**d*</sub> exists and is non-zero, and that daily carbon
    gains are greater than or equal to zero. This is detailed in
    `p1_explicit_rmd_section`.
2.  It is assumed that boundary condition for *C*<sub>*g**a**i**n*</sub>
    has already decucted maintenance respiration costs. Here,
    *R*<sub>*m**d*</sub> is always zero, and if the plant is not
    metabolically dormant, *C*<sub>*g**a**i**n*</sub> may be positive or
    negative. This is detailed in :ref:"p1\_implicit\_rmd\_section'.

### Priority 1 Carbon Fluxes with explicit Maintenance Respiration Deficit

> First, we assess how much total demand is coming from the priority 1
> carbon pools.

<span label="h2_c_priority1_sum_eq">
$$\\check{C}\_1 &= \\sum\_{o=\\mathbb{O}\_{1}} \\check{C}\_{(o)}$$
</span>

The total carbon that can be translocated from storage is
*C⃗*<sub>*s**t* − *t**r**a**n*</sub>. Any number of models could be used
to determine how resistant the storage is to pay off high-priority
tissues and maintenance respiration costs. Below is an example of a
simple function where the transferable carbon decreases as the square of
the pool's proportion with its target. Where storage is denoted organ
index *o* = *s**t*:

<span label="h2_c_st_trans_eq">
$$C\_{st-tran} &= C\_{(st)} \\cdot \\text{min}(1,C\_{(st)} / \\grave{C}\_{(st)}  )$$
</span>

The total carbon that is transferred *C⃗*<sub>*t**o**t*</sub> is the
minimum between the demanded and what can be transferred from both
storage and carbon gains *C*<sub>*g**a**i**n*</sub>. The fraction of how
much is transferred versus demanded, *f*<sub>*t**o**t*</sub>, is also
useful.

<span label="h2_c_vec_tot_eq">
$$\\vec{C}\_{tot} &= \\quad \\text{min}( \\check{C}\_1 + R\_{md} , C\_{st-tran} + C\_{gain} )$$
$$f\_{tot} &= \\quad \\vec{C}\_{tot} / (\\check{C}\_1 + R\_{md})$$
</span>

Preference can be specified to allocate available carbon to either
maintenance respiration, or the priority 1 pools. To do so, we define a
redistribution flux *C⃗*<sub>*R**D*</sub> that scales the transfer
between the two options. The parameter *p*<sub>*t**m*</sub>, which
varies betwen 0 and 1, sets the relative priority of each. When the
parameter is greater than 0.5, *C⃗*<sub>*R**D*</sub> re-directs flux from
relieving maintenance respiration deficit (*C⃗*<sub>*m**d*</sub>) towards
priority 1 tissues (*C⃗*<sub>1</sub>). Alternatively, when the parameter
is less than 0.5, *C⃗*<sub>*R**D*</sub> is redictect from replacing
priority 1 tissues into maintenance respiration deficit.

<span label="h2_redirection_eq">
for *p*<sub>*t**m*</sub> &gt; 0.5
$$\\vec{C}\_{RD}   &= \\quad \\text{min}( (p\_{tm}-0.5)/0.5 \\cdot f\_{tot} \\cdot R\_m, (1-f\_{tot}) \\cdot \\check{C}\_1 )$$
$$\\vec{C}\_1      &= \\quad f\_{tot} \\cdot \\check{C}\_1 + \\vec{C}\_{RD}$$
$$\\vec{R}\_{md} &= \\quad f\_{tot} \\cdot R\_{md} - \\vec{C}\_{RD}$$
for *p*<sub>*t**m*</sub> &lt; 0.5
$$\\vec{C}\_{RD}   &= \\quad \\text{min}( (0.5-p\_{tm})/0.5 \\cdot f\_{tot} \\cdot \\check{C}\_1, (1-f\_{tot}) \\cdot R\_{md} )$$
$$\\vec{C}\_1      &= \\quad  f\_{tot} \\cdot \\check{C}\_1 - C\_{RD}$$
$$\\vec{R}\_{md} &= \\quad  f\_{tot} \\cdot R\_{md} + \\vec{C}\_{RD}$$
</span>

The total flux of carbon into each priority 1 pool is then governed,
linearly, by the fraction of which their demand constitutes the whole
demand. For any carbon pool in organ found in priority set
𝕆<sub>1</sub>.

<span label="h2_p1_c_vec_eq">
$$\\vec{C}\_{(\\mathbb{O}\_1)} &= \\vec{C}\_1 \\cdot \\check{C}\_{(\\mathbb{O}\_1)} / \\check{C}\_1$$
</span>

With the fluxes known, increment the priority 1 carbon pools, increment
their growth respiration. For each organ in set 𝕆<sub>1</sub>:

<span label="h2_p1_increment_pools_eq">
$$C\_{(\\mathbb{O}\_1)} &= \\quad C\_{(\\mathbb{O}\_1)} + \\vec{C}\_{(\\mathbb{O}\_1)} / (1+r\_{g(\\mathbb{O}\_1)})$$
$$R\_{g(\\mathbb{O}\_1)} &= \\quad R\_{g(\\mathbb{O}\_1)} + \\vec{C}\_{(\\mathbb{O}\_1)} \\cdot  r\_{g(\\mathbb{O}\_1)} / (1+r\_{g(\\mathbb{O}\_1)})$$
</span>

Decrement maintenance respiration deficit, daily carbon gain, and
potentially, storage carbon (where *o* = *s**t*).

<span label="h2_p1_decrement_pools_eq">
$$R\_{md} &= \\quad R\_{md} - \\vec{R}\_{md}$$
$$\\vec{C}\_{gain} &= \\quad \\text{min}(C\_{gain}, \\vec{C}\_{tot})$$
$$C\_{gain} &= \\quad C\_{gain} - \\vec{C}\_{gain}$$
$$C\_{(st)} &= \\quad C\_{(st)} - \\text{max}(0,  \\vec{C}\_{tot} - \\vec{C}\_{gain})$$
</span>

### Priority 1 Carbon Fluxes with Implicit Maintenance Respiration

Recall that as an alternative to `p1_explicit_rmd_section`, carbon gains
may subsume maintenance respiration. With this assumption, the equations
in the previous section are valid in all cases, except for when
*C*<sub>*g**a**i**n*</sub> &lt; 0. For this condition, it is assumed
that storage carbon will pay off the negative carbon gain and bring it
back to zero. Caution must be made, in so much that calculations of
maintenance respiration are conducted so that the plant does create
impossible conditions where storage carbon becomes zero. PARTEH will
fail gracefully in this condition. The remainder of this section
specifically details the condition where
*C*<sub>*g**a**i**n*</sub> &lt; 0.

The flux from storage brings negative daily carbon gain up to zero.

<span label="h2_implicit_c_gain_eq">
$$\\vec{C}\_{gain} &= \\quad - C\_{gain}$$
$$C\_{(st)} &= \\quad C\_{(st)} - \\vec{C}\_{gain}$$
$$C\_{gain} &= 0$$
</span>

Any extra flux that can transferred out of storage and into priority 1
tissues, would then be calculated by using the same function that
determines the maximum transferrable carbon, as in `h2_c_st_trans_eq`.
However, in this case *C*<sub>*s**t* − *t**r**a**n**s*</sub> is
calculated after the carbon to replace the negative
*C*<sub>*g**a**i**n*</sub> is removed in `h2_implicit_c_gain_eq`. The
demand for carbon to priority 1 tissues follows the same methods as
`p1_explicit_rmd_section`.

<span label="h2_implicit_extra_eq">
if  *C*<sub>*g**a**i**n*</sub> &lt; 0
$$\\vec{C}\_1 &= \\quad \\text{min}(C\_{st-trans},\\check{C}\_1)$$
</span>

Transfer from storage into priority 1 tissues also follows the same
logic as `p1_explicit_rmd_section`, specifically `h2_p1_c_vec_eq`. And
finally, decrement storage again, as per total flux into priority 1
organs *C⃗*<sub>1</sub>.

<span label="h2_p1_implicit_store2c1_eq">
$$C\_{(st)} &= \\quad C\_{(st)} + \\vec{C}\_{1}$$
</span>

### Priority 1 Nutrient Fluxes

With the priority 1 carbon pools updated, the fluxes of nutrients into
those pools can proceed. The targets *Ǹ*<sub>(*o*, *s*)</sub>, and
subsequently the deficit from the target *Ň*<sub>(*o*, *s*)</sub>, is
set by the organ of interest's current (and newly updated) carbon mass.
For all nutrient species *s*, and all organs *o* in set 𝕆<sub>1</sub>,
the targets and demands are updated via `h2_n_target_eq` and
`h2_n_demand_eq`.

The total demand for each nutrient species $s$ across priority 1 tissues
is thus:

<span label="h2_p1_groupnsum_eq">
$$\\check{N}\_{1(s)} = & \\quad  \\sum\_{o=\\mathbb{O}\_{1}} \\check{N}\_{(o,s)}$$
</span>

And therefore the fluxes for each species *s* and each organ in priority
set 𝕆<sub>1</sub> are transferred into their respective pools.

<span label="h2_p1_nvec_eq

\vec{N}_{(\mathbb{O}_1,s)} = &amp; \quad \text{min}(N_{gain(s)},\check{N}_{1(s)}) \cdot ( \check{N}_{(\mathbb{O}_1,s)} / \check{N}_{1(s)} )

N_{(\mathbb{O}_1,s)} = &amp; \quad N_{(\mathbb{O}_1,s)} + \vec{N}_{(\mathbb{O}_1,s)}"></span>

The daily nutrient gains for each species are correspondingly
decremented.

<span label="h2_p1_n_gain">
$$N\_{gain(s)} = & \\quad N\_{gain(s)} - \\text{min}(N\_{gain(s)},\\check{N}\_{1(s)})$$
</span>

### Carbon and Nutrient Fluxes after Priority Level 1

At this point, all priority 1 fluxes have been allocated. The next
priority level fluxes are enacted sequentially, and the procedure is
much the same as priority 1, without the complications of shunting
carbon to maintenance respiration or paying back negative carbon gains,
or **transfering from storage to pay for priority 1 demands**.

For each priority level *p**r*, a new set of organs is sub-set into
group 𝕆<sub>*p**r*</sub>, thereby calculating fluxes of carbon and
nutrients and decrementing *C*<sub>*g**a**i**n*</sub> and
*N*<sub>*g**a**i**n*(*s*)</sub> correspondingly. The algorithm follows
generally:

1.  Sum the carbon demands of the set, via `h2_c_priority1_sum_eq`
2.  Calculate carbon fluxes based on relative demand, similar to
    `h2_p1_c_vec_eq`
3.  Increment carbon pools, growth respiration and decrement carbon
    gain, via `h2_p1_increment_pools_eq` and `h2_p1_decrement_pools_eq`
    (ignoring parts where storage is translocated)
4.  Re-assess nutrient demands, via `h2_n_demand_eq`
5.  Sum the nutrient demands of the set, similar too
    `h2_p1_groupnsum_eq`
6.  Calculate nutrient fluxes and perform transfers, similar to
    `h2_p1_nvec_eq` and `h2_p1_n_gain`

## Grow Stature Concurrently

If there is at some of each daily carbon gain, and daily nutrient gain
for all species remaining, the plant will grow out its stature. This
method assumes that the organs will grow out concurrently.

As a default, the carbon in these organs will be allocated as dictated
by the derivatives of the allometric functions. Other hypotheses, such
as those that seek to optimize root tissues to increase nutrient
acquisition will break from this.

Of important note, is that for either reasons governed outside of the
PARTEH framework, or because of numerical integration errors, some
organs may have slightly more carbon than their allometric target. In
doing so, we remove these organs from the set to be grown out.
Structural carbon is an exception, and is always "on-allometry", since
it is directly tied to stature and dbh. This is actually forced by
adjusting the plant's diameter to match the structural carbon in cases
where structural carbon was higher than its allometric target.

Broadly, the first objective in this section, is to determine which
species, be it carbon or nutrient, will limit growth. To do this, we
calculate an approximation of how much equivalent growth in carbon each
of them could provide, by extrapolating the derivatives at the current
plant's stature. The derivatives for target carbon per change in
diameter, $\\frac{dC\_{(o)}}{dd}$, are provided by allometric functions.
In the following set of organs, we exlude reproduction (which does not
have a derivative wrt size), creating subset of organs
𝕆<sub>*s**g*</sub>.

<span label="h2_sg_sum_dcgdd_eq">
$$\\frac{dC\_{sg}}{dd}     =& \\quad \\sum\_{o=\\mathbb{O}\_{sg}} \\frac{d\\grave{C}\_{(o)}}{dd}$$
</span>

With this sum, we can determine the relative fraction of carbon that is
sent to each organ in set 𝕆<sub>*s**g*</sub>, that is directed to
stature growth, denoted: *f*<sub>*s**g*(𝕆<sub>*s**g*</sub>)</sub>. The
fraction of flux that is directed towards reproductive organs,
*f*<sub>*s**g*(*o* = *r**e**p**r**o*)</sub> is special, and is
**calculated from an external module**.

For the other organs, in set 𝕆<sub>*s**g*</sub>:

<span label="h2_sg_c_reflrac_eq">
$$f\_{sg(\\mathbb{O}\_{sg})} &= \\frac{d\\grave{C}\_{(\\mathbb{O}\_{sg})}}{dd} / \\frac{dC\_{sg}}{dd} \\cdot (1 - f\_{sg(repro)})$$
</span>

The approximated amount of carbon would be transferred into plant
tissues *C⃗*<sub>*s**g*</sub><sup>\*</sup>, is calculated via assembling
these relative fractions, and divesting the total available carbon gain
of the growth respiration rates for each pool. Note the asterisk in the
symbology is meant to reflect an approximate value.

<span label="h2_sg_c_limiting_sum_eq">
$$\\vec{C}^\*\_{sg}  \\quad    &= \\quad C\_{gain} \\cdot \\left( \\frac{ f\_{sg(repro)} }{ 1 + r\_{g(repro)}} + \\sum\_{o=\\mathbb{O}\_{sg}} \\frac{ f\_{sg(o)} }{ 1 + r\_g(o) }  \\right)$$
</span>

The approximated amount of nutrient of each species *s* that would be
transferred into plant tissues *N⃗*<sub>*s**g*(*s*)</sub><sup>\*</sup>,
is calculated much in the same way, however there is no growth
respiration tax. Also, it is possible that a nutrient pool may have a
mass that is already greater than the mass equivalent to the target
associated with the minimum stoichiometry. Such cases must be accounted
for, because they will reduce the likelihood of nutrient needs in that
organ limiting growth.

<span label="h2_sg_n_limiting_sum_eq">
$$\\begin{aligned}
\\vec{N}^\*\_{sg(s)} \\quad  &= \\quad N\_{gain(s)} \\cdot \\left( f\_{sg(repro)} / \\beta\_{(repro,s)}  + \\sum\_{o=\\mathbb{O}\_{sg}} f\_{sg(o)} / \\beta\_{(o,s)} \\right) \\\\
                  &+ \\quad \\text{max}(0,N\_{(repro,s)} - \\grave{N}\_{(repro,s)}) / \\beta\_{(repro,s)} \\\\
          &+ \\quad \\sum\_{o=\\mathbb{O}\_{sg}} \\text{max}(0,N\_{(o,s)} - \\grave{N}\_{(o,s)}) / \\beta\_{(o,s)}
\\end{aligned}$$
</span>

The actual carbon that is then set aside for stature growth
*C⃗*<sub>*s**g*</sub> , based on the minimum of approximations
*C⃗*<sub>*s**g*</sub><sup>\*</sup> and
*N⃗*<sub>*s**g*(*s*)</sub><sup>\*</sup>.

<span label="h2_sg_c_gstature_eq">
$$\\vec{C}\_{sg} &= \\quad C\_{gain} \\cdot \\text{min}( \\vec{C}^\*\_{sg}, \\vec{N}^\*\_{sg(s)} ) /  \\vec{C}^\*\_{sg}$$
</span>

Carbon fluxes into each of the plant's organs are conducted via
numerical integration, which is a coupled set of ordinary differential
equations, integrated over *C⃗*<sub>*s**g*</sub>. For each organ in set
𝕆<sub>*s**g*</sub>.

Where the rate of change of carbon for a given organ is its
proportionality relative to the whole:

<span label="h2_sg_ode_eq">
$$\\frac{d C\_{(\\mathbb{O}\_{sg})}}{d C\_{sg}} &=  \\quad \\overbrace{\\frac{dC\_{(\\mathbb{O}\_{sg})}}{dd} \\cdot \\frac{dd}{d C\_{sg}}}^{ \\text{Continuous allometry equations} }$$
</span>

<span label="h2_sg_ode_int_eq">
$$\\vec{C}\_{sg(\\mathbb{O}\_{sg})} &=  \\quad  \\int\_{dC\_{sg}=0}^{\\vec{C}\_{sg}}  \\frac{d C\_{(\\mathbb{O}\_{sg})}}{d C\_{sg}} dC\_{sg}$$
</span>

The fluxes are then transferred to increment the carbon pools, increment
the growth respiration and decrement the carbon gain.

## Allocate Nutrients Towards Ideal Stoichiometric Ratios

## Send Excess Quantities to Storage or Exude to Soil
