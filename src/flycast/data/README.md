# Connectome data

`fly_larva_edges.csv.gz` / `fly_larva_nodes.csv.gz` — complete synaptic wiring of the
*Drosophila melanogaster* larval brain.

- 2,956 neurons, 116,922 directed synaptic connections.
- Same files as Fly Hero (`actuallyrizzn/fly-hero`).

## Provenance (upstream)

Source: M. Winding et al., "The connectome of an insect brain", *Science* 379
eadd9330 (2023), https://doi.org/10.1126/science.add9330 — via Netzschleuder
(`fly_larva`), https://networks.skewed.de/net/fly_larva.

**Upstream license: CC-BY** (not CC-BY-SA). Keep attribution when redistributing these files.

This README (our packaging notes) is **CC-BY-SA-4.0** with the rest of Fly Cast docs.
Library code that loads the graph is **AGPL-3.0-or-later**. See [LICENSING.md](../../../LICENSING.md).

## Fly Cast lock

The wiring *layout* (which cells connect) stays frozen. Magnitudes may be gently
retuned later (Level C) only after basic text works and product owners reopen that
gate. Until then, treat `W` as frozen data for Level A/B.
