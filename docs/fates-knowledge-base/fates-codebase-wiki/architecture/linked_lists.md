---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Linked List Data Structures

## Purpose and Scope

This page documents the doubly-linked lists used to organize vegetation in FATES. The model uses two levels of linked lists: a per-site age-ordered list of patches, and a per-patch height-ordered list of cohorts. The lists are manipulated during disturbance, demographic turnover, and restart/inventory initialization.

For the full cohort and patch field inventories, see `biogeochem/FatesCohortMod.F90` and `biogeochem/FatesPatchMod.F90`. For the higher-level role of these structures in the design, see [Code Architecture and Design Patterns](index.md).

## Hierarchical Organization

FATES organizes vegetation into a three-level hierarchy: each `ed_site_type` contains patches, and each `fates_patch_type` contains cohorts. Both levels use doubly-linked pointer lists:

```
ed_site_type
   ├── oldest_patch  ---> fates_patch_type --- older/younger ---> fates_patch_type ---> ...
   └── youngest_patch --> (list tail)

fates_patch_type
   ├── tallest  ---> fates_cohort_type --- taller/shorter ---> fates_cohort_type ---> ...
   └── shortest --> (list tail)
```

Source files for the three types:

- `main/EDTypesMod.F90:231-235` (`ed_site_type` with `oldest_patch` and `youngest_patch`)
- `biogeochem/FatesPatchMod.F90:35-41` (`fates_patch_type`)
- `biogeochem/FatesCohortMod.F90:60-64` (`fates_cohort_type`)

## Patch Linked List Structure

Patches within a site are held in a doubly-linked list ordered by patch age, from oldest to youngest. Age-based ordering facilitates succession bookkeeping and ensures consistent iteration order across routines that depend on patch age history.

### Patch Type Definition

The `fates_patch_type` is declared at `biogeochem/FatesPatchMod.F90:35-41`, and holds four pointer fields directly relevant to list traversal:

| Pointer field | Type | Purpose | Source |
| --- | --- | --- | --- |
| `older` | `type(fates_patch_type), pointer` | Next older patch in the site list | `biogeochem/FatesPatchMod.F90:40` |
| `younger` | `type(fates_patch_type), pointer` | Next younger patch in the site list | `biogeochem/FatesPatchMod.F90:41` |
| `tallest` | `type(fates_cohort_type), pointer` | Head of the patch's cohort list | `biogeochem/FatesPatchMod.F90:38` |
| `shortest` | `type(fates_cohort_type), pointer` | Tail of the patch's cohort list | `biogeochem/FatesPatchMod.F90:39` |

All four fields are initialized with `=> null()` in the type declaration.

Because the cohort list head and tail live on the patch, cohorts are rooted at the patch, not the site. Moving cohorts between patches therefore requires pointer updates on both the source and destination patches.

The site type maintains endpoint pointers for the patch list at `main/EDTypesMod.F90:234-235`:

| Site field | Type | Purpose |
| --- | --- | --- |
| `oldest_patch` | `type(fates_patch_type), pointer` | Head of the age-ordered patch list |
| `youngest_patch` | `type(fates_patch_type), pointer` | Tail of the age-ordered patch list |

### Patch Traversal Patterns

The two standard patch traversals walk the list from oldest to youngest or from youngest to oldest. Both patterns use `associated()` to detect list termination.

Forward (oldest → youngest), from `biogeochem/EDPatchDynamicsMod.F90:222-265`:

```fortran
currentPatch => site_in%oldest_patch
do while (associated(currentPatch))
   ! ... work ...
   currentPatch => currentPatch%younger
end do
```

Backward (youngest → oldest), exemplified at `biogeochem/EDPatchDynamicsMod.F90:483` and `:537`:

```fortran
currentPatch => currentSite%youngest_patch
do while (associated(currentPatch))
   ! ... work ...
   currentPatch => currentPatch%older
end do
```

Additional forward-traversal sites in `EDPatchDynamicsMod.F90` include lines 264, 287, 390, 1174, 1264, 1307, 1364, 1379, 2803, and 2890 (partial list; use `grep "currentPatch%younger\|currentPatch%older"` for a complete inventory).

### Patch Insertion

When a disturbance event creates a new patch (for example in `spawn_patches` at `biogeochem/EDPatchDynamicsMod.F90:398`), the new patch must be inserted into the age-ordered list. Near-bare-ground initialization also builds the list from scratch in `init_patches` at `main/EDInitMod.F90:534`. Insertion handles three cases — insertion at the head (new youngest), insertion at the tail (new oldest), and middle insertion found by traversing the list until the correct age slot is located.

## Cohort Linked List Structure

Cohorts within a patch are held in a doubly-linked list ordered by height, from tallest to shortest. Height ordering lets the light-interception calculation proceed naturally top-down, and makes height-dependent operations such as crown damage and fire scorch trivial to walk.

### Cohort Type Definition

The `fates_cohort_type` is declared at `biogeochem/FatesCohortMod.F90:60-64`, and holds two linked-list pointer fields:

| Pointer field | Type | Purpose | Source |
| --- | --- | --- | --- |
| `taller` | `type(fates_cohort_type), pointer` | Next taller cohort | `biogeochem/FatesCohortMod.F90:63` |
| `shorter` | `type(fates_cohort_type), pointer` | Next shorter cohort | `biogeochem/FatesCohortMod.F90:64` |

Both are initialized with `=> null()`.

Note that unlike patches, which carry both endpoints of the cohort list, cohorts do not themselves know which patch they belong to through a back-pointer field on `fates_cohort_type`; routines that need patch context pass it explicitly as an argument (for example `patchptr` in `create_cohort` at `biogeochem/EDCohortDynamicsMod.F90:160`).

### Cohort Traversal Patterns

Tallest → shortest walk (used for disturbance and mortality processing), from `biogeochem/EDPatchDynamicsMod.F90:225-262`:

```fortran
currentCohort => currentPatch%shortest
do while (associated(currentCohort))
   ! ... work ...
   currentCohort => currentCohort%taller
end do
```

Note that the example above iterates from `%shortest` upward through `%taller`, demonstrating that the two patterns (head/tail, taller/shorter) can be combined in either direction depending on the algorithm. For light-interception work that really needs to go top-down, the equivalent starts at `currentPatch%tallest` and follows `currentCohort%shorter`.

## Nested Site–Patch–Cohort Iteration

The most common loop structure in FATES is a nested three-level walk:

```fortran
currentPatch => site_in%oldest_patch
do while (associated(currentPatch))
   currentCohort => currentPatch%shortest
   do while (associated(currentCohort))
      ! ... per-cohort work ...
      currentCohort => currentCohort%taller
   end do
   currentPatch => currentPatch%younger
end do
```

This pattern appears throughout the codebase; representative examples in `biogeochem/EDPatchDynamicsMod.F90` are disturbance-rate calculations at lines 222-265, and cohort mortality processing with the same loop structure across several routines (see the `currentPatch%younger` and `currentPatch%older` occurrences enumerated above).

## Safe Iteration During Modification

When the loop body may deallocate the current node (for example during `terminate_cohort` or `terminate_cohorts` at `biogeochem/EDCohortDynamicsMod.F90:464` and `:347`), the code must capture the next pointer before processing, to avoid dereferencing a freed pointer:

```fortran
currentCohort => currentPatch%shortest
do while (associated(currentCohort))
   nextCohort => currentCohort%taller   ! capture first
   call terminate_cohort(...)            ! may deallocate currentCohort
   currentCohort => nextCohort
end do
```

The same pattern applies to patch termination during list cleanup.

## Pointer Management in Key Operations

### Patch Creation During Disturbance

`spawn_patches` (`biogeochem/EDPatchDynamicsMod.F90:398`) creates one or more new patches after a disturbance event. Its pointer bookkeeping allocates the new patches, initializes their internal state, splices them into the site's age-ordered list, and updates the site endpoint pointers `oldest_patch` / `youngest_patch` as needed.

### Cohort Transfer During Disturbance

When disturbance pushes part of the existing cohort population into a newly spawned patch, the cohorts in the donor patch have their density reduced and copies are inserted into the new patch. Cohort copy is performed by the type-bound procedure `cohort%Copy` (declared at `biogeochem/FatesCohortMod.F90:279`).

Inside the cohort-transfer loop, pointer fields on the new cohort clone are explicitly nulled before insertion so the clone joins the destination list cleanly. For example, `biogeochem/EDPatchDynamicsMod.F90:1118` sets `nc%taller => null()` and `:1126` sets `nc%shorter => null()` to prepare a fresh cohort node for insertion.

### Cohort Fusion

Cohort fusion merges similar cohorts to keep list length bounded, trading a small accuracy loss for a significant runtime gain. Fusion is a module-level public subroutine, not a type-bound procedure, and has the signature

```fortran
subroutine fuse_cohorts(currentSite, currentPatch, bc_in)
```

declared in `biogeochem/EDCohortDynamicsMod.F90:694`. Similar routines `insert_cohort` (`:1322`), `sort_cohorts` (`:1271`), and `count_cohorts` (`:1433`) also operate on the linked list at module scope.

## Initialization Patterns

### Near-Bare-Ground Initialization

When starting from near-bare-ground conditions, `init_patches` (`main/EDInitMod.F90:534`) creates the initial patches, then calls `create_cohort` (`biogeochem/EDCohortDynamicsMod.F90:160`) to seed cohorts into each patch. Both routines perform the pointer splicing needed to attach new patches to the site's linked list and to attach new cohorts to their patches' cohort lists.

### Inventory Initialization

When starting from an inventory file, `initialize_sites_by_inventory` (invoked from `init_patches`, declared in `main/FatesInventoryInitMod.F90`) reads patches and cohorts from PSS/CSS files and inserts them into the linked lists, rebuilding the same hierarchy as near-bare-ground initialization but with prescribed age and structure.

## Memory Management Considerations

### Pointer Nullification

After deallocating a patch or cohort, any pointers that referenced it must be updated to avoid dangling references. The patterns observed in the code are: explicit `=> null()` assignment on freshly allocated clones (e.g., `biogeochem/EDPatchDynamicsMod.F90:1118,1126`), and reliance on the endpoint pointers (`oldest_patch`, `youngest_patch`, `tallest`, `shortest`) to correctly reflect the list state after removal.

### Null Pointer Checks

All traversal code uses `associated()` to check pointer validity before dereferencing. Common checks:

| Check | Purpose |
| --- | --- |
| `associated(currentPatch)` | Patch pointer is valid before access |
| `associated(currentCohort)` | Cohort pointer is valid before access |
| `associated(patch%older)` / `associated(patch%younger)` | Detect end-of-list in patch walk |
| `associated(cohort%taller)` / `associated(cohort%shorter)` | Detect end-of-list in cohort walk |

## Restart and I/O Implications

Linked lists must be serialized to flat arrays when written to restart files, and rebuilt on read. The serialization and deserialization routines live in `main/FatesRestartInterfaceMod.F90`; they walk the patch and cohort lists on write, and re-splice patches and cohorts into the correct linked-list positions on read.

## Performance Considerations

### List Ordering Benefits

| Ordering | Benefit |
| --- | --- |
| Age-based patches | Enables early termination when searching for similar-age patches during fusion, and simplifies successional bookkeeping |
| Height-based cohorts | Light interception proceeds top-down naturally; crown damage and fire scorch are height-dependent |

### Fusion Operations

Both patch and cohort fusion reduce the list length by merging sufficiently similar elements. Fusion is cheap on a doubly-linked list — the merged node's neighbours get their pointers rewired, and the merged node is freed — whereas an array-backed implementation would force a compaction pass.

Sources: `biogeochem/EDPatchDynamicsMod.F90` (list traversal, patch creation, and cohort transfer), `biogeochem/EDCohortDynamicsMod.F90` (cohort creation, termination, fusion, insertion, sorting, counting), `biogeochem/FatesPatchMod.F90` and `biogeochem/FatesCohortMod.F90` (type definitions), `main/EDTypesMod.F90` (site-level endpoints), `main/EDInitMod.F90` and `main/FatesInventoryInitMod.F90` (initialization), and `main/FatesRestartInterfaceMod.F90` (restart I/O).
