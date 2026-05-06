# Technical Documentation for FATES

FATES is the "Functionally Assembled Terrestrial Ecosystem Simulator".
It is an external module which can run within a given "Host Land Model"
(HLM). Currently (November 2017) implementations are supported in both
the Community Land Model of the Community Terrestrial Systems Model
(CLM-CTSM) and in the Energy Exascale Earth Systems Model (E3SM) Land
Model (ELM).

FATES was derived from the CLM Ecosystem Demography model (CLM(ED)),
which was documented in:

Fisher, R. A., Muszala, S., Verteinstein, M., Lawrence, P., Xu, C.,
McDowell, N. G., Knox, R. G., Koven, C., Holm, J., Rogers, B. M.,
Spessa, A., Lawrence, D., and Bonan, G.: Taking off the training wheels:
the properties of a dynamic vegetation model without climate envelopes,
CLM4.5(ED), Geosci. Model Dev., 8, 3593-3619,
<https://doi.org/10.5194/gmd-8-3593-2015>, 2015.

and this technical note was first published as an appendix to that
paper.

<https://pdfs.semanticscholar.org/396c/b9f172cb681421ed78325a2237bfb428eece.pdf>

## Authors of FATES code and technical documentation.

Rosie A. Fisher <sup>1,2</sup>, Ryan G. Knox <sup>3</sup>, Charles D.
Koven <sup>3</sup>, Gregory Lemieux <sup>3</sup>, Chonggang Xu
<sup>4</sup>, Brad Christofferson <sup>5</sup>, Jacquelyn Shuman
<sup>1</sup>, Maoyi Huang <sup>6</sup>, Erik Kluzek <sup>1</sup>,
Benjamin Andre <sup>1</sup>, Jessica F. Needham <sup>3</sup>, Jennifer
Holm <sup>3</sup>, Marlies Kovenock <sup>7</sup>, Abigail L. S. Swann
<sup>7</sup>, Stefan Muszala <sup>1</sup>, Shawn P. Serbin <sup>8</sup>,
Qianyu Li <sup>8</sup>, Mariana Verteinstein <sup>1</sup>, Anthony P.
Walker <sup>11</sup>, Alan di Vittorio <sup>3</sup>, Yilin Fang
<sup>9</sup>, Yi Xu <sup>6</sup>, Junyan Ding <sup>12</sup>, Shijie Shu
<sup>3</sup>, Marcos Longo <sup>3</sup>, Adrianna Foster <sup>1</sup>,
Adam Hanbury-Brown <sup>3,14</sup>, Lara Kueppers <sup>13</sup>, Jeffrey
Q. Chambers <sup>13</sup>, Sam Levis <sup>1</sup>, Zachary Robbins
<sup>4</sup>, Claire Zarakas <sup>7</sup>

<sup>1</sup> Climate and Global Dynamics Division, National Center for
Atmospheric Research, Boulder, CO, USA

<sup>2</sup> Center for International Climate Research (CICERO), Oslo,
Norway

<sup>3</sup> Climate and Ecosystem Sciences Division, Lawrence Berkeley
National Laboratory, Berkeley, CA, USA

<sup>4</sup> Earth and Environmental Sciences Division, Los Alamos
National Laboratory, Los Alamos, NM, USA

<sup>5</sup> Department of Biology, University of Texas, Rio Grande
Valley, Edinburg, TX, USA

<sup>6</sup> Atmospheric Sciences and Global Change Division, Pacific
Northwest National Laboratory, Richland, WA, USA

<sup>7</sup> University of Washington, Seattle, WA, USA

<sup>8</sup> Environmental and Climate Sciences Department, Brookhaven
National Laboratory, Upton, NY, USA

<sup>9</sup> Energy and Environment Directorate, Pacific Northwest
National Laboratory, Richland, WA, USA

<sup>10</sup> Jet Propulsion Laboratory, Pasadena, CA, USA

<sup>11</sup> Climate Change Science Institute, Environmental Sciences
Division, Oak Ridge National Laboratory, Oak Ridge, TN, USA

<sup>12</sup> Earth & Biological Sciences, Pacific Northwest National
Laboratory, Richland, WA, USA

<sup>13</sup> University of California, Berkeley

<sup>14</sup> University of California, Davis

## Introduction

The Ecosystem Demography ('ED'), concept within FATES is derived from
the work of `Moorcroft et al. (2001)<mc_2001>`

and is a cohort model of vegetation competition and co-existence,
allowing a representation of the biosphere which accounts for the
division of the land surface into successional stages, and for
competition for light between height structured cohorts of
representative trees of various plant functional types.

The implementation of the Ecosystem Demography concept within FATES
links the surface flux and canopy physiology concepts in the CLM/ELM
with numerous additional developments necessary to accommodate the new
model also documented here. These include a version of the SPITFIRE
(Spread and InTensity of Fire) model of
`Thonicke et al. (2010)<thonickeetal2010>`, and an adoption of the
concept of <span class="title-ref">Perfect Plasticity
Approximation</span> approach of `Purves et al. 2008<purves2008>`,
`Lichstein et al. 2011<lichstein2011>` and `Weng et al. 2014<weng2014>`,
in accounting for the spatial arrangement of crowns. Novel algorithms
accounting for the fragmentation of coarse woody debris into chemical
litter streams, for the physiological optimisation of canopy thickness,
for the accumulation of seeds in the seed bank, for multi-layer
multi-PFT radiation transfer, for drought-deciduous and cold-deciduous
phenology, for carbon storage allocation, and for tree mortality under
carbon stress, are also included and presented here.

Numerous other implementations of the Ecosystem Demography concept exist
(See `Fisher et al. (2018)<Fisheretal2018>` for a review of these)
Therefore, to avoid confusion between the concept of 'Ecosystem
Demography' and the implementation of this concept in different models,
the CLM(ED) implementation described by
`Fisher et al. (2015)<Fisheretal2015>` will hereafter be called 'FATES'
(the Functionally Assembled Terrestrial Ecosystem Simulator).

## The representation of ecosystem heterogeneity in FATES

The terrestrial surface of the Earth is heterogeneous for many reasons,
driven by variations in climate, edaphic history, ecological
variability, geological forcing and human interventions. Land surface
models represent this variability first by introducing a grid structure
to the land surface, allowing different atmospheric forcings to operate
in each grid cell, and subsequently by representing 'sub-grid'
variability in the surface properties. In the CLM, the land surface is
divided into numerous 'landunits' corresponding to the underlying
condition of the surface (e.g. soils, ice, lakes, bare ground) and then
'columns' referring to elements of the surface that share below ground
resources (water & nutrients). Within the soil landunit, for example,
there are separate columns for crops, and for natural vegetation, as
these are assumed to use separate resource pools. The FATES model at
present only operates on the naturally vegetated column. The soil column
is sub-divided into numerous tiles, that correspond to statistical
fractions of the potentially vegetated land area. In the CLM 4.5 (and
all previous versions of the model), sub-grid tiling operates on the
basis of plant functional types (PFTs). That is, each piece of land is
assumed to be occupied by only one plant functional type, with multiple
PFT-specific tiles sharing a common soil water and nutrient pool. This
PFT-based tiling structure is the standard method used by most land
surface models deployed in climate prediction.

The introduction of the Ecosystem Demography concept introduces
significant alterations to the representation of the land surface in the
CLM. In FATES, the tiling structure represents the disturbance history
of the ecosystem. Thus, some fraction of the land surface is
characterized as 'recently disturbed', some fraction has escaped
disturbance for a long time, and other areas will have intermediate
disturbances. Thus the ED concept essentially discretizes the trajectory
of succession from disturbed ground to 'mature' ecosystems. Within
FATES, each "disturbance history class" is referred to as a ‘patch’. The
word "patch" has many possible interpretations, so it is important to
note that: **there is no spatial location associated with the concept of
a 'patch' . It refers to a fraction of the potential vegetated area
consisting of all parts of the ecosystem with similar disturbance
history.**

The 'patch' organizational structure in CLM thus replaces the previous
'PFT' structure in the organization heirarchy. The original hierarchical
land surface organizational structure of CLM as described in
`Oleson et al. 2013<olesonetal2013>` may be depicted as:

$$\\begin{aligned}
\\mathbf{gridcell} \\left\\{
\\begin{array}{cc} 
\\mathbf{landunit} &   \\\\ 
\\mathbf{landunit} &\\left\\{ 
\\begin{array}{ll} 
\\mathbf{column}&\\\\
\\mathbf{column}&\\left\\{ 
\\begin{array}{ll} 
\\mathbf{pft}&\\\\
\\mathbf{pft}&\\\\
\\mathbf{pft}&\\\\
\\end{array}\\right.\\\\ 
\\mathbf{column}&\\\\
\\end{array}\\right.\\\\ 
\\mathbf{landunit} &   \\\\
\\end{array}\\right.
\\end{aligned}$$

and the new structure is altered to the following:

$$\\begin{aligned}
\\mathbf{gridcell} \\left\\{
\\begin{array}{cc} 
\\mathbf{landunit} &   \\\\ 
\\mathbf{landunit} &\\left\\{ 
\\begin{array}{ll} 
\\mathbf{column}&\\\\
\\mathbf{column}&\\left\\{ 
\\begin{array}{ll} 
\\mathbf{patch}&\\\\
\\mathbf{patch}&\\\\
\\mathbf{patch}&\\\\
\\end{array}\\right.\\\\ 
\\mathbf{column}&\\\\
\\end{array}\\right.\\\\ 
\\mathbf{landunit} &   \\\\
\\end{array}\\right.
\\end{aligned}$$

Thus, each gridcell becomes a matrix of 'patches' that are
conceptualized by their 'age since disturbance' in years. This is the
equivalent of grouping together all those areas of a gridcell that are
'canopy gaps', into a single entity, and all those areas that are
'mature forest' into a single entity.

### Cohortized representation of tree populations

Each common-disturbance-history patch is a notional ecosystem that might
in reality contain numerous individual plants which vary in their
physiological attributes, in height and in spatial position. One way of
addressing this heterogeneity is to simulate a forest of specific
individuals, and to monitor their behavior through time. This is the
approach taken by "gap" and individual-based models
(`Smith et al. 2001<smith2001>`, `Sato et al. 2007<sato2007>`,
`Uriarte et al. 2009<uriarte2009>`, `Fyllas et al. 2014 <fyllas2014>`).
The depiction of individuals typically implies that the outcome of the
model is stochastic. This is because we lack the necessary detailed
knowledge to simulate the individual plant's fates. Thus gap models
imply both stochastic locations and mortality of plants. Thus, (with a
genuinely random seed) each model outcome is different, and an ensemble
of model runs is required to generate an average representative
solution. Because the random death of large individual trees can cause
significant deviations from the mean trajectory for a small plot (a
typical simulated plot size is 30m x 30 m) the number of runs required
to minimize these deviations is large and computationally expensive. For
this reason, models that resolve individual trees typically use a
physiological timestep of one day or longer (e.g.
`Smith et al. 2001<smith2001>`, `Xiaidong et al. 2005 <xiaodong2005>`,
`Sato et al. 2007<sato2007>`

The approach introduced by the Ecosystem Demography model
`Moorcroft et al. 2001<mc_2001>` is to group the hypothetical population
of plants into "cohorts". In the notional ecosystem, after the
land-surface is divided into common-disturbance-history patches, the
population in each patch is divided first into plant functional types
(the standard approach to representing plant diversity in large scale
vegetation models), and then each plant type is represented as numerous
height classes. Importantly, **for each PFT/height class bin, we model
\*one\* representative individual plant, which tracks the average
properties of this \`cohort\` of individual plants.** Thus, each
common-disturbance-history patch is typically occupied by a set of
cohorts of different plant functional types, and different height
classes within those plant functional types. Each cohort is associated
with a number of identical trees, *n*<sub>*c**o**h*</sub> (where
*c**o**h* denotes the identification or index number for a given
cohort)..

The complete hierarchy of elements in FATES is therefore now described
as follows:

$$\\begin{aligned}
\\mathbf{gridcell}\\left\\{
\\begin{array}{cc} 
\\mathbf{landunit} &   \\\\ 
\\mathbf{landunit} &\\left\\{ 
\\begin{array}{ll} 
\\mathbf{column}&\\\\
\\mathbf{column}&\\left\\{ 
\\begin{array}{ll} 
\\mathbf{patch}&\\\\
\\mathbf{patch}&\\left\\{ 
\\begin{array}{ll} 
\\mathbf{cohort}&\\\\
\\mathbf{cohort}&\\\\
\\mathbf{cohort}&\\\\
\\end{array}\\right.\\\\ 
\\mathbf{patch}&\\\\
\\end{array}\\right.\\\\ 
\\mathbf{column}&\\\\
\\end{array}\\right.\\\\ 
\\mathbf{landunit} &   \\\\
\\end{array}\\right.
\\end{aligned}$$

### Discretization of cohorts and patches

Newly disturbed land and newly recruited seedlings can in theory be
generated at each new model timestep as the result of germination and
disturbance processes. If the new patches and cohorts established at
*every* timestep were tracked by the model structure, the computational
load would of course be extremely high (and thus equivalent to an
individual-based approach). A signature feature of the ED model is the
system by which <span class="title-ref">functionally equivalent</span>
patches and cohorts are fused into single model entities to save memory
and computational time.

This functionality requires that criteria are established for the
meaning of <span class="title-ref">functional equivalence</span>, which
are by necessity slightly subjective, as they represent ways of
abstracting reality into a more tractable mathematical representation.
As an example of this, for height-structured cohorts, we calculate the
relativized differences in height (*h*<sub>*c**o**h*</sub>, m) between
two cohorts of the same pft, *p* and *q* as

$$d\_{height,p,q} = \\frac{\\mathrm{abs}(h\_{p-}h\_{q})}{\\frac{1}{2}(h\_{p}+h\_{q})}$$

If *d*<sub>*h**e**i**g**h**t*, *p*, *q*</sub> is smaller than some
threshold *t*<sub>*c**h*</sub>, and they are of the same plant
functional type, the two cohorts are considered equivalent and merged to
form a third cohort *r*, with the properties of cohort *p* and *q*
averaged such that they conserve mass. The model parameter
*t*<sub>*c**h*</sub> can be adjusted to adjust the trade-off between
simulation accuracy and computational load. There is no theoretical
optimal value for this threshold but it may be altered to have finer or
coarser model resolutions as needed.

Similarly, for common-disturbance-history patches, we again assign a
threshold criteria, which is then compared to the difference between
patches *m* and *n*, and if the difference is less than some threshold
value (*t*<sub>*p*</sub>) then patches are merged together, otherwise
they are kept separate. However, in contrast with height-structured
cohorts, where the meaning of the difference criteria is relatively
clear, how the landscape should be divided into
common-disturbance-history units is less clear. Several alternative
criteria are possible, including Leaf Area Index, total biomass and
total stem basal area.

In this implementation of FATES we assess the amount of above-ground
biomass in each PFT/plant diameter bin. Biomass is first grouped into
fixed diameter bins for each PFT (*f**t*) and a significant difference
in any bin will cause patches to remain separated. This means that if
two patches have similar total biomass, but differ in the distribution
of that biomass between diameter classes or plant types, they remain as
separate entities. Thus

$$B\_{profile,m,dc,ft} = \\sum\_{d\_{c,min}}^{d\_{c,max}} (B\_{ag,coh}n\_{coh})$$

*B*<sub>*p**r**o**f**i**l**e*, *m*, *d**c*, *f**t*</sub> is the binned
above-ground biomass profile for patch *m*,*d*<sub>*c*</sub> is the
diameter class. *d*<sub>*c*, *m**i**n*</sub> and
*d*<sub>*c*, *m**a**x*</sub> are the lower and upper boundaries for the
*d*<sub>*c*</sub> diameter class. *B*<sub>*a**g*, *c**o**h*</sub> and
*n*<sub>*c**o**h*</sub> depict the biomass (KgC m<sup>-2</sup>) and the
number of individuals of each cohort respectively. A difference matrix
between patches *m* and *n* is thus calculated as

$$d\_{biomass,mn,dc,ft} = \\frac{\\rm{abs}\\it(B\_{profile,m,hc,ft}-B\_{profile,n,hc,ft})}{\\frac{1}{2}(B\_{profile,m,hc,ft}+B\_{profile,n,hc,ft})}$$

If all the values of
*d*<sub>*b**i**o**m**a**s**s*, *m**n*, *h**c*, *f**t*</sub> are smaller
than the threshold, *t*<sub>*p*</sub>, then the patches *m* and *n* are
fused together to form a new patch *o*.

To increase computational efficiency and to simplify the coding
structure of the model, the maximum number of patches is capped at
*P*<sub>*n**o*, *m**a**x*</sub>. To force the fusion of patches down to
this number, the simulation begins with a relatively sensitive
discretization of patches (*t*<sub>*p*</sub> = 0.2) but if the patch
number exceeds the maximum, the fusion routine is repeated iteratively
until the two most similar patches reach their fusion threshold. This
approach maintains an even discretization along the biomass gradient, in
contrast to, for example, simply fusing the oldest or youngest patches
together.

The area of the new patch (*A*<sub>*p**a**t**c**h*, *o*</sub>,
m<sup>2</sup>) is the sum of the area of the two existing patches,

*A*<sub>*p**a**t**c**h*, *o*</sub> = *A*<sub>*p**a**t**c**h*, *n*</sub> + *A*<sub>*p**a**t**c**h*, *m*</sub>

and the cohorts ‘belonging’ to patches *m* and *n* now co-occupy patch
*o*. The state properties of *m* and *n* (litter, seed pools, etc. ) are
also averaged in accordance with mass conservation .

### Linked Lists: the general code structure of FATES

The number of patches in each natural vegetation column and the number
of cohorts in any given patch are variable through time because they are
re-calculated for each daily timestep of the model. The more complex an
ecosystem, the larger the number of patches and cohorts. For a slowly
growing ecosystem, where maximum cohort size achieved between
disturbance intervals is low, the number of cohorts is also low. For
fast-growing ecosystems where many plant types are viable and maximum
heights are large, more cohorts are required to represent the ecosystem
with adequate complexity.

In terms of variable structure, the creation of an array whose size
could accommodate every possible cohort would mean defining the maximum
potential number of cohorts for every potential patch, which would
result in very large amounts of wasted allocated memory, on account of
the heterogeneity in the number of cohorts between complex and simple
ecosystems (n.b. this does still happen for some variables at restart
timesteps). To resolve this, the cohort structure in FATES model does
not use an array system for internal calculations. Instead it uses a
system of *linked lists* where each cohort structure is linked to the
cohorts larger than and smaller than itself using a system of pointers.
The shortest cohort in each patch has a ‘shorter’ pointer that points to
the *null* value, and the tallest cohort has a ‘taller’ pointer that
points to the null value.

Instead of iterating along a vector indexed by *c**o**h*, the code
structures typically begin at the tallest cohort in a given patch, and
iterate until a null pointer is encountered.

Using this structure, it is therefore possible to have an unbounded
upper limit on cohort number, and also to easily alter the ordering of
cohorts if, for example, a cohort of one functional type begins to grow
faster than a competitor of another functional type, and the cohort list
can easily be re-ordered by altering the pointer structure. Each cohort
has <span class="title-ref">pointers</span> indicating to which patch
and gridcell it belongs. The patch system is analogous to the cohort
system, except that patches are ordered in terms of their relative age,
with pointers to older and younger patches where cp<sub>1</sub> is the
oldest:

### Indices used in FATES

Some of the indices used in FATES are similar to those used in the
standard CLM4.5 model; column (*c*), land unit(*l*), grid cell(*g*) and
soil layer (*j*). On account of the additional complexity of the new
representation of plant function, several additional indices are
introduced that describe the discritization of plant type, fuel type,
litter type, plant height, canopy identity, leaf vertical structure and
fuel moisture characteristics. To provide a reference with which to
interpret the equations that follow, they are listed here.

\bigskip
\captionof{table}{Table of subscripts used in this document  }

| Parameter Symbol | Parameter Name         |
|------------------|------------------------|
| *ft*             | Plant Functional Type  |
| *fc*             | Fuel Class             |
| *lsc*            | Litter Size Class      |
| *coh*            | Cohort Index           |
| *patch*          | Patch Index            |
| *cl*             | Canopy Layer           |
| *z*              | Leaf Layer             |
| *mc*             | Moisture Class         |
| *o*              | Plant Organ Index      |
| *s*              | Nutrient Species Index |

\bigskip 

### Cohort State Variables

The unit of allometry in the ED model is the cohort. Each cohort
represents a group of plants with similar functional types and heights
that occupy portions of column with similar disturbance histories. The
state variables of each cohort therefore consist of several pieces of
information that fully describe the growth status of the plant and its
position in the ecosystem structure, and from which the model can be
restarted. The state variables of a cohort are as follows:

\bigskip
\captionof{table}{State Variables of  `cohort' sructure}

| Quantity | Variable name | Units | Notes |
|------------------|------------------|------------------|------------------|
| Plant Functional Type | ${\\it{ft}
\_{coh}}$ | integer |  |
| Number of Individuals | *n*<sub>*c**o**h*</sub> | n ha<sup>-2</sup> |  |
| Height | *h*<sub>*c**o**h*</sub> | m |  |
| Diameter | $\\it{dbh\_
{coh}}$ | cm |  |
| Carbon Mass | *C*<sub>(*o*, *c**o**h*)</sub> | Kg plant<sup>-1</sup> | leaf, fine-root sapwood, storage, structural, reproductive |
| Nutrient Mass | *N*<sub>(*o*, *s*, *c**o**h*)</sub> | Kg plant<sup>-1</sup> | Optional depending on hypothesis. See PARTEH documentation. |
| Leaf memory | *l*<sub>*m**e**m**o**r**y*, *c**o**h*</sub> | Kg plant<sup>-1</sup> | Leaf mass when leaves are dropped |
| Phenological Status | *S*<sub>*p**h**e**n*, *c**o**h*</sub> | integer | 1=leaves off. 2=leaves on |
| Canopy Layer Index | *c**l*<sub>*c**o**h*</sub> | integer | 1=top canopy &gt;1=understory |
| Canopy trimming | *C*<sub>*t**r**i**m*, *c**o**h*</sub> | fraction | 1.0=max leaf area |
| Patch Index | *p*<sub>*c**o**h*</sub> | integer | To which patch does this cohort belong? |

### Patch State Variables

A patch, as discuss earlier, is a fraction of the landscape which
contains ecosystems with similar structure and disturbance history. A
patch has no spatial location. The state variables, which are
‘ecosystem’ rather than ‘tree’ scale properties, from which the model
can be restarted, are as follows

\bigskip
\captionof{table}{State variables of `patch' structure}

| Quantity | Variable name | Units | Indexed By |
|---------------|---------------|---------------|---------------|
| Area | $\\it{
A\_{patch}}$ | m<sup>2</sup> |  |
| Age | *a**g**e*<sub>*p**a**t**c**h*</sub> | years |  |
| Seed | *s**e**e**d*<sub>*p**a**t**c**h*</sub> | KgC m<sup>-2</sup> | *f**t* |
| Leaf Litter | *l*<sub>*l**i**t**t**e**r*, *p**a**t**c**h*</sub> | KgC m<sup>-2</sup> | *f**t* |
| Root Litter | *r*<sub>*l**i**t**t**e**r*, *p**a**t**c**h*</sub> | KgC m<sup>-2</sup> | *f**t* |
| AG Coarse Woody Debris | *C**W**D*<sub>*A**G*, *p**a**t**c**h*</sub> | KgC m<sup>-2</sup> | Size Class (lsc) |
| BG Coarse Woody Debris | *C**W**D*<sub>*B**G*, *p**a**t**c**h*</sub> | KgC m<sup>-2</sup> | Size Class (lsc) |
| Column Index | *l*<sub>*p**a**t**c**h*</sub> | integer |  |

### Model Structure

Code concerned with the Ecosystem Demography model interfaces with the
CLM model in four ways: i) During initialization, ii) During the
calculation of surface processes (albedo, radiation absorption, canopy
fluxes) each model time step (typically half-hourly), iii) During the
main invokation of the ED model code at the end of each day. Daily
cohort-level NPP is used to grow plants and alter the cohort structures,
disturbance processes (fire and mortality) operate to alter the patch
structures, and all fragmenting carbon pool dynamics are calculated. iv)
during restart reading and writing. The net assimilation (NPP) fluxes
attributed to each cohort are accumulated throughout each daily cycle
and passed into the ED code as the major driver of vegetation dynamics.

## Initialization of vegetation from bare ground

If the model is restarted from a bare ground state (as opposed to a
pre-existing vegetation state), the state variables above are
initialized as follows. First, the number of plants per PFT is allocated
according to the initial seeding density (*S*<sub>*i**n**i**t*</sub>,
individuals per m<sup>2</sup>) and the area of the patch
*A*<sub>*p**a**t**c**h*</sub>, which in the first timestep is the same
as the area of the notional ecosystem *A*<sub>*t**o**t*</sub>. The model
has no meaningful spatial dimension, but we assign a notional area such
that the values of ‘*n*<sub>*c**o**h*</sub>’ can be attributed. The
default value of *A*<sub>*t**o**t*</sub> is one hectare (10,000
m<sub>2</sub>), but the model will behave identically irrepective of the
value of this parameter.

*n*<sub>*c**o**h*, 0</sub> = *S*<sub>*i**n**i**t*</sub>*A*<sub>*p**a**t**c**h*</sub>

Each cohort is initialized at the minimum canopy height
*h*<sub>*m**i**n*, *f**t*</sub>, which is specified as a parameter for
each plant functional type and denotes the smallest size of plant which
is tracked by the model. Smaller plants are not considered, and their
emergence from the recruitment processes is unresolved and therefore
implicitly parameterized in the seedling establishment model.

The diameter of each cohort is then specified according to the
height-diameter allometry function associated with the PFT of interest,
see `allometry_table`. The biomass pools for the newly recruited plant
are then determined from the allometry equations that define the target
(idealized) sizes for each pool.

\captionof{table}{(INCOMPLETE) List of the parameters that define the intialization of new plants during a "cold-start" simulation.}

| Parameter Symbol | Parameter Name | Units | Default Value |
|------------------|------------------|------------------|------------------|
| *h*<sub>*m**i**n*</sub> | Minimum plant height | m | 1.5 |
| *S*<sub>*i**n**i**t*</sub> | Initial Planting density | Individuals m<sup>-2</sup> |  |

## Allocation and Reactive Transport (PARTEH)

The **Plant Allocation** and **Reactive Transport Extensible Hypotheses
(PARTEH)** is a suite of modules that handle the processes of
allocation, transport and reactions (i.e. thos processes related to
movement and change, yet perhaps not the genesis) of various arbitrary
species (carbon, nutrients, toxins, etc) within the various organs of
live vegetation. In FATES, these processes are resolved per unit plant,
for each cohort.

parteh/overview\_domain.rst parteh/hypotheses.rst

## Allometry and Growth Along Allometric Curves

In the previous section, `parteh_section`, we covered the equations that
describe how growth is implemented, as well the order of operations and
logic of that forumlation. In this section, we will discuss the various
allometric functions that generate the relative rates of change, as well
as the target biomass quantities *X̀*.

### "Forced" Growth Along Allometric Curves

Growth specified by current PARTEH hypotheses follow along the
allometric curves. A hypothetical example of a cohorts integration along
such a curve is provided in the top panel of the diagram below. It is
assumed that when a plant grows in stature, the structural biomass
matches the target structural biomass for its size (DBH). This is
represented by the grey dot sitting on the allometry line for structural
biomass.

**A state of being "on allometry" is consistent with the cohort (grey
dot) existing on the allometric curve.**

It is expected, and it is represented in the model, that due to either
continuous or event based turnover, that biomass pools are continually
depleted, thus pulling the grey dot straight down, away from the
allometry line. Recall from the PARTEH description, that the first step
in the growth algorithm is to use available carbon to replace these lost
biomass pools (without increasing dbh) so that it is "on allometry".

Also, all numerical integration has some amount of truncation error
(step error). When FATES conducts the stature growth integration step,
it typically uses Euler integration, because it is fast and simple. As a
result, all biomass pools are projected along the tangent of the
allometric curves from where they started. When the curvature parameters
that govern these relationships are greater than 1, this results in
continual "undershooting" of the actual target quantity. This is not a
liability, firstly because growth is forced to be mass conservative. And
secondly, to re-iterate the explanation above, upon the next growth step
the algorithm will spend carbon to first get the pools back "on
allometry", before it projects along the tangent again. This is
represented in the lower panel.

<figure>
<img src="images/growth_allometry_p1.png" />
</figure>

However, we also have to accomodate for cases where the actual amount of
biomass in the cohort's pools are larger than the target sizes dictated
by the cohort's diameter. This can be visualized by the cohort residing
somewhere above the line. This can happen for two reasons, 1) cohort
fusion or 2) growth along allometric curves with curvature parameters
(exponents) less than 1.

For woody plants, if a non-structural biomass pool is greater than the
target pool size, the solution is simple. That pool is flagged to be
ignored during the stature growth step, and eventually the cohort's dbh
will increase such that the target size exceeds its actual size again.
This is visualized in the top panel of the diagram below.

There is a caveat here. The diameter must be "tied" to one of the
biomass pools. And for woody plants, we choose structural carbon. And
thus, we cannot flag to ignore structural carbon during stature growth
since it is inextricably linked to diameter. Therefore, cohorts that
have structural biomass that is greater than the target biomass dictated
by its diameter, will have their DBH forceably increased (without
increasing any biomass) until the allometric target matches the actual
biomass. See the lower panel in the diagram below.

<figure>
<img src="images/growth_allometry_p2.png" />
</figure>

Note, the explanation above was explained for woody plants, which tie
diameter to structural biomass. For non-woody plants, such as grasses,
we tie leaf biomass to diameter instead.

### Allometric Relationships

FATES-PARTEH (in its base hypotheses) uses allometry to dictate the
target biomass quantities of structure, sapwood, leaf, fine-root,
reproduction and storage. Further, FATES also uses allometric
relationships to define a cohort's height and crown area. All of these
target quantities are tied to diameter. Biomass pools may also be
functionally dependent on other biomass pools, as long as a cyclical
relationship is not generated, and can ultimately be related to diameter
or other external factors. For instance, target root biomass is
typically defined as proportional to leaf biomass. Target leaf biomass
is dependent on height and a canopy trimming function, while crown area
and above ground biomass are each also dependent on height.

The FATES code is written in a way that offers flexibility in how these
relationships are cast. Each of these forumulations uses one or more
user defined constant parameters, but it also allows for completely
different functional forms. All of FATES allometric relationships can be
found in the file
[FatesAllometryMod.F90](https://github.com/NGEET/fates/blob/master/biogeochem/FatesAllometryMod.F90).

Important note. Most allometry relationships from field research define
total above ground biomass (AGB) as their estimated quantity instead of
structural biomass. In FATES, since AGB is not a state-variable, it must
be derived from the portions of several state variables. However, we
make a simplification in FATES, and assume that the allometric
relationships for AGB only contain structural wood and sapwood, and do
not contain leaves, storage or reproductive tissues. Diagnostics on AGB
will include all terms. Thus the allometric target for AGB contains the
state targets and the fraction of above ground biomass (pft constant
parameter) *f*<sub>*a*</sub>.

<span label="allom_agb_eq">
$$\\grave{C}\_{(AGB)} &= (\\grave{C}\_{(structure)} + \\grave{C}\_{(sapwood)}) \* f\_{agb}$$
</span>

Note that the diameter to height relationships all use an effective
diameter, *d*<sub>\*</sub>. This is the minimum between the actual plant
diameter, and the PFT specific parameter that specifies the diameter at
which maximum height occurs *d*<sub>*h**m**a**x*</sub>.

<span label="allom_dbh_maxh">
*d*<sub>\*</sub> = min(*d*, *d*<sub>*h**m**a**x*</sub>)
</span>

The following table details the different allometric relationships that
governs growth and stature, and the optional relationships and
parameters associated with those relationships.

<table>
<caption>Table of Allometric Functions</caption>
<colgroup>
<col style="width: 38%" />
<col style="width: 61%" />
</colgroup>
<thead>
<tr>
<th>Reference</th>
<th>Function</th>
</tr>
</thead>
<tbody>
<tr>
<td colspan="2"><strong>Diameter to Height</strong></td>
</tr>
<tr>
<td>Power Function</td>
<td><span
class="math inline"><em>h</em> = <em>p</em><sub>1</sub> ⋅ <em>d</em><sub>*</sub><sup><em>p</em><sub>2</sub></sup></span></td>
</tr>
<tr>
<td><code class="interpreted-text"
role="Ref">Obrien et al (1995)&lt;Obrienetal1995&gt;</code></td>
<td><span
class="math inline"><em>h</em> = 10<sup>(<em>l</em><em>o</em><em>g</em>10(<em>d</em><sub>*</sub>) ⋅ <em>p</em><sub>1</sub> + <em>p</em><sub>2</sub>)</sup></span></td>
</tr>
<tr>
<td><code class="interpreted-text"
role="ref">Poorter et al (2006)&lt;Poorteretal2006&gt;</code></td>
<td><span
class="math inline"><em>h</em> = <em>p</em><sub>1</sub> ⋅ (1 − <em>e</em><sup><em>p</em><sub>2</sub> ⋅ <em>d</em><sub>*</sub><sup><em>p</em><sub>3</sub></sup></sup>)</span></td>
</tr>
<tr>
<td><code class="interpreted-text"
role="ref">Martinez Cano et al (2019)&lt;MartinezCanoetal2019&gt;</code></td>
<td><span
class="math inline"><em>h</em> = (<em>p</em><sub>1</sub> ⋅ <em>d</em><sub>*</sub><sup><em>p</em><sub>2</sub></sup>)/(<em>p</em><sub>3</sub> + <em>d</em><sub>*</sub><sup><em>p</em><sub>2</sub></sup>)</span></td>
</tr>
<tr>
<td colspan="2"></td>
</tr>
<tr>
<td colspan="2"><strong>Target Above Ground Biomass</strong></td>
</tr>
<tr>
<td><code class="interpreted-text"
role="ref">Saldarriaga et al. (1998)&lt;Saldarriaga1988&gt;</code></td>
<td><span
class="math inline"><em>C̀</em><sub><em>a</em><em>g</em><em>b</em></sub> = <em>f</em><sub><em>a</em><em>g</em><em>b</em></sub> ⋅ <em>p</em><sub>1</sub> ⋅ <em>h</em><sup><em>p</em><sub>2</sub></sup> ⋅ <em>d</em><sup><em>p</em><sub>3</sub></sup> ⋅ <em>ρ</em><sup><em>p</em><sub>4</sub></sup></span></td>
</tr>
<tr>
<td>2 Parameter power function</td>
<td><span
class="math inline"><em>C̀</em><sub><em>a</em><em>g</em><em>b</em></sub> = <em>p</em><sub>1</sub>/c2b ⋅ <em>d</em><sup><em>p</em><sub>2</sub></sup></span></td>
</tr>
<tr>
<td><code class="interpreted-text"
role="ref">Chave et al. (2014)&lt;Chaveetal2014&gt;</code></td>
<td><span
class="math inline"><em>C̀</em><sub><em>a</em><em>g</em><em>b</em></sub> = <em>p</em><sub>1</sub>/c2b ⋅ (<em>ρ</em> ⋅ <em>d</em><sup>2</sup> ⋅ <em>h</em>)<sup><em>p</em><sub>2</sub></sup></span></td>
</tr>
<tr>
<td></td>
<td></td>
</tr>
<tr>
<td colspan="2">Target Leaf Biomass (TBD)</td>
</tr>
<tr>
<td></td>
<td></td>
</tr>
<tr>
<td colspan="2">Target Sapwood Biomass (TBD)</td>
</tr>
<tr>
<td></td>
<td></td>
</tr>
<tr>
<td colspan="2">Target Fine-root Biomass (TBD)</td>
</tr>
<tr>
<td></td>
<td></td>
</tr>
<tr>
<td colspan="2">Target Storage Biomass (TBD)</td>
</tr>
</tbody>
</table>

*List of allometric relationships, their functional forms, and relevant
parameters.*

## Canopy Structure and the Perfect Plasticity Approximation

During initialization and every subsequent daily ED timestep, the canopy
structure model is called to determine how the leaf area of the
different cohorts is arranged relative to the incoming radiation, which
will then be used to drive the radiation and photosynthesis
calculations. This task requires that some assumptions are made about 1)
the shape and depth of the canopy within which the plant leaves are
arranged and 2) how the leaves of different cohorts are arranged
relative to each other. This set of assumptions are critical to model
performance in ED-like cohort based models, since they determine how
light resources are partitioned between competing plants of varying
heights, which has a very significant impact on how vegetation
distribution emerges from competition
`Fisher et al. 2010<Fisheretal2010>`.

The standard ED1.0 model makes a simple 'flat disk' assumption, that the
leaf area of each cohort is spread in an homogenous layer at one exact
height across entire the ground area represented by each patch. FATES
has diverged from this representation due to (at least) two problematic
emergent properties that we identified as generating unrealistic
behaviours espetially for large-area patches.

1\. Over-estimation of light competition . The vertical stacking of
cohorts which have all their leaf area at the same nominal height means
that when one cohort is only very slightly taller than it’s competitor,
it is completely shaded by it. This means that any small advantage in
terms of height growth translates into a large advantage in terms of
light competition, even at the seedling stage. This property of the
model artificially exaggerates the process of light competition. In
reality, trees do not compete for light until their canopies begin to
overlap and canopy closure is approached.

2\. Unrealistic over-crowding. The 'flat-disk' assumption has no
consideration of the spatial extent of tree crowns. Therefore it has no
control on the packing density of plants in the model. Given a mismatch
between production and mortality, entirely unrealistic tree densities
are thus possible for some combinations of recruitment, growth and
mortality rates.

To account for the filling of space in three dimensions using the
one-dimensional representation of the canopy employed by CLM, we
implement a new scheme derived from that of
`Purves et al. 2008<purves2008>`. Their argument follows the development
of an individual-based variant of the SORTIE model, called SHELL, which
allows the location of individual plant crowns to be highly flexible in
space. Ultimately, the solutions of this model possess an emergent
property whereby the crowns of the plants simply fill all of the
available space in the canopy before forming a distinct understorey.

Purves et al. developed a model that uses this feature, called the
‘perfect plasticity approximation’, which assumes the plants are able to
perfectly fill all of the available canopy space. That is, at canopy
closure, all of the available horizontal space is filled, with
negligible gaps, owing to lateral tree growth and the ability of tree
canopies to grow into the available gaps (this is of course, an
over-simplified but potential useful ecosystem property). The ‘perfect
plasticity approximation’ (PPA) implies that the community of trees is
subdivided into discrete canopy layers, and by extension, each cohort
represented by FATES model is assigned a canopy layer status flag,
*C*<sub>*L*</sub>. In this version, we set the maximum number of canopy
layers at 2 for simplicity, although is possible to have a larger number
of layers in theory. *C*<sub>*L*, *c**o**h*</sub> = 1 means that all the
trees of cohort *c**o**h* are in the upper canopy (overstory), and
*C*<sub>*L*, *c**o**h*</sub> = 2 means that all the trees of cohort
*c**o**h* are in the understorey.

In this model, all the trees in the canopy experience full light on
their uppermost leaf layer, and all trees in the understorey experience
the same light (full sunlight attenuated by the average LAI of the upper
canopy) on their uppermost leaves, as described in the radiation
transfer section (more nuanced versions of this approach may be
investigated in future model versions). The canopy is assumed to be
cylindrical, the lower layers of which experience self-shading by the
upper layers.

To determine whether a second canopy layer is required, the model needs
to know the spatial extent of tree crowns. Crown area,
*A*<sub>*c**r**o**w**n*</sub>, m<sup>2</sup>, is defined as

*A*<sub>*c**r**o**w**n*, *c**o**h*</sub> = *S*<sub>*c*</sub>.*d**b**h*<sub>*c**o**h*</sub><sup>(*p*<sub>*e*, *l**e**a**f*</sub> − *p*<sub>*e*, *l**e**a**f* − *c**r**o**w**n*</sub>)</sup>

where *A*<sub>*c**r**o**w**n*, *c**o**h*</sub> is the crown area of a
single tree canopy (m<sup>2</sup>) and *S*<sub>*c*</sub> is the ‘canopy
spread’ parameter (unitless), which is assigned as a function of canopy
space filling, discussed below. *S*<sub>*c*</sub> is effectively a
normalisation constant in the power law describing the relationship of
crown area to dbh. However, this is not constant but varies by the
canopy areae to ground area fraction. In contrast to
`Purves et al. 2008<purves2008>` , by default we use an exponent,
identical to that for leaf biomass, *p*<sub>*e*, *l**e**a**f*</sub>, not
2.0, such that tree leaf area index does not change as a function of
diameter. The option is also available to modify the exponent using the
difference parameter, *p*<sub>*e*, *l**e**a**f* − *c**r**o**w**n*</sub>.

To determine whether the canopy is closed, we calculate the total canopy
area as:

$$A\_{canopy} = \\sum\_{coh=1}^{nc,patch}{A\_{crown,coh}.n\_{coh}}$$

where *n**c*<sub>*p**a**t**c**h*</sub> is the number of cohorts in a
given patch. If the area of all crowns *A*<sub>*c**a**n**o**p**y*</sub>
(m<sup>2</sup>) is larger than the total ground area of a patch
(*A*<sub>*p**a**t**c**h*</sub>), which typically happens at the end of
the day, after growth and updated crown allometry is resolved in the
model, then some fraction of each cohort is demoted to the understorey.

<figure>
<img src="images/Sorting_Schematic.png" />
</figure>

Under these circumstances, the <span class="title-ref">extra</span>
crown area *A*<sub>*l**o**s**s*</sub> (i.e.,
*A*<sub>*c**a**n**o**p**y*</sub> - *A*<sub>*p*</sub>) is moved into the
understorey. For each cohort already in the canopy, we determine a
fraction of trees that are moved from the canopy (*L*<sub>*c*</sub>) to
the understorey. *L*<sub>*c*</sub> is calculated as
`Fisher et al. 2010<Fisheretal2010>`

$$L\_{c}= \\frac{A\_{loss,patch} w\_{coh}}{\\sum\_{coh=1}^{nc,patch}{w\_{coh}}} ,$$

where *w*<sub>*c**o**h*</sub> is a weighting of each cohort. There are
two possible ways of calculating this weighting coefficient. The first,
as described in `Fisher et al. 2010<Fisheretal2010>`, is to
probabilistically weight cohorts based on their height *h* (m) and the
competitive exclusion coefficient *C*<sub>*e*</sub>

*w*<sub>*c**o**h*</sub> = *h*<sub>*c**o**h*</sub>*C*<sub>*e*</sub>.

The higher the value of *C*<sub>*e*</sub> the greater the impact of tree
diameter on the probability of a given tree obtaining a position in the
canopy layer. That is, for high *C*<sub>*e*</sub> values, competition is
highly deterministic. The smaller the value of *C*<sub>*e*</sub>, the
greater the influence of random factors on the competitive exclusion
process, and the higher the probability that slower growing trees will
get into the canopy. Appropriate values of *C*<sub>*e*</sub> are poorly
constrained but alter the outcome of competitive processes.

The second way of weighting the cohorts is a more determinstic method
based on a strict rank-ordering of the cohorts by height, where all
cohorts shorter than that cohorts whose cumulative (from the tallest
cohort) rank-ordered crown area equals the area of the patch area are
demoted to the lower canopy layer. This is derived from the original PPA
algorithm described in `Purves et al. 2008<purves2008>`.

The process by which trees are moved between canopy layers is complex
because 1) the crown area predicted for a cohort to lose may be larger
than the total crown area of the cohort, which requires iterative
solutions, and 2) on some occasions (e.g. after fire, or if the
parameter which sets the disturbed area as a function of the fractional
crown area of canopy tree mortality is less than one), the canopy may
open up and require ‘promotion’ of cohorts from the understorey, and 3)
canopy area may change due to the variations of canopy spread values
(*S*<sub>*c*</sub>, see the section below for details) when fractions of
cohorts are demoted or promoted. Further details can be found in the
code references in the footnote.

### Horizontal Canopy Spread

`Purves et al. 2008<purves2008>` estimated the ratio between canopy and
stem diameter *c*<sub>*p*</sub> as 0.1 m cm<sup>-1</sup> for canopy
trees in North American forests, but this estimate was made on trees in
closed canopies, whose shape is subject to space competition from other
individuals. Sapling trees have no constraints in their horizontal
spatial structure, and as such, are more likely to display their leaves
to full sunlight. Also, prior to canopy closure, light interception by
leaves on the sides of the canopy is also higher than it would be in a
closed canopy forest. If the ‘canopy spread’ parameter is constant for
all trees, then we simulate high levels of self-shading for plants in
unclosed canopies, which is arguably unrealistic and can lower the
productivity of trees in areas of unclosed canopy (e.g. low productivity
areas of boreal or semi-arid regions where LAI and canopy cover might
naturally be low). We here interpret the degree of canopy spread,
*S*<sub>*c*</sub> as a function of how much tree crowns interfere with
each other in space, or the total canopy area
*A*<sub>*c**a**n**o**p**y*</sub>. However
*A*<sub>*c**a**n**o**p**y*</sub> itself is a function of
*S*<sub>*c*</sub>, leading to a circularity. *S*<sub>*c*</sub> is thus
solved iteratively through time.

Each daily model step, *A*<sub>*c**a**n**o**p**y*</sub> and the fraction
of the gridcell occupied by tree crowns in the top canopy layer is
calculated (based on *S*<sub>*c*</sub> from the previous timestep):

(*A*<sub>*f*, 1</sub> =
*A*<sub>*c**a**n**o**p**y*, 1</sub>/*A*<sub>*s**i**t**e*</sub>)

If *A*<sub>*f*, 1</sub> is greater than a threshold value
*A*<sub>*t*</sub>, *S*<sub>*c*</sub> is increased by a small increment
*i*, where $i
= i\_p \\left\\{ S\_{c,\\rm{max}} - S\_{c,\\rm{min}} \\right\\}$ (see
bleow for definitions). The threshold *A*<sub>*t*</sub> is,
hypothetically, the canopy fraction at which light competition begins to
impact on tree growth. This is less than 1.0 owing to the non-perfect
spatial spacing of tree canopies. If *A*<sub>*f*, 1</sub> is greater
than *A*<sub>*t*</sub>, then *S*<sub>*c*</sub> is reduced by an
increment *i*, to reduce the spatial extent of the canopy, thus.

$$\\begin{aligned}
S\_{c,t+1} = \\left\\{ \\begin{array}{ll}
S\_{c,t} + i& \\textrm{for $A\_{f,cl} &lt; A\_{t}$}\\\\
&\\\\
S\_{c,t} - i& \\textrm{for $A\_{f,cl} &gt; A\_{t}$}\\\\
\\end{array} \\right.
\\end{aligned}$$

The values of *S*<sub>*c*</sub> are bounded to upper and lower limits.
The lower limit corresponds to the observed canopy spread parameter for
canopy trees *S*<sub>*c*, *m**i**n*</sub> and the upper limit
corresponds to the largest canopy extent *S*<sub>*c*, *m**a**x*</sub>

$$\\begin{aligned}
S\_{c} = \\left\\{ \\begin{array}{ll}
S\_{c,min}& \\textrm{for } S\_{c}&lt; S\_{c,\\rm{min}}\\\\
&\\\\
S\_{c,max}& \\textrm{for } S\_{c} &gt; S\_{c,\\rm{max}}\\\\
\\end{array} \\right.
\\end{aligned}$$

This iterative scheme requires two additional parameters
(*i*<sub>*p*</sub> and *A*<sub>*t*</sub>). *i*<sub>*p*</sub> takes a
value between 0 and 1 and affects the speed with which canopy spread,
*S*<sub>*c*</sub> changes. However, the model is relatively insensitive
to the choice of either *i*<sub>*p*</sub> or *A*<sub>*t*</sub>.

### Definition of Leaf and Stem Area Profile

Within each patch, the model defines and tracks cohorts of multiple
plant functional types that exist either in the canopy or understorey.
Light on the top leaf surface of each cohort in the canopy is the same,
and the rate of decay through the canopy is also the same for each PFT.
Therefore, we accumulate all the cohorts of a given PFT together for the
sake of the radiation and photosynthesis calculations (to avoid separate
calculations for every cohort).

Therefore, the leaf area index for each patch is defined as a
three-dimensional array *l**a**i*<sub>*c**l*, *f**t*, *z*</sub> where
*C*<sub>*l*</sub>

is the canopy layer, *f**t* is the functional type and *z* is the leaf
layer within each canopy. This three-dimensional structure is the basis
of the radiation and photosynthetic models. In addition to a leaf area
profile matrix, we also define, for each patch, the area which is
covered by leaves at each layer as
*c**a**r**e**a*<sub>*c**l*, *f**t*, *z*</sub>.

Each plant cohort is already defined as a member of a single canopy
layer and functional type. This means that to generate the
*x*<sub>*c**l*, *f**t*, *z*</sub> matrix, it only remains to divide the
leaf area of each cohort into leaf layers. First, we determine how many
leaf layers are occupied by a single cohort, by calculating the ‘tree
LAI’ as the total leaf area of each cohort divided by its crown area
(both in m<sup>2</sup>)

$$\\mathit{tree}\_{lai,coh} = \\frac{C\_{leaf,coh}\\cdot\\mathrm{sla}\_{ft}}{A\_{crown,coh}}$$

where sla<sub>*f**t*</sub> is the specific leaf area in m<sup>2</sup>
KgC<sup>-1</sup> and *C*<sub>*l**e**a**f*</sub> is in KgC per plant.

Stem area index (SAI) is ratio of the total area of all woody stems on a
plant to the area of ground covered by the plant. During winter in
deciduous areas, the extra absorption by woody stems can have a
significant impact on the surface energy budget. However, in previous
<span class="title-ref">big leaf</span> versions of the CLM, computing
the circumstances under which stem area was visible in the absence of
leaves was difficult and the algorithm was largely heuristic as a
result. Given the multi-layer canopy introduced for FATES, we can
determine the leaves in the higher canopy layers will likely shade stem
area in the lower layers when leaves are on, and therefore stem area
index can be calculated as a function of woody biomass directly.

Literature on stem area index is particularly poor, as it’s estimation
is complex and not particularly amenable to the use of, for example,
assumptions of random distribution in space that are typically used to
calculate leaf area from light interception.
`Kucharik et al. 1998<kucharik1998>` estimated that SAI visible from an
LAI2000 sensor was around 0.5 m<sup>2</sup> m<sup>-2</sup>. Low et al.
2001 estimate that the wood area index for Ponderosa Pine forest is
0.27-0.33. The existing CLM(CN) algorithm sets the minimum SAI at 0.25
to match MODIS observations, but then allows SAI to rise as a function
of the LAI lost, meaning than in some places, predicted SAI can reach
value of 8 or more. Clearly, greater scientific input on this quantity
is badly needed. Here we determine that SAI is a linear function of
woody biomass, to at very least provide a mechanistic link between the
existence of wood and radiation absorbed by it. The non-linearity
between how much woody area exists and how much radiation is absorbed is
provided by the radiation absorption algorithm. Specifically, the SAI of
an individual cohort (tree<sub>*s**a**i*, *c**o**h*</sub>, m<sup>2</sup>
m<sup>-2</sup>) is calculated as follows,

tree<sub>*s**a**i*, *c**o**h*</sub> = *k*<sub>*s**a**i*</sub> ⋅ *C*<sub>*s**t**r**u**c*, *c**o**h*</sub>,

where *k*<sub>*s**a**i*</sub> is the coefficient linking structural
biomass to SAI. The number of occupied leaf layers for cohort *c**o**h*
(*n*<sub>*z*, *c**o**h*</sub>) is then equal to the rounded up integer
value of the tree SAI (*t**r**e**e*<sub>*s**a**i*, *c**o**h*</sub>) and
LAI (*t**r**e**e*<sub>*l**a**i*, *c**o**h*</sub>) divided by the layer
thickness (i.e., the resolution of the canopy layer model, in units of
vegetation index (*l**a**i*+*s**a**i*) with a default value of 1.0,
*δ*<sub>*v**a**i*</sub> ),

$$n\_{z,coh} = {\\frac{\\mathrm{tree}\_{lai,coh}+\\mathrm{tree}\_{sai,coh}}{\\delta\_{vai}}}.$$

The fraction of each layer that is leaf (as opposed to stem) can then be
calculated as

$$f\_{leaf,coh} = \\frac{\\mathrm{tree}\_{lai,coh}}{\\mathrm{tree}\_{sai,coh}+\\mathrm{tree}\_{lai,coh}}.$$

Finally, the leaf area in each leaf layer pertaining to this cohort is
thus

$$\\begin{aligned}
\\mathit{lai}\_{z,coh}  = \\left\\{ \\begin{array}{ll}
 \\delta\_{vai} \\cdot f\_{leaf,coh} \\frac{A\_{canopy,coh}}{A\_{canopy,patch}}& \\textrm{for $i=1,..., i=n\_{z,coh}-1$}\\\\
&\\\\
 \\delta\_{vai} \\cdot f\_{leaf,coh} \\frac{A\_{canopy,coh}}{A\_{canopy,patch}}\\cdot r\_{vai}& \\textrm{for $i=n\_{z,coh}$}\\\\
\\end{array} \\right.
\\end{aligned}$$

and the stem area index is

$$\\begin{aligned}
\\mathit{sai}\_{z,coh}  = \\left\\{ \\begin{array}{ll}
 \\delta\_{vai} \\cdot (1-f\_{leaf,coh})\\frac{A\_{canopy,coh}}{A\_{canopy,patch}}& \\textrm{for $i=1,..., i=n\_{z,coh}-1$}\\\\
&\\\\
 \\delta\_{vai} \\cdot (1-f\_{leaf,coh}) \\frac{A\_{canopy,coh}}{A\_{canopy,patch}}\\cdot r\_{vai}& \\textrm{for $i=n\_{z,coh}$}\\\\
\\end{array} \\right.
\\end{aligned}$$

where *r*<sub>*v**a**i*</sub> is the remainder of the canopy that is
below the last full leaf layer

*r*<sub>*v**a**i*</sub> = (tree<sub>*l**a**i*, *c**o**h*</sub> + tree<sub>*s**a**i*, *c**o**h*</sub>) − (*δ*<sub>*v**a**i*</sub> ⋅ (*n*<sub>*z*, *c**o**h*</sub> − 1)).

*A*<sub>*c**a**n**o**p**y*, *p**a**t**c**h*</sub> is the total canopy
area occupied by plants in a given patch (m<sup>2</sup>) and is
calculated as follows,

$$A\_{canopy,patch} = \\textrm{min}\\left( \\sum\_{coh=1}^{coh = ncoh}A\_{canopy,coh}, A\_{patch}  \\right).$$

The canopy is conceived as a cylinder, although this assumption could be
altered given sufficient evidence that canopy shape was an important
determinant of competitive outcomes, and the area of ground covered by
each leaf layer is the same through the cohort canopy. With the
calculated SAI and LAI, we are able to calculate the complete canopy
profile. Specifically, the relative canopy area for the cohort *c**o**h*
is calculated as

$$\\mathit{area}\_{1:nz,coh}  =  \\frac{A\_{crown,coh}}{A\_{canopy,patch}}.$$

The total occupied canopy area for each canopy layer (*c**l*), plant
functional type (*f**t*) and leaf layer (*z*) bin is thus

$$\\mathit{c}\_{area,cl,ft,z} = \\sum\_{coh=1}^{coh=ncoh} area\_{1:nz,coh}$$

where *f**t*<sub>*c**o**h*</sub> = *f**t* and
*c**l*<sub>*c**o**h*</sub> = *c**l*.

All of these quantities are summed across cohorts to give the complete
leaf and stem area profiles,

$$\\mathit{lai} \_{cl,ft,z} = \\sum\_{coh=1}^{coh=ncoh} \\mathit{lai}\_{z,coh}$$

$$\\mathit{sai}\_{cl,ft,z} = \\sum\_{coh=1}^{coh=ncoh} \\mathit{sai}\_{z,coh}$$

### Burial of leaf area by snow

The calculations above all pertain to the total leaf and stem area
indices which charecterize the vegetation structure. In addition, the
model must know when the vegetation is covered by snow, and by how much,
so that the albedo and energy balance calculations can be adjusted
accordingly. Therefore, we calculated a ‘total’ and ‘exposed’ *l**a**i*
and *s**a**i* profile using a representation of the bottom and top
canopy heights, and the depth of the average snow pack. For each leaf
layer *z* of each cohort, we calculate an ‘exposed fraction
*f*<sub>*e**x**p*, *z*</sub> via consideration of the top and bottom
heights of that layer *h*<sub>*t**o**p*, *z*</sub> and
*h*<sub>*b**o**t*, *z*</sub> (m),

$$\\begin{aligned}
\\begin{array}{ll}
h\_{top,z} = h\_{coh} - h\_{coh}\\cdot f\_{crown,ft}\\cdot\\frac{z}{n\_{z,coh}}& \\\\
&\\\\
h\_{bot,z} = h\_{coh} - h\_{coh}\\cdot f\_{crown,ft}\\cdot\\frac{z+1}{n\_{z,coh}}&\\\\
\\end{array}
\\end{aligned}$$

where *f*<sub>*c**r**o**w**n*, *f**t*</sub> is the plant functional type
(*f**t*) specific fraction of the cohort height that is occupied by the
crown. Specifically, the ‘exposed fraction *f*<sub>*e**x**p*, *z*</sub>
is calculated as follows,

$$\\begin{aligned}
f\_{exp,z}\\left\\{ \\begin{array}{ll}
= 1.0 &  h\_{bot,z}&gt; d\_{snow}\\\\
&\\\\
= \\frac{d\_{snow} -h\_{bot,z}}{h\_{top,z}-h\_{bot,z}}  & h\_{top,z}&gt; d\_{snow}, h\_{bot,z}&lt; d\_{snow}\\\\
&\\\\
= 0.0 & h\_{top,z}&lt; d\_{snow}\\\\
\\end{array} \\right.
\\end{aligned}$$

The resulting exposed (*e**l**a**i*, *e**s**a**i*) and total
(*t**l**a**i*, *t**s**a**i*) leaf and stem area indicies are calculated
as

$$\\begin{aligned}
\\begin{array}{ll}
\\mathit{elai} \_{cl,ft,z} &= \\mathit{lai} \_{cl,ft,z} \\cdot f\_{exp,z}\\\\
\\mathit{esai} \_{cl,ft,z} &= \\mathit{sai} \_{cl,ft,z} \\cdot f\_{exp,z}\\\\
\\mathit{tlai} \_{cl,ft,z} &= \\mathit{lai} \_{cl,ft,z}\\\\
\\mathit{tsai} \_{cl,ft,z} &= \\mathit{sai} \_{cl,ft,z} \\
\\end{array} ,
\\end{aligned}$$

and are used in the radiation interception and photosynthesis algorithms
described later.

| Parameter Symbol | Parameter Name | Units | Notes | Indexed by |
|--------------------|-------------|--------------|-------------|-------------|
| *δ*<sub>*v**a**i*</sub> | Thickness of single canopy layer | m<sup>2</sup> m<sup>-2</sup> |  |  |
| *C*<sub>*e*</sub> | Competitive Exclusion Parameter | none |  |  |
| *c*<sub>*p*, *m**i**n*</sub> | Minimum canopy spread | m<sup>2</sup> cm<sup>-1</sup> |  |  |
| *c*<sub>*p*, *m**a**x*</sub> | Competitive Exclusion Parameter | m<sup>2</sup> cm<sup>-1</sup> |  |  |
| *i* | Incremental change in *c*<sub>*p*</sub> | m<sup>2</sup> cm<sup>-1</sup> y<sup>-1</sup> |  |  |
| *A*<sub>*t*</sub> | Threshold canopy closure | none |  |  |
| *f*<sub>*c**r**o**w**n*, *f**t*</sub> | Crown fraction | none |  | *f**t* |
| *k*<sub>*s**a**i*</sub> | Stem area per unit woody biomass | m<sup>2</sup> KgC<sup>-1</sup> |  |  |

## Radiation Transfer

### Fundamental Radiation Transfer Theory

The first interaction of the land surface with the properties of
vegetation concerns the partitioning of energy into that which is
absorbed by vegetation, reflected back into the atmosphere, and absorbed
by the ground surface. Older versions of the CLM have utilized a
"two-stream" approximation `Sellers 1985<sellers1985>`,
`Sellers et al. 1986<sellers1996>` that provided an empirical solution
for the radiation partitioning of a multi-layer canopy for two streams,
of diffuse and direct light. However, implementation of the Ecosystem
Demography model requires a) the adoption of an explicit multiple layer
canopy b) the implementation of a multiple plant type canopy and c) the
distinction of canopy and under-storey layers, in-between which the
radiation streams are fully mixed. The radiation mixing between canopy
layers is necessary as the position of different plants in the
under-storey is not defined spatially or relative to the canopy trees
above. In this new scheme, we thus implemented a one-dimensional scheme
that traces the absorption, transmittance and reflectance of each canopy
layer and the soil, iterating the upwards and downwards passes of
radiation through the canopy until a pre-defined accuracy tolerance is
reached. This approach is based on the work of
`Norman 1979<norman1979>`.

Here we describe the basic theory of the radiation transfer model for
the case of a single homogenous canopy, and in the next section we
discuss how this is applied to the multi layer multi PFT canopy in the
FATES implementation. The code considers the fractions of a single unit
of incoming direct and a single unit of incoming diffuse light, that are
absorbed at each layer of the canopy for a given solar angle
(*α*<sub>*s*</sub>, radians). Direct radiation is extinguished through
the canopy according to the coefficient *k*<sub>*d**i**r*</sub> that is
calculated from the incoming solar angle and the dimensionless leaf
angle distribution parameter (*χ*) as

$$\\begin{aligned}
k\_{dir} = g\_{dir} / \\sin(\\alpha\_s)\\\\
\\end{aligned}$$

where

$$\\begin{aligned}
g\_{dir} = \\phi\_1 + \\phi\_2 \\cdot \\sin(\\alpha\_s)\\\\
\\end{aligned}$$

and

$$\\begin{aligned}
\\begin{array} {l}
\\phi\_1 = 0.5 - 0.633\\chi\_{l} - 0.33\\chi\_l ^2\\\\
\\phi\_2 =0.877 (1 - 2\\phi\_1)\\\\
\\end{aligned}$$
$$\\end{array}$$

The leaf angle distribution is a descriptor of how leaf surfaces are
arranged in space. Values approaching 1.0 indicate that (on average) the
majority of leaves are horizontally arranged with respect to the ground.
Values approaching -1.0 indicate that leaves are mostly vertically
arranged, and a value of 0.0 denotes a canopy where leaf angle is random
(a ‘spherical’ distribution).

According to Beer’s Law, the fraction of light that is transferred
through a single layer of vegetation (leaves or stems) of thickness
*δ*<sub>*v**a**i*</sub>, without being intercepted by any surface, is

*t**r*<sub>*d**i**r*</sub> = *e*<sup>−*k*<sub>*d**i**r*</sub>*δ*<sub>*v**a**i*</sub></sup>

and the incident direct radiation transmitted to each layer of the
canopy (*d**i**r*<sub>*t**r*, *z*</sub>) is thus calculated from the
cumulative leaf area ( *L*<sub>*a**b**o**v**e*</sub> ) shading each
layer (*z*):

*d**i**r*<sub>*t**r*, *z*</sub> = *e*<sup>−*k*<sub>*d**i**r*</sub>*L*<sub>*a**b**o**v**e*, *z*</sub></sup>

The fraction of the leaves *f*<sub>*s**u**n*</sub> that are exposed to
direct light is also calculated from the decay coefficient
*k*<sub>*d**i**r*</sub>.

$$\\begin{aligned}
\\begin{array}{l}
f\_{sun,z} = e^{-k\_{dir}  L\_{above,z}}\\\\
 \\rm{and} 
\\\\ f\_{shade,z} = 1-f\_{sun,z}
\\end{array}
\\end{aligned}$$

where *f*<sub>*s**h**a**d**e*, *z*</sub> is the fraction of leaves that
are shaded from direct radiation and only receive diffuse light.

Diffuse radiation, by definition, enters the canopy from a spectrum of
potential incident directions, therefore the un-intercepted transfer
(*t**r*<sub>*d**i**f*</sub>) through a leaf layer of thickness
*δ*<sub>*l*</sub> is calculated as the mean of the transfer rate from
each of 9 different incident light directions (*α*<sub>*s*</sub>)
between 0 and 180 degrees to the horizontal.

$$\\begin{aligned}
\\mathit{tr}\_{dif} = \\frac{1}{9} \\sum\\limits\_{\\alpha\_s=5\\pi/180}^{\\alpha\_s=85\\pi/180} e^{-k\_{dir,l} \\delta\_{vai}} \\\\ \\\\
\\end{aligned}$$

$$tr\_{dif}= \\frac{1}{9} \\pi \\sum\_{\\alpha s=0}^{ \\pi / 2}  \\frac{e^{-gdir} \\alpha\_s}{\\delta\_{vai} \\cdot \\rm{sin}(\\alpha\_s) \\rm{sin}(\\alpha\_s) \\rm{cos}(\\alpha\_s)}$$

The fraction (1-*t**r*<sub>*d**i**f*</sub>) of the diffuse radiation is
intercepted by leaves as it passes through each leaf layer. Of this,
some fraction is reflected by the leaf surfaces and some is transmitted
through. The fractions of diffuse radiation reflected from
(*r**e**f**l*<sub>*d**i**f*</sub>) and transmitted though
(*t**r**a**n*<sub>*d**i**f*</sub>) each layer of leaves are thus,
respectively

$$\\begin{aligned}
\\begin{array}{l}
\\mathit{refl\_{dif}} = (1 - tr\_{dif})  \\rho\_{l,ft}\\\\
\\mathit{tran}\_{dif} = (1 - tr\_{dif})  \\tau\_{l,ft} + tr\_{dif}
\\end{array}
\\end{aligned}$$

where *ρ*<sub>*l*, *f**t*</sub> and *τ*<sub>*l*, *f**t*</sub> are the
fractions of incident light reflected and transmitted by individual leaf
surfaces.

Once we know the fractions of light that are transmitted and reflected
by each leaf layer, we begin the process of distributing light through
the canopy. Starting with the first leaf layer (*z*=1), where the
incident downwards diffuse radiation (*d**i**f*<sub>*d**o**w**n*</sub>)
is 1.0, we work downwards for *n*<sub>*z*</sub> layers, calculating the
radiation in the next layer down (*z* + 1) as:

$$\\mathit{dif}\_{down,z+1} = \\frac{\\mathit{dif}\_{down,z} \\mathit{tran}\_{dif} }    {1 - \\mathit{r}\_{z+1}  \\mathit{refl}\_{dif}}$$

Here,
*d**i**f*<sub>*d**o**w**n*, *z*</sub>*t**r**a**n*<sub>*d**i**f*</sub>
calculates the fraction of incoming energy transmitted downwards onto
layer *z* + 1. This flux is then increased by the additional radiation
*r*<sub>*z*</sub> that is reflected upwards from further down in the
canopy to layer *z*, and then is reflected back downwards according to
the reflected fraction *r**e**f**l*<sub>*d**i**f*</sub>. The more
radiation in *r*<sub>*z* + 1</sub>*r**e**f**l*<sub>*d**i**f*</sub>, the
smaller the denominator and the larger the downwards flux. *r* is also
calculated sequentially, starting this time at the soil surface layer
(where *z* = *n*<sub>*z*</sub> + 1)

*r*<sub>*n**z* + 1</sub> = *a**l**b*<sub>*s*</sub>

where *a**l**b*<sub>*s*</sub> is the soil albedo characteristic. The
upwards reflected fraction *r*<sub>*z*</sub> for each leaf layer, moving
upwards, is then `Norman 1979<norman1979>`

$$r\_z  = \\frac{r\_{z+1}  \\times \\mathit{tran}\_{dif}  ^{2} }{ (1 - r\_{z+1}  \\mathit{refl\_{dif}}) + \\mathit{refl\_{dif}}}.$$

The corresponding upwards diffuse radiation flux is therefore the
fraction of downwards radiation that is incident on a particular layer,
multiplied by the fraction that is reflected from all the lower layers:

*d**i**f*<sub>*u**p*, *z*</sub> = *r*<sub>*z*</sub>*d**i**f*<sub>*d**o**w**n*, *z* + 1</sub>

Now we have initial conditions for the upwards and downwards diffuse
fluxes, these must be modified to account for the fact that, on
interception with leaves, direct radiation is transformed into diffuse
radiation. In addition, the initial solutions to the upwards and
downwards radiation only allow a single ‘bounce’ of radiation through
the canopy, so some radiation which might be intercepted by leaves
higher up is potentially lost. Therefore, the solution to this model is
iterative. The iterative solution has upwards and a downwards components
that calculate the upwards and downwards fluxes of total radiation at
each leaf layer (*r**a**d*<sub>*d**n*, *z*</sub> and
*r**a**d*<sub>*u**p*, *z*</sub>) . The downwards component begins at the
top canopy layer (*z* = 1). Here we define the incoming solar diffuse
and direct radiation ($\\it{solar}\_{dir}$ and $\\it{solar}\_{dir}$
respectively).

$$\\begin{aligned}
\\begin{array}{l}
 \\mathit{dif}\_{dn,1} =  \\it{solar}\_{dif} \\\\
\\mathit{rad}\_{dn, z+1} = \\mathit{dif}\_{dn,z} \\cdot  \\mathit{tran}\_{dif}  +\\mathit{dif}\_{up,z+1}   \\cdot  \\mathit{refl}\_{dif}   + \\mathit{solar}\_{dir}  \\cdot  dir\_{tr,z}  (1- tr\_{dir})  \\tau\_l.
\\end{array}
\\end{aligned}$$

The first term of the right-hand side deals with the diffuse radiation
transmitted downwards, the second with the diffuse radiation travelling
upwards, and the third with the direct radiation incoming at each layer
(*d**i**r*<sub>*t**r*, *z*</sub>) that is intercepted by leaves
(1 − *t**r*<sub>*d**i**r*</sub>) and then transmitted through through
the leaf matrix as diffuse radiation (*τ*<sub>*l*</sub>). At the bottom
of the canopy, the light reflected off the soil surface is calculated as

$$rad \_{up, nz} =  \\rm{\\it{dif}}\_{down,z}  \\cdot  salb\_{dif} +\\it{solar}\_{dir} \\cdot dir\_{tr,z} salb\_{dir}.$$

The upwards propagation of the reflected radiation is then

$$rad\_{up, z} = \\mathit{dif}\_{up,z+1} \\cdot  \\mathit{tran}\_{dif}  +\\mathit{dif}\_{dn,z}   \\cdot  \\mathit{refl}\_{dif}   + \\it{solar}\_{dir}  \\cdot  dir\_{tr,z}  (1- tr\_{dir})  \\rho\_l.$$

Here the first two terms deal with the diffuse downwards and upwards
fluxes, as before, and the third deals direct beam light that is
intercepted by leaves and reflected upwards. These upwards and downwards
fluxes are computed for multiple iterations, and at each iteration,
*r**a**d*<sub>*u**p*, *z*</sub> and
*r**a**d*<sub>*d**o**w**n*, *z*</sub> are compared to their values in
the previous iteration. The iteration scheme stops once the differences
between iterations for all layers is below a predefined tolerance
factor, (set here at 10<sup>−4</sup>). Subsequently, the fractions of
absorbed direct (*a**b**s*<sub>*d**i**r*, *z*</sub>) and diffuse
(*a**b**s*<sub>*d**i**f*, *z*</sub>) radiation for each leaf layer then

$$abs\_{dir,z} = \\it{solar}\_{dir}   \\cdot dir\_{tr,z} \\cdot (1- tr\_{dir}) \\cdot (1 - \\rho\_l-\\tau\_l)$$

*a**b**s*<sub>*d**i**f*, *z*</sub> = (*d**i**f*<sub>*d**n*, *z*</sub> + *d**i**f*<sub>*u**p*, *z* + 1</sub>) ⋅ (1 − *t**r*<sub>*d**i**f*</sub>) ⋅ (1 − *ρ*<sub>*l*</sub> − *τ*<sub>*l*</sub>).

and, the radiation energy absorbed by the soil for the diffuse and
direct streams is is calculated as

$$\\it{abs}\_{soil} = \\mathit{dif}\_{down,nz+1} \\cdot (1 -  salb\_{dif}) +\\it{solar}\_{dir}   \\cdot dir\_{tr,nz+1} \\cdot (1-  salb\_{dir}).$$

Canopy level albedo is denoted as the upwards flux from the top leaf
layer

$$\\it{alb}\_{canopy}=  \\frac{\\mathit{dif}\_{up,z+1}  }{  \\it{solar}\_{dir} + \\it{solar}\_{dif}}$$

and the division of absorbed energy into sunlit and shaded leaf
fractions, (required by the photosynthesis calculations), is

*a**b**s*<sub>*s**h**a*, *z*</sub> = *a**b**s*<sub>*d**i**f*, *z*</sub> ⋅ *f*<sub>*s**h**a*</sub>

*a**b**s*<sub>*s**u**n*, *z*</sub> = *a**b**s*<sub>*d**i**f*, *z*</sub> ⋅ *f*<sub>*s**u**n*</sub> + *a**b**s*<sub>*d**i**r*, *z*</sub>

### Resolution of radiation transfer theory within the FATES canopy structure

The radiation transfer theory above, was described with reference to a
single canopy of one plant functional type, for the sake of clarity of
explanation. The FATES model, however, calculates radiative and
photosynthetic fluxes for a more complex hierarchical structure within
each patch/time-since-disturbance class, as described in the leaf area
profile section. Firstly, we denote two or more canopy layers (denoted
*c**l*). The concept of a ‘canopy layer’ refers to the idea that plants
are organized into discrete over and under-stories, as predicted by the
Perfect Plasticity Approximation (`Purves et al. 2008<purves2008>`,
`Fisher et al. 2010<Fisheretal2010>`). Within each canopy layer there
potentially exist multiple cohorts of different plant functional types
and heights. Within each canopy layer, *c**l*, and functional type,
*f**t*, the model resolves numerous leaf layers *z*, and, for some
processes, notably photosynthesis, each leaf layer is split into a
fraction of sun and shade leaves, *f*<sub>*s**u**n*</sub> and
*f*<sub>*s**h**a*</sub>, respectively.

The radiation scheme described in Section is solved explicitly for this
structure, for both the visible and near-infrared wavebands, according
to the following assumptions.

- A *canopy layer* (*c**l*) refers literally to the vertical layer
  within the canopy this cohort resides in. The top canopy layer has
  index 1. A closed canopy forest will therefore by definition have at
  least two layers, and perhaps more.
- A *leaf layer* (*z*) refers to the discretization of the LAI within
  the canopy of a given plant functional type.
- All PFTs in the same canopy layer have the same solar radiation
  incident on the top layer of the canopy
- Light is transmitted through the canopy of each plant functional type
  independently
- Between canopy layers, the light streams from different plant
  functional types are mixed, such that the (undefined) spatial location
  of plants in lower canopy layers does not impact the amount of light
  received.
- Where understorey layers fill less area than the overstorey layers,
  radiation is directly transferred to the soil surface.
- All these calculations pertain to a single patch, so we omit the
  <span class="title-ref">patch</span> subscript for simplicity in the
  following discussion.

Within this framework, the majority of the terms in the radiative
transfer scheme are calculated with indices of *c**l*, $\\it{ft}$ and
*z*. In the following text, we revisit the simplified version of the
radiation model described above, and explain how it is modified to
account for the more complex canopy structure used by FATES.

Firstly, the light penetration functions, *k*<sub>*d**i**r*</sub> and
*g*<sub>*d**i**r*</sub> are described as functions of $\\it{ft}$,
because the leaf angle distribution, *χ*<sub>*l*</sub>, is a
pft-specific parameter. Thus, the diffuse irradiance transfer rate,
*t**r*<sub>*d**i**f*</sub> is also $\\it{ft}$ specific because
*g*<sub>*d**i**r*</sub>, on which it depends, is a function of
*χ*<sub>*l*</sub>.

The amount of direct light reaching each leaf layer is a function of the
leaves existing above the layer in question. If a leaf layer ‘*z*’ is in
the top canopy layer (the over-storey), it is only shaded by leaves of
the same PFT so *k*<sub>*d**i**r*</sub> is unchanged from equation. If
there is more than one canopy layer (*c**l*<sub>*m**a**x*</sub> &gt; 1),
then the amount of direct light reaching the top leaf surfaces of the
second/lower layer is the weighted average of the light attenuated by
all the parallel tree canopies in the canopy layer above, thus.

$$dir\_{tr(cl,:,1)} =\\sum\_{ft=1}^{npft}{(dir\_{tr(cl,ft,z\_{max})} \\cdot c\_{area(cl-1,ft,z\_{max})})}$$

where $\\it{pft}\_{wt}$ is the areal fraction of each canopy layer
occupied by each functional type and *z*<sub>*m**a**x*</sub> is the
index of the bottom canopy layer of each pft in each canopy layer (the
subscripts

*c**l* and *f**t* are implied but omitted from all
*z*<sub>*m**a**x*</sub> references to avoid additional complications)

Similarly, the sunlit fraction for a leaf layer ‘*z*’ in the second
canopy layer (where *c**l* &gt; 1) is

*f*<sub>*s**u**n*(*c**l*, *f**t*, *z*)</sub> = *W*<sub>*s**u**n*(*c**l*)</sub> ⋅ *e*<sup>*k*<sub>*d**i**r*(*f**t*, *l**a**i**c*, *z*)</sub></sup>

where *W*<sub>*s**u**n*, *c**l*</sub> is the weighted average sunlit
fraction in the bottom layer of a given canopy layer.

$$W\_{sun(cl)} = \\sum\_{ft=1}^{npft}{(f\_{sun(cl-1,ft,zmax)} \\cdot  c\_{area(cl-1,ft,zmax)})}$$

Following through the sequence of equations for the simple single pft
and canopy layer approach above, the *r**e**f**l*<sub>*d**i**f*</sub>
and *t**r**a**n*<sub>*d**i**f*</sub> fluxes are also indexed by *c**l*,
$\\it{ft}$, and *z*. The diffuse radiation reflectance ratio
*r*<sub>*z*</sub> is also calculated in a manner that homogenizes fluxes
between canopy layers. For the canopy layer nearest the soil (*c**l* =
*c**l*<sub>*m**a**x*</sub>). For the top canopy layer (*c**l*=1), a
weighted average reflectance from the lower layers is used as the
baseline, in lieu of the soil albedo. Thus:

$$r\_{z(cl,:,1)} =  \\sum\_{ft=1}^{npft}{(r\_{z(cl-1,ft,1)}   \\it{pft}\_{wt(cl-1,ft,1)})}$$

For the iterative flux resolution, the upwards and downwards fluxes are
also averaged between canopy layers, thus where *c**l* &gt; 1

$$rad\_{dn(cl,ft,1)} = \\sum\_{ft=1}^{npft}{(rad\_{dn(cl-1,ft,zmax)} \\cdot  \\it{pft}\_{wt(cl-1,ft,zmax)})}$$

and where *c**l* =1, and *c**l*<sub>*m**a**x*</sub> &gt; 1

$$rad\_{up(cl,ft,zmax)} = \\sum\_{ft=1}^{npft}{(rad\_{up(cl+1,ft,1)} \\cdot  \\it{pft}\_{wt(cl+1,ft,1)})}$$

The remaining terms in the radiation calculations are all also indexed
by *c**l*, *f**t* and *z* so that the fraction of absorbed radiation
outputs are termed *a**b**s*<sub>*d**i**r*(*c**l*, *f**t*, *z*)</sub>
and *a**b**s*<sub>*d**i**f*(*c**l*, *f**t*, *z*)</sub>. The sunlit and
shaded absorption rates are therefore

*a**b**s*<sub>*s**h**a*(*c**l*, *f**t*, *z*)</sub> = *a**b**s*<sub>*d**i**f*(*c**l*, *f**t*, *z*)</sub> ⋅ *f*<sub>*s**h**a*(*c**l*, *f**t*, *z*)</sub>

and

*a**b**s*<sub>*s**u**n*(*c**l*, *f**t*, *z*)</sub> = *a**b**s*<sub>*d**i**f*(*c**l*, *f**t*, *z*)</sub> ⋅ *f*<sub>*s**u**n*(*c**l*, *f**t*, *z*)</sub> + *a**b**s*<sub>*d**i**r*(*c**l*, *f**t*, *z*)</sub>

The albedo of the mixed pft canopy is calculated as the weighted average
of the upwards radiation from the top leaf layer of each pft where
*c**l*=1:

$$\\it{alb}\_{canopy}=  \\sum\_{ft=1}^{npft}{\\frac{\\mathit{dif}\_{up(1,ft,1)}    \\it{pft}\_{wt(1,ft,1)}} {\\it{solar}\_{dir} + \\it{solar}\_{dif}}}$$

The radiation absorbed by the soil after passing through through
under-storey vegetation is:

$$\\it{abs}\_{soil}=  \\sum\_{ft=1}^{npft}{ \\it{pft}\_{wt(1,ft,1)}( \\mathit{dif}\_{down(nz+1)} (1 -  salb\_{dif}) +\\it{solar}\_{dir}   dir\_{tr(nz+1)}  (1-  salb\_{dir}))}$$

to which is added the diffuse flux coming directly from the upper canopy
and hitting no understorey vegetation.

$$\\it{abs}\_{soil}=  \\it{abs}\_{soil}+dif\_{dn(2,1)}  (1-  \\sum\_{ft=1}^{npft}{\\it{pft}\_{wt(1,ft,1)}})  (1 -  salb\_{dif})$$

and the direct flux coming directly from the upper canopy and hitting no
understorey vegetation.

$$\\it{abs}\_{soil}=  \\it{abs}\_{soil}+\\it{solar}\_{dir} dir\_{tr(2,1)}(1-  \\sum\_{ft=1}^{npft}{\\it{pft}\_{wt(1,ft,1)}})  (1 -  salb\_{dir})$$

These changes to the radiation code are designed to be structurally
flexible, and the scheme may be collapsed down to only include on canopy
layer, functional type and pft for testing if necessary.

\captionof{table}{Parameters needed for radiation transfer model. }

| Parameter Symbol | Parameter Name | Units | indexed by |
|------------------|------------------|------------------|------------------|
| *χ* | Leaf angle distribution parameter | none | *ft* |
| *ρ*<sub>*l*</sub> | Fraction of light reflected by leaf surface | none | *ft* |
| *τ*<sub>*l*</sub> | Fraction of light transmitted by leaf surface | none | *ft* |
| *a**l**b*<sub>*s*</sub> | Fraction of light reflected by soil | none | direct vs diffuse |

\bigskip 

## Photosynthesis

### Fundamental photosynthetic physiology theory

In this section we describe the physiological basis of the
photosynthesis model before describing its application to the FATES
canopy structure. This description in this section is largely repeated
from the Oleson et al. CLM4.5 technical note but included here for
comparison with its implementation in FATES. Photosynthesis in C3 plants
is based on the model of `Farquhar 1980<Farquharetal1980>` as modified
by `Collatz et al. (1991)<Collatzetal1991>`. Photosynthetic assimilation
in C4 plants is based on the model of
`Collatz et al. (1991)<Collatzetal1991>`. In both models, leaf
photosynthesis, gpp (*μ*mol CO<sub>2</sub> m<sup>−2</sup>
s<sup>−1</sup>) is calculated as the minimum of three potentially
limiting fluxes, described below:

$$\\textrm{gpp} = \\rm{min}(w\_{j}, w\_{c},w\_{p}).$$

The RuBP carboxylase (Rubisco) limited rate of carboxylation
*w*<sub>*c*</sub> (*μ*mol CO<sub>2</sub> m<sup>−2</sup> s<sup>−1</sup>)
is determined as

$$\\begin{aligned}
w\_{c}=  \\left\\{ \\begin{array}{ll}
\\frac{V\_{c,max}(c\_{i} - \\Gamma\_\*)}{ci+K\_{c}(1+o\_{i}/K\_{o})} & \\textrm{for $C\_{3}$ plants}\\\\
&\\\\
V\_{c,max}& \\textrm{for $C\_{4}$ plants}\\\\
\\end{array} \\right.
c\_{i}-\\Gamma\_\*\\ge 0
\\end{aligned}$$

where *c*<sub>*i*</sub> is the internal leaf CO<sub>2</sub> partial
pressure (Pa) and *o*<sub>*i*</sub>(0.209*P*<sub>*a**t**m*</sub>) is the
O<sub>2</sub> partial pressure (Pa). *K*<sub>*c*</sub> and
*K*<sub>*o*</sub> are the Michaelis-Menten constants (Pa) for
CO<sub>2</sub> and O<sub>2</sub>. These vary with vegetation temperature
*T*<sub>*v*</sub> (<sup>*o*</sup>C) according to an Arrhenious function
described in `Oleson et al. 2013<olesonetal2013>`.
*V*<sub>*c*, *m**a**x*</sub> is the leaf layer photosynthetic capacity
(*μ* mol CO<sub>2</sub> m<sup>−2</sup> s<sup>−1</sup>).

The maximum rate of carboxylation allowed by the capacity to regenerate
RuBP (i.e., the light-limited rate) *w*<sub>*j*</sub> (*μ*mol
CO<sub>2</sub> m<sup>−2</sup> s<sup>−1</sup>) is

$$\\begin{aligned}
w\_j=  \\left\\{ \\begin{array}{ll}
\\frac{J(c\_i - \\Gamma\_\*)}{4ci+8\\Gamma\_\*} & \\textrm{for C$\_3$ plants}\\\\
&\\\\
4.6\\phi\\alpha & \\textrm{for C$\_4$ plants}\\\\
\\end{array} \\right.
c\_i-\\Gamma\_\*\\ge 0
\\end{aligned}$$

To find *J*, the electron transport rate (*μ* mol CO<sub>2</sub>
m<sup>−2</sup> s<sup>−1</sup>), we solve the following quadratic term
and take its smaller root,

*Θ*<sub>*p**s**I**I*</sub>*J*<sup>2</sup> − (*I*<sub>*p**s**I**I*</sub> + *J*<sub>*m**a**x*</sub>)*J* + *I*<sub>*p**s**I**I*</sub>*J*<sub>*m**a**x*</sub> = 0

where *J*<sub>*m**a**x*</sub> is the maximum potential rate of electron
transport (*μ*mol m<sub>−2</sub> s<sup>−1</sup>),
*I*<sub>*P**S**I**I*</sub> is the is the light utilized in electron
transport by photosystem II (*μ*mol m<sub>−2</sub> s<sup>−1</sup>) and
*Θ*<sub>*P**S**I**I*</sub> is is curvature parameter.
*I*<sub>*P**S**I**I*</sub> is determined as

*I*<sub>*P**S**I**I*</sub> = 0.5*Φ*<sub>*P**S**I**I*</sub>(4.6*ϕ*)

where *ϕ* is the absorbed photosynthetically active radiation
(Wm<sup>−2</sup>) for either sunlit or shaded leaves
(*a**b**s*<sub>*s**u**n*</sub> and *a**b**s*<sub>*s**h**a*</sub>). *ϕ*
is converted to photosynthetic photon flux assuming 4.6 *μ*mol photons
per joule. Parameter values are *Φ*<sub>*P**S**I**I*</sub> = 0.7 for C3
and *Φ*<sub>*P**S**I**I*</sub> = 0.85 for C4 plants.

The export limited rate of carboxylation for C3 plants and the PEP
carboxylase limited rate of carboxylation for C4 plants
*w*<sub>*e*</sub> (also in *μ*mol CO<sub>2</sub> m<sup>−2</sup>
s<sup>−1</sup>) is

$$\\begin{aligned}
w\_e=  \\left\\{ \\begin{array}{ll}
3 T\_{p,0} & \\textrm{for $C\_3$ plants}\\\\
&\\\\
k\_{p} \\frac{c\_i}{P\_{atm}}& \\textrm{for $C\_4$ plants}.\\\\
\\end{array} \\right.
\\end{aligned}$$

*T*<sub>*p*</sub> is the triose-phosphate limited rate of
photosynthesis, which is equal to 0.167*V*<sub>*c*, *m**a**x*0</sub>.
*k*<sub>*p*</sub> is the initial slope of C4 CO<sub>2</sub> response
curve. The Michaelis-Menten constants *K*<sub>*c*</sub> and
*K*<sub>*o*</sub> are modeled as follows,

$$K\_{c} = K\_{c,25}(a\_{kc})^{\\frac{T\_v-25}{10}},$$

$$K\_{o} = K\_{o,25}(a\_{ko})^{\\frac{T\_v-25}{10}},$$

where *K*<sub>*c*, 25</sub> = 30.0 and *K*<sub>*o*, 25</sub> = 30000.0
are values (Pa) at 25 <sup>*o*</sup>C, and *a*<sub>*k**c*</sub> = 2.1
and *a*<sub>*k**o*</sub> =1.2 are the relative changes in
*K*<sub>*c*, 25</sub> and *K*<sub>*o*, 25</sub> respectively, for a
10<sup>*o*</sup>C change in temperature. The CO<sub>2</sub> compensation
point *Γ*<sub>\*</sub> (Pa) is

$$\\Gamma\_\* = \\frac{1}{2} \\frac{K\_c}{K\_o}0.21o\_i$$

where the term 0.21 represents the ratio of maximum rates of oxygenation
to carboxylation, which is virtually constant with temperature
`Farquhar, 1980<Farquharetal1980>`.

### Resolution of the photosynthesis theory within the FATES canopy structure.

The photosynthesis scheme is modified from the CLM4.5 model to give
estimates of photosynthesis, respiration and stomatal conductance for a
three dimenstional matrix indexed by canopy level (*C*<sub>*l*</sub>),
plant functional type (*f**t*) and leaf layer (*z*). We conduct the
photosynthesis calculations at each layer for both sunlit and shaded
leaves. Thus, the model also generates estimates of
*w*<sub>*c*</sub>, *w*<sub>*j*</sub> and *w*<sub>*e*</sub> indexed in
the same three dimensional matrix. In this implementation, some
properties (stomatal conductance parameters, top-of-canopy
photosynthetic capacity) vary with plant functional type, and some vary
with both functional type and canopy depth (absorbed photosynthetically
active radiation, nitrogen-based variation in photosynthetic
properties). The remaining drivers of photosynthesis
(*P*<sub>*a**t**m*</sub>, *K*<sub>*c*</sub>, *o*<sub>*i*</sub>,
*K*<sub>*o*</sub>, temperature, atmospheric CO<sub>2</sub>) remain the
same throughout the canopy. The rate of gross photosynthesis
(*g**p**p*<sub>*c**l*, *f**t*, *z*</sub>)is the smoothed minimum of the
three potentially limiting processes (carboxylation, electron transport,
export limitation), but calculated independently for each leaf layer:

$$\\textrm{gpp}\_{cl,ft,z} = \\rm{min}(w\_{c,cl,ft,z},w\_{j,cl,ft,z},w\_{e,cl,ft,z}).$$

For *w*<sub>*c*, *c**l*, *f**t*, *z*</sub>,, we use

$$\\begin{aligned}
w\_{c,cl,ft,z}=  \\left\\{ \\begin{array}{ll}
\\frac{V\_{c,max,cl,ft,z}(c\_{i,cl,ft,z}- \\Gamma\_\*)}{c\_{i,cl,ft,z}+K\_c(1+o\_i/K\_o)} & \\textrm{for $C\_3$ plants}\\\\
&\\\\
V\_{c,max,cl,ft,z}& \\textrm{for $C\_4$ plants}\\\\
\\end{array} \\right.
c\_{i,cl,ft,z}-\\Gamma\_\*\\ge 0
\\end{aligned}$$

where *V*<sub>*c*, *m**a**x*</sub> now varies with PFT, canopy depth and
layer (see below). Internal leaf *C**O*<sub>2</sub>
(*c*<sub>*i*, *c**l*, *f**t*, *z*</sub>) is tracked seperately for each
leaf layer. For the light limited rate *w*<sub>*j*</sub>, we use

$$\\begin{aligned}
w\_j=  \\left\\{ \\begin{array}{ll}
\\frac{J(c\_i - \\Gamma\_\*)4.6\\phi\\alpha}{4ci+8\\Gamma\_\*} & \\textrm{for C$\_3$ plants}\\\\
&\\\\
4.6\\phi\\alpha & \\textrm{for C$\_4$ plants}\\\\
\\end{array} \\right.
\\end{aligned}$$

where *J* is calculated as above but based on the absorbed
photosynthetically active radiation( *ϕ*<sub>*c**l*, *f**t*, *z*</sub>)
for either sunlit or shaded leaves in Wm<sup>−2</sup>. Specifically,

$$\\begin{aligned}
\\phi\_{cl,ft,z}=  \\left\\{ \\begin{array}{ll}
abs\_{sun,cl,ft,z}& \\textrm{for sunlit leaves}\\\\
&\\\\
abs\_{sha,cl,ft,z}& \\textrm{for shaded leaves}\\\\
\\end{array} \\right.
\\end{aligned}$$

The export limited rate of carboxylation for C3 plants and the PEP
carboxylase limited rate of carboxylation for C4 plants
*w*<sub>*c*</sub> (also in *μ*mol CO<sub>2</sub> m<sup>−2</sup>
s<sup>−1</sup>) is calculated in a similar fashion,

$$\\begin{aligned}
w\_{e,cl,ft,z}=  \\left\\{ \\begin{array}{ll}
0.5V\_{c,max,cl,ft,z} & \\textrm{for $C\_3$ plants}\\\\
&\\\\
4000 V\_{c,max,cl,ft,z} \\frac{c\_{i,cl,ft,z}}{P\_{atm}}& \\textrm{for $C\_4$ plants}.\\\\
\\end{array} \\right.
\\end{aligned}$$

### Variation in plant physiology with canopy depth

Both *V*<sub>*c*, *m**a**x*</sub> and *J*<sub>*m**a**x*</sub> vary with
vertical depth in the canopy on account of the well-documented reduction
in canopy nitrogen through the leaf profile, see
`Bonan et al. 2012<bonanetal2012>` for details). Thus, both
*V*<sub>*c*, *m**a**x*</sub> and *J*<sub>*m**a**x*</sub> are indexed by
by *C*<sub>*l*</sub>, *f**t* and *z* according to the nitrogen decay
coefficient *K*<sub>*n*</sub> and the amount of vegetation area shading
each leaf layer *V*<sub>*a**b**o**v**e*</sub>,

$$\\begin{aligned}
\\begin{array}{ll}
V\_{c,max,cl,ft,z} & = V\_{c,max0,ft} e^{-K\_{n,ft}V\_{above,cl,ft,z}},\\\\
J\_{max,cl,ft,z} & = J\_{max0,ft} e^{-K\_{n,ft}V\_{above,cl,ft,z}},\\\\
\\end{array}
\\end{aligned}$$

where *V*<sub>*c*, *m**a**x*, 0</sub> and *J*<sub>*m**a**x*, 0</sub> are
the top-of-canopy photosynthetic rates. *V*<sub>*a**b**o**v**e*</sub> is
the sum of exposed leaf area index (elai<sub>*c**l*, *f**t*, *z*</sub>)
and the exposed stem area index (esai<sub>*c**l*, *f**t*, *z*</sub>)(
m<sup>2</sup> m<sup>−2</sup> ). Namely,

*V*<sub>*c**l*, *f**t*, *z*</sub> = elai<sub>*c**l*, *f**t*, *z*</sub> + esai<sub>*c**l*, *f**t*, *z*</sub>.

The vegetation index shading a particular leaf layer in the top canopy
layer is equal to

$$\\begin{array}{ll}
V\_{above,cl,ft,z}= \\sum\_{1}^{z} V\_{cl,ft,z} & \\textrm{for $cl= 1$. }
\\end{array}$$

For lower canopy layers, the weighted average vegetation index of the
canopy layer above (*V*<sub>*c**a**n**o**p**y*</sub>) is added to this
within-canopy shading. Thus,

$$\\begin{aligned}
\\begin{array}{ll}
V\_{above,cl,ft,z}=  \\sum\_{1}^{z}  V\_{cl,ft,z} + V\_{canopy,cl-1} & \\textrm{for $cl &gt;1$, }\\\\
\\end{array}
\\end{aligned}$$

where *V*<sub>*c**a**n**o**p**y*</sub> is calculated as

$$V\_{canopy,cl} =  \\sum\_{ft=1}^{\\emph{npft}} {\\sum\_{z=1}^{nz(ft)} (V\_{cl,ft,z} \\cdot  \\it{pft}\_{wt,cl,ft,1}).}$$

*K*<sub>*n*</sub> is the coefficient of nitrogen decay with canopy
depth. The value of this parameter is taken from the work of
`Lloyd et al. 2010<Lloydetal2010>` who determined, from 204 vertical
profiles of leaf traits, that the decay rate of N through canopies of
tropical rainforests was a function of the *V*<sub>*c**m**a**x*</sub> at
the top of the canopy. They obtain the following term to predict
*K*<sub>*n*</sub>,

*K*<sub>*n*, *f**t*</sub> = *e*<sup>0.00963*V*<sub>*c*, *m**a**x*0, *f**t*</sub> − 2.43</sup>,

where *V*<sub>*c**m**a**x*</sub> is again in *μ*mol CO<sub>2</sub>
m<sup>−2</sup> s<sup>−1</sup>.

### Water Stress on gas exchange

The top of canopy leaf photosynthetic capacity,
*V*<sub>*c*, *m**a**x*0</sub>, is also adjusted for the availability of
water to plants as

*V*<sub>*c*, *m**a**x*0, 25</sub> = *V*<sub>*c*, *m**a**x*0, 25</sub>*β*<sub>*s**w*</sub>,

where the adjusting factor *β*<sub>*s**w*</sub> ranges from one when the
soil is wet to zero when the soil is dry. It depends on the soil water
potential of each soil layer, the root distribution of the plant
functional type, and a plant-dependent response to soil water stress,

$$\\beta\_{sw} = \\sum\_{j=1}^{nj}w\_{j}r\_{j},$$

where *w*<sub>*j*</sub> is a plant wilting factor for layer *j* and
*r*<sub>*j*</sub> is the fraction of roots in layer *j*.The plant
wilting factor *w*<sub>*j*</sub> is

$$\\begin{aligned}
w\_{j}=  \\left\\{ \\begin{array}{ll}
\\frac{\\psi\_c-\\psi\_{j}}{\\psi\_c - \\psi\_o} (\\frac{\\theta\_{sat,j} - \\theta\_{ice,j}}{\\theta\_{sat,j}})& \\textrm{for $T\_i &gt;$-2C}\\\\
&\\\\
0 & \\textrm{for $T\_{j} \\ge$-2C}\\\\
\\end{array} \\right.
\\end{aligned}$$

where *ψ*<sub>*i*</sub> is the soil water matric potential (mm) and
*ψ*<sub>*c*</sub> and *ψ*<sub>*o*</sub> are the soil water potential
(mm) when stomata are fully closed or fully open, respectively. The term
in brackets scales *w*<sub>*i*</sub> the ratio of the effective porosity
(after accounting for the ice fraction) relative to the total porosity.
*w*<sub>*i*</sub> = 0 when the temperature of the soil layer
(*T*<sub>*i*</sub> ) is below some threshold (-2<sup>*o*</sup>C) or when
there is no liquid water in the soil layer
(*θ*<sub>*l**i**q*, *i*</sub> ≤ 0). For more details on the calculation
of soil matric potential, see the CLM4.5 technical note.

#### Variation of water stress and water uptake within tiles

The remaining drivers of the photosynthesis model remain constant
(atmospheric CO<sub>2</sub> and O<sup>2</sup> and canopy temperature)
throughout the canopy, except for the water stress index
*β*<sub>*s**w*</sub>. *β*<sub>*s**w*</sub> must be indexed by *f**t*,
because plants of differing functional types have the capacity to have
varying root depth, and thus access different soil moisture profile and
experience differing stress functions. Thus, the water stress function
applied to gas exchange calculation is now calculated as

$$\\beta\_{sw,ft} = \\sum\_{j=1}^{nj}w\_{j,ft} r\_{j,ft},$$

where *w*<sub>*j*</sub> is the water stress at each soil layer *j* and
*r*<sub>*j*, *f**t*</sub> is the root fraction of each PFT’s root mass
in layer *j*. Note that this alteration of the *β*<sub>*s**w*</sub>
parameter also necessitates recalculation of the vertical water
extraction profiles. In the original model, the fraction of extraction
from each layer (*r*<sub>*e*, *j*, *p**a**t**c**h*</sub>) is the product
of a single root distribution, because each patch only has one plant
functional type. In FATES, we need to calculate a new weighted patch
effective rooting depth profile *r*<sub>*e*, *j*, *p**a**t**c**h*</sub>
as the weighted average of the functional-type level stress functions
and their relative contributions to canopy conductance. Thus for each
layer *j*, the extraction fraction is summed over all PFTs as

$$r\_{e,j,patch} =  \\sum\_{ft=1}^{ft=npft} \\frac{w\_{j,ft}}{\\sum\_{j=1}^{=nj} w\_{j,ft} }\\frac{G\_{s,ft}}{G\_{s,canopy}},$$

where *n**j* is the number of soil layers,
*G*<sub>*s*, *c**a**n**o**p**y*</sub>is the total canopy (see section 9
for details) and *G*<sub>*s*, *f**t*</sub> is the canopy conductance for
plant functional type *f**t*,

*G*<sub>*s*, *f**t*</sub> = ∑<sub>1</sub>*w*<sub>*n**c**o**h*, *f**t*</sub>*g**s*<sub>*c**a**n*, *c**o**h*</sub>*n*<sub>*c**o**h*</sub>.

### Aggregation of assimilated carbon into cohorts

The derivation of photosynthetic rates per leaf layer, as above, give us
the estimated rate of assimilation for a unit area of leaf at a given
point in the canopy in *μ*mol CO<sub>2</sub> m<sup>−2</sup>
s<sub>−1</sub>. To allow the integration of these rates into fluxes per
individual tree, or cohort of trees (gCO<sub>2</sub> tree<sup>−1</sup>
s<sup>−1</sup>), they must be multiplied by the amount of leaf area
placed in each layer by each cohort. Each cohort is described by a
single functional type, *f**t* and canopy layer *C*<sub>*l*</sub> flag,
so the problem is constrained to integrating these fluxes through the
vertical profile (*z*).

We fist make a weighted average of photosynthesis rates from sun
(gpp<sub>*s**u**n*</sub>, *μ*mol CO<sub>2</sub> m<sup>−2</sup>
s<sup>−1</sup>) and shade leaves ( gpp<sub>*s**h**a**d**e*</sub>, *μ*mol
CO<sub>2</sub> m<sup>−2</sup> s<sup>−1</sup>) as

gpp<sub>*c**l*, *f**t*, *z*</sub> = gpp<sub>*s**u**n*, *c**l*, *f**t*, *z*</sub>*f*<sub>*s**u**n*, *c**l*, *f**t*, *z*</sub> + gpp<sub>*s**h**a*, *c**l*, *f**t*, *z*</sub>(1 − *f*<sub>*s**u**n*, *c**l*, *f**t*, *z*</sub>).

The assimilation per leaf layer is then accumulated across all the leaf
layers in a given cohort (*coh*) to give the cohort-specific gross
primary productivity (*G**P**P*<sub>*c**o**h*</sub>),

$$\\textit{GPP}\_{coh} = 12\\times 10^{-9}\\sum\_{z=1}^{nz(coh)}gpp\_{cl,ft,z} A\_{crown,coh} \\textrm{elai}\_{cl,ft,z}$$

The elai<sub>*l*, *c**l*, *f**t*, *z*</sub> is the exposed leaf area
which is present in each leaf layer in m<sup>2</sup> m<sup>−2</sup>.
(For all the leaf layers that are completely occupied by a cohort, this
is the same as the leaf fraction of *δ*<sub>*v**a**i*</sub>). The fluxes
are converted from *μ*mol into mol and then multiplied by 12 (the
molecular weight of carbon) to give units for GPP<sub>*c**o**h*</sub> of
KgC cohort<sup>−1</sup> s<sup>−1</sup>. These are integrated for each
timestep to give KgC cohort<sup>−1</sup> day<sup>−1</sup>

\captionof{table}{Parameters needed for photosynthesis model.}

| Parameter Symbol | Parameter Name | Units | indexed by |
|------------------|------------------|------------------|------------------|
| *V*<sub>*c*, *m**a**x*0</sub> | Maximum carboxylation capacity | *μ* mol CO <sub>2</sub> m <sup>−2</sup> s <sup>−1</sup> | *ft* |
| *r*<sub>*b*</sub> | Base Rate of Respiration | gC gN<sup>−1</sup>*s*<sup>−1</sup>) |  |
| *q*<sub>10</sub> | Temp. Response of stem and root respiration |  |  |
| *R*<sub>*c**n*, *l**e**a**f*, *f**t*</sub> | CN ratio of leaf matter | gC/gN | *ft* |
| *R*<sub>*c**n*, *r**o**o**t*, *f**t*</sub> | CN ratio of root matter | gC/gN | *ft* |
| *f*<sub>*g**r*</sub> | Growth Respiration Fraction | none |  |
| *ψ*<sub>*c*</sub> | Water content when stomata close | Pa | *ft* |
| *ψ*<sub>*o*</sub> | Water content above which stomata are open | Pa | *ft* |

\bigskip 

## Plant respiration

Plant respiration per individual
*R*<sub>*p**l**a**n**t*, *c**o**h*</sub> (KgC individual <sup>−1</sup>
s<sup>−1</sup>) is the sum of two terms, growth and maintenance
respiration *R*<sub>*g*, *c**o**h*</sub> and
*R*<sub>*m*, *c**o**h*</sub>

*R*<sub>*p**l**a**n**t*</sub> = *R*<sub>*g*, *c**o**h*</sub> + *R*<sub>*m*, *c**o**h*</sub>

Maintenance respiration is the sum of the respiration terms from four
different plant tissues, leaf,
*R*<sub>*m*, *l**e**a**f*, *c**o**h*</sub>, fine root
*R*<sub>*m*, *f**r**o**o**t*, *c**o**h*</sub>, coarse root
*R*<sub>*m*, *c**r**o**o**t*, *c**o**h*</sub>and stem
*R*<sub>*m*, *s**t**e**m*, *c**o**h*</sub>, all also in (KgC individual
<sup>−1</sup> s<sup>−1</sup>) .

*R*<sub>*m*, *c**o**h*</sub> = *R*<sub>*m*, *l**e**a**f*, *c**o**h*</sub> + *R*<sub>*m*, *f**r**o**o**t*, *c**o**h*</sub> + *R*<sub>*m*, *c**r**o**o**t*, *c**o**h*</sub> + *R*<sub>*m*, *s**t**e**m*, *c**o**h*</sub>

### Leaf maintenance respiration - Atkin et al. 2017

The `Atkin et al. 2017<atkin2017>` leaf maintenance respiration (Rdark)
model includes temperature acclimation. We first determine the
top-of-canopy Rdark rate.

*r*<sub>*t**r**e**f*</sub> = *m**a**x*(0, *r*<sub>0</sub> + *r*<sub>1</sub> \* *l**n**c*<sub>*t**o**p*</sub> + *r*<sub>2</sub> \* *m**a**x*(0, *t**g**r**o**w**t**h*))

where *r*<sub>0</sub> is the PFT-dependent base Rdark rate,
*r*<sub>1</sub> is a parameter that determines the effects of nitrogen
availability on Rdark, *r*<sub>2</sub> is a parameter that determines
the effects of temperature on Rdark, and *t**g**r**o**w**t**h* is the
lagged vegetation temperature averaged over the acclimation timescale.
We use *r*<sub>1</sub> = 0.2061 and *r*<sub>2</sub> = -0.0402 following
`Atkin et al. 2017<atkin2017>`.

At very high temperatures, and with low values of *r*<sub>0</sub>, the
whole term can become negative, and we therefore cap it at 0 to prevent
negative Rdark.

We scale vertically through the canopy based on nitrogen availability
following `Lloyd et al. 2010<Lloydetal2010>`, in the same way that
*V*<sub>*c*, *m**a**x*</sub> values are scaled uisng
*V*<sub>*a**b**o**v**e*</sub>, described above.

*r*<sub>*t**r**e**f*</sub> = *n**s**c**a**l**e**r* \* *r*<sub>*t**r**e**f*</sub>

where

*n**s**c**a**l**e**r* = *e**x**p*(−*k**n* \* *c**u**m**u**l**a**t**i**v**e**l**a**i*)

and

*k**n* = *e**x**p*(0.00963 \* *v**c**m**a**x*25*t**o**p* − 2.43)

where *v**c**m**a**x*25*t**o**p* is PFT-dependent maximum carboxylation
rate of rubisco at the top of the canopy at 25 degrees C, and
*c**u**m**u**l**a**t**i**v**e**l**a**i* is the cumulative LAI, top down,
to the leaf layer of interest.

We then adjust Rdark for current vegetation temperature
(*v**e**g*<sub>*t**e**m**p*</sub>).

*R*<sub>*m*, *l**e**a**f*, *c**o**h*</sub> = *r*<sub>*t**r**e**f*</sub> \* *e**x**p*(*b* \* (*v**e**g*<sub>*t**e**m**p*</sub> − *T**r**e**f**C*) + *c* \* (*v**e**g*<sub>*t**e**m**p*</sub><sup>2</sup> − *T**r**e**f**C*<sup>2</sup>))

where *T**r**e**f**C* is the reference temperature of 25 degrees C, and
*b* and *c* are parameters from `Heskel et al. 2016<Heskel2016>`, set as
*b* = 0.1012 and *c* = -0.0005.

### Leaf maintenance respiration - Ryan 1991

To calculate canopy leaf respiration following
`Ryan et al. 1991<ryan1991>`, we first determine the top-of-canopy leaf
respiration rate (*r*<sub>*m*, *l**e**a**f*, *f**t*, 0</sub>, gC
s<sup>−1</sup> m<sup>−2</sup>) is calculated from a base rate of
respiration per unit leaf nitrogen derived from
`Ryan et al. 1991<ryan1991>`. The base rate for leaf respiration
(*r*<sub>*b*</sub>) is 2.525 gC/gN s<sup>−1</sup>,

*r*<sub>*m*, *l**e**a**f*, *f**t*, 0</sub> = *r*<sub>*b*</sub>*N*<sub>*a*, *f**t*</sub>(1.5<sup>(25 − 20)/10</sup>)

where *r*<sub>*b*</sub> is the base rate of metabolism (2.525 x
10<sup>6</sup> gC/gN s<sup>−1</sup>. This base rate is adjusted assuming
a Q<sub>10</sub> of 1.5 to scale from the baseline of 20C to the CLM
default base rate temperature of 25C. For use in the calculations of net
photosynthesis and stomatal conductance, leaf respiration is converted
from gC s<sup>−1</sup> m<sup>−2</sup>, into *μ*mol CO<sub>2</sub>
m<sup>−2</sup> s<sup>−1</sup> (/12 ⋅ 10<sup>−6</sup>).

This top-of-canopy flux is scaled to account for variation in
*N*<sub>*a*</sub> through the vertical canopy, in the same manner as the
*V*<sub>*c*, *m**a**x*</sub> values are scaled using
*V*<sub>*a**b**o**v**e*</sub>.

*r*<sub>*l**e**a**f*, *c**l*, *f**t*, *z*</sub> = *r*<sub>*m*, *l**e**a**f*, *f**t*, 0</sub>*e*<sup>−*K*<sub>*n*, *f**t*</sub>*V*<sub>*a**b**o**v**e*, *c**l*, *f**t*, *z*</sub></sup>*β*<sub>*f**t*</sub>*f*(*t*)

Leaf respiration is also adjusted such that it is reduced by drought
stress, *β*<sub>*f**t*</sub>, and canopy temperature,
*f*(*t*<sub>*v**e**g*</sub>). For details of the temperature functions
affecting leaf respiration see the CLM4 technical note, Section 8,
Equations 8.13 and 8.14. The adjusted leaf level fluxes are scaled to
individual-level (gC individual <sup>−1</sup> s<sup>−1</sup>) in the
same fashion as the $\\rm{GPP}\_{coh}$ calculations

$$\\rm{R}\_{m,leaf,coh} = 12\\times 10^{-9}\\sum\_{z=1}^{nz(coh)}r\_{leaf,cl,ft,z} A\_{crown} \\textrm{elai}\_{cl,ft,z}$$

The stem and the coarse-root respiration terms are derived using the
same base rate of respiration per unit of tissue Nitrogen.

$$R\_{m,croot,coh} =  10^{-3}r\_b t\_c \\beta\_{ft} N\_{\\rm{livecroot,coh}}$$

$$R\_{m,stem,coh} =   10^{-3}r\_b t\_c \\beta\_{ft} N\_{\\rm{stem,coh}}$$

Here, *t*<sub>*c*</sub> is a temperature relationship based on a
*q*<sub>10</sub> value of 1.5, where *t*<sub>*v*</sub> is the vegetation
temperature. We use a base rate of 20 here as, again, this is the
baseline temperature used by `Ryan et al. 1991<ryan1991>`. The
10<sup>−3</sup> converts from gC invididual<sup>−1</sup> s<sup>−1</sup>
to KgC invididual<sup>−1</sup> s<sup>−1</sup>

*t*<sub>*c*</sub> = *q*<sub>10</sub><sup>(*t*<sub>*v*</sub> − 20)/10</sup>

The tissue N contents for live sapwood are derived from the leaf CN
ratios, and for fine roots from the root CN ratio as:

$$N\_{\\rm{stem,coh}}  = \\frac{B\_{\\rm{sapwood,coh}}}{ R\_{cn,leaf,ft}}$$

and

$$N\_{\\rm{livecroot,coh}}  = \\frac{ B\_{\\rm{root,coh}}w\_{frac,ft}}{R\_{cn,root,ft}}$$

where $B\_{\\rm{sapwood,coh}}$ and $B\_{\\rm{root,coh}}$ are the biomass
pools of sapwood and live root biomass respectively (KgC individual) and
*w*<sub>*f**r**a**c*, *f**t*</sub> is the fraction of coarse root tissue
in the root pool (0.5 for woody plants, 0.0 for grasses and crops). We
assume here that stem CN ratio is the same as the leaf C:N ratio, for
simplicity. The final maintenance respiration term is derived from the
fine root respiration, which accounts for gradients of temperature in
the soil profile and thus calculated for each soil layer *j* as follows:

$$R\_{m,froot,j } = \\frac{(1 - w\_{frac,ft})B\_{\\rm{root,coh}}b\_r\\beta\_{ft}}{10^3R\_{cn,leaf,ft}}   \\sum\_{j=1}^{nj}t\_{c,soi,j} r\_{i,ft,j}$$

*t*<sub>*c*, *s**o**i*</sub> is a function of soil temperature in layer
*j* that has the same form as that for stem respiration, but uses
vertically resolved soil temperature instead of canopy temperature. In
the CLM4.5, only coarse and not fine root respriation varies as a
function of soil depth, and we maintain this assumption here, although
it may be altered in later versions.

The source of maintenance respiration is the plant's carbon storage
pool, which is updated daily. For plants that are in long-term negative
carbon balance, FATES assumes a tradoff between reduced maintenance
respiration expenditures and increased carbon-starvation mortality (see
section 'Plant Mortality'). This reduction of maintenance respiration
during carbon starvation is consistent with observations of trees under
acute carbon stress (Sevanto et al., 2014). Because the physiologic
basis and form of this process is poorly constrained, we use heuristic
functions here to define these processes. First, we define a target
carbon storage pool (*C̀*<sub>*s**t**o**r**e*, *c**o**h*</sub>):

*C̀*<sub>*s**t**o**r**e*, *c**o**h*</sub> = *r*<sub>*s**t**o**r**e*</sub>*C̀*<sub>*l**e**a**f*, *c**o**h*</sub>

where *r*<sub>*s**t**o**r**e*</sub> is a pft-specific parameter that
linearly relates the target storage pool to the target leaf biomass
*C̀*<sub>*l**e**a**f*, *c**o**h*</sub>. If a given plant is unable to
achieve its target carbon storage because of having a negative NPP at
any given time, then its actual storage pool
*C*<sub>*s**t**o**r**e*, *c**o**h*</sub> will drop below the target
storage pool *C̀*<sub>*s**t**o**r**e*, *c**o**h*</sub>. Then FATES sets
the fractional rate of maintenance respiration (R) on the ratio of
*C*<sub>*s**t**o**r**e*, *c**o**h*</sub> to
*C̀*<sub>*l**e**a**f*, *c**o**h*</sub>:

$$\\begin{aligned}
R = \\left\\{ \\begin{array}{ll}
(1-q^{(C\_{store,coh}/\\grave{C}\_{leaf,coh})})/(1-q)& C\_{store,coh}&lt;\\grave{C}\_{leaf,coh}\\\\
&\\\\
1& C\_{store,coh} &gt;= \\grave{C}\_{leaf,coh}\\\\
\\end{array} \\right.
\\end{aligned}$$

where *q* is a parameter that governs the curvature of the respiration
reduction function. This parameter is specific to a given PFT.

The growth respiration, *R*<sub>*g*, *c**o**h*</sub> is a fixed fraction
*f*<sub>*g**r*</sub> of the carbon remaining after maintenance
respiration has occurred.

$$R\_{g,coh}=\\textrm{max}(0,GPP\_{g,coh} - \\it R\\rm\_{m,coh})f\_{gr}$$

\captionof{table}{Parameters needed for plant respiration model.  }

| Parameter Symbol | Parameter Name | Units | indexed by |
|------------------|------------------|------------------|------------------|
| −*K*<sub>*n*, *f**t*</sub> | Rate of reduction of N through the canopy | none |  |
| *r*<sub>*b*</sub> | Base Rate of Respiration | gC gN<sup>−1</sup>*s*<sup>−1</sup>) |  |
| *q*<sub>10</sub> | Temp. Response of stem and root respiration |  |  |
| *R*<sub>*c**n*, *l**e**a**f*, *f**t*</sub> | CN ratio of leaf matter | gC/gN | *ft* |
| *R*<sub>*c**n*, *r**o**o**t*, *f**t*</sub> | CN ratio of root matter | gC/gN | *ft* |
| *f*<sub>*g**r*</sub> | Growth Respiration Fraction | none | *ft* |
| *q* | Low-Storage Maintenance Respiration Reduction Param. | none | *ft* |

\bigskip 

## Stomatal Conductance

### Fundamental stomatal conductance theory

Within FATES, leaf-level stomatal conductance is representated by two
main approaches. The first calculates stomatal conductance
(1/resistance) using the Ball-Berry model as implemented in CLM4.5
(<http://www.cesm.ucar.edu/models/cesm1.2/clm/CLM45_Tech_Note.pdf>) and
described by `Collatz et al. (1991)<Collatzetal1991>` and
`Sellers et al. 1996<sellers1996>`. The model relates stomatal
conductance (i.e., the inverse of resistance) to net leaf
photosynthesis, scaled by the relative humidity at the leaf surfaceand
the CO<sub>2</sub> concentration at the leaf surface. The primary
difference between the CLM implementation and that used by
`Collatz et al. (1991)<Collatzetal1991>` and
`Sellers et al. (1996)<sellers1996>` is that they used net
photosynthesis (i.e., leaf photosynthesis minus leaf respiration)
instead of gross photosynthesis. As implemented here, stomatal
conductance equals the minimum conductance (*b*) when gross
photosynthesis (*A*) is zero. Leaf stomatal conductance is

$$\\frac{1}{r\_{s}} = m\_{ft} \\frac{A}{c\_s}\\frac{e\_s}{e\_i}P\_{atm}+b\_{ft} \\beta\_{sw}$$

where *r*<sub>*s*</sub> is leaf stomatal resistance (s m<sup>2</sup>
leaf area *μ*mol *H*<sub>2</sub>*O*<sup>−1</sup>), *b*<sub>*f**t*</sub>
in units of *μ*mol *H*<sub>2</sub>*O* m<sup>−2</sup> leaf area
s<sup>−1</sup> is a plant functional type dependent parameter equivalent
to *g*<sub>0</sub> in the Ball-Berry model literature. This parameter is
also scaled by the water stress index *β*<sub>*s**w*</sub>. Similarly,
*m*<sub>*f**t*</sub> is the slope of the relationship (i.e. stomatal
slope, or the *g*<sub>1</sub> term in the stomatal literature) between
stomatal conductance and the stomatal index, comprised of the leaf
assimilation rate, *A* (*μ*mol CO<sub>2</sub> m<sup>−2</sup> leaf area
s<sup>−1</sup>), *c*<sub>*s*</sub> is the CO<sub>2</sub> partial
pressure at the leaf surface (Pa), *e*<sub>*s*</sub> is the vapor
pressure at the leaf surface (Pa), *e*<sub>*i*</sub> is the saturation
vapor pressure (Pa) inside the leaf at the vegetation temperature
*T*<sub>*v*</sub> (K), and *b*<sub>*f**t*</sub> is the conductace
(*μ*mol*H*<sub>2</sub>*O* m<sup>−2</sup> leaf area s<sup>−1</sup>) when
*A* = 0.

The second (default) representation of stomatal conductance in FATES
follows the Unified Stomatal Optimization (USO) theory, otherwise known
as the Medlyn model of stomatal conductance
(`Medlyn et al. 2011<Medlynetal2011>`). The Medlyn model calculates
stomatal conductance (i.e., the inverse of resistance) based on net leaf
photosynthesis, the vapor pressure deficit, and the CO2 concentration at
the leaf surface. Leaf stomatal resistance is calculated as:

$$\\frac{1}{r\_{s}} = g\_{s} = b\_{ft} \\beta\_{sw}+1.6(1+\\frac{m\_{ft}}{\\sqrt{D\_{s}}})\\frac{A\_{n}}{C\_{s}/{P\_{atm}}}$$

\captionof{table}{Variables use in the Medlyn equation}

| Parameter Symbol | Parameter Name | Units | indexed by |
|-----------------|----------------------|---------------------|------------|
| *r*<sub>*s*</sub> | Leaf stomatal resistance | s m<sup>2</sup> leaf area *μ*mol *H*<sub>2</sub>*O*<sup>−1</sup> |  |
| *g*<sub>*s*</sub> | Leaf stomatal conductance | *μ*mol *H*<sub>2</sub>*O* m<sup>2</sup> leaf area s<sup>−1</sup> |  |
| *b*<sub>*f**t*</sub> | Minimum stomatal conductance or the cuticular conductance | *μ*mol *H*<sub>2</sub>*O* m<sup>2</sup> leaf area s<sup>−1</sup> | *ft* |
| *β*<sub>*s**w*</sub> | Soil water stress factor | none |  |
| *D*<sub>*s*</sub> | Vapor pressure deficit at the leaf surface | kPa |  |
| *m*<sub>*f**t*</sub> | Stomatal slope | kPa<sup>0.5</sup> | *ft* |
| *A*<sub>*n*</sub> | Leaf net photosynthesis | *μ*mol *C**O*<sub>2</sub> m<sup>−2</sup> leaf area s<sup>−1</sup> |  |
| *C*<sub>*s*</sub> | *C**O*<sub>2</sub> partial pressure at the leaf surface | Pa |  |
| *P*<sub>*a**t**m*</sub> | Atmospheric pressure | Pa |  |

In both models leaf resistance is converted from units of s
m<sup>2</sup>*μ*mol*H*<sub>2</sub>*O*<sup>−1</sup> to s m<sup>−1</sup>
as: 1 s m<sup>−1</sup> =
1 × 10<sup>−9</sup>R$\_{\\rm{gas}} \\theta\_{\\rm{atm}}P\_{\\rm{atm}}$
(*μ*mol<sup>−1</sup> m<sup>2</sup> s), where R<sub>*g**a**s*</sub> is
the universal gas constant (J K<sup>−1</sup> kmol<sup>−1</sup>) and
*θ*<sub>*a**t**m*</sub> is the atmospheric potential temperature (K).

Both *b*<sub>*f**t*</sub> and *m*<sub>*f**t*</sub> are PFT-specific
parameters. The default values for the Ball-Berry and Medlyn stomatal
conductance model representations are provide below:

\captionof{table}{Variables use in the Medlyn equation}

| PFT Name | Ball-Berry *m*<sub>*f**t*</sub> (unitless) | Medlyn *m*<sub>*f**t*</sub> (kPa<sup>0.5</sup>) |
|-------------------|------------------------|----------------------------|
| Broadleaf evergreen tropical tree | 8 | 4.1 |
| Needleleaf evergreen extratropical tree | 8 | 2.3 |
| Needleleaf colddecid extratropical tree | 8 | 2.3 |
| Broadleaf evergreen extratropical tree | 8 | 4.1 |
| Broadleaf hydrodecid tropical tree | 8 | 4.4 |
| Broadleaf colddecid extratropical tree | 8 | 4.4 |
| Broadleaf evergreen extratropical shrub | 8 | 4.7 |
| Broadleaf hydrodecid extratropical shrub | 8 | 4.7 |
| Broadleaf colddecid extratropical shrub | 8 | 4.7 |
| Arctic *C*<sub>3</sub> grass | 8 | 2.2 |
| Cool *C*<sub>3</sub> grass | 8 | 5.3 |
| *C*<sub>4</sub> grass | 8 | 1.6 |

For both the Ball-Berry and Medlyn stomatal models the default
*b*<sub>*f**t*</sub> is 1000 for all PFTs.

### Numerical implementation of the Medlyn stomatal conductance model

Photosynthesis is calculated assuming there is negligible capacity to
store *C**O*<sub>2</sub> and water vapor at the leaf surface so that：

$$A\_{n} = \\frac{c\_{a}-c\_{i}}{(1.4r\_{b}+1.6r\_{s})P\_{atm}} = \\frac{c\_{a}-c\_{s}}{1.4r\_{b}P\_{atm}} = \\frac{c\_{s}-c\_{i}}{1.6r\_{s}P\_{atm}}$$

The terms 1.4 and 1.6 are the ratios of diffusivity of
*C**O*<sub>2</sub> to *H*<sub>2</sub>*O* for the leaf boundary layer
resistance and stomatal resistance. The transpiration fluxes are related
as:

$$\\frac{e\_{a}-e\_{i}}{r\_{b}+r\_{s}} = \\frac{e\_{a}-e\_{s}}{r\_{b}} = \\frac{e\_{s}-e\_{i}}{r\_{s}}$$

$$e\_{a} = \\frac{P\_{atm}q\_{s}}{0.622}$$

| Parameter Symbol | Parameter Name | Units | indexed by |
|-----------------|-------------------------|-----------------|------------|
| *c*<sub>*a*</sub> | Atmospheric *C**O*<sub>2</sub> pressure | Pa |  |
| *c*<sub>*i*</sub> | Internal leaf *C**O*<sub>2</sub> partial pressure | Pa |  |
| *r*<sub>*b*</sub> | Leaf boundary layer resistance | s m<sup>2</sup> leaf area *μ*mol *H*<sub>2</sub>*O*<sup>−1</sup> |  |
| *e*<sub>*a*</sub> | Vapor pressure of air | Pa |  |
| *e*<sub>*i*</sub> | Saturation vapor pressure | Pa |  |
| *e*<sub>*s*</sub> | Vapor pressure at the leaf surface | Pa |  |
| *q*<sub>*s*</sub> | Specific humidity of canopy air | kg kg <sup>−1</sup> |  |

In the Medlyn model, an initial guess of *c*<sub>*i*</sub> is obtained
assuming the ratio between *c*<sub>*i*</sub> and *c*<sub>*a*</sub> (0.7
for *C*<sub>3</sub> plants and 0.4 for *C*<sub>4</sub> plants) to
calculate *A*<sub>*n*</sub> based on `Farquhar 1980<Farquharetal1980>`.
Solving for *c*<sub>*s*</sub>:

*c*<sub>*s*</sub> = *c*<sub>*a*</sub> − 1.4*r*<sub>*b*</sub>*P*<sub>*a**t**m*</sub>*A*<sub>*n*</sub>

*e*<sub>*s*</sub> can be represented as:

$$e\_{s} = \\frac{e\_{a}r\_{s}+e\_{i}r\_{b}}{r\_{b}+r\_{s}}$$

Where *e*<sub>*i*</sub> is a function of temperature

Substitution of *e*<sub>*s*</sub> following
*D*<sub>*s*</sub> = *e*<sub>*i*</sub> − *e*<sub>*s*</sub> gives an
expression for stomatal resistance (*r*<sub>*s*</sub>) as a function of
photosynthesis (*A*<sub>*n*</sub>), given here in terms of conductance
with $g\_{s} =
\\frac{1}{r\_{s}}$ and $g\_{b} =\\frac{1}{r\_{b}}$

(*g*<sub>*s*</sub>)<sup>2</sup> + *b**g*<sub>*s*</sub> + *c* = 0

where

$$b = -\[2(b\_{ft} \\times \\beta\_{sw}+d)+\\frac{(m\_{ft})^{2}d^{2}}{g\_{b}D\_{a}}\]$$

$$c = (b\_{ft} \\times \\beta\_{sw})^{2}+\[2g\_{0} \\times \\beta\_{sw}+d(1-\\frac{{m\_{ft}}^{2}}{D\_{a}})\]d$$

and

$$d = \\frac{1.6A\_{n}}{c\_{s}/P\_{atm}}$$

$$D\_{a} = \\frac{e\_{i}-e\_{a}}{1000}$$

Stomatal conductance is the larger of the two roots that satisfies the
quadratic equation. Values for *c*<sub>*i*</sub> are given by:

*c*<sub>*i*</sub> = *c*<sub>*a*</sub> − (1.4*r*<sub>*b*</sub> + 1.6*r*<sub>*s*</sub>)*P*<sub>*a**t**m*</sub>*A*<sub>*n*</sub>

The equations for
*c*<sub>*i*</sub>, *c*<sub>*s*</sub>, *r*<sub>*s*</sub>, and
*A*<sub>*n*</sub> are solved iteratively until *c*<sub>*i*</sub>
converges. Iteration will be exited if convergence criteria is met or if
at least five iterations are completed.

### Resolution of stomatal conductance theory in the FATES canopy structure

The stomatal conductance is calculated, as with photosynthesis, for each
canopy, PFT and leaf layer. The HLM code requires a single canopy
conductance estimate to be generated from the multi-layer multi-PFT
array. In previous iterations of the HLM, sun and shade-leaf specific
values have been reported and then averaged by their respective leaf
areas. In this version, the total canopy condutance
*G*<sub>*s*, *c**a**n**o**p**y*</sub>, is calculated as the sum of the
cohort-level conductance values.

$$G\_{s,canopy} =  \\sum{ \\frac{gs\_{can,coh} n\_{coh} }{A\_{patch}}}$$

Cohort conductance is the sum of the inverse of the leaf resistances at
each canopy layer (*r*<sub>*s*, *z*</sub> ) multipled by the area of
each cohort.

$$gs\_{can,coh} =\\sum\_{z=1}^{z=nv,coh}{\\frac{ A\_{crown,coh}}{r\_{s,cl,ft,z}+r\_{b}}}$$

\bigskip 

## Control of Leaf Area Index

The leaf area *A*<sub>*l**e**a**f*</sub> (m<sup>2</sup>) of each cohort
is calculated from leaf biomass *C*<sub>*l**e**a**f*, *c**o**h*</sub>
(kgC individual<sup>−1</sup>) and specific leaf area (SLA, m<sup>2</sup>
kg C<sup>−1</sup>). Leaf biomass *C*<sub>*l**e**a**f*, *c**o**h*</sub>
is controlled by the processes of phenology, allocation and turnover,
described in detail in the PARTEH submodule.

*A*<sub>*l**e**a**f*, *c**o**h*</sub> = *C*<sub>*l**e**a**f*, *c**o**h*</sub> ⋅ *S**L**A*<sub>*f**t*</sub>

However, using this model, where leaf area and crown area are both
functions of diameter, the leaf area index of each tree in a closed
canopy forest is always the same (where
*S*<sub>*c*, *p**a**t**c**h*</sub> = *S*<sub>*c*, *m**i**n*</sub> ,
irrespective of the growth conditions. To allow greater plasticity in
tree canopy structure, and for tree leaf area index to adapt to
prevailing conditions, we implemented a methodology for removing those
leaves in the canopy that exist in negative carbon balance. That is,
their total annual assimilation rate is insufficient to pay for the
turnover and maintenance costs associated with their supportive root and
stem tissue, plus the costs of growing the leaf. The tissue turnover
maintenance cost (KgC m<sup>−2</sup>*y*<sup>−1</sup> of leaf is the
total maintenance demand divided by the leaf area:

$$L\_{cost,coh} = \\frac{t\_{md,coh}} {C\_{leaf,coh} \\cdot \\textrm{SLA}}$$

The net uptake for each leaf layer *U*<sub>*n**e**t*, *z*</sub> in (KgC
m<sup>−2</sup> year<sup>−1</sup>) is

*U*<sub>*n**e**t*, *c**o**h*, *z*</sub> = *g*<sub>*c**o**h*, *z*</sub> − *r*<sub>*m*, *l**e**a**f*, *c**o**h*, *z*</sub>

where *g*<sub>*z*</sub> is the GPP of each layer of leaves in each tree
(KgC m<sup>−2</sup> year<sup>−1</sup>),
*r*<sub>*m*, *l**e**a**f*, *z*</sub> is the rate of leaf dark
respiration (also KgC m<sup>−2</sup> year<sup>−1</sup>). We use an
iterative scheme to define the cohort specific canopy trimming fraction
*C*<sub>*t**r**i**m*, *c**o**h*</sub>, on an annual time-step, where

*C*<sub>*l**e**a**f*, *c**o**h*</sub> = *C*<sub>*t**r**i**m*</sub> × 0.0419*d**b**h*<sub>*c**o**h*</sub><sup>1.56</sup>*d*<sub>*w*</sub><sup>0.55</sup>

If the annual maintenance cost of the bottom layer of leaves (KgC m-2
year-1) is less than then the canopy is trimmed by an increment
*ι*<sub>*l*</sub>(0.01), which is applied until the end of next calander
year. Because this is an optimality model, there is an issue of the
timescale over which net assimilation is evaluated, the timescale of
response, and the plasticity of plants to respond to these pressures.
These properties should be investigated further in future efforts.

$$\\begin{aligned}
C\_{trim,y+1}  = \\left\\{ \\begin{array}{ll}
\\rm{max}(C\_{trim,y}-\\iota\_l,1.0)&\\rm{for} (L\_{cost,coh} &gt; U\_{net,coh,nz})\\\\
&\\\\
\\rm{min}(C\_{trim,y}+\\iota\_l,L\_{trim,min})&\\rm{for} (L\_{cost,coh} &lt; U\_{net,coh,nz})\\\\
\\end{array} \\right.
\\end{aligned}$$

We impose an arbitrary minimum value on the scope of canopy trimming of
*L*<sub>*t**r**i**m*, *m**i**n*</sub> (0.5). If plants are able simply
to drop all of their canopy in times of stress, with no consequences,
then tree mortality from carbon starvation is much less likely to occur
because of the greatly reduced maintenance and turnover requirements.

\bigskip
\captionof{table}{Parameters needed for leaf area control model.  }

| Parameter Symbol | Parameter Name | Units | indexed by |
|------------------|------------------|------------------|------------------|
| *ι*<sub>*l*</sub> | Fraction by which leaf mass is reduced next year | none |  |
| *L*<sub>*t**r**i**m*, *m**i**n*</sub> | Minimum fraction to which leaf mass can be reduced | none |  |

\bigskip 

## Phenology

In deciduous plant functional types, the target leaf biomass
(*C*<sub>leaf, coh</sub>) can be regulated through the leaf elongation
factor (*ε*<sub>leaf, PFT</sub>), a non-dimensional, fractional quantity
(i.e., 0 ≥ *ε*<sub>leaf, PFT</sub> ≥ 1) that quantifies the degree of
environmental stress (cold or drought) experienced by the PFT
environmental conditions (temperature or moisture):

*C*<sub>leaf, coh</sub> = *ε*<sub>leaf, coh</sub> *C*<sub>leaf, coh</sub><sup>⊙</sup>,

where (*C*<sub>leaf, coh</sub><sup>⊙</sup>) is the leaf biomass given
size and PFT when the cohort does not experience any stress.
Importantly, *C*<sub>leaf, coh</sub><sup>⋆</sup> is not the absolute
maximum leaf biomass given size, as it can be still impacted by crown
damage or canopy trimming.

Two categories of deciduous PFTs are currently implemented in FATES,
**cold deciduous** (summergreen) and **drought deciduous** (raingreen).
Cold deciduous plants are always *hard-deciduous*, meaning that
*ε*<sub>leaf, coh</sub> can only be either 0 (leaves completely
abscised) or 1 (PFTs will fully flush leaves provided that enough carbon
storage is available). For drought-deciduous PFTs, two strategies are
available, *hard-deciduous* phenology, akin to the cold deciduous, and
the *semi-deciduous* phenology, where *ε*<sub>leaf, coh</sub> can be any
fraction between 0 and 1 (inclusive), which allows plants to partially
abscise or partially flush leaves when drought conditions are moderate.
For evergreen PFTs, *ε*<sub>leaf, coh</sub> = 1 at all times.

In addition to leaf phenology, in FATES it is possible to simulate
active flushing and abscission of fine roots and stems in response to
environmental conditions. In the case of fine roots, the main purpose is
to reduce the maintenance of high-turnover tissues when plants are not
assimilating carbon. In the case of stems, phenology is intended to be
used for grass PFTs only, with the goal of avoiding numerical
instabilities when running plant hydraulics (FATES-Hydro).

Fine-root and stem phenologies are controlled by PFT-specific drop
fraction parameters, namely *ν*<sub>root, PFT</sub> (FATES parameter
`fates_phen_fnrt_drop_fraction`) and *ν*<sub>stem, PFT</sub> (FATES
parameter `fates_phen_stem_drop_fraction`). Both parameters range from 0
(perennial) to 1 (tissue phenology tracks leaf phenology), and are used
to determine elongation-factor-equivalent values for these tissues after
the elongation factor for leaves is determined:

$$\\begin{aligned}
\\begin{array}{l}
\\varepsilon\_{\\mathrm{root,PFT}} = 1 - \\left( 1 - \\varepsilon\_{\\mathrm{leaf,PFT}} \\right) \\, \\nu\_{\\mathrm{root,PFT}}, \\\\
\\varepsilon\_{\\mathrm{stem,PFT}} = 1 - \\left( 1 - \\varepsilon\_{\\mathrm{leaf,PFT}} \\right) \\, \\nu\_{\\mathrm{stem,PFT}}.
\\end{array}
\\end{aligned}$$

In the next sections, we describe how *ε*<sub>leaf, coh</sub> is defined
for non-evergreen PFTs.

### Cold Deciduous Leaf Phenology

#### Cold Leaf-out timing

The phenology model of `Botta et al. 2000<botta2000>` is used in FATES
to determine the leaf-on timing. The Botta et al. model was verified
against satellite data and is one of the only globally verified and
published models of leaf-out phenology. This model differs from the
phenology model in the CLM4.5. The model simulates leaf-on date as a
function of the number of growing degree days (GDD), defined by the sum
of mean daily temperatures (*T*<sub>day</sub>
$\\phantom{.}^{\\circ}\\mathrm{C}$) above a given threshold
*T*<sub>*g*</sub> (0<sup>∘</sup>C).

GDD = ∑max (*T*<sub>day</sub> − *T*<sub>*g*</sub>, 0)

Budburst occurs when GDD exceeds a threshold (GDD<sub>crit</sub>). The
threshold is modulated by the number of chilling days experienced (NCD)
where the mean daily temperature falls below a threshold determined by
`Botta et al. 2000<botta2000>` as 5<sup>∘</sup>C. A greater number of
chilling days means that fewer growing degree days are required before
budburst:

GDD<sub>crit</sub> = *a* + *b* exp (*c* NCD)

where *a* = −68, *b* = 638 and *c* = −0.01
(`Botta et al. 2000<botta2000>`). In the Northern Hemisphere, counting
of degree days begins on 1st January, and of chilling days on 1st
November. In the Southern Hemisphere, we use 1st July (growing degree
days) and 1st May (chilling days) instead.

If the growing degree days exceed the critical threshold, leaf-on is
triggered by a change in the leaf elongation factor:

$$\\begin{aligned}
\\varepsilon\_\\mathrm{leaf,PFT}(t) =
\\begin{cases}
1 & \\textrm{, if } \\varepsilon\_\\mathrm{leaf,PFT}(t-1) = 0 \\textrm{ and } \\mathrm{GDD}(t) \\ge \\mathrm{GDD}\_\\mathrm{crit} \\\\
\\varepsilon\_\\mathrm{leaf,PFT}(t-1) & \\textrm{, otherwise}
\\end{cases}
\\end{aligned}$$

#### Cold Leaf-off timing

The leaf-off model is taken from the Sheffield Dynamic Vegetation Model
(SDGVM) and is similar to that for LPJ `Sitch et al. 2003<sitch2003>`
and IBIS `Foley et al. 1996<Foley1996>` models. The average daily
temperatures of the previous 10 day period are stored. Senescence is
triggered when the number of days with an average temperature below
7.5<sup>∘</sup>C (*n*<sub>colddays</sub>) rises above a threshold values
*n*<sub>crit, cold</sub>, set at 5 days.

$$\\begin{aligned}
\\varepsilon\_\\mathrm{leaf,PFT}(t) =
\\begin{cases}
0 & \\textrm{, if} \\varepsilon\_\\mathrm{leaf,PFT}(t-1) = 1 \\textrm{ and } n\_\\mathrm{colddays}(t) \\ge n\_\\mathrm{crit,cold} \\\\
\\varepsilon\_\\mathrm{leaf,PFT}(t-1) & \\textrm{, otherwise}
\\end{cases}
\\end{aligned}$$

#### Global implementation modifications

Because of the global implementation of the cold-deciduous phenology
scheme, adjustments must be made to account for the possibility of
cold-deciduous plants experiencing situations where no chilling period
triggering leaf-off ever happens. If left unaccounted for, these leaves
will last indefinitely, resulting in highly unrealistic behaviour.
Therefore, we implement two additional rules. Firstly, if the number of
days since the last senescence event was triggered is larger than 364,
then leaf-off is triggered on that day. Secondly, if no chilling days
have occured during the winter accumulation period, then leaf-on is not
triggered. This means that in effect, where there are no cold periods,
leaves will fall off and not come back on, meaning that cold-deciduous
plants can only grow in places where there is a cold season.

Further to this rule, we introduce a ‘buffer’ time periods after leaf-on
of 30 days, so that cold-snap periods in the spring cannot trigger a
leaf senescence. The 30 day limit is an arbitrary limit. In addition, we
constrain growing degree day accumulation to the second half of the year
(July-December in the Northern hemisphere, or January-June in the
Southern Hemisphere) and only allow GDD accumulation while the leaves
are off.

### Drought-deciduous leaf phenology (hard-deciduous)

The hard-, drought-deciduous phenology in FATES is based on CLM-4
(`Dahlin et al. 2015<Dahlinetal2015>`;
`Oleson et al. 2013<Olesonetal2013>`). Both leaf flushing (growth) and
leaf abscission (senescence) are controlled by the plant available water
(*ψ*<sub>PFT, grid</sub> mm), a PFT-specific variable that is defined as
the 10-day running average of the soil matric potential across the
rooting zone:

$$\\psi\_\\mathrm{PFT,grid}\\left(t\\right) = \\frac{1}{10} \\,
\\left\[ \\sum\_{t'=t-9}^{t} \\left( \\frac{\\displaystyle \\sum\_{k=k\_\\mathrm{root,PFT}}^{N\_\\mathrm{soil}-1} \\psi\\left(z\_k,t'\\right) \\, r\_{z\_k,\\mathrm{PFT}}}
{\\displaystyle \\sum\_{k=k\_\\mathrm{root,PFT}}^{N\_\\mathrm{soil}-1} r\_{z\_k,\\mathrm{PFT}}} \\right) \\right\],$$

where *ψ*(*z*<sub>*k*</sub>, *t*<sup>′</sup>) is the soil matric
potential of layer *k* at time *t*<sup>′</sup>, *k*<sub>root, PFT</sub>
is the deepest soil layer in the PFT's rooting zone,
*r*<sub>*z*<sub>*k*</sub>, PFT</sub> is the fraction of roots of each
plant functional type at each soil layer, and *N*<sub>soil</sub> is the
total number of soil layers. To avoid a strong influence of the
typically very thin top soil layer, we exclude this layer when
estimating *ψ*<sub>PFT, grid</sub>.

For the most part, drought conditions are based on a comparison between
*ψ*<sub>PFT, grid</sub>(*t*) and a PFT-specific, threshold parameter
*ψ*<sub>PFT, drought</sub>\|*ψ*<sub>PFT, drought</sub> ∈ \]−∞, 0\[ (mm).
When *ψ*<sub>PFT, grid</sub>(*t*) &lt; *ψ*<sub>PFT, drought</sub>, we
assume drought conditions (plants likely to be or become leafless), and
when *ψ*<sub>PFT, grid</sub>(*t*) ≥ *ψ*<sub>PFT, drought</sub>, we
assume non-drought conditions (plants likely to be or become fully
flushed).

Similarly to the cold-deciduous phenology, we must include additional
constrains to ensure that plants are truly deciduous, even when the
seasonal cycle of *ψ*<sub>PFT, grid</sub>(*t*) never crosses the drought
threshold. To prevent plants to remain leafless for long periods of
time, PFTs will forcibly flush leaves when the time since last flushing
(*t*<sub>Flush, coh</sub>, day) exceeds 395 days (13 months). Likewise,
the maximum time leaves can remain fully flushed is defined by the
PFT-specific leaf life span (*τ*<sub>Leaf, coh</sub>) or 12 months,
whichever is the shortest.

The use of a single-parameter threshold to define drought conditions can
potentially lead to a *flickering* behaviour, in which deciduous PFTs
would flush and abscise leaves multiple times if plant available water
(*ψ*<sub>PFT, grid</sub>(*t*)) straddles around
*ψ*<sub>PFT, drought</sub>. To prevent this, leaf abscission can only
occur if the time since last flushing has exceeded 90 days (3 months).
Similarly, plants can only flush leaves when the time since last
abscission (*t*<sub>Abscise, coh</sub>, day) exceeds a PFT-specific
parameter (*t*<sub>PFT, MinOff</sub>, day). The only exception to this
rule is when a site is perennially moist, in which case PFTs can flush
their leaves after 30 days, akin to a brevi-deciduous behaviour.

The diagram below summarises how elongation factor is defined after
accounting for the time-driven phenological cycles:

<figure>
<img src="images/PhenologyDecisionTreeHard.png" />
</figure>

### Drought-deciduous leaf phenology (semi-deciduous)

The semi-, drought-deciduous phenology in FATES is based on the hard-,
drought-deciduous phenology, with a further modification in the
elongation factor dynamics based on the ED-2.2 model
(`Longo et al. 2019<Longoetal2019a>`). Semi-, drought-deciduous PFTs can
partially abscise or partially flush leaves when drought conditions are
moderate, and therefore can experience non-instantaneous flushing and
abscission seasons.

To define the degree of abscission or flushing, we define a first guess
for the elongation factor (*ε*<sub>leaf, PFT</sub><sup>⋆</sup>) that
compares the plant available water with two thresholds:

$$\\varepsilon^{\\star}\_\\mathrm{leaf,PFT}(t) =
\\max{\\left\[0,\\min{\\left(1,\\frac{\\psi\_\\mathrm{PFT,grid}\\left(t\\right)-\\psi\_\\mathrm{PFT,drought}}{\\psi\_\\mathrm{PFT,moist}-\\psi\_\\mathrm{PFT,drought}}\\right)}\\right\]}$$

where *ψ*<sub>PFT, moist</sub> (mm) is a PFT-specific parameter that
defines the threshold above which plant available water is no longer a
limiting factor, and *ψ*<sub>PFT, drought</sub> defines the threshold
below which plant available water is strongly limiting. The latter
parameter is defined by the same parameter name in the FATES parameter
file.

Typically, *ε*<sub>leaf, PFT</sub><sup>⋆</sup> will be the actual
elongation factor. However, akin to the hard-deciduous PFTs, we must
ensure that semi-deciduous PFTs still have at least one
abscission/flushing cycle every year, and that PFTs do not switch
between abscising and flushing phases too frequently, especially when
the elongation factor is zero. To this end, we define
*t*<sub>Abscise, coh</sub> (day) to be the time since last full
abscission (i.e., when PFT lost all leaves), and
*t*<sub>Flush, coh</sub> (day) as the time since last
"out-of-leafless-state" flushing event. We then apply the set of rules
described in the figure below.

<figure>
<img src="images/PhenologyDecisionTreeSemi.png" />
</figure>

**Note**. The semi-deciduous implementation is still experimental, and
may be revised as more experiments are carried out and more data become
available.

### Carbon allocation dynamics of deciduous plants

In the present version, phenology (i.e., the elongation factors) is
updated at daily time steps. Once phenology is updated, carbon pools
(i.e., plant tissues, storage and litter) are updated too.

To facilitate the tracking of phenology dynamics, we define a flag
variable (*S*<sub>phen, coh</sub>) that describes the leaf phenology
status of every cohort:

$$\\begin{aligned}
S\_\\mathrm{phen,coh} =
\\begin{cases}
1 & \\textrm{, if cohort is completely leafless,} \\\\
2 & \\textrm{, if cohort is flushing leaves or leaves are fully flushed,} \\\\
3 & \\textrm{, if cohort is abscising leaves (but not completely leafless).}
\\end{cases}
\\end{aligned}$$

#### Expansion (flushing) phase

When cohorts are in expansion phase (i.e., *S*<sub>phen, coh</sub> = 2),
carbon will be transferred from the storage pool, based on the expected
carbon stocks:

$$\\begin{aligned}
\\begin{array}{l}
C^{\\star}\_\\mathrm{leaf,coh}\\left(t\\right) = \\varepsilon\_\\mathrm{leaf,coh}\\left(t\\right) \\, C^{\\odot}\_\\mathrm{leaf,coh}, \\\\
C^{\\star}\_\\mathrm{root,coh}\\left(t\\right) = \\varepsilon\_\\mathrm{root,coh}\\left(t\\right) \\, C^{\\odot}\_\\mathrm{root,coh}, \\\\
C^{\\star}\_\\mathrm{stem,coh}\\left(t\\right) = \\varepsilon\_\\mathrm{stem,coh}\\left(t\\right) \\, C^{\\odot}\_\\mathrm{stem,coh},
\\end{array}
\\end{aligned}$$

where *C*<sub>leaf, coh</sub><sup>⋆</sup>,
*C*<sub>root, coh</sub><sup>⋆</sup> and
*C*<sub>stem, coh</sub><sup>⋆</sup> are respectively the maximum carbon
biomass of leaves, fine roots and stems (sapwood + heartwood) that the
cohort can attain given their size, PFT, canopy trimming status, damage
status and elongation factors.

In reality, the actual carbon stocks *C*<sub>tissue, coh</sub>(*t*) will
depend on both on *C*<sub>tissue, coh</sub><sup>⋆</sup> and the amount
of carbon storage at the previous time step (*C*<sub>store, coh</sub>),
meaning that
*C*<sub>tissue, coh</sub>(*t*) ≤ *C*<sub>tissue, coh</sub><sup>⋆</sup>.
The transfer of carbon from storage to the living tissues is solved by
the `parteh_section` module.

#### Abscission phase

When cohorts are abscising tissues (i.e.,
*S*<sub>phen, coh</sub> ∈ {1, 3}), the updated carbon pools are defined
based on the updated elongation factors:

$$\\begin{aligned}
\\begin{array}{l}
C\_\\mathrm{leaf,coh}\\left(t\\right) = \\min{\\left\[\\varepsilon\_\\mathrm{leaf,coh}\\left(t\\right) \\, C^{\\odot}\_\\mathrm{leaf,coh}, C\_\\mathrm{leaf,coh}\\left(t-1\\right)\\right\]}, \\\\
C\_\\mathrm{root,coh}\\left(t\\right) = \\min{\\left\[\\varepsilon\_\\mathrm{root,coh}\\left(t\\right) \\, C^{\\odot}\_\\mathrm{root,coh}, C\_\\mathrm{root,coh}\\left(t-1\\right)\\right\]}, \\\\
C\_\\mathrm{stem,coh}\\left(t\\right) = \\min{\\left\[\\varepsilon\_\\mathrm{stem,coh}\\left(t\\right) \\, C^{\\odot}\_\\mathrm{stem,coh}, C\_\\mathrm{stem,coh}\\left(t-1\\right)\\right\]},
\\end{array}
\\end{aligned}$$

where *C*<sub>leaf, coh</sub><sup>⊙</sup>,
*C*<sub>root, coh</sub><sup>⊙</sup> and
*C*<sub>stem, coh</sub><sup>⊙</sup> are respectively the maximum carbon
biomass of leaves, fine roots and stems (sapwood + heartwood) that the
cohort can attain given their size, PFT, canopy trimming status and
damage status.

Litter fluxes (kgC individual<sup>−1</sup> day<sup>−1</sup>) are defined
as follows:

$$\\begin{aligned}
\\begin{array}{l}
{\\displaystyle l\_\\mathrm{leaf,coh}\\left(t\\right) = \\frac{1}{\\Delta t} \\, \\left\[C\_\\mathrm{leaf,coh}\\left(t-1\\right) - C\_\\mathrm{leaf,coh}\\left(t\\right)\\right\]}, \\\\
{\\displaystyle l\_\\mathrm{root,coh}\\left(t\\right) = \\frac{1}{\\Delta t} \\, \\left\[C\_\\mathrm{root,coh}\\left(t-1\\right) - C\_\\mathrm{root,coh}\\left(t\\right)\\right\]}, \\\\
{\\displaystyle l\_\\mathrm{stem,coh}\\left(t\\right) = \\frac{1}{\\Delta t} \\, \\left\[C\_\\mathrm{stem,coh}\\left(t-1\\right) - C\_\\mathrm{stem,coh}\\left(t\\right)\\right\]}, \\\\
\\end{array}
\\end{aligned}$$

where *Δ**t* is the phenological time step.

During abscission phase, cold-deciduous PFTs will use any storage carbon
available to bring living tissues to the expected level (i.e.,
*C*<sub>tissue, coh</sub><sup>⋆</sup>), similarly to what occurs during
the expansion (flushing) phase. This has minimum impact on
cold-deciduous viability because tissue turnover rate is a function of
temperature, and therefore the costs are low during their leaf-off
season. This is not the case for drought deciduous, because the
atmospheric temperature (and the maintenance costs) are typically high
in the leaf-off season, particularly in dry tropical ecosystems.
Therefore, when drought-deciduous PFTs status is
*S*<sub>phen, coh</sub> ∈ {1, 3}, they completely halt allocation to any
tissue, and all carbon acquired during the abscission phase (only
possible when *S*<sub>phen, coh</sub> = 3) is transferred to carbon
storage.

\bigskip
\captionof{table}{Parameters needed for phenology model.  }

| Parameter Symbol | Parameter Name | Units | indexed by |
|------------------|------------------|------------------|------------------|
| *n*<sub>*c**r**i**t*, *c**o**l**d*</sub> | Threshold of cold days for senescence | none |  |
| *T*<sub>*g*</sub> | Threshold for counting growing degree days | <sup>∘</sup>C |  |
| *ν*<sub>root, PFT</sub> | Fraction of active abscission of fine roots, relative to leaves. | none |  |
| *ν*<sub>stem, PFT</sub> | Fraction of active abscission of stems, relative to leaves. | none |  |
| *ψ*<sub>PFT, drought</sub> | Threshold below which drought deciduous cohorts abscise all leaves | mm |  |
| *ψ*<sub>PFT, moist</sub> | Threshold above which water is no longer a limiting factor | mm |  |
| *t*<sub>PFT, MinOff</sub> | Minimum leaf-off time for hard-, drought deciduous PFTs | day |  |

\bigskip 

## Seed Dynamics and Recruitment

The production of seeds and their subsequent germination is a process
that must be captured explicitly or implicitly in vegetation models.
FATES contains a seed bank model designed to allow the dynamics of seed
production and germination to be simulated independently. In the ED1.0
model, seed recruitment occurs in the same timestep as allocation to
seeds, which prohibits the survival of a viable seed bank through a
period of disturbance or low productivity (winter, drought). In FATES, a
plant functional type specific seed bank is tracked in each patch
(*S**e**e**d**s*<sub>*p**a**t**c**h*</sub> KgC m<sup>−2</sup>), whose
rate of change (KgC m<sup>−2</sup> y<sup>−1</sup>) is the balance of
inputs, germination and decay:

$$\\frac{\\delta Seeds\_{FT}}{\\delta t } = Seed\_{in,ft} - Seed\_{germ,ft} - Seed\_{decay,ft}$$

where *S**e**e**d*<sub>*i**n*</sub>, *S**e**e**d*<sub>*g**e**r**m*</sub>
and *S**e**e**d*<sub>*d**e**c**a**y*</sub> are the production,
germination and decay (or onset of inviability) of seeds, all in KgC
m<sup>−2</sup> year<sup>−1</sup>.

Seeds are assumed to be distributed evenly across the site (in this
version of the model), so the total input to the seed pool is therefore
the sum of all of the reproductive output of all the cohorts in each
patch of the correct PFT type.

$$Seed\_{in,ft} =  \\frac{\\sum\_{p=1}^{n\_{patch}}\\sum\_{i=1}^{n\_{coh}}p\_{seed,i}.n\_{coh}}{area\_{site}}$$

Seed decay is the sum of all the processes that reduce the number of
seeds, taken from `Lischke et al. 2006<lischke2006>`. Firstly, the rate
at which seeds become inviable is described as a constant rate *ϕ*
(y<sup>−1</sup>) which is set to 0.51, the mean of the parameters used
by `Lischke et al. 2006<lischke2006>`.

*S**e**e**d*<sub>*d**e**c**a**y*, *f**t*</sub> = *S**e**e**d**s*<sub>*F**T*</sub>.*ϕ*

The seed germination flux is also prescribed as a fraction of the
existing pool (*α*<sub>*s**g**e**r**m*</sub>), but with a cap on maximum
germination rate *β*<sub>*s**g**e**r**m*</sub>, to prevent excessive
dominance of one plant functional type over the seed pool.

*S**e**e**d*<sub>*g**e**r**m*, *f**t*</sub> = max(*S**e**e**d**s*<sub>*F**T*</sub> ⋅ *α*<sub>*s**g**e**r**m*</sub>, *β*<sub>*s**g**e**r**m*</sub>)

\bigskip
\captionof{table}{Parameters needed for seed model.  }

<table style="width:97%;">
<colgroup>
<col style="width: 24%" />
<col style="width: 24%" />
<col style="width: 24%" />
<col style="width: 24%" />
</colgroup>
<thead>
<tr>
<th>Parameter Symbol</th>
<th>Parameter Name</th>
<th>Units</th>
<th>indexed by</th>
</tr>
</thead>
<tbody>
<tr>
<td><span
class="math inline"><em>K</em><sub><em>s</em></sub></span></td>
<td>Maximum seed mass</td>
<td>kgC m<span class="math inline"><sup>−2</sup></span></td>
<td></td>
</tr>
<tr>
<td><span
class="math inline"><em>α</em><sub><em>s</em><em>g</em><em>e</em><em>r</em><em>m</em></sub></span></td>
<td>Proportional germination rate</td>
<td>none</td>
<td></td>
</tr>
<tr>
<td><span
class="math inline"><em>β</em><sub><em>s</em><em>g</em><em>e</em><em>r</em><em>m</em></sub></span></td>
<td>Maximum germination rate</td>
<td><p>KgC m<span class="math inline"><sup>−2</sup></span></p>
<p>y<span class="math inline"><sup>−1</sup></span></p></td>
<td></td>
</tr>
<tr>
<td><span class="math inline"><em>ϕ</em></span></td>
<td>Decay rate of viable seeds</td>
<td>none</td>
<td><em>ft</em></td>
</tr>
<tr>
<td><span
class="math inline"><em>R</em><sub><em>f</em><em>r</em><em>a</em><em>c</em>, <em>f</em><em>t</em></sub></span></td>
<td>Fraction of <span
class="math inline"><em>C</em><sub><em>b</em><em>a</em><em>l</em></sub></span>
devoted to reproduction</td>
<td>none</td>
<td><em>ft</em></td>
</tr>
</tbody>
</table>

\bigskip 

### Environmentally Sensitive Tree Recruitment

FATES has the option to represent environmentally sensitive tree
recruitment using the Tree Recruitment Scheme (TRS), a module that was
originally presented offline of FATES
(`Hanbury-Brown et al. 2022<Hanbury-Brown2022>`). The primary goal of
the TRS is to more mechanistically constrain the amount of carbon
available for recruitment based on conditions at the forest floor.

The TRS is off by default (fates\_regeneration\_model = 1), but can be
switched on using the parameter file. The TRS can be switched on in a
reduced complexity mode (fates\_regeneration\_model = 3) without
seedling dynamics where it represents 1) pft-specific reproductive
allocation schedules as a function of dbh and 2) allocation to non-seed
reproductive biomass. If the TRS is switched on with seedling dynamics
(fates\_regeneration\_model = 2) it will also represent environmentally
sensitive seedling emergence, seedling mortality and transition into the
sapling stage (i.e. cohorts tracked by FATES).

The TRS allocates a dynamic fraction of carbon for growth and
reproduction (*C*<sub>*g* + *r*</sub>; positive carbon balance net after
tissue turnover and allocation to storage) to reproduction. Regeneration
processes, described in detail below, move dynamic fractions of
*C*<sub>*g* + *r*</sub> through a seedbank and seedling pool which are
tracked in units of carbon. Carbon recruiting out of the seedling pool
each day is passed back to FATES’s default recruitment subroutine. The
TRS determines how much carbon is available for recruitment and FATES’s
recruitment subroutine calculates how many new recruits to produce and
initializes the new cohort. Carbon in seeds or seedlings that die or
that is allocated to non-seed reproductive biomass, moves to the litter
pool. Unlike the offline version of the TRS presented in
`Hanbury-Brown et al. (2022)<Hanbury-Brown2022>`, FATES-TRS uses
exponential moving averages (EMAs) of environmental variables in the
seedling layer to calculate the rates of regeneration processes. EMAs
are tracked on different timescales depending on the process.

<figure>
<img src="images/TRS_overview.png" alt="TRS image" />
<figcaption>Daily regeneration processes (depicted with hour glasses)
represented by FATES-TRS transfer reproductive carbon through seed bank
and seedling carbon pools (depicted as circles). Processes are sensitive
to DBH or environmental conditions (see inset key). The litter pool
receives non-seed reproductive carbon, dead seeds, and dead seedlings.
Carbon for new recruits is passed back to FATES’s default recruitment
subroutine. "Host VDM" = FATES.</figcaption>
</figure>

#### Allocation to reproduction

Allocation to reproduction occurs in FATES’s parteh module
(parteh/PRTAllometricCarbonMod.F90). FATES without the TRS switched on
(i.e. “default FATES”) assumes reproductive allocation is either
insensitive to size or is a step function of size, depending on the
parameterization. In contrast, the TRS allocates a dynamic fraction of
cohort-level *C*<sub>*g* + *r*</sub> to reproduction based on the
cohort’s size and the TRS’s reproductive allocation (RA) function. This
follows observations that the probability a tree is reproductive
increases sigmoidally with size within species
(`Visser et al., 2016<Visser2016>`). Each mature cohort contributes to
recruitment via the TRS if they are in positive carbon balance. The
effective fraction of cohort-level *C*<sub>*g* + *r*</sub> allocated to
reproduction, *F*<sub>*E*, *r**e**p**r**o*</sub>, is calculated based on
a sigmoidal relationship relating the cohort’s current dbh (cm) to the
probability of being reproductive (*P*<sub>*r**e**p**r**o*</sub>). This
formulation assumes that all reproductive individuals in a cohort
allocate to reproduction at a constant, PFT-specific rate,
*F*<sub>*r**e**p**r**o*</sub>, which is modified by
*P*<sub>*r**e**p**r**o*</sub> to calculate
*F*<sub>*E*, *r**e**p**r**o*</sub>

<span label="Eqn 1.14.1">
$$P\_{repro} =  \\frac{e^{( a\_{RA}  (dbh) +  b\_{RA}) } }{1 + e^{(  a\_{RA}  (dbh) +  b\_{RA}  )} }$$
</span>

<span label="Eqn 1.14.2">
*F*<sub>*E*, *r**e**p**r**o*</sub> = (*P*<sub>*r**e**p**r**o*</sub>)(*F*<sub>*r**e**p**r**o*</sub>)
</span>

where *a*<sub>*R**A*</sub> and *b*<sub>*R**A*</sub> are PFT-specific
parameters describing the shape of the sigmoidal curve. This functional
form is consistent with empirical data
(`Visser et al., 2016<Visser2016>`;
`Minor & Kobe, 2019<MinorKobe2019>`). The TRS subsequently multiplies
*F*<sub>*E*, *r**e**p**r**o*</sub> by *C*<sub>*g* + *r*</sub> to get
reproductive carbon per cohort.

See Table below for all TRS parameters.

#### Allocation to seed vs. non-seed reproductive biomass and seed mortality

In nature, only a subset of the carbon allocated to reproduction becomes
seeds, with the rest going to flowers, fruit flesh, capsules, etc.
(`Wenk et al., 2017<Wenk2017>`). Default FATES sends all reproductive
carbon to an undifferentiated “seed pool” from which carbon is lost and
recruits are formed (`Fisher et al., 2015<Fisheretal2015>`). The TRS
partitions each cohort’s reproductive carbon into seed carbon and
non-seed reproductive carbon (e.g., flowers, fruit flesh, and capsules)
based on a prescribed, PFT-specific fraction of reproductive carbon that
is seed, *F*<sub>*s**e**e**d*</sub>. This happens in the SeedIn
subroutine (biogeochem/EDPhysiologyMod). Seed carbon moves to the seed
bank each day and non-seed reproductive carbon moves to litter. Seeds in
the seed bank die at a PFT-specific, constant rate,
*S*<sub>*m**o**r**t*</sub>, which represents all modes of seed mortality
including predation and decay (same as default FATES).

#### Seedling emergence

Seedling emergence is sensitive to soil moisture
(`Garwood, 1983<Garwood1983>`;
`Atondo-Bueno et al., 2016<Atondo-Bueno2016>`;
`Ruiz Talonia et al., 2017<Ruiz2017>`) and light
(`Pearson et al., 2002<Pearson2002>`) in nature. Default FATES
represents it as an environmentally insensitive constant. In the TRS,
emergence depends on both soil moisture and light.

Light-dependence of germination is captured on day i in a
Michaelis-Menten rate modifier \[0,1\]

$$f(PAR\_i) = \\frac{ PAR\_i}  {PAR\_i  + PAR\_{crit}}$$

based on *P**A**R*<sub>*i*</sub>, the 24-hour EMA of photosynthetically
active radiation (PAR) at the seedling layer. Seedling layer PAR is
sensitive to canopy layer and understory layer vegetation cover such
that seedling layer PAR is an area-weighted average of PAR incident at
the top and bottom of the understory layer. When there is very little
vegetation present, PAR at the seedling layer is taken from the boundary
conditions (i.e. same as top of canopy).
*P**A**R*<sub>*c**r**i**t*</sub> is a PFT-specific PAR threshold
governing the shape of the germination response to reduced light. Most
tropical pioneer species exhibit an increase in germination probability
with increases in light, whereas germination in shade-tolerant species
is insensitive to light (captured by
*P**A**R*<sub>*c**r**i**t*</sub> = 0).

The EMA of soil matric potential on day i
(*S**M**P*<sub>*E**M**A*, *i*</sub>) at seedling rooting depth,
*d*<sub>*s**e**e**e**d**l**i**n**g*</sub>, is influenced by SMP in a
rolling window of days, *W*<sub>*e**m**e**r**g*</sub> (default = 7
days), prior to i. If *S**M**P*<sub>*E**M**A*, *i*</sub> is above a
critical threshold, *ψ*<sub>*e**m**e**r**g*</sub>, then seedling
emergence occurs. The emergence rate on day i,
*F*<sub>*e**m**e**r**g*, *i*</sub>, is dynamically calculated as a
function of *S**M**P*<sub>*E**M**A*, *i*</sub>. The pft-specific
moisture response parameter, *b*<sub>*e**m**e**r**g*</sub>, modifies the
mean seedling emergence coefficient (*a*<sub>*e**m**e**r**g*</sub>) in
response to variation in *S**M**P*<sub>*E**M**A*</sub> such that

$$\\begin{aligned}
F\_{emerg,i} = \\left\\{
\\begin{array}{ll}
0 & \\quad SMP\_{i} &lt; \\psi\_{emerg} \\\\
f(PAR\_{i}) (a\_{emerg}) \\left(  \\frac {   \\sum\_{j = i - W\_{emerg} }^{ i} ( 1 / -SMP\_{j}  ) } {W\_{emerg}} \\right) ^{ b\_{emerg} } & \\quad SMP\_{i} \\geq \\psi\_{emerg}
\\end{array}
\\right .
\\end{aligned}$$

This produces pulses of seedling emergence in response to seasonal and
interannual precipitation events, and stalls seedling emergence under
relatively dry conditions.

#### Moisture and light-sensitive seedling survival

The TRS tracks a seedling pool that is sensitive to light and moisture
stress. Seedling survival decreases differentially at low soil moisture
and low light, affecting forest composition across environmental
gradients (`Kobe, 1999<Kobe1999>`;
`Engelbrecht et al., 2007<Engelbrecht2007>`).

The TRS seeks to capture this with a PFT-specific moisture stress
threshold, *ψ*<sub>*c**r**i**t*</sub>, below which the seedling pool
starts to “accumulate” (mathematically an EMA is tracked with a
timescale of *W*<sub>*ψ*</sub> days; default = 126) moisture deficit
days (MDD) similar to the concept of growing degree days. The new MDD
value on day i, *M**D**D*<sub>*i*</sub>, is calculated as the difference
between the absolute value of site-level SMP on day i,
*S**M**P*<sub>*i*</sub>, and the absolute value of
*ψ*<sub>*c**r**i**t*</sub>.

$$\\begin{aligned}
MDD\_i = \\sum\_{j = i - W\_{\\psi}}^{i} \\left\\{
\\begin{array}{ll}
0 & \\quad \\psi\_j \\geq \\psi\_{crit} \\\\
\|\\psi\_j\| - \|\\psi\_{crit}\| & \\quad \\psi\_j &lt; \\psi\_{crit}
\\end{array}
\\right.
\\end{aligned}$$

*M**D**D*<sub>*i*</sub> is then used to update an EMA of MDD,
*M**D**D*<sub>*E**M**A*</sub>. Finally, *M**D**D*<sub>*E**M**A*</sub> is
multiplied by the timescale of the EMA (in days), *W*<sub>*ψ*</sub>, to
approximate an “accumulation” of MDD.

This formulation simultaneously captures the magnitude and duration of
moisture stress. Observations of seedling wilting points from a
manipulative drought experiment at BCI
(`Engelbrecht & Kursar, 2003<EngelbrechtKursar2003>`;
`Engelbrecht et al., 2007<Engelbrecht2007>`) were used to explore the
relationship between MDD accumulation and seedling mortality. Observed
drought-induced mortality is 0 up to a critical accumulation of MDD,
*M**D**D*<sub>*c**r**i**t*</sub>, at which point a convex quadratic
relationship best explained drought-induced seedling mortality as a
function of MDD (see SI Methods S1 and Fig. S1 in
`Hanbury-Brown et al., 2022<Hanbury-Brown2022>` for more details). The
mortality rate from moisture stress (*M*<sub>*ψ*</sub>) on day i is
therefore

$$\\begin{aligned}
M\_{\\psi,i} =  \\left\\{
\\begin{array}{ll}
0 & \\quad MDD\_i &lt; MDD\_{crit} \\\\
a\_{\\psi}MDD\_i^2 + b\_{\\psi}MDD\_i + c\_{\\psi} & \\quad  MDD\_i  \\geq MDD\_{crit}
\\end{array}
\\right. .
\\end{aligned}$$

Seedlings also die from insufficient light, which we refer to as light
stress. The light stress mortality rate, *M*<sub>*L*</sub>, on day i is
a function of “cumulative” (mathematically an EMA is tracked with a
timescale of W\_L days; default = 32) PAR at the seedling layer,
*L*<sub>*s**e**e**d**l**i**n**g*</sub>, within a moving window of days,
*W*<sub>*L*</sub>, prior to i. Similar to the approach used to calculate
*M**D**D*<sub>*E**M**A*</sub>, *L*<sub>*s**e**e**d**l**i**n**g*</sub> is
calculated by multiplying an EMA of seedling layer PAR,
*P**A**R*<sub>*E**M**A*</sub>, by *W*<sub>*L*</sub> to approximate the
cumulative light incident at the seedling layer prior to i. Two
PFT-specific parameters determine the shape of the negative exponential
relationship between mortality and and light

$$M\_{L,i} = e^{a\_{ML} \\left ( \\sum\_{j=i-W\_{L}}^{i} L\_{seedling,j} \\right) + b\_{ML}}$$

where *a*<sub>*M**L*</sub> is a PFT-specific light response parameter
and *b*<sub>*M**L*</sub> is the intercept. This function is based on an
analysis by `Kobe (1999)<Kobe1999>` who tested four functional forms and
found that the negative exponential best described light stress
mortality for two shade tolerant and one light demanding species that
were transplanted into varied light environments. A background seedling
mortality rate, *M*<sub>*b**a**c**k**g**r**o**u**n**d*</sub>, represents
other seedling mortality (e.g. herbivory, pathogens, tree fall, etc.).
Total seedling mortality is the sum of moisture-dependent,
light-dependent and background mortality.

#### Recruitment

The rate of transition from seedling to sapling increases with
understory light (`Brokaw, 1985<Brokaw1985>`;
`Rüger et al., 2009b<Ruger2009b>`). Recruitment in the TRS is
represented with a dynamic seedling to sapling transition rate (TR)
which is the fraction of total carbon in the seedling pool,
*C*<sub>*s**e**e**d**l**i**n**g*</sub>, that is available to make new
recruits each day. The TR on day i is calculated as a power function of
*P**A**R*<sub>*E**M**A*, *i*</sub>. If SMP on day i, *ψ*<sub>*i*</sub>,
is drier than *ψ*<sub>*c**r**i**t*</sub> the transition rate goes to
zero such that

$$\\begin{aligned}
TR\_{i} = \\left\\{
     \\begin{array}{ll}
         0 & \\quad \\psi\_i &lt; \\psi\_{crit} \\\\
        a\_{TR} \\left( \\frac{ \\sum\_{j = i - W\_{L}}^{i} PAR\_{j} } {W\_{L}} \\right)^{b\_{TR}}  & \\quad  \\psi\_i \\geq \\psi\_{crit}
     \\end{array}
 \\right.
\\end{aligned}$$

where *a*<sub>*T**R*</sub> is a coefficient derived from the mean
transition rate at observed mean understory PAR (see SI Methods S1 in
`Hanbury-Brown et al. (2022)<Hanbury-Brown2022>` for more information)
and *b*<sub>*T**R*</sub> is the light response modifier. The light
response modifier produces accelerating (i.e. light demanding) or
decelerating responses to light (Fig. 2f) depending on if
*b*<sub>*T**R*</sub> is greater or less than 1. Of a variety of
functional forms tested at BCI, a power function with species-specific
light response modifiers best explained observed variation in
recruitment rates under spatially heterogenous patch-level light
(`Rüger et al., 2009<Ruger2009b>`). This formulation is more broadly
supported by the growth-mortality functional trade-off axis where light
demanding species can take advantage of higher light conditions through
faster relative growth rates (`Wright et al., 2010<Wright2010>`).

Carbon transitioning out of the seedling layer is available to FATES’s
default recruitment subroutine which converts carbon available for
recruitment into a number density of new recruits based on the amount of
carbon required to form an individual in the smallest size class tracked
by the VDM, Z0. The number of new recruits predicted on day i,
*R*<sub>*i*</sub>, is

$$R\_i = \\frac{(TR\_i) (C\_{seedling,i}) } {Z\_0}$$

The regeneration processes represented above introduce 18 new parameters
used by FATES-TRS that are not used by default FATES.

| Parameter symbol and full parameter name | Value optimized for BCI | Units | Description |
|------------------|------------------|------------------|------------------|
| *F*<sub>*r**e**p**r**o*</sub> (fates\_trs\_seed\_alloc) | 0.1 (all PFTs) | None | Fraction of *C*<sub>*g* + *r*</sub> allocated to reproduction |
| *a*<sub>*R**A*</sub> (fates\_trs\_repro\_alloc\_a) | LD-DI: 0.0058 LD-DT: 0.0059 ST-DI: 0.0042 ST-DT: 0.0049 | *δ**R**A*\[*δ**d**b**h*\]<sup>−1</sup> | Governs RA as function of dbh (logit function coefficient) |
| *b*<sub>*R**A*</sub> (fates\_trs\_repro\_alloc\_b) | LD-DI: -3.1380 LD-DT: -2.4607 ST-DI: -2.6518 ST-DT: -2.6171 | None | Governs RA as function of dbh (intercept in logit function) |
| *F*<sub>*s**e**e**d*</sub> (fates\_trs\_repro\_frac\_seed) | 0.24 (all PFTs) | None | Fraction of reproductive C that is seed |
| *s*<sub>*m**o**r**t*</sub> (fates\_trs\_seed\_decay\_rate) | 0.51 (all PFTs) | yr-1 | Seed mortality rate |
| *d*<sub>*s**e**e**d**l**i**n**g*</sub> (fates\_trs\_seedling\_root\_depth) | 0.06 (all PFTs) | m | Seedling rooting depth |
| *a*<sub>*e**m**e**r**g*</sub> (fates\_trs\_a\_emerg) | 0.0003 | day-1 | Coefficient for seedling emergence rate |
| *b*<sub>*e**m**e**r**g*</sub> (fates\_trs\_b\_emerg) | LD-DI: 1.6 LD-DT: 1.6 ST-DI: 1.2 ST-DT: 1.2 | None | Seedling emergence sensitivity to soil moisture |
| *W*<sub>*e**m**e**r**g*</sub> (fates\_trs\_sdlng\_emerg\_h2o\_timescale) | 7 (all PFTs) | days | Time window for emergence response to soil moisture |
| *ψ*<sub>*e**m**e**r**g*</sub> (fates\_trs\_seedling\_psi\_emerg) | -15744.65 | mm H2O suction | Soil moisture required for emergence |
| *P**A**R*<sub>*c**r**i**t*</sub> (fates\_trs\_par\_crit\_germ) | 0.656 | MJ m-2 day-1 | Critical PAR level for light-sensitive germination |
| *M*<sub>*b**a**c**k**g**r**o**u**n**d*</sub> (fates\_trs\_background\_seedling\_mort) | LD-DI: 0.17 LD-DT: 0.18 ST-DI: 0.19 ST-DT: 0.11 | yr-1 | Background seedling mortality rate |
| *ψ*<sub>*c**r**i**t*</sub> (fates\_trs\_seedling\_psi\_crit) | DI: -175912.9 DT: -251995.7 | mm H2O suction | Seedling moisture stress threshold |
| *M**D**D*<sub>*c**r**i**t*</sub> (fates\_trs\_seedling\_mdd\_crit) | DI: 46E5 DT: 14E5 | mm H2O suction days | Moisture deficit day threshold for seedling mortality |
| *a*<sub>*ψ*</sub> (fates\_trs\_seedling\_h2o\_mort\_a) | DI: 1.04E-16 DT: 4.07E-17 | None | Moisture-based mortality coefficient |
| *b*<sub>*ψ*</sub> (fates\_trs\_seedling\_h2o\_mort\_b) | DI:-5.5E-10 DT:-6.4E-11 | None | Moisture-based mortality coefficient |
| *c*<sub>*ψ*</sub> (fates\_trs\_seedling\_h2o\_mort\_c) | DI:3.5E-04 DT:1.3E-05 | None | Moisture-based mortality coefficient |
| *W*<sub>*ψ*</sub> (fates\_trs\_sdlng\_mdd\_timescale) | 126 (all PFTs) | days | Time window for MDD |
| *a*<sub>*M**L*</sub> (fates\_trs\_seedling\_light\_mort\_a) | LD:-0.033 ST:-0.00990 | None | Light-based mortality coefficient |
| *b*<sub>*M**L*</sub> (fates\_trs\_seedling\_light\_mort\_b) | LD:-3.84 ST:-7.15 | None | Light-based mortality coefficient |
| *W*<sub>*L*</sub> (fates\_trs\_sdlng\_mort\_par\_timescale) | 32 (all PFTs) | days | Time window for seedling light response |
| *a*<sub>*T**R*</sub> (fates\_trs\_seedling\_light\_rec\_a) | LD:0.010 ST:0.007 | None | Seedling to sapling transition rate coefficient |
| *b*<sub>*T**R*</sub> (fates\_trs\_seedling\_light\_rec\_b) | LD: 1.0653 ST: 0.8615 | None | Recruitment light response parameter |
| *H*<sub>*m**i**n*</sub> (fates\_trs\_recruit\_hgt\_min) | 2.345 | m | Min height of a new recruit |
| fates\_trs\_regeneration\_model | 2 | None | Switch to choose regeneration mode (1: default FATES 2: TRS 3: TRS no seedling dynamics) |

Tree Recruitment Scheme Parameters. LD = light-demanding, ST =
shade-tolerant, DT = drought-tolerant, DI = drought-intolerant.

## Litter Production and Fragmentation

The original CLM4.5 model contains streams of carbon pertaining to
different chemical properties of litter (lignin, cellulose and labile
streams, specifically). In FATES model, the fire simulation scheme in
the SPITFIRE model requires that the model tracks the pools of litter
pools that differ with respect to their propensity to burn (surface
area-volume ratio, bulk density etc.). Therefore, this model contains
more complexity in the representation of coarse woody debris. We also
introduce the concept of ’fragmenting’ pools, which are pools that can
be burned, but are not available for decomposition or respiration. In
this way, we can both maintain above-ground pools that affect the rate
of burning, and the lag between tree mortality and availability of woody
material for decomposition.  
FATES recognizes four classes of litter. Above- and below-ground coarse
woody debris (*C**W**D*<sub>*A**G*</sub>, *C**W**D*<sub>*B**G*</sub>)
and leaf litter (*l*<sub>*l**e**a**f*</sub> and fine root litter
*l*<sub>*r**o**o**t*</sub>). All pools are represented per patch, and
with units of kGC m<sup>−</sup>2. Further to this,
*C**W**D*<sub>*A**G*</sub>, *C**W**D*<sub>*B**G*</sub> are split into
four litter size classes (*l**s**c*) for the purposes of proscribing
this to the SPITFIRE fire model (seed ’Fuel Load’ section for more
detail. 1-hour (twigs), 10-hour (small branches), 100-hour (large
branches) and 1000-hour(boles or trunks). 4.5 %, 7.5%, 21 % and 67% of
the woody biomass
(*C*<sub>*s**t**o**r**e*, *c**o**h*</sub> + *C*<sub>*s**w*, *c**o**h*</sub>)
is partitioned into each class, respectively. If the cohort dbh is
smaller than the fuel class size threshold specified by the
<span class="title-ref">fates\_frag\_cwd\_frac</span> parameter then no
biomass is sent to that class. The relative proportions of biomass sent
to each of the remaining fuel classes are preserved.

*l*<sub>*l**e**a**f*</sub> and *l*<sub>*r**o**o**t*</sub> are indexed by
plant functional type (*f**t*). The rational for indexing leaf and fine
root by PFT is that leaf and fine root matter typically vary in their
carbon:nitrogen ratio, whereas woody pools typically do not.

Rates of change of litter, all in kGC m<sup>−</sup>2 year<sup>−1</sup>,
are calculated as

$$\\frac{\\delta CWD\_{AG,out,lsc}}{ \\delta t }= CWD\_{AG,in,lsc} - CWD\_{AG,out,lsc}$$

$$\\frac{\\delta CWD\_{BG,out,lsc}}{ \\delta t } = CWD\_{BG,in,lsc} - CWD\_{BG,in,lsc}$$

$$\\frac{\\delta l\_{leaf,out,ft} }{ \\delta t } = l\_{leaf,in,ft} -  l\_{leaf,out,ft}$$

$$\\frac{\\delta l\_{root,out,ft} }{ \\delta t } = l\_{root,in,ft} - l\_{root,out,ft}$$

### Litter Inputs

Inputs into the litter pools come from tissue turnover, mortality of
canopy trees, mortality of understorey trees, mortality of seeds, and
leaf senescence of deciduous plants.

$$l\_{leaf,in,ft} =\\Big(\\sum\_{i=1}^{n\_{coh,ft}} n\_{coh}(l\_{md,coh}  + l\_{leaf,coh}) + M\_{t,coh}.C\_{leaf,coh}\\Big)/\\sum\_{p=1}^{n\_{pat}}A\_{patch}$$

where *l*<sub>*m**d*, *c**o**h*</sub> is the leaf turnover rate for
evergreen trees and *l*<sub>*l**e**a**f*, *c**o**h*</sub> is the leaf
loss from phenology in that timestep (KgC *m*<sup>−2</sup>.
*M*<sub>*t*, *c**o**h*</sub> is the total mortality flux in that
timestep (in individuals). For fine root input.
*n*<sub>*c**o**h*, *f**t*</sub> is the number of cohorts of functional
type ‘*F**T*’ in the current patch.

$$l\_{root,in,ft} =\\Big(\\sum\_{i=1}^{n\_{coh,ft}} n\_{coh}(r\_{md,coh} ) + M\_{t,coh}.C\_{root,coh}\\Big)/\\sum\_{p=1}^{n\_{pat}}A\_p$$

where *r*<sub>*m**d*, *c**o**h*</sub> is the root turnover rate. For
coarse woody debris input (*C**W**D*<sub>*A**G*, *i**n*, *l**s**c*</sub>
, we first calculate the sum of the mortality
*M*<sub>*t*, *c**o**h*</sub>.(*C*<sub>*s**t**r**u**c*, *c**o**h*</sub> + *C*<sub>*s**w*, *c**o**h*</sub>)
and turnover *n*<sub>*c**o**h*</sub>(*w*<sub>*m**d*, *c**o**h*</sub>)
fluxes, then separate these into size classes and above/below ground
fractions using the fixed fractions assigned to each
(*f*<sub>*l**s**c*</sub> and *f*<sub>*a**g*</sub>)

$$\\mathit{CWD}\_{AG,in,lsc} =\\Big(f\_{lsc}.f\_{ag}\\sum\_{i=1}^{n\_{coh,ft}}n\_{coh}w\_{md,coh}  + M\_{t,coh}.(C\_{struc,coh}+C\_{sw,coh})\\Big)/\\sum\_{p=1}^{n\_{pat}}A\_p$$

$$\\mathit{CWD}\_{BG,in,lsc} =\\Big(f\_{lsc}.(1-f\_{ag})\\sum\_{i=1}^{n\_{coh,ft}}n\_{coh}w\_{md,coh}  + M\_{t,coh}.(C\_{struc,coh}+C\_{sw,coh})\\Big)/\\sum\_{p=1}^{n\_{pat}}A\_p$$

### Litter Outputs

The fragmenting litter pool is available for burning but not for
respiration or decomposition. Fragmentation rates are calculated
according to a maximum fragmentation rate
(*α*<sub>*c**w**d*, *l**s**c*</sub> or *α*<sub>*l**i**t**t**e**r*</sub>)
which is ameliorated by a temperature and water dependent scalar
*S*<sub>*t**w*</sub>. The form of the temperature scalar is taken from
the existing CLM4.5BGC decomposition cascade calculations). The water
scaler is equal to the water limitation on photosynthesis (since the
CLM4.5BGC water scaler pertains to the water potential of individual
soil layers, which it is difficult to meaningfully average, given the
non-linearities in the impact of soil moisture). The scaler code is
modular, and new functions may be implemented trivially. Rate constants
for the decay of the litter pools are extremely uncertain in literature,
as few studies either separate litter into size classes, nor examine its
decomposition under non-limiting moisture and temperature conditions.
Thus, these parameters should be considered as part of sensitivity
analyses of the model outputs.

*C**W**D*<sub>*A**G*, *o**u**t*, *l**s**c*</sub> = *C**W**D*<sub>*A**G*, *l**s**c*</sub>.*α*<sub>*c**w**d*, *l**s**c*</sub>.*S*<sub>*t**w*</sub>

*C**W**D*<sub>*B**G*, *o**u**t*, *l**s**c*</sub> = *C**W**D*<sub>*B**G*, *l**s**c*</sub>.*α*<sub>*c**w**d*, *l**s**c*</sub>.*S*<sub>*t**w*</sub>

*l*<sub>*l**e**a**f*, *o**u**t*, *f**t*</sub> = *l*<sub>*l**e**a**f*, *f**t*</sub>.*α*<sub>*l**i**t**t**e**r*</sub>.*S*<sub>*t**w*</sub>

*l*<sub>*r**o**o**t*, *o**u**t*, *f**t*</sub> = *l*<sub>*r**o**o**t*, *f**t*</sub>.*α*<sub>*r**o**o**t*, *f**t*</sub>.*S*<sub>*t**w*</sub>

### Flux into decompsition cascade

Upon fragmentation and release from the litter pool, carbon is
transferred into the labile, lignin and cellulose decomposition pools.
These pools are vertically resolved in the biogeochemistry model. The
movement of carbon into each vertical layer is obviously different for
above- and below-ground fragmenting pools. For each layer *z* and
chemical litter type *i*, we derive a flux from ED into the
decomposition cascade as *E**D*<sub>*l**i**t*, *i*, *z*</sub> (kGC
m<sup>−2</sup> s<sup>−1</sup>)

where *t*<sub>*c*</sub> is the time conversion factor from years to
seconds, *f*<sub>*l**a**b*, *l*</sub>, *f*<sub>*c**e**l*, *l*</sub> and
*f*<sub>*l**i**g*, *l*</sub> are the fractions of labile, cellulose and
lignin in leaf litter, and *f*<sub>*l**a**b*, *r*</sub>,
*f*<sub>*c**e**l*, *r*</sub> and *f*<sub>*l**i**g*, *r*</sub> are their
counterparts for root matter. Similarly, *l*<sub>*p**r**o**f*</sub>,
*r*<sub>*f*, *p**r**o**f*</sub>and *r*<sub>*c*, *p**r**o**f*</sub> are
the fractions of leaf, coarse root and fine root matter that are passed
into each vertical soil layer *z*, derived from the CLM(BGC) model.

\bigskip
\captionof{table}{Parameters needed for litter model.  }

| Parameter Symbol | Parameter Name | Units | indexed by |
|------------------|------------------|------------------|------------------|
| *α*<sub>*c**w**d*, *l**s**c*</sub> | Maximum fragmentation rate of CWD | y<sup>−1</sup> |  |
| *α*<sub>*l**i**t**t**e**r*</sub> | Maximum fragmentation rate of leaf litter | y<sup>−1</sup> |  |
| *α*<sub>*r**o**o**t*</sub> | Maximum fragmentation rate of fine root litter | y<sup>−1</sup> |  |
| *f*<sub>*l**a**b*, *l*</sub> | Fraction of leaf mass in labile carbon pool | none |  |
| *f*<sub>*c**e**l*, *l*</sub> | Fraction of leaf mass in cellulose carbon pool | none |  |
| *f*<sub>*l**i**g*, *l*</sub> | Fraction of leaf mass in lignin carbon pool | none |  |
| *f*<sub>*l**a**b*, *r*</sub> | Fraction of root mass in labile carbon pool | none |  |
| *f*<sub>*c**e**l*, *r*</sub> | Fraction of root mass in cellulose carbon pool | none |  |
| *f*<sub>*l**i**g*, *r*</sub> | Fraction of root mass in lignin carbon pool | none |  |
| *l*<sub>*p**r**o**f*, *z*</sub> | Fraction of leaf matter directed to soil layer z | none | soil layer |
| *r*<sub>*c*, *p**r**o**f*, *z*</sub> | Fraction of coarse root matter directed to soil layer z | none | soil layer |
| *r*<sub>*f*, *p**r**o**f*, *z*</sub> | Fraction of fine root matter directed to soil layer z | none | soil layer |

\bigskip 

## Disturbance

FATES allows disturbance through three processes: (1) mortality of
canopy trees, (2) fire, (3) anthropogenic disturbance. Each of these is
discussed in more detail below. For the case of canopy tree mortality,
some fraction of the crown area *f*<sub>*d*</sub> of deceased trees is
used to generate newly-disturbed patch area, while the rest
(1 − *f*<sub>*d*</sub>) remains in the existing patch. Thus varying
*f*<sub>*d*</sub> from zero to 1 can lead to three different cases of
how mortlaity leads to disturbance. If *f*<sub>*d*</sub> = 1, then all
canopy area is converted into newly-disturbed patch area, and a fraction
of understory trees equal to the ratio of dying-tree crown are a to the
patches area are moved to the newly-disturbed patch, at which time they
are promoted to the canopy of the new patch; this is labeled below as
the 'Pure ED' case. For those trees that are moved to the new patch,
some fraction of these will die due to impacts from the disturbance
process itself, this fraction *i*<sub>*d*</sub> is currently a global
parameter for all individual-tree disturbance processes, with a default
value of 0.55983. If *f*<sub>*d*</sub> = 0, then no disturbance occurs
and all mortality is accomodated by promotion of trees from the
understory to the canopy within a patch; this is the structure of the
PPA formulation as described in `Purves et al. 2008<purves2008>`, and is
labelled below as 'Pure PPA'. If 0 &gt; *f*<sub>*d*</sub> &gt; 1, then
some both processes of promotion within a patch and promotion into a new
patch occur. A special case of this is when all trees that would be
moved into the new patch are killed in the process, thus guaranteeing
that newly-disturbed patches are devoid of any surviving trees; this is
blabelled below as the 'bare-ground intermediate case'.

<figure>
<img src="images/Disturbance_schematic.png" />
</figure>

## Plant Mortality

Total plant mortality per cohort *M*<sub>*t*, *c**o**h*</sub>, (fraction
year<sup>−1</sup>) is simulated as the sum of several additive terms,

*M*<sub>*t*, *c**o**h*</sub> = *M*<sub>*b*, *c**o**h*</sub> + *M*<sub>*c**s*, *c**o**h*</sub> + *M*<sub>*h**f*, *c**o**h*</sub> + *M*<sub>*f*, *c**o**h*</sub> + *M*<sub>*i*, *c**o**h*</sub> + *M*<sub>*f**r*, *c**o**h*</sub> + *M*<sub>*s*, *c**o**h*</sub> + *M*<sub>*a*, *c**o**h*</sub>,

where *M*<sub>*b*</sub> is the background mortality that is unaccounted
by any of the other mortality rates and is fixed at a constant
PFT-dependent rate in the parameter file.

*M*<sub>*c**s*</sub> is the carbon starvation derived mortality, which
is a function of the non-structural carbon storage term
*C*<sub>*s**t**o**r**e*, *c**o**h*</sub> and the ‘target’ leaf biomass,
*C̀*<sub>*l**e**a**f*, *c**o**h*</sub>, as follows:

$$\\begin{aligned}
M\_{cs} = \\left\\{ \\begin{array}{ll}
M\_{cs,max} (1-C\_{store,coh}/\\grave{C}\_{leaf,coh})& C\_{store,coh}&lt;\\grave{C}\_{leaf,coh}\\\\
&\\\\
0& C\_{store,coh} &gt;= \\grave{C}\_{leaf,coh}\\\\
\\end{array} \\right.
\\end{aligned}$$

where *M*<sub>*c**s*, *m**a**x*</sub> is the maximum rate of carbon
storage mortality parameter, or the maximum rate of trees in a landscape
that will die when their carbon stores are exhausted. This parameter is
needed to scale from individual-level mortality simulation to grid-cell
average conditions.

Thus FATES implicitly assumes that there is a critical storage pool
*C*<sub>*s**t**o**r**e*, *c**o**h*, *c**r**i**t**i**c**a**l*</sub> = *C̀*<sub>*l**e**a**f*, *c**o**h*</sub>
that sets the total-plant storage level where mortality begins; the
implied parameter
*C*<sub>*s**t**o**r**e*, *c**o**h*, *c**r**i**t**i**c**a**l*</sub>/*C̀*<sub>*l**e**a**f*, *c**o**h*</sub> = 1
could be made explicit, but we left this as an implicit parameter here
due to the generally weak data constraints on it at present. Because
both the increase in mortality and the decrease in respiration (see
section 'Respiration') begin when
*C*<sub>*s**t**o**r**e*, *c**o**h*</sub> drops below
*C̀*<sub>*l**e**a**f*, *c**o**h*</sub>, and
*C̀*<sub>*s**t**o**r**e*, *c**o**h*</sub> = *r*<sub>*s**t**o**r**e*</sub>*C̀*<sub>*l**e**a**f*, *c**o**h*</sub>,
the parameter *r*<sub>*s**t**o**r**e*</sub> − 1, thus sets the size of
the carbon storage buffer that determines how much cumulative negative
NPP a plant can experience before it begins to suffer from carbon
starvation.

Mechanistic simulation of hydraulic failure is not undertaken on account
of it’s mechanistic complexity (see
`McDowell et al. 2013<Mcdowelletal2013>` for details). Instead, we use a
proxy for hydraulic failure induced mortality
(*M*<sub>*h**f*, *c**o**h*</sub>) that uses a water potential threshold
beyond which mortality is triggered, such that the tolerance of low
water potentials is a function of plant functional type (as expressed
via the *ψ*<sub>*c*</sub> parameter). For each day that the aggregate
water potential falls below a threshold value, a set fraction of the
trees are killed. To prevent hydraulic failure mortality of vegetation
at high latitudes, *M*<sub>*h**f*, *c**o**h*</sub> = 0 when the
temperature of any soil layer (*t* − *s**o**i**s**n**o* − *s**l*) falls
below -2 degrees C. The aggregation of soil moisture potential across
the root zone is expressed using the *β* function. We thus determine
plant mortality caused by extremely low water potentials as

$$\\begin{aligned}
M\_{hf,coh} = \\left\\{ \\begin{array}{ll}
S\_{m,ft}& \\textrm{for } \\beta\_{ft} &lt; 10^{-6}  \\textrm{and } min(t-soisno-sl) &gt;= -2.0\\\\
&\\\\
0.0& \\textrm{for } \\beta\_{ft}&gt;= 10^{-6} \\textrm{and } min(t-soisno-sl) &lt;  -2.0.\\\\
\\end{array} \\right.
\\end{aligned}$$

The threshold value of 10<sup>−6</sup> represents a state where the
average soil moisture potential is within 10<sup>−6</sup> of the wilting
point (a PFT specific parameter *θ*<sub>*w*, *f**t*</sub>).

*M*<sub>*f*, *c**o**h*</sub> is the fire-induced mortality, as described
in the fire modelling section.

Impact mortality [M](){i,coh} occurs to understory trees that are kille
dduring the process of disturbance, as described above.

*M*<sub>*s*, *c**o**h*</sub> and *M*<sub>*a*, *c**o**h*</sub> are size-
and age-dependent mortality respectively. These terms model a gradual
increase in mortality rate with either cohort DBH (cm) or cohort age. We
model *M*<sub>*s*, *c**o**h*</sub> as:

$$M\_{s,coh} = \\frac{1}{1 + e^{(-r\_s \* (DBH - p\_s))}}$$

where *D**B**H* is diameter at breast height in cm, *r*<sub>*s*</sub> is
the rate that mortality increases with DBH, and *p*<sub>*s*</sub> is the
inflection point of the curve, i.e. the DBH at which annual mortality
rate has increased to 50%. We model *M*<sub>*a*, *c**o**h*</sub> as :

$$M\_{a,coh} = \\frac{1}{1 + e^{(-r\_a \* (age - p\_a))}}$$

where *a**g**e* is cohort age in years, *r*<sub>*a*</sub> is the rate
that mortality increases with age, and *p*<sub>*a*</sub> is the
inflection point of the curve, i.e. the age at which annual mortality
rate has increased to 50%.

Cohort age is not tracked in default FATES. In order to have
age-dependent mortality on, set the flag
use\_fates\_cohort\_age\_tracking to .true. in the FATES namelist
options. To turn on either size- or age-dependent mortality set the *p*
and *r* parameters to sensible values in the FATES parameter file.

\bigskip
\captionof{table}{Parameters needed for mortality model.  }

| Parameter Symbol | Parameter Name | Units | indexed by |
|--------------------|------------------------------|--------|-------------|
| *S*<sub>*m*, *f**t*</sub> | Stress Mortality Scaler | none |  |
| *l*<sub>*t**a**r**g*, *f**t*</sub> | Target carbon storage fraction | none | ft |

\bigskip 

## Fire (SPITFIRE)

The influence of fire on vegetation is estimated using the SPITFIRE
model, which has been modified for use in ED following it’s original
implementation in the LPJ-SPITFIRE model
(`Thonicke et al. 2010<thonickeetal2010>`,
`Pfeiffer et al. 2013<pfeiffer2013>`). This model as described is
substantially different from the existing CLM4.5 fire model
`Li et al. 2012<Lietal2012a>`, however, further developments are
intended to increase the merging of SPITFIRE’s natural vegetation fire
scheme with the fire suppression, forest-clearing and peat fire
estimations in the existing model. The coupling to the ED model allows
fires to interact with vegetation in a size-structured manner, so small
fires can burn only understorey vegetation. Also, the patch structure
and representation of succession in the ED model allows the model to
track the impacts of fire on different forest stands, therefore removing
the problem of area-averaging implicit in area-based DGVMs. The SPITFIRE
approach has also been coupled to the LPJ-GUESS individual-based model
(Forrest et al. in prep) and so this is not the only implementation of
this type of scheme in existence.

The SPITFIRE model operates at a daily timestep and at the patch level,
meaning that different litter pools and vegetation charecteristics of
open and closed forests can be represented effectively (we omit the
<span class="title-ref">patch</span> subscript throughout for
simplicity).

### Properties of fuel load

Many fire processes are impacted by the properties of the litter pool in
the SPITFIRE model. There are one live (live grasses) and five dead fuel
categories (dead leaf litter and four pools of coarse woody debris).
Coarse woody debris is classified into 1h, 10h, 100h, and 1000h fuels,
defined by the order of magnitude of time required for fuel to lose (or
gain) 63% of the difference between its current moisture content and the
equilibrium moisture content under defined atmospheric conditions.
`Thonicke et al. 2010<thonickeetal2010>`. For the purposes of describing
the behaviour of fire, we introduce a new index 'fuel class' *fc*, the
values of which correspond to each of the six possible fuel categories
as follows.

| *fc* index | Fuel type        | Drying Time |
|------------|------------------|-------------|
| 1          | dead grass       | n/a         |
| 2          | twigs            | 1h fuels    |
| 3          | small branches   | 10h fuel    |
| 4          | large branches   | 100h fuel   |
| 5          | stems and trunks | 1000h fuel  |
| 6          | live grasses     | n/a         |

\bigskip 

### Nesterov Index

Dead fuel moisture ($\\emph{moist}\_{df,fc}$), and several other
properties of fire behaviour, are a function of the ‘Nesterov Index’
(*N*<sub>*I*</sub>) which is an accumulation over time of a function of
temperature and humidity (Eqn 5,
`Thonicke et al. 2010<Thonickeetal2010>`),

*N*<sub>*I*</sub> = ∑max(*T*<sub>*d*</sub>(*T*<sub>*d*</sub> − *D*), 0)

where *T*<sub>*d*</sub> is the daily mean temperature in <sup>*o*</sup>C
and *D* is the dew point calculated as .

$$\\begin{aligned}
\\begin{aligned}
\\upsilon&=&\\frac{17.27T\_{d}}{237.70+T\_{d}}+\\log(RH/100)\\\\
D&=&\\frac{237.70\\upsilon}{17.27-\\upsilon}\\end{aligned}
\\end{aligned}$$

where *R**H* is the relative humidity (%).

On days when the total precipitation exceeds 3.0mm, the Nesterov index
accumulator is reset back to zero.

### Fuel properties

Total fuel load *F*<sub>*t**o**t*, *p**a**t**c**h*</sub> for a given
patch is the sum of the above ground coarse woody debris and the leaf
litter, plus the alive grass leaf biomass
*b*<sub>*l*, *g**r**a**s**s*</sub> multiplied by the non-mineral
fraction (1-*M*<sub>*f*</sub>).

$$F\_{tot,patch}=\\left(\\sum\_{fc=1}^{fc=5}  CWD\_{AG,fc}+l\_{litter}+b\_{l,grass}\\right)(1-M\_{f})$$

Many of the model behaviours are affected by the patch-level weighted
average properties of the fuel load. Typically, these are calculated in
the absence of 1000-h fuels because these do not contribute greatly to
fire spread properties.

#### Dead Fuel Moisture Content

Dead fuel moisture is calculated as

$$\\emph{moist}\_{df,fc}=e^{-\\alpha\_{fmc,fc}N\_{I}}$$

where *α*<sub>*f**m**c*, *f**c*</sub> is a parameter defining how fuel
moisture content varies between the first four dead fuel classes.

#### Live grass moisture Content

The live grass fractional moisture content($\\emph{moist}\_{lg}$) is a
function of the soil moisture content. (Equation B2 in
`Thonicke et al. 2010<Thonickeetal2010>`)

$$\\emph{moist}\_{lg}=\\textrm{max}(0.0,\\frac{10}{9}\\theta\_{30}-\\frac{1}{9})$$

where *θ*<sub>30</sub> is the fractional moisture content of the top
30cm of soil.

#### Patch Fuel Moisture

The total patch fuel moisture is based on the weighted average of the
different moisture contents associated with each of the different live
grass and dead fuel types available (except 1000-h fuels).

$$F\_{m,patch}=\\sum\_{fc=1}^{fc=4}  \\frac{F\_{fc}}{F\_{tot}}\\emph{moist}\_{df,fc}+\\frac{b\_{l,grass}}{F\_{tot}}\\emph{moist}\_{lg}$$

#### Effective Fuel Moisture Content

Effective Fuel Moisture Content is used for calculations of fuel
consumed, and is a function of the ratio of dead fuel moisture content
*M*<sub>*d**f*, *f**c*</sub> and the moisture of extinction factor,
*m*<sub>*e**f*, *f**c*</sub>

$$E\_{moist,fc}=\\frac{\\emph{moist}\_{fc}}{m\_{ef,fc}}$$

where the *m*<sub>*e**f*</sub> is a function of surface-area to volume
ratio.

*m*<sub>*e**f*, *f**c*</sub> = 0.524 − 0.066log<sub>10</sub>*σ*<sub>*f**c*</sub>

#### Patch Fuel Moisture of Extinction

The patch ‘moisture of extinction’ factor (*F*<sub>*m**e**f*</sub>) is
the weighted average of the *m*<sub>*e**f*</sub> of the different fuel
classes

$$F\_{mef,patch}=\\sum\_{fc=1}^{fc=5}  \\frac{F\_{fc}}{F\_{tot}}m\_{ef,fc}+\\frac{b\_{l,grass}}{F\_{tot}}m\_{ef,grass}$$

#### Patch Fuel Bulk Density

The patch fuel bulk density is the weighted average of the bulk density
of the different fuel classes (except 1000-h fuels).

$$F\_{bd,patch}=\\sum\_{fc=1}^{fc=4} \\frac{F\_{fc}}{F\_{tot}}\\beta\_{fuel,fc}+\\frac{b\_{l,grass}}{F\_{tot}}\\beta\_{fuel,lgrass}$$

where *β*<sub>*f**u**e**l*, *f**c*</sub> is the bulk density of each
fuel size class (kG m<sup>−3</sup>)

#### Patch Fuel Surface Area to Volume

The patch surface area to volume ratio (*F*<sub>*σ*</sub>) is the
weighted average of the surface area to volume ratios
(*σ*<sub>*f**u**e**l*</sub>) of the different fuel classes (except
1000-h fuels).

$$F\_{\\sigma}=\\sum\_{fc=1}^{fc=4}  \\frac{F\_{fc}}{F\_{tot}}\\sigma\_{fuel,fc}+\\frac{b\_{l,grass}}{F\_{tot}}\\sigma\_{fuel,grass}$$

### Forward rate of spread

For each patch and each day, we calculate the rate of forward spread of
the fire *ros*<sub>*f*</sub> (nominally in the direction of the wind).

$$\\emph{ros}\_{f}=\\frac{i\_{r}x\_{i}(1+\\phi\_{w})}{F\_{bd,patch}e\_{ps}q\_{ig}}$$

*e*<sub>*p**s*</sub> is the effective heating number
($e^{\\frac{-4.528}{F\_{\\sigma,patch}}}$). *q*<sub>*i**g*</sub> is the
heat of pre-ignition (581 + 2594*F*<sub>*m*</sub>). *x*<sub>*i*</sub> is
the propagating flux calculated as (see
`Thonicke et al. 2010<Thonickeetal2010>` Appendix A).

$$x\_{i}= \\frac{e^{0.792+3.7597F\_{\\sigma,patch}^{0.5}(\\frac{F\_{bd,patch}}{p\_{d}}+0.1)}}{192+7.9095F\_{\\sigma,patch}}$$

*ϕ*<sub>*w*</sub> is the influence of windspeed on rate of spread.

*ϕ*<sub>*w*</sub> = *c**b*<sub>*w*</sub><sup>*b*</sup>.*β*<sup>−*e*</sup>

Where *b*, *c* and *e* are all functions of surface-area-volume ratio
*F*<sub>*σ*, *p**a**t**c**h*</sub>:
*b* = 0.15988*F*<sub>*σ*, *p**a**t**c**h*</sub><sup>0.54</sup>,
*c* = 7.47*e*<sup>−0.8711*F*<sub>*σ*, *p**a**t**c**h*</sub><sup>0.55</sup></sup>,
*e* = 0.715*e*<sup>−0.01094*F*<sub>*σ*, *p**a**t**c**h*</sub></sup>.
*b*<sub>*w*</sub> = 196.86*W* where *W* is the the windspeed in
ms<sup>−1</sup>, and
$\\beta=\\frac{F\_{bd}/p\_{d}}{0.200395F\_{\\sigma,patch}^{-0.8189}}$
where *p*<sub>*d*</sub> is the particle density (513).

*i*<sub>*r*</sub> is the reaction intensity, calculated using the
following set of expressions (from
`Thonicke et al. 2010<Thonickeetal2010>` Appendix A).:

$$\\begin{aligned}
\\begin{aligned}
i\_{r}&=&\\Gamma\_{opt}F\_{tot}Hd\_{moist}d\_{miner}\\\\
d\_{moist}&=&\\textrm{max}\\Big(0.0,(1-2.59m\_{w}+5.11m\_{w}^{2}-3.52m\_{w}^{3})\\Big)\\\\
m\_{w}&=&\\frac{F\_{m,patch}}{F\_{mef,patch}}\\\\
\\Gamma \_{opt}&=&\\Gamma\_{max}\\beta^{a}\\lambda\\\\
\\Gamma \_{max}&=&\\frac{1}{0.0591+2.926F\_{\\sigma,patch}^{-1.5}}\\\\
\\lambda&=&e^{a(1-\\beta)}\\\\
a&=&8.9033F\_{\\sigma,patch}^{-0.7913}\\end{aligned}
\\end{aligned}$$

*Γ*<sub>*o**p**t*</sub> is the residence time of the fire, and
*d*<sub>*m**i**n**e**r*</sub> is the mineral damping coefficient (=0.174
*S*<sub>*e*</sub><sup>−0.19</sup> , where *S*<sub>*e*</sub> is 0.01 and
so = *d*<sub>*m**i**n**e**r*</sub> 0.41739).

### Fuel Consumption

The fuel consumption (fraction of biomass pools) of each dead biomass
pool in the area affected by fire on a given day
(*f*<sub>*c*, *d**e**a**d*, *f**c*</sub>) is a function of effective
fuel moisture *E*<sub>*m**o**i**s**t*, *f**c*</sub> and size class *fc*
(Eqn B1, B4 and B5, `Thonicke et al. 2010<Thonickeetal2010>`). The
fraction of each fuel class that is consumed decreases as its moisture
content relative to its moisture of extinction
(*E*<sub>*m**o**i**s**t*, *f**c*</sub>) increases.

*f*<sub>*c**d**e**a**d*, *f**c*</sub> = max(0, min(1, *m*<sub>*i**n**t*, *m**c*, *f**c*</sub> − *m*<sub>*s**l**o**p**e*, *m**c*, *f**c*</sub>*E*<sub>*m**o**i**s**t*, *f**c*</sub>))

*m*<sub>*i**n**t*</sub> and *m*<sub>*s**l**o**p**e*</sub> are
parameters, the value of which is modulated by both size class *f**c*
and by the effective fuel moisture class *m**c*, defined by
*E*<sub>*m**o**i**s**t*, *f**c*</sub>. *m*<sub>*i**n**t*</sub> and
*m*<sub>*s**l**o**p**e*</sub> are defined for low-, mid-, and
high-moisture conditions, the boundaries of which are also functions of
the litter size class following `Peterson and Ryan 1986 <Peterson1986>`
(page 802). The fuel burned, *f*<sub>*c**g**r**o**u**n**d*, *f**c*</sub>
(Kg m<sup>−2</sup> day<sup>−1</sup>) iscalculated from
*f*<sub>*c**d**e**a**d*, *f**c*</sub> for each fuel class:

$$f\_{cground,fc}=f\_{c,dead,fc}(1-M\_{f})\\frac{F\_{fc}}{0.45}$$

Where 0.45 converts from carbon to biomass. The total fuel consumption,
*f*<sub>*c**t**o**t*, *p**a**t**c**h*</sub>(Kg m<sup>−2</sup>), used to
calculate fire intensity, is then given by

$$f\_{ctot,patch}=\\sum\_{fc=1}^{fc=4} f\_{c,ground,fc} +  f\_{c,ground,lgrass}$$

There is no contribution from the 1000 hour fuels to the patch-level
*f*<sub>*c**t**o**t*, *p**a**t**c**h*</sub> used in the fire intensity
calculation.

### Fire Intensity

Fire intensity at the front of the burning area
(*I*<sub>*s**u**r**f**a**c**e*</sub>, kW m<sup>−2</sup>) is a function
of the total fuel consumed (*f*<sub>*c**t**o**t*, *p**a**t**c**h*</sub>)
and the rate of spread at the front of the fire, *r**o**s*<sub>*f*</sub>
(m min<sup>−1</sup>) (Eqn 15 `Thonicke et al. 2010<Thonickeetal2010>`)

$$I\_{surface}=\\frac{0.001}{60}f\_{energy} f\_{ctot,patch}\\mathit{ros}\_{f}$$

where *f*<sub>*e**n**e**r**g**y*</sub> is the energy content of fuel
(Kj/Kg - the same, 18000 Kj/Kg for all fuel classes). Fire intensity is
used to define whether an ignition is successful. If the fire intensity
is greater than 50Kw/m then the ignition is successful.

### Fire Duration

Fire duration is a function of the fire danger index with a maximum
length of *F*<sub>*d**u**r*, *m**a**x*</sub> (240 minutes in
`Thonicke et al. 2010<Thonickeetal2010>` Eqn 14, derived from Canadian
Forest Fire Behaviour Predictions Systems)

$$D\_{f}=\\textrm{min}\\Big(F\_{dur,max},\\frac{F\_{dur,max}}{1+F\_{dur,max}e^{-11.06fdi}}\\Big)$$

### Fire Danger Index

Fire danger index (*fdi*) is a representation of the effect of
meteorological conditions on the likelihood of a fire. It is calculated
for each gridcell as a function of the Nesterov Index . $\\emph{fdi}$ is
calculated from *N**I* as

$$\\emph{fdi}=1-e^{\\alpha N\_{I}}$$

where *α* = 0.00037 following `Venevsky et al. 2002<venevsky2002>`.

### Area Burned

Total area burnt is assumed to be in the shape of an ellipse, whose
major axis *f*<sub>*l**e**n**g**t**h*</sub> (m) is determined by the
forward and backward rates of spread (*r**o**s*<sub>*f*</sub> and
*r**o**s*<sub>*b*</sub> respectively).

*f*<sub>*l**e**n**g**t**h*</sub> = *F*<sub>*d*</sub>(*r**o**s*<sub>*b*</sub> + *r**o**s*<sub>*f*</sub>)

*r**o**s*<sub>*b*</sub> is a function of *r**o**s*<sub>*f*</sub> and
windspeed (Eqn 10 `Thonicke et al. 2010<Thonickeetal2010>`)

*r**o**s*<sub>*b*</sub> = *r**o**s*<sub>*f*</sub>*e*<sup>−0.012*W*</sup>

The minor axis to major axis ratio (i.e. the length-to-breadth ratio)
*l*<sub>*b*</sub> of the ellipse is determined by the windspeed. If the
windspeed (*W*) is less than 16.67 m min<sup>−1</sup> (i.e., 1 km hr
<sup>−1</sup>) then *l*<sub>*b*</sub> = 1. Otherwise (Eqn 12 and 13,
`Thonicke et al. 2010<Thonickeetal2010>`, Eqn 79 and 80 Canadian Forest
Fire Behavior Prediction System Ont.Inf.Rep. ST-X-3, 1992, as corrected
in errata reported in Information Report GLC-X-10 by Bottom et al.,
2009)

$$\\begin{aligned}
l\_{b}= \\left\\{ \\begin{array}{ll}
1.0+8.729(1.0-e^{-0.108W})^{2.155},   & f\_{tree} &gt; 0.55 \\\\
&\\\\
1.1\*(3.6W^{0.0464}), & f\_{tree} &lt;= 0.55 \\\\
\\end{array} \\right\\}
\\end{aligned}$$

*f*<sub>*g**r**a**s**s*</sub> and *f*<sub>*t**r**e**e*</sub> are the
fractions of the patch surface covered by grass and trees respectively.

The total area burned (*A*<sub>*b**u**r**n*</sub> in m<sup>2</sup>) is
therefore (Eqn 11, `Thonicke et al. 2010<Thonickeetal2010>`)

$$A\_{burn}=\\frac{n\_{f}\\frac{3.1416}{4l\_{b}}(f\_{length}^{2}))}{10000}$$

where *n*<sub>*f*</sub> is the number of fires.

### Crown Damage

*c*<sub>*k*</sub> is the fraction of the crown which is consumed by the
fire. This is calculated from scorch height *H*<sub>*s*</sub>, tree
height *h* and the crown fraction parameter
*F*<sub>*c**r**o**w**n*</sub> (Eqn 17
`Thonicke et al. 2010<Thonickeetal2010>`):

$$\\begin{aligned}
c\_{k} = \\left\\{ \\begin{array}{ll}
0 & \\textrm{for $H\_{s}&lt;(h-hF\_{crown})$}\\\\
1-\\frac{h-H\_{s}}{h-F\_{crown}}& \\textrm{for $h&gt;H\_{s}&gt;(h-hF\_{crown})$}\\\\
1 & \\textrm{for $H\_{s}&gt;h$ }
\\end{array} \\right.
\\end{aligned}$$

The scorch height *H*<sub>*s*</sub> (m) is a function of the fire
intensity, following `Byram, 1959<byram1959>`, and is proportional to a
plant functional type specific parameter *α*<sub>*s*, *f**t*</sub> (Eqn
16 `Thonicke et al. 2010<Thonickeetal2010>`):

$$H\_{s}=\\sum\_{FT=1}^{NPFT}{\\alpha\_{s,p}\\cdot f\_{biomass,ft}} I\_{surface}^{0.667}$$

where *f*<sub>*b**i**o**m**a**s**s*, *f**t*</sub> is the fraction of the
above-ground biomass in each plant functional type.

### Cambial Damage and Kill

The cambial kill is a function of the fuel consumed
*f*<sub>*c*, *t**o**t*</sub>, the bark thickness *t*<sub>*b*</sub>, and
*τ*<sub>*l*</sub>, the duration of cambial heating (minutes) (Eqn 8,
`Peterson and Ryan 1986<peterson1986>`):

$$\\tau\_{l}=\\sum\_{fc=1}^{fc=5}39.4F\_{p,c}\\frac{10000}{0.45}(1-(1-f\_{c,dead,fc})^{0.5})$$

Bark thickness is a linear function of tree diameter
*d**b**h*<sub>*c**o**h*</sub>, defined by PFT-specific parameters
*β*<sub>1, *b**t*</sub> and *β*<sub>2, *b**t*</sub> (Eqn 21
`Thonicke et al. 2010<Thonickeetal2010>`):

*t*<sub>*b*, *c**o**h*</sub> = *β*<sub>1, *b**t*, *f**t*</sub> + *β*<sub>2, *b**t*, *f**t*</sub>*d**b**h*<sub>*c**o**h*</sub>

The critical time for cambial kill, *τ*<sub>*c*</sub> (minutes) is given
as (Eqn 20 `Thonicke et al. 2010<Thonickeetal2010>`):

*τ*<sub>*c*</sub> = 2.9*t*<sub>*b*</sub><sup>2</sup>

The mortality rate caused by cambial heating *τ*<sub>*p**m*</sub> of
trees within the area affected by fire is a function of the ratio
between *τ*<sub>*l*</sub> and *τ*<sub>*c*</sub> (Eqn 19,
`Thonicke et al. 2010<Thonickeetal2010>`):

$$\\begin{aligned}
\\tau\_{pm} = \\left\\{ \\begin{array}{ll}
1.0 & \\textrm{for } \\tau\_{1}/\\tau\_{c}\\geq \\textrm{2.0}\\\\
0.563(\\tau\_{l}/\\tau\_{c}))-0.125 & \\textrm{for } \\textrm{2.0} &gt; \\tau\_{1}/\\tau\_{c}\\ge \\textrm{0.22}\\\\
0.0 & \\textrm{for } \\tau\_{1}/\\tau\_{c}&lt; \\textrm{0.22}\\\\
\\end{array} \\right.
\\end{aligned}$$

\bigskip
\captionof{table}{Parameters needed for fire model.  }

| Parameter Symbol | Parameter Name | Units | indexed by |
|------------------|------------------|------------------|------------------|
| *β*<sub>1, *b**t*</sub> | Intercept of bark thickness function | mm | *FT* |
| *β*<sub>2, *b**t*</sub> | Slope of bark thickness function | mm cm<sup>−1</sup> | *FT* |
| *F*<sub>*c**r**o**w**n*</sub> | Ratio of crown height to total height | none | *FT* |
| *α*<sub>*f**m**c*</sub> | Fuel moisture parameter | <sup>*o*</sup>C <sup>−2</sup> | *fc* |
| *β*<sub>*f**u**e**l*</sub> | Fuel Bulk Density | kG m<sup>−3</sup> | *fc* |
| *σ*<sub>*f**u**e**l*, *f**c*</sub> | Surface area to volume ratio | cm <sup>−1</sup> | *fc* |
| *m*<sub>*i**n**t*</sub> | Intercept of fuel burned | none | *f**c*, moisture class |
| *m*<sub>*s**l**o**p**e*</sub> | Slope of fuel burned | none | *f**c*, moisture class |
| *M*<sub>*f*</sub> | Fuel Mineral Fraction |  |  |
| *F*<sub>*d**u**r*, *m**a**x*</sub> | Maximum Duration of Fire | Minutes |  |
| *f*<sub>*e**n**e**r**g**y*</sub> | Energy content of fuel | kJ/kG |  |
| *α*<sub>*s*</sub> | Flame height parameter |  | *FT* |

## Land Use, Land Use Change, and Forestry

The demographic representation in FATES allows for a complex
representation of land use change and its legacies. FATES uses the patch
concept to apply to both natural and anthropogenic disturbance
histories. Thus each patch can be indexed by both a continuous variable
(patch age) and a categorical variable (patch land use label). FATES
treats two distinct types of anthropogenic disturbance: logging and land
use change. Logging causes trees to be harvested, and the land that
those trees had grown on to become disturbed. Land use change is
represented as a disturbance rate that updates the land use label of the
resulting patch, and may lead to harvest or other changes during the
land use change disturbance.

### Wood Harvest

Over half of all tropical forests have been cleared or logged, and
almost half of standing old-growth tropical forests are designated by
national forest services for timber production
(`Sist et al., 2015<sistetal2015>`). Disturbances that result from
logging are known to cause forest degradation at the same magnitude as
deforestation each year in terms of both geographic extent and
intensity, with widespread collateral damage to remaining trees,
vegetation and soils, leading to disturbance to water, energy, and
carbon cycling, as well as ecosystem integrity
(`Keller et al., 2004 <kelleretal2004>`;
`Asner et al., 2004 <asneretal2004>`).

The selective logging module in FATES mimics the ecological,
biophysical, and biogeochemical processes following a logging event. The
module (1) specifies the timing and areal extent of a logging event; (2)
calculates the fractions of trees that are damaged by direct felling,
collateral damage, and infrastructure damage, and adds these
size-specific plant mortality types to FATES; (3) splits the logged
patch into disturbed and intact new patches; (4) applies the calculated
survivorship to cohorts in the disturbed patch; and (5) transports
harvested logs off-site by adding the remaining necromass from damaged
trees into coarse woody debris and litter pool.

#### Logging practices

The logging module struture and parameterization is based on detailed
field and remote sensing studies (`Putz et al., 2008<putzetal2008>`;
`Asner et al., 2004 <asneretal2004>`;
`Pereira Jr et al., 2002 <Pereirajretal2002>`;
`Asner et al., 2005 <asneretal2005>`;
`Feldpausch et al., 2005 <feldpauschetal2005>`). Logging infrastructure
including roads, skids, trails, and log decks are represented (Figure
1.17.1). The construction of log decks used to store logs prior to road
transport leads to large canopy openings but their contribution to
landscape-level gap dynamics is small. In contrast, the canopy gaps
caused by tree felling are small but their coverage is spatially
extensive at the landscape scale. Variations in logging practices
significantly affect the level of disturbance to tropical forest
following logging (`Pereira Jr et al., 2002 <Pereirajretal2002>`;
`Macpherson et al., 2012 <macphersonetal2012>`;
`Dykstra, 2002 <dykstraetal2002>`; `Putz et al., 2008 <putzetal2008>`.

Logging operations in the tropics are often carried out with little
planning, and typically use heavy machinery to access the forests
accompanied by construction of excessive roads and skid trails, leading
to unnecessary tree fall and compaction of the soil. We refer to these
typical operations as conventional logging (CL). In contrast, reduced
impact logging (RIL) is a practice with extensive pre-harvest
planning,where trees are inventoried and mapped out for the most
efficient and cost-effective harvest and seed trees are deliberately
left on site to facilitate faster recovery. Through planning, the
construction of skid trails and roads, soil compaction and disturbance
can be minimized. Vines connecting trees are cut and tree-fall
directions are controlled to reduce damages to surrounding trees.
Reduced impact logging results in consistently less disturbance to
forests than conventional logging
(`Pereira Jr et al. 2002 <Pereirajretal2002>`;
`Putz et al. 2008 <putzetal2008>`).

<figure>
<img src="images/Logging_figure1.png" />
</figure>

#### Mortality associated with logging

The FATES logging module was designed to represent a range of logging
practices in field operations at a landscape level. Once logging events
are activated, we define three types of mortality associated with
logging practices: direct-felling mortality
(*l**m**o**r**t*<sub>*d**i**r**e**c**t*</sub>), collateral mortality
(*l**m**o**r**t*<sub>*c**o**l**l**a**t**e**r**a**l*</sub>), and
mechanical mortality
(*l**m**o**r**t*<sub>*m**e**c**h**a**n**i**c**a**l*</sub>). The direct
felling mortality represents the fraction of trees selected for
harvesting that are greater or equal to a diameter threshold (this
threshold is defined by the diameter at breast height (DBH) = 1.3 m
denoted as *D**B**H*<sub>*m**i**n*</sub>); collateral mortality denotes
the fraction of adjacent trees that killed by felling of the harvested
trees; and the mechanical mortality represents the fraction of trees
killed by construction of log decks, skid trails and roads for accessing
the harvested trees, as well as storing and transporting logs offsite
(Figure 1.17.1a). In a logging operation, the loggers typically avoid
large trees when they build log decks, skids, and trails by knocking
down relatively small trees as it is not economical to knock down large
trees. Therefore, we implemented another DBH threshold,
*D**B**H*<sub>*m**a**x*<sub>*i**n**f**r**a*</sub></sub>, so that only a
fraction of trees
 &lt;  = *D**B**H*<sub>*m**a**x*<sub>*i**n**f**r**a*</sub></sub> (called
mechanical damage fraction) are removed for building infrastructure
(`Feldpausch et al., 2005 <feldpauschetal2005>`).

#### Patch dynamics following logging disturbance

To capture the disturbance mechanisms and degree of damage associated
with logging practices at the landscape level, we apply the mortality
types following a workflow designed to correspond to field operations.
In FATES, as illustrated in Figure 1.17.2., individual trees of all
plant functional types (PFTs) in one patch are grouped into cohorts of
similar-sized trees, whose size and population sizes evolve in time
through processes of recruitment, growth, and mortality. As described
abve, cohorts are organized into canopy and understory layers, which are
subject to different light conditions (Figure 1.17.2a). When logging
activities occur, the canopy trees and a portion of big understory trees
lose their crown coverage through direct felling for harvesting logs, or
as a result of collateral and mechanical damages ((Figure 1.17.2b). The
fractions of (only the) canopy trees affected by the three mortality
mechanisms are then summed up to specify the areal percentages of an old
(undisturbed) and a new (disturbed) patch caused by logging in the patch
fission process (Figure 1.17.2c). After patch fission, the canopy layer
over the disturbed patch is removed, while that over the undisturbed
patch stays untouched (Figure 1.17.2d). In the undisturbed patch, the
survivorship of understory trees is calculated using an understory death
fraction consistent with whose default value corresponds to that used
for natural disturbance (*i*<sub>*d*</sub>, 0.559). To differentiate
logging from natural disturbance, a slightly elevated, logging-specific
understory death fraction is applied in the disturbed patch instead at
the time of the logging event. Based on data from field surveys over
logged forest plots in southern Amazon
(`Feldpausch et al., 2005 <feldpauschetal2005>`), understory death
fraction corresponding to logging is now set to be 0.65 as the default,
but can be modified via the FATES parameter file (Figure 1.17.2e).
Therefore, the logging operations will change the forest from the
undisturbed state shown in Figure 1.17.2a to a disturbed state in Figure
1.17.2f in the logging module. It is worth mentioning that the newly
generated patches are tracked according to age since disturbance and
will be merged with other patches of similar canopy structure following
the patch fusion processes in FATES in later time steps of a simulation,
pending the inclusion of separate land-use fractions for managed and
unmanaged forest.

<figure>
<img src="images/Logging_figure2.png" />
</figure>

#### Flow of necromass following logging disturbance

Logging operations affect forest structure and composition, and also
carbon cycling (`Palace et al., 2008 <palaceetal2008>`) by modifying the
live biomass pools and flow of necromass (Figure 1.17.3). Following a
logging event, the logged trunk products from the harvested trees are
transported off-site (as an added carbon pool for resource management in
the model), while their branches enter the coarse woody debris (CWD)
pool, and their leaves and fine roots enter the litter pool. Similarly,
trunks and branches of the dead trees caused by collateral and
mechanical damages also become CWD, while their leaves and fine roots
become litter. Specifically, the densities of dead trees as a result of
direct felling, collateral, and mechanical damages in a cohort are
calculated as follows:

*D*<sub>*d**i**r**e**c**t*</sub> = *l**m**o**r**t*<sub>*d**i**r**e**c**t*</sub> \* *n*/*A*

*D*<sub>*c**o**l**l**a**t**e**r**a**l*</sub> = *l**m**o**r**t*<sub>*c**o**l**l**a**t**e**r**a**l*</sub> \* *n*/*A*

*D*<sub>*m**e**c**h**a**n**i**c**a**l*</sub> = *l**m**o**r**t*<sub>*m**e**c**h**a**n**i**c**a**l*</sub> \* *n*/*A*

where *A* stands for the area of the patch being logged, and *n* is the
number of individuals in the cohort where the mortality types apply
(i.e., as specified by the size thresholds,
*D**B**H*<sub>*m**i**n*</sub> and
*D**B**H*<sub>*m**a**x*<sub>*i**n**f**r**a*</sub></sub>). For each
cohort, we denote
*D*<sub>*i**n**d**i**r**e**c**t*</sub> = *D*<sub>*c**o**l**l**a**t**e**r**a**l*</sub> + *D*<sub>*m**e**c**h**a**n**i**c**a**l*</sub>
and
*D*<sub>*t**o**t**a**l*</sub> = *D*<sub>*d**i**r**e**c**t*</sub> + *D*<sub>*i**n**d**i**r**e**c**t*</sub>,
respectively.

<figure>
<img src="images/Logging_figure3.png" />
</figure>

Leaf litter (*L**i**t**t**e**r*<sub>*l**e**a**f*</sub>, \[*k**g**C*\])
and root litter
(*L**i**t**t**e**r*<sub>*r**o**o**t*</sub>, \[*k**g**C*\]) at the cohort
level are then calculated as:

*L**i**t**t**e**r*<sub>*l**e**a**f*</sub> = *D*<sub>*t**o**t**a**l*</sub> \* *B*<sub>*l**e**a**f*</sub> \* *A*

*D*<sub>*l**e**a**f*</sub> = *D*<sub>*t**o**t**a**l*</sub> \* (*B*<sub>*r**o**o**t*</sub> + *B*<sub>*s**t**o**r**e*</sub>) \* *A*

where *B*<sub>*l**e**a**f*</sub>, *B*<sub>*r**o**o**t*</sub>,
*B*<sub>*s**t**o**r**e*</sub> are live biomass in leaves and fine roots,
and stored biomass in the labile carbon reserve in all individual trees
in the cohort of interest.

Following the existing CWD structure in FATES
(`Fisher et al., 2015 <Fisheretal2015>`), CWD in the logging module is
first separated into two categories: above-ground CWD and below-ground
CWD. Within each category, four size classes are tracked based on their
source, following `Thonicke et al. (2010)<thonickeetal2010>`: trunks,
large branches, small branches and twigs. Above-ground CWD from trunks
(*C**W**D*<sub>*t**r**u**n**k*<sub>*a**g**b*</sub></sub>, \[*k**g**C*\])
and large branches/small branches/twig
(*C**W**D*<sub>*b**r**a**n**c**h*<sub>*a**g**b*</sub></sub>, \[*k**g**C*\])
are calculated as follows:

*C**W**D*<sub>*t**r**u**n**k*<sub>*a**g**b*</sub></sub> = *D*<sub>*i**n**d**i**e**c**t*</sub> \* *A**G**B*<sub>*s**t**e**m*</sub> \* *f*<sub>*t**r**u**n**k*</sub> \* *A*

*C**W**D*<sub>*b**r**a**n**c**h*<sub>*a**g**b*</sub></sub> = *D*<sub>*t**o**t**a**l*</sub> \* *A**G**B*<sub>*s**t**e**m*</sub> \* *f*<sub>*b**r**a**n**c**h*</sub> \* *A*

where *A**G**B*<sub>*s**t**e**m*</sub> is the amount of above ground
stem biomass in the cohort, *f*<sub>*t**r**u**n**k*</sub> and
*f*<sub>*b**r**a**n**c**h*</sub> represent the fraction of trunks and
large branches/small branches/twig. Similarly, the below-ground CWD from
trunks
(*C**W**D*<sub>*t**r**u**n**k*<sub>*b**g*</sub></sub>, \[*k**g**C*\])
and branches/twig
(*C**W**D*<sub>*b**r**a**n**c**h*<sub>*b**g*</sub></sub>, \[*k**g**C*\])
are calculated as follows:

*C**W**D*<sub>*t**r**u**n**k*<sub>*b**g*</sub></sub> = *D*<sub>*t**o**t**a**l*</sub> \* *B*<sub>*r**o**o**t*<sub>*b**g*</sub></sub> \* *f*<sub>*t**r**u**n**k*</sub> \* *A*

*C**W**D*<sub>*b**r**a**n**c**h*<sub>*b**g*</sub></sub> = *D*<sub>*t**o**t**a**l*</sub> \* *B*<sub>*r**o**o**t*<sub>*b**g*</sub></sub> \* *f*<sub>*b**r**a**n**c**h*</sub> \* *A*

where *B*<sub>*c**r**o**o**t*</sub>\[*k**g**C*\] is the amount of coarse
root biomass in the cohort. Site-level total litter and CWD inputs can
then be obtained by integrating the corresponding pools over all the
cohorts in the site. To ensure mass conservation,

*δ*<sub>*B*</sub> = *δ*<sub>*L**i**t**t**e**r*</sub> + *δ*<sub>*C**W**D*</sub> + *t**r**u**n**k*<sub>*p**r**o**d**u**c**t*</sub>

where *δ*<sub>*B*</sub> is total loss of biomass due to logging,
*δ*<sub>*l**i**t**t**e**r*</sub> and *δ*<sub>*C**W**D*</sub> are the
increments in litter and CWD pools, and
*t**r**u**n**k*<sub>*p**r**o**d**u**c**t*</sub> represents harvested
logs shipped offsite.

Following the logging event, the forest structure and composition in
terms of cohort distributions, as well as the live biomass and necromass
pools are updated. Following this logging event update to forest
structure, the native processes simulating physiology, growth and
competition for resources in and between cohorts resume. Since the
canopy layer is removed in the disturbed patch, the existing understory
trees are promoted to the canopy layer, but, in general, the canopy is
incompletely filled in by these newly-promoted trees, and thus the
canopy does not fully close. Therefore, more light can penetrate and
reach the understory layer in the disturbed patch, leading to increases
in light-demanding species in the early stage of regeneration, followed
by a succession process in which shade tolerant species dominate
gradually.

The above describes the case where the canopy is closed (by treees)
prior to logging. If this is not the case, some amount of
non-tree-occupied canopy area is also moved to the newly-disturbed patch
so as to maintain the composition of the undisturbed patch or patches in
their original state (albeit in covering a smaller area).

<figure>
<img src="images/logging_schematic_mixed_open_closed_canopy.png" />
</figure>

After logging occurs, the patches that have been disturbed are tracked
as belonging to secondary lands, by updating their land use labels, and
are not fused with patches on primary lands. This allows primary and
secondary land areas to be tracked, with possibly different ecological
dynamics occuring on each.

### Land Use Change

Land use change in FATES is driven by a transition matrix that specifies
what areal fraction of land is converted from one land use type to
another, in rates of fraction/year. Land use types in FATES are
currently allowed five distinct categories:

1.  Primary Lands
2.  Secondary Lands
3.  Rangelands
4.  Pasture Lands
5.  Crop Lands

In the special case of 'nocomp' mode, there may also be bare ground
lands, which also have an absence of land use (i.e. they have a
bare-ground land use) as well. Each of these land use types are tracked
via an integer flag for each patch. Natural disturbance processes retain
the land flag for the resulting patch as the parent patch, and patches
with differing land use type flags cannot be fused. This ensures that
total patch area of each land use type is conserved, in the absence of
land use change and logging disturbance.

<figure>
<img src="images/land_use_transition_matrix.png"
alt="Possible disturbances in FATES, represented as a land use transition matrix of land use changing from a donor type to a receiver type. Bold text on diagonals are for the FATES land use types. Disturbance types that may generate eahc type of land use transition are listed in italics. Natural disturbance rates (fire, treefall) are only permitted on diagonal elements, i.e. they do not result in land use change. Harvest results in secondary land, whether the donor type is primary or secondary land. All other transition types are represented as land use change rates that are read in from the land use driver file. Black squares are non-permitted transitions; i.e., nothing can become primary land after it has transitioned away from primary land." />
<figcaption aria-hidden="true">Possible disturbances in FATES,
represented as a land use transition matrix of land use changing from a
donor type to a receiver type. Bold text on diagonals are for the FATES
land use types. Disturbance types that may generate eahc type of land
use transition are listed in italics. Natural disturbance rates (fire,
treefall) are only permitted on diagonal elements, i.e. they do not
result in land use change. Harvest results in secondary land, whether
the donor type is primary or secondary land. All other transition types
are represented as land use change rates that are read in from the land
use driver file. Black squares are non-permitted transitions; i.e.,
nothing can become primary land after it has transitioned away from
primary land.</figcaption>
</figure>

<figure>
<img src="images/land_use_data_workflow.png"
alt="Work flow for land use driver tools. LUH2 data (leftmost blue box) is regridded vi a aset of puython tools (red box) to create a single netcdf file (next blue box), which is read by host model and passed to FATES." />
<figcaption aria-hidden="true">Work flow for land use driver tools. LUH2
data (leftmost blue box) is regridded vi a aset of puython tools (red
box) to create a single netcdf file (next blue box), which is read by
host model and passed to FATES.</figcaption>
</figure>

The land use transition matrix is input to FATES via a separate file,
that is read by the host model and passed to FATES, alongside a land-use
state vector. Currently, the LUH2 (`Hurtt et al. 2020<hurttetal2020>`)
dataset is used for these drivers. The dimensions of the land-use
transition matrix are lat x lon x donor land use type x receiver land
use type x time.

#### Initialization of land use

The land use state vector is used to initialize the land use states via
one of two ways:

<figure>
<img src="images/land_use_initialization_flowcharts.png"
alt="FLow chart of two ways of initializing FATES with land use change: A no-spinup case initializes land use states at the start of a transient run, bu twith no attempt to first spin up to an equilibrium state. A Spinup case first runs the model under potential vegetation (i.e., no land use) and then applies initial land use change to get to a desired compositino of land use at the time point that starts a transient run, followed by transient land use after that." />
<figcaption aria-hidden="true">FLow chart of two ways of initializing
FATES with land use change: A no-spinup case initializes land use states
at the start of a transient run, bu twith no attempt to first spin up to
an equilibrium state. A Spinup case first runs the model under potential
vegetation (i.e., no land use) and then applies initial land use change
to get to a desired compositino of land use at the time point that
starts a transient run, followed by transient land use after
that.</figcaption>
</figure>

The first way of initializing land use states is to runwith no spinup
from bare ground, starting in some specific year of the historical
record. In this case, the land use state vector is used to initialize a
set of patches whose areal fraction and land use labels then match the
land use state vector at the time of initialization, but all of which
start from a near-bare-ground initialization. In this way, land use is
always transient, there is not any steady-state equilibration period.

The second way is to first run the model through a period of
steady-state land use forcing to achieve spun-up initial conditions.
However, because land use change away from primary lands is a one-way
process, there cannot be steady-state conditions if land use change that
includes such transition rates are nonzero. Thus the simplest
steady-state condition that does allow equilibration is the absence of
land use, which we call 'potential vegetation mode'. In this case, a
flag is set that asserts 100% primary land fraction and no harvest,
until steady state conditions are met. This may also involve methods to
accelerate soil organic matter spinup, which will thus also be in steady
state with respect to the no-land-use conditions.

After sufficiently spun up steady-state conditions are achieved in
potential vegetation mode, land use is introduced upon exiting potential
vegetation mode; this is triggered automatically based on logical flags
that are passed within the restart file. In this case, land use change
rates are diagnosed from the land use state vector in the driving
dataset, so that disturbance rates on the first day lead to the desired
land use state distribiutions on the second day of the simulation. This
will create an initial disequilibrium in the age distributions and
disturbance products (e.g. necromass), which must then propagate through
the system for some time, and thus must be done ~100 years prior to the
start of the period of interest (see `Sentman et al.,
2011<Sentmanetal2011>` for further discussion).

#### Running Dynamic Land-use with prescribed land cover (i.e., 'nocomp' configuration)

If FATES is run with both land use chaneg and prescribed landcover, then
the patch structure must handle three specific pieces of infoirmation:
(1) Land Use label, (2) nocomp PFT label, and (3) patch age. The first
two of these are categorical and the third is continuous. An example of
what such a patch structure might look like is below:

<figure>
<img src="images/landuse_nocomp_tiling_structure.png"
alt="Schematic of an example patch structure when land use change, and prescribed land cover (i.e. &#39;nocomp&#39; configuration) are both active. (a) Land Use fractions. (b) PFT Land Cover fractions nested within Land Use fractinos. (c) Full patch mosaic with Land Use, Land Cover, and patch age all distinguishing patches." />
<figcaption aria-hidden="true">Schematic of an example patch structure
when land use change, and prescribed land cover (i.e. 'nocomp'
configuration) are both active. (a) Land Use fractions. (b) PFT Land
Cover fractions nested within Land Use fractinos. (c) Full patch mosaic
with Land Use, Land Cover, and patch age all distinguishing
patches.</figcaption>
</figure>

Because land use change drives changes to land cover, in a prescribed
land-cover case with land use change, the prescribed land cover must be
dependent on land use. Thus, under this configuration, a second dataset
is read that specifies, for each gridcell, what the nocomp PFT
composition should be on each non-crop land use type. The crop land use
type is assigned a single PFT that is permitted to grow on crop patches.

The land cover is thus a function of both the land use in a given
gridcell at a given time, and the prescribed PFT composition conditional
on land use:

*A*<sub>*p*</sub>(*x*, *y*, *t*) = ∑<sub>*i*</sub>(*U*<sub>*i*</sub>(*x*, *y*, *t*) \* *C*<sub>*p*, *i*</sub>(*x*, *y*))

Where *A*<sub>*p*</sub>(*x*, *y*, *t*) is the fractional area covered by
all patches with a given nocomp PFT label *p* at gridcell (*x*, *y*) and
timestep *t*; *U*<sub>*i*</sub>(*x*, *y*, *t*) is the fractional area of
all patches with a given land use type *i* at that point in space and
time, and *C*<sub>*p*, *i*</sub>(*x*, *y*) is the composition of PFT *p*
for a given gridcell and land use type *i*. Note that
*C*<sub>*p*, *i*</sub> is time-invariant in such a configuration.

During either land use change disturbance or tree harvest disturbance,
the resulting patches may need to have their nocomp PFTs changed so that
they match the PFT distribiution of the resulting land use. This is
accomplished as below:

<figure>
<img src="images/LU_nocomp_transition_schematic.png"
alt="Schematic of series of steps that occur when changing land use and land cover, under a prescribed land cover configuration. Colors indicate patches with nocomp PFTs. (a) disturbed area is calculated across all patches of donor land use type(s). (b) Newly disturbed patches are separated after main disturbance sequence. (c) Patch nocomp PFT areas are changed and/or reweighted, so that the proportion of PFTs in newly disturbed patch area matches that of the receiver land use type. (d) newly disturbed patches are added back to FATES patch structure with new land use and land cover labels." />
<figcaption aria-hidden="true">Schematic of series of steps that occur
when changing land use and land cover, under a prescribed land cover
configuration. Colors indicate patches with nocomp PFTs. (a) disturbed
area is calculated across all patches of donor land use type(s). (b)
Newly disturbed patches are separated after main disturbance sequence.
(c) Patch nocomp PFT areas are changed and/or reweighted, so that the
proportion of PFTs in newly disturbed patch area matches that of the
receiver land use type. (d) newly disturbed patches are added back to
FATES patch structure with new land use and land cover
labels.</figcaption>
</figure>

## Plant Hydraulic module

For each plant cohort, the hydraulic module tracks water flow along a
soil–plant–atmosphere continuum of a representative individual tree
based on hydraulic laws, and updates the water content and potential of
leaves, stem, and roots with a 30 minutes model time step. Water flow
from each soil layer within the root zone into the plant root system is
calculated as a function of the hydraulic conductance as determined by
root biomass and root traits such as specific root length, and the
difference in water potential between the absorbing roots and the
rhizosphere. The root distribution is based on Zeng's (2001) two
parameter power law function which takes into account the regolith
depth:

$$Y\_{i} = \\frac{0.5(e^{- r\_{a}z\_{li}} + e^{- r\_{b}z\_{li}}) - 0.5(e^{- r\_{a}z\_{ui}} + e^{- r\_{b}z\_{ui}})}{1 - 0.5(e^{- r\_{a}z} + e^{- r\_{b}z})}$$

where *Y*<sub>*i*</sub> is the fraction of fine or coarse roots in the
*i* th soil layer, *r*<sub>*a*</sub> and *r*<sub>*b*</sub> are the two
parameters that determine the vertical root distribution,
*z*<sub>*l**i*</sub> is the depth of the lower boundary of the *i* th
soil layer, and *z*<sub>*u**i*</sub> is the depth of the upper boundary
of the *i* th soil layer, and *z* is the total regolith depth. The
vertical root distribution affects water uptake by the hydrodynamic
model by distributing the total amount of root, and thus root
resistance, through the soils.

The total transpiration of a tree is the product of total leaf area (LA)
and the transpiration rate per unit leaf area *J*. In this version of
FATES-Hydro, we adopt the model developed by Vesala et al. (2017) to
take into account the effect of leaf water potential on the within-leaf
relative humidity and transpiration rate:

*E* = *L**A* ⋅ *J*

$$J = \\rho\_{atm}\\frac{(q\_{l} - q\_{s})}{1/g\_{s} + r\_{b}}$$

$$q\_{l} = \\exp(\\frac{k\_{LWP} \\cdot LWP \\cdot V\_{H2O}}{R \\cdot T}) \\cdot q\_{sat}$$

Where, *E* is the total transpiration of a tree, *L**A* \[m2\] is the
total leaf area, *J* \[kg/s/m2\] is the transpiration per unit leaf
area, *ρ* \[kg/m3\] is the density of atmospheric air, *q*<sub>*l*</sub>
\[kg/kg\] is the within-leaf specific humidity, *q*<sub>*s*</sub>
\[kg/kg\] is the atmosphere specific humidity, *g*<sub>*s*</sub> \[m/s\]
is the stoma conductance per unit leaf area, *r*<sub>*b*</sub> \[s/m\]
is the leaf boundary layer resistance, *k*<sub>*l**w**p*</sub> is a
unitless scaling coefficient, which can vary between 1 and 7, and here
we use a value of 3; *L**W**P* \[Mpa\] is the leaf water potential,
*V*<sub>*H*2*O*</sub> \[1.8e-6 m3/mol\] is the constant molar volume,
*R* is the universal gas constant, and *T* \[K\] is the leaf
temperature.

The sap flow from absorbing roots to the canopy through each compartment
of the tree along the flow path way (absorbing roots, transport roots,
stem, and leaf) is computed according to Darcy’s law in terms of the
plant sapwood water conductance, the water potential gradient:

*Q*<sub>*i*</sub> = −*K*<sub>*i*</sub>\[*ρ*<sub>*w*</sub>*g*(*z*<sub>*i*</sub> − *z*<sub>*i* + 1</sub>) + (*Ψ*<sub>*i*</sub> − *Ψ*<sub>*i* + 1</sub>)\]

where *ρ*<sub>*w*</sub> is the density of water; *z*<sub>*i*</sub> \[m\]
is the height of the compartment; *z*<sub>*i* + 1</sub> \[m\] is the
height of the next compartment down the flow path; *Ψ*<sub>*i*</sub>
\[MPa\] is the water potential of the compartment; *Ψ*<sub>*i* + 1</sub>
\[MPa\] is the water potential of the next compartment down the flow
path; and *g* \[kg/MPa/m/s\] is the hydraulic conductance of the
compartment . The hydraulic conductance of the compartments is by the
water potential and maximum hydraulic conductance of the compartment
through the pressure-volume (P-V) curve and the vulnerability curve
(Manzoni et al. 2013, Christoffersen et al. 2016).

The plant hydrodynamic representation and numerical solver scheme within
FATES-HYDRO follows Christoffersen et al. (2016). A few modifications
are made to accommodate the multi-soil layers and improve the numerical
stability. First, to accommodate the multi-soil layers, we have
sequentially solved the Richards' equation for each individual soil
layers, with each layer-specific solution proportional to each layer's
contribution to the total root-soil conductance. Second, to improve the
numerical stability, we have linearly interpolated the PV curve beyond
the residual and saturated tissue water content to avoid the rare cases
of overshooting in the numerical scheme under very dry or wet
conditions. Third, Christoffersen et al. (2016) used three phases to
describe the PV curves: 1) dehydration phases representing capillary
water (sapwood only), 2) elastic cell drainage (positive turgor), and 3)
continued drainage after cells have lost turgor. Due to the
discontinuity of the curve between these three phases, it leads to some
numerical instability. To resolve this instability, FATES-HYDRO added
the Van Genuchten model (Van Genuchten 1980, July and Horton 2004) and
the Campbell model (Campbell 1974) as an alternatives to describe the PV
curves.

The Van Genuchten model has two advantages: 1) it is simple, with only
three parameters needed for both curves, and 2) it is mechanistically
based, with both the P-V curve and vulnerability curve derived from a
pipe model thus are connected through the three shared parameters:

$$\\Psi = \\frac{1}{- \\alpha} \\cdot \\left( \\frac{1}{Se^{1/m}} - 1 \\right)^{1/n}$$

$$FMC = \\left( 1 - \\left( \\frac{( - \\alpha \\cdot \\Psi)^{n}}{1 + ( - \\alpha \\cdot \\Psi)^{n}} \\right)^{m} \\right)^{2}$$

where *Ψ* \[MPa\] is the water potential of the media (xylem in this
case); *F**M**C*\[*K*/*K*<sub>*m**a**x*</sub>\] is the fraction of xylem
conductivity; *α* \[/MPa\] is a scaling parameter for air entering
point, *S**e* is the dimensionless standardized relative water content
as:

$$Se =\\frac{theta-theta\_{r}}{theta\_{sat}-theta\_{r}}$$

where *θ*, *θ*<sub>*r*</sub> and *θ*<sub>*s**a**t*</sub> \[m3/m3\] are
volumetric water content, residual volumetric water content, and
saturated volumetric water content correspondingly; and *m* and *n* are
dimensionless (xylem conduits) size distribution parameters.

The stomatal conductance is modelled in the form of Ball-Berry
conductance model (Ball et al. 1987, Oleson et al. 2013, Fisher et al.
2015):

$$g\_{s} = m\\frac{A\_{n}}{c\_{s}/P\_{atm}}\\frac{e\_{s}}{e\_{i}} + b\\beta\_{t}$$

where *m* and *b* are parameters equivalent to slope and intercept in
the Ball-Berry model correspondingly. These terms are plant strategy
dependent and can vary widely with plant functional types (Medlyn et al.
2011). The parameter *b* is also scaled by the water stress index
*β*<sub>*t*</sub>. *A*<sub>*n*</sub> \[umol CO2/m2/s\] is the net carbon
assimilation rate based on Farquhar’s (1980) formula. This term is also
constrained by water stress index *β*<sub>*t*</sub> in the way that the
*V*<sub>*c**m**a**x*, 25</sub> is scaled by *β*<sub>*t*</sub> as
*V*<sub>*c**m**a**x*, 25</sub>*β*<sub>*t*</sub> (Fisher et al. 2018).
*c*<sub>*s*</sub> \[Pa\] is the CO2 partial pressure at the leaf
surface, *e*<sub>*s*</sub> \[Pa\] is the vapor pressure at the leaf
surface, *e*<sub>*i*</sub> \[Pa\] is the saturation vapor pressure
inside the leaf at a given vegetation temperature when
*A*<sub>*n*</sub> = 0.

The water stress index, a proxy for stomatal closure in response to
desiccation, is determined by the leaf water potential adopted from the
FMCgs term from Christoffersen et al. (2016):

$$\\beta\_{t} = \\left\\lbrack 1 + (\\frac{\\Psi\_{l}}{P50\_{gs}})^{ags} \\right\\rbrack^{- 1}$$

where *Ψ*<sub>*l*</sub> \[MPa\] is the leaf water potential,
*P*50<sub>*g**s*</sub> \[MPa\] is the leaf water potential of 50%
stomatal closure, and *a*<sub>*g**s*</sub> governs the steepness of the
function. For a given set of *a*<sub>*g**s*</sub> , the
*P*50<sub>*g**s*</sub> controls the degree of hydraulic vulnerability
segmentation (Christoffersen et al. 2016, Powell et al. 2017). A more
negative *P*50<sub>*g**s*</sub> means that, during leaf dry down from
full turgor, the stomatal aperture stays open and thus allows the
transpiration rate to remain high and xylem to dry out, which thus can
maintain high photosynthetic rates at the risk of exposing xylem to
embolism and thus plant mortality. Conversely, a plant with a less
negative *p*50<sub>*g**s*</sub> will close stomata quickly during leaf
dry down, thus limiting transpiration and the risk of xylem embolism and
mortality associated with it.

References

Ball, J. Timothy, Ian E. Woodrow, and Joseph A. Berry. 1987. "A model
predicting stomatal conductance and its contribution to the control of
photosynthesis under different environmental conditions." Progress in
photosynthesis research. Springer, Dordrecht, 221-224.

Campbell, G.S., 1974. A simple method for determining unsaturated
conductivity from moisture retention data. \*Soil science\*, \*117\*(6),
pp.311-314.

Christoffersen, Bradley O et al. 2016. “Linking Hydraulic Traits to
Tropical Forest Function in a Size-Structured and Trait-Driven Model
(TFS v . 1-Hydro ).” : 4227–55.

Fisher, R. a. et al. 2015. “Taking off the Training Wheels: The
Properties of a Dynamic Vegetation Model without Climate Envelopes,
CLM4.5(ED).” *Geoscientific Model Development* 8(11): 3593–3619.

Jury, W.A. and Horton, R., 2004. \*Soil physics\*. John Wiley & Sons.

Manzoni, S., 2014. Integrating plant hydraulics and gas exchange along
the drought-response trait spectrum. \*Tree physiology\*, \*34\*(10),
pp.1031-1034.

Oleson, Keith W et al. 2013. “Technical Description of Version 4.5 of
the Community Land Model (CLM) Coordinating.” In *Natl. Cent. Atmos.
Res. Tech. Note*, Natl. Cent. for Atmos. Res., Boulder, Colo.

Van Genuchten, M.T., 1980. A closed‐form equation for predicting the
hydraulic conductivity of unsaturated soils. \*Soil science society of
America journal\*, \*44\*(5), pp.892-898.

Vesala, T., Sevanto, S., Gronholm, T., Salmon, Y., Nikinmaa, E., Hari,
P., & Holtta, T. 2017. “Effect of leaf water potential on internal
humidity and CO2 dissolution: Reverse transpiration and improved water
use efficiency under negative pressure.” \*Frontiers in Plant
Science\*, \*\*8\*\*, 54.

Zeng, Xubin. 2001. “Global Vegetation Root Distribution for Land
Modeling.” *Journal of Hydrometeorology* 2(5): 525–30.

## Crown Damage Module

The crown damage module represents crown damage as a reduction in crown
area and the biomass of tissues in the crown (leaves, sapwood, storage,
structural and reproductive tissues), implemented via changes to
allometric relationships. Damage currently does not change the height of
cohorts or the biomass of the stem.

We treat damage as a categorical variable with each cohort associated
with a ‘damage class’ that describes its degree of crown loss. Damage
classes can be set in the parameter file via `damage_bin_edges`, which
sets the lower bin edges for the percentage of crown loss in each damage
class. Damage classes do not need to be evenly spaced. Damage class is
an argument to allometric equations and is used to reduce the biomass of
crown tissues. For example:

*b**l* = *b**l* \* (1 − *c**r**o**w**n**r**e**d**u**c**t**i**o**n*)

where *b**l* is leaf biomass.

We reduce sapwood and structural tissues in proportion to their branch
fraction.

*b**s**a**p* = *b**s**a**p* − (*b**s**a**p* \* *a**g**b**f**r**a**c* \* *b**r**a**n**c**h**f**r**a**c* \* *c**r**o**w**n**r**e**d**u**c**t**i**o**n*)

where *b**s**a**p* is sapwood biomass, *a**g**b**f**r**a**c* is
aboveground biomass fraction and *b**r**a**n**c**h**f**r**a**c* is the
branch fraction. Branch fraction is calculated as the sum of the first
three coarse woody debris pools (i.e. excluding the main stem).

Damage is not currently linked to explicit drivers. The timing of damage
events is set by the `damage_event_code` parameter - described in table
`crown_damage_event_table`.

| Event code      | Description                                             |
|------------------------------------|------------------------------------|
| 1               | Damage is off                                           |
| 2               | Damage occurs on the first time step                    |
| 3               | Damage occurs every day (not recommended)               |
| 4               | Damage occurs once a month (on the first day)           |
| negative number | Damage occurs annually on the specified day of the year |
| YYYYMMDD        | Damage occurs on a given date.                          |

Crown damage event codes

The `damage_frac` parameter determines the proportion of a cohort that
is damaged with each damage event. Part of the cohort keeps its current
damage class, while the damaged portion of the cohort is equally divided
into cohorts with higher damage classes. In the figure below there are
five damage classes including undamaged and `damage_frac` is set to
`0.1`. Of the intial cohort of 1000 individuals 25 individuals are
therefore moved into each of the four higher damage classes.

<figure>
<img src="images/Damage_1.png" />
</figure>

Recovery from crown damage is set via the `damage_recovery_scalar`
parameter. A value of zero means that during daily allocation of NPP, no
recovery occurs and damaged cohorts will allocate all available carbon
to growth along their altered allometric trajectories. A value of one
means that cohorts will use all available carbon to regrow damaged
tissues, at the expense of dbh growth. The maximum number of individuals
of a cohort that can recover in each timestep (*n**m**a**x*) is a
function of the available allocatable carbon to grow with
(*C*<sub>*b*</sub>) and the change in carbon between the damage class
*i* and *i* − 1 (*C*<sub>*r*</sub>):

*n**m**a**x* = *n*<sub>*i*</sub> \* *C*<sub>*b*</sub>/*C*<sub>*r*</sub>

Where *n*<sub>*i*</sub> is the initial number density of the cohort. The
number of plants that recover is then *n**m**a**x* \* *f**r* where
*f**r* is the `damage_recovery_scalar` parameter.

<figure>
<img src="images/Damage_2.png" />
</figure>

Crown damage in FATES can lead to mortality via carbon starvation.
However, to capture mortality associated with crown loss from mechanisms
not currently in FATES (e.g. pathogen entry) an additional mortality
term describes an increase in mortality with crown loss
*M*<sub>*d*, *c**o**h*</sub>.

$$M\_{d,coh} = \\frac{1}{1 + e^{(-r\_d \* (damage - p\_d))}}$$

where *d**a**m**a**g**e* is the fraction of crown loss,
*r*<sub>*d*</sub> is the rate that mortality increases with crown loss,
and *p*<sub>*d*</sub> is the inflection point of the curve, i.e. the
crown loss at which annual mortality rate has increased to 50%.

For an application of the FATES crown damage module see
`Needham et al. (2022)<Needhametal2022>`.

## FATES Reduced Complexity Configurations

The full FATES model has a high degree of structural complexity, with
interactions between processes acting at short timescales such as
photosynthesis and processes acting at longer timescales such as
competition and community restructuring. In order to better isolate
different processes, allow for cleaner experimental design, and
facilitate calibration and testing of different model components, FATES
includes a number of reduced-complexity configurations. A summary of
these configurations is shown in table `reduced_complexity_table`.

| Mode | How to enable | Vegetation structure | Leaf Area Index | Photosynthesis and Physiology | Competition between PFTs for canopy space |
|------------|------------|------------|------------|------------|------------|
| **Primarily site-level modes** |  |  |  |  |  |
| Static Stand Structure (ST3) | `use_fates_ed_st3 = .true.` | Fixed after initialization | Fixed after initialization | Active | No |
| Prescribed Physiology | `use_fates_ed_prescribed_phys = .true.` | Active | Inactive | Prescribed NPP per unit crown area and mortality rate | Active if multiple PFTs present |
| **Primarily large-scale modes** |  |  |  |  |  |
| Satellite Phenology mode (FATES-SP) | `use_fates_sp = .true.` | Simplified: 1 patch per PFT and one cohort per patch | Prescribed via dynamic dataset | Active | No |
| No competition mode, with prescribed biogeography (FATES-nocomp) | `use_fates_nocomp = .true., use_fates_fixed_biogeog = .true.` | Active | Active | Active | No competition: Each PFT allotted a total fixed areas based on input dataset |
| No competition mode, without prescribed biogeography | `use_fates_nocomp = .true., use_fates_fixed_biogeog = .false.` | Active | Active | Active | No competition: Each PFT allotted the same area everywhere |
| Prescribed biogeography | `use_fates_fixed_biogeog = .true.` | Active | Active | Active | Active, put PFTs only allowed to grow where they are present in input dataset |
| Full FATES |  | Active | Active | Active | Active |

FATES reduced-complexity modes

Each of these modes is described in more detail below. We here separate
them into those that are primarily intended for site-scale simulations
and those that are primarily intended for large-scale simulations;
However we note that all modes have valid use-cases for both site-scale
and large-scale simulations.

### Primarily site-level FATES reduced complexity modes

Two reduced complexity configurations are designed primarily for
site-level testing. These are Static Stand Structure mode and Prescribed
Physiology mode, which enable only the fast-timesale and slow-timescale
processes, respectively.

#### Static Stand Structure Mode

This mode turns of all growth and mortality processes. It is best used
with an inventory initialization to set the initial stand structure as
has been observed at a given location. By turning off growth and
mortality, this mode cuts all feedbacks between fast and slow processes,
and thus can be used to look at changes to physiological processes or
parameters conditional on a given ecosystem structure, or alternately
can be used to calibrate physiological dynamics at a specific site given
known ecosystem structure. Note that leaf phenology is also disabled in
this mode, and thus a user may want to accomplish similar goals using
the Satellite Phenology mode for sites with strong phenological cycles.

#### Prescribed Physiology Mode

This mode ignores all prognositc physiology calculatino,and instead
allows the user to assert growth and mortality rates in the canopy and
understory. Growth rates are specified via a parameter that governs the
NPP per unit crown area. The crown area scaling is to align overall
growth trajectories as plants grow in size with the full FATES model:
since both light interception and maintenance respiration (assuming the
leaf biomass allometric exponent is the same as that for crown area)
scale with leaf and crown area, this implies an NPP scaling with crown
area as well. Thus this mode allows testign the effects of different
ways of organizing the canopy, or other slow-timescale processes,
conditional on some known growth and mortality rates.

### Primarily large-scale FATES reduced complexity modes

The primarily large-scale reduced complexity modes are designed to allow
separation of processes in support of model complexity hierarchies and
global calibration efforts. A schematic of these configurations is
below:

<figure>
<img src="images/fates_reduced_complexity_modes_slide1.png" />
</figure>

#### Satellite Phenology (FATES-SP) Mode

This is the simplest of the large-scale configurations, and reverts the
behavior of the model as close as possible to the existing CLM-SP and
ELM-SP configurations. In this mode, FATES is given information about
the static areal coverage of each PFT, as well as time-varying
information about LAI and canopy height in the model. FATES uses this
information to construct a canopy structure with a single patch per PFT
and a single cohort per patch, whose stem diameter corresponds
allometrically to the canopy height, and whose number density allows the
cohort to fill the patch given the allometric crown area per plant. Leaf
biomass is dynamically calculated to achieve the specified LAI for each
PFT.

#### No competition with prescribed biogeography (nocomp) mode

In this mode, all processes are active except for light competition
between PFTs. Each PFT is given a total patch area to grow on, but
unlike FATES-SP mode, disturbance can occur on each patch and thus the
space allocated to each PFT may be split into one or more patches based
on disturbance history. Each patch has a PFT label, and only that PFT is
allowed to grow on the patch. Cohorts of a given PFT compete against
each other for canopy access and thus light.

#### No competition without prescribed biogeography mode

This mode is imilar to the 'nocomp' mode described above, but instead of
each PFT being allocated areas based on a PFT map read from an input
surface dataset, each PFT is allocated the same area on all gridcells.
Thus it can be used for specific experiemnts looking at PFT differences
across climate gradients.

In no competition with and without prescribed biogeography cohorts can
be initialised based on a given dbh, rather than spun up from bare
ground, by setting the fates\_recruit\_init\_density parameter to a
negative number, which is then interpreted as initial dbh.

#### Prescribed biogeography with competition mode

In this mode, PFTs compete against each other, but a given PFT is only
allowed to grow and exist in places where it has some coverage in an
input surface datset. Thus, for example, boreal plants are not allowed
to grow in the tropics and vice-versa, but competition betwen various
plants that coexist in the surface datset can occur. This mode may also
be used to impose biogeographic differences between, e.g. neotropical
versus African and/or Asian tropical forest PFTs.

#### Full FATES

All processes are active.
