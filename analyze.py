import polars as pl
import networkx as nx
from pathlib import Path
import argparse
import json


def cmd_search(input_file: str, keyword: str, output: str, limit: int | None = None) -> None:
    kw = keyword.lower()
    refs = pl.read_csv(input_file, columns=["ref"])["ref"].to_list()

    if limit:
        refs = refs[:limit]

    lazy_frames = []
    total = len(refs)
    for i, ref in enumerate(refs, 1):
        print(f"Reading Destino de donativos: {i}/{total}", end="\r", flush=True)
        try:
            df = (
                pl.read_excel(
                    ref,
                    sheet_name="Destino de donativos",
                    columns=["Rfc", "Razón social", "Folio", "Concepto", "Sector beneficiado",
                             "Monto", "Número de beneficiados", "Entidad federativa", "Municipio"],
                )
                .cast({"Monto": pl.Float64, "Número de beneficiados": pl.Int64})
                .filter(pl.col("Concepto").str.to_lowercase().str.contains(kw, literal=True))
                .with_columns(pl.lit(ref).alias("ref"))
            )
            if not df.is_empty():
                lazy_frames.append(df.lazy())
        except ValueError:
            continue
    print()

    if not lazy_frames:
        print(f"No 'Destino de donativos' rows matched keyword '{keyword}' in Concepto")
        return

    pl.concat(lazy_frames).collect().write_csv(output)
    print(f"Wrote {output} ({len(lazy_frames)} foundations with matches)")


def _build_graph(input_file: str, limit: int | None = None) -> nx.DiGraph:
    refs = pl.read_csv(input_file, columns=["ref"])["ref"].to_list()
    if limit:
        refs = refs[:limit]
    total = len(refs)

    best: dict[str, tuple[str, str]] = {}
    for i, ref in enumerate(refs, 1):
        print(f"Indexing RFC files: {i}/{total}", end="\r", flush=True)
        try:
            row = (
                pl.read_excel(ref, sheet_name="Carátula", columns=["Folio", "Rfc"])
                .sort("Folio")
                .tail(1)
            )
            rfc_val = row["Rfc"][0]
            folio_val = row["Folio"][0]
        except Exception:
            continue
        if rfc_val not in best or folio_val > best[rfc_val][0]:
            best[rfc_val] = (folio_val, ref)
    print()

    G = nx.DiGraph()
    unique = list(best.items())
    for i, (rfc_val, (_, ref_path)) in enumerate(unique, 1):
        print(f"Building graph edges: {i}/{len(unique)}", end="\r", flush=True)
        try:
            df = (
                pl.read_excel(
                    ref_path,
                    sheet_name="Donativos otorgados",
                    columns=["Rfc destinatario", "Monto efectivo", "Monto especie"],
                )
                .drop_nulls(subset=["Rfc destinatario"])
                .with_columns(
                    pl.col("Monto efectivo").cast(pl.Float64).fill_null(0.0),
                    pl.col("Monto especie").cast(pl.Float64).fill_null(0.0),
                )
            )
            for dest, efectivo, especie in (
                df.group_by("Rfc destinatario")
                .agg(pl.col("Monto efectivo").sum(), pl.col("Monto especie").sum())
                .iter_rows()
            ):
                G.add_edge(rfc_val, dest, monto_efectivo=efectivo, monto_especie=especie)
        except ValueError:
            continue
    print()

    return G


def _shortest_cycles_distinct_prev(subG: nx.DiGraph, rfc: str, max_cycles: int | None):
    count = 0
    for prev in subG.predecessors(rfc):
        try:
            path = nx.shortest_path(subG, rfc, prev)
        except nx.NetworkXNoPath:
            continue
        yield path
        count += 1
        if max_cycles and count >= max_cycles:
            return


def _shortest_cycles_through(subG: nx.DiGraph, rfc: str, max_cycles: int | None):
    min_dist = None
    for succ in subG.successors(rfc):
        try:
            d = nx.shortest_path_length(subG, succ, rfc)
            if min_dist is None or d < min_dist:
                min_dist = d
        except nx.NetworkXNoPath:
            continue
    if min_dist is None:
        return
    count = 0
    for succ in subG.successors(rfc):
        for path in nx.all_simple_paths(subG, succ, rfc, cutoff=min_dist):
            if len(path) - 1 == min_dist:
                yield [rfc] + path[:-1]
                count += 1
                if max_cycles and count >= max_cycles:
                    return


def _cycles_through(subG: nx.DiGraph, rfc: str, max_cycles: int | None, max_depth: int | None) -> list[list[str]]:
    count = 0
    for succ in subG.successors(rfc):
        for path in nx.all_simple_paths(subG, succ, rfc, cutoff=max_depth):
            yield [rfc] + path[:-1]
            count += 1
            if max_cycles and count >= max_cycles:
                return


def _edge_amount(data: dict) -> float:
    return data.get("monto_efectivo", 0.0) + data.get("monto_especie", 0.0)


def _cycle_edges(cycle: list[str], start: str, G: nx.DiGraph):
    idx = cycle.index(start)
    rotated = cycle[idx:] + cycle[:idx]
    nodes = rotated + [rotated[0]]
    for i in range(len(nodes) - 1):
        src, dst = nodes[i], nodes[i + 1]
        yield src, dst, (G[src][dst] if G.has_edge(src, dst) else {})


def _cycle_amount(cycle: list[str], start: str, G: nx.DiGraph) -> tuple[float, float]:
    amounts = [_edge_amount(data) for _, _, data in _cycle_edges(cycle, start, G)]
    if not amounts:
        return 0.0, 0.0
    return min(amounts), sum(amounts)


def _format_cycle(cycle: list[str], start: str, G: nx.DiGraph | None = None) -> str:
    idx = cycle.index(start)
    rotated = cycle[idx:] + cycle[:idx]
    nodes = rotated + [rotated[0]]
    if G is None:
        return " -> ".join(nodes)
    bottleneck, total = _cycle_amount(cycle, start, G)
    parts = []
    for src, _, data in _cycle_edges(cycle, start, G):
        efectivo = data.get("monto_efectivo", 0)
        especie = data.get("monto_especie", 0)
        parts.append(f"{src} -[ef:{efectivo:,.0f} esp:{especie:,.0f}]->")
    parts.append(nodes[-1])
    return f"[min:{bottleneck:,.0f} total:{total:,.0f} hops:{len(cycle)}]  " + " ".join(parts)


def _emit(found: list[str], title: str, output: str | None) -> None:
    if output:
        Path(output).write_text("\n".join(found) + "\n")
        print(f"Wrote {len(found)} line(s) to {output}")
        return
    width = len(str(len(found)))
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")
    for i, line in enumerate(found, 1):
        print(f"  {i:>{width}}.  {line}")
    print(f"{'─' * 60}\n")


def _find_reciprocal(G: nx.DiGraph, rfc: str | None, min_amount: float) -> list[str]:
    seen: set[frozenset] = set()
    rows = []
    for u, v in G.edges():
        if u == v or not G.has_edge(v, u):
            continue
        key = frozenset((u, v))
        if key in seen:
            continue
        seen.add(key)
        if rfc and rfc not in (u, v):
            continue
        tot_uv = _edge_amount(G[u][v])
        tot_vu = _edge_amount(G[v][u])
        roundtrip = min(tot_uv, tot_vu)
        if roundtrip < min_amount:
            continue
        hi = max(tot_uv, tot_vu)
        balance = roundtrip / hi if hi else 0.0
        rows.append((roundtrip, u, v, tot_uv, tot_vu, balance))
    rows.sort(key=lambda r: r[0], reverse=True)
    return [
        f"{u} <-> {v}   {u}->{v}:{tot_uv:,.0f}   {v}->{u}:{tot_vu:,.0f}   balance:{balance:.2f}"
        for _, u, v, tot_uv, tot_vu, balance in rows
    ]


def _find_conduits(G: nx.DiGraph, rfc: str | None, min_amount: float, ratio_min: float) -> list[str]:
    if rfc:
        if rfc not in G:
            print(f"RFC not found in graph: {rfc}")
            return []
        candidates = [rfc]
    else:
        candidates = list(G.nodes())
    rows = []
    for n in candidates:
        in_total = sum(_edge_amount(G[p][n]) for p in G.predecessors(n))
        out_total = sum(_edge_amount(G[n][s]) for s in G.successors(n))
        throughput = min(in_total, out_total)
        hi = max(in_total, out_total)
        ratio = throughput / hi if hi else 0.0
        retained = in_total - out_total
        if not rfc and (in_total <= 0 or out_total <= 0 or throughput < min_amount or ratio < ratio_min):
            continue
        rows.append((throughput, n, in_total, out_total, retained, ratio))
    rows.sort(key=lambda r: r[0], reverse=True)
    return [
        f"{n}   in:{in_t:,.0f}   out:{out_t:,.0f}   retained:{ret:,.0f}   ratio:{ratio:.2f}"
        for _, n, in_t, out_t, ret, ratio in rows
    ]


def _find_clusters(G: nx.DiGraph, rfc: str | None, min_amount: float) -> list[str]:
    sccs = [c for c in nx.strongly_connected_components(G) if len(c) >= 2]
    if rfc:
        sccs = [c for c in sccs if rfc in c]
        if not sccs:
            print(f"RFC not in any multi-node cluster: {rfc}")
            return []
    rows = []
    for members in sccs:
        internal = external_out = 0.0
        for u in members:
            for v in G.successors(u):
                amt = _edge_amount(G[u][v])
                if v in members:
                    internal += amt
                else:
                    external_out += amt
        if internal < min_amount:
            continue
        denom = internal + external_out
        retention = internal / denom if denom else 0.0
        rows.append((len(members), internal, retention, sorted(members)))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
    lines = []
    for size, internal, retention, members in rows:
        more = "" if size <= 10 else f" ...(+{size - 10})"
        member_str = ", ".join(members[:10]) + more
        lines.append(f"size:{size}   internal:{internal:,.0f}   retention:{retention:.0%}   [{member_str}]")
    return lines


def _find_self_loops(G: nx.DiGraph, rfc: str | None, min_amount: float) -> list[str]:
    if rfc:
        if not G.has_edge(rfc, rfc):
            print(f"No self-loop for RFC: {rfc}")
            return []
        candidates = [rfc]
    else:
        candidates = [n for n in G if G.has_edge(n, n)]
    rows = []
    for n in candidates:
        data = G[n][n]
        ef = data.get("monto_efectivo", 0.0)
        esp = data.get("monto_especie", 0.0)
        total = _edge_amount(data)
        if not rfc and total < min_amount:
            continue
        rows.append((total, n, ef, esp))
    rows.sort(key=lambda r: r[0], reverse=True)
    return [
        f"{n}   ef:{ef:,.0f}   esp:{esp:,.0f}   total:{total:,.0f}"
        for total, n, ef, esp in rows
    ]


def _load_or_build_graph(input_file: str, force: bool, limit: int | None) -> nx.DiGraph:
    p = Path(input_file)
    cache_file = p.with_name(p.stem + "_graph.json")
    if not force and not limit and cache_file.exists():
        print(f"Loading graph from cache: {cache_file}")
        with open(cache_file) as f:
            return nx.node_link_graph(json.load(f), directed=True)
    print("Building graph from XLSX files...")
    G = _build_graph(input_file, limit)
    if not limit:
        with open(cache_file, "w") as f:
            json.dump(nx.node_link_data(G), f)
        print(f"Graph cached to: {cache_file}")
    return G


def cmd_graph(input_file: str, rfc: str | None, force: bool = False, limit: int | None = None, output: str | None = None, max_cycles: int | None = None, max_depth: int | None = None, predecessors: bool = False, shortest: bool = False, min_size: int = 0, distinct_prev: bool = False, min_amount: float = 0.0, ratio_min: float = 0.0, reciprocal: bool = False, conduits: bool = False, clusters: bool = False, self_loops: bool = False, successors: bool = False) -> None:
    if predecessors and not rfc:
        print("--predecessors requires --rfc.")
        return
    if distinct_prev and not rfc:
        print("--distinct-prev requires --rfc.")
        return
    if successors and not rfc:
        print("--successors requires --rfc.")
        return

    G = _load_or_build_graph(input_file, force, limit)

    if reciprocal:
        found = _find_reciprocal(G, rfc, min_amount)
        if not found:
            print("No reciprocal pairs found.")
            return
        _emit(found, f"{len(found)} reciprocal pair(s)" + (f" involving {rfc}" if rfc else ""), output)
        return

    if conduits:
        found = _find_conduits(G, rfc, min_amount, ratio_min)
        if not found:
            print("No conduit nodes found.")
            return
        _emit(found, f"{len(found)} conduit node(s)", output)
        return

    if clusters:
        found = _find_clusters(G, rfc, min_amount)
        if not found:
            print("No closed clusters found.")
            return
        _emit(found, f"{len(found)} closed cluster(s)", output)
        return

    if self_loops:
        found = _find_self_loops(G, rfc, min_amount)
        if not found:
            print("No self-loops found.")
            return
        _emit(found, f"{len(found)} self-loop(s)", output)
        return

    if rfc and predecessors:
        if rfc not in G.nodes():
            print(f"RFC not found in graph: {rfc}")
            return
        preds = [(p, G[p][rfc]) for p in G.predecessors(rfc)]
        if not preds:
            print(f"No predecessors found for RFC: {rfc}")
            return
        width = len(str(len(preds)))
        print(f"\n{'─' * 60}")
        print(f"  {len(preds)} predecessor(s) for {rfc}")
        print(f"{'─' * 60}")
        for i, (p, data) in enumerate(sorted(preds, key=lambda x: x[1].get("monto_efectivo", 0), reverse=True), 1):
            ef = data.get("monto_efectivo", 0)
            esp = data.get("monto_especie", 0)
            print(f"  {i:>{width}}.  {p}  ef:{ef:,.0f}  esp:{esp:,.0f}")
        print(f"{'─' * 60}\n")
        return

    if rfc and successors:
        if rfc not in G.nodes():
            print(f"RFC not found in graph: {rfc}")
            return
        succs = [(s, G[rfc][s]) for s in G.successors(rfc)]
        if not succs:
            print(f"No successors found for RFC: {rfc}")
            return
        width = len(str(len(succs)))
        print(f"\n{'─' * 60}")
        print(f"  {len(succs)} successor(s) for {rfc}")
        print(f"{'─' * 60}")
        for i, (s, data) in enumerate(sorted(succs, key=lambda x: x[1].get("monto_efectivo", 0), reverse=True), 1):
            ef = data.get("monto_efectivo", 0)
            esp = data.get("monto_especie", 0)
            print(f"  {i:>{width}}.  {s}  ef:{ef:,.0f}  esp:{esp:,.0f}")
        print(f"{'─' * 60}\n")
        return

    if rfc:
        if rfc not in G.nodes():
            print(f"No cycle found for RFC: {rfc}")
            return
        scc = next((c for c in nx.strongly_connected_components(G) if rfc in c), None)
        if scc is None or len(scc) < 2:
            print(f"No cycle found for RFC: {rfc}")
            return
        subG = G.subgraph(scc)
        if distinct_prev:
            gen = _shortest_cycles_distinct_prev(subG, rfc, max_cycles)
        elif shortest:
            gen = _shortest_cycles_through(subG, rfc, max_cycles)
        else:
            gen = _cycles_through(subG, rfc, max_cycles, max_depth)
        cycles = []
        yielded = 0
        for cycle_nodes in gen:
            yielded += 1
            if len(cycle_nodes) <= min_size:
                continue
            bottleneck, total = _cycle_amount(cycle_nodes, rfc, G)
            if bottleneck < min_amount:
                continue
            cycles.append((bottleneck, total, cycle_nodes))
            print(f"Cycles found: {len(cycles)}", end="\r", flush=True)
        print()
        if max_cycles and yielded >= max_cycles:
            print(f"(stopped at {max_cycles} cycles — use --max-cycles to increase)")
        if not cycles:
            print(f"No qualifying cycle found for RFC: {rfc}")
            return
        cycles.sort(key=lambda c: (c[0], c[1]), reverse=True)
        found = [_format_cycle(nodes, rfc, G) for _, _, nodes in cycles]
        _emit(found, f"{len(found)} cycle(s) found", output)
    else:
        all_rfcs = set(pl.read_csv(input_file, columns=["Rfc"])["Rfc"].to_list())
        graph_rfcs = all_rfcs & set(G.nodes())
        seen: set[frozenset] = set()
        if shortest:
            min_len = None
            raw = []
            print("Scanning graph for shortest cycles...", end="\r", flush=True)
            for cycle in nx.simple_cycles(G, length_bound=max_depth):
                key = frozenset(cycle)
                if key in seen:
                    continue
                seen.add(key)
                if len(cycle) <= min_size:
                    continue
                start = next((n for n in cycle if n in graph_rfcs), None)
                if start is None:
                    continue
                bottleneck, total = _cycle_amount(cycle, start, G)
                if bottleneck < min_amount:
                    continue
                if min_len is None or len(cycle) < min_len:
                    min_len = len(cycle)
                    raw = [(bottleneck, total, cycle, start)]
                elif len(cycle) == min_len:
                    raw.append((bottleneck, total, cycle, start))
                    if max_cycles and len(raw) >= max_cycles:
                        break
                print(f"Scanning graph for shortest cycles: {len(raw)} found (len={min_len})...", end="\r", flush=True)
            raw.sort(key=lambda c: (c[0], c[1]), reverse=True)
            found = [_format_cycle(c, s, G) for _, _, c, s in raw]
        else:
            cycles = []
            print("Scanning graph for cycles...", end="\r", flush=True)
            for cycle in nx.simple_cycles(G, length_bound=max_depth):
                key = frozenset(cycle)
                if key in seen:
                    continue
                seen.add(key)
                if len(cycle) <= min_size:
                    continue
                start = next((n for n in cycle if n in graph_rfcs), None)
                if start is None:
                    continue
                bottleneck, total = _cycle_amount(cycle, start, G)
                if bottleneck < min_amount:
                    continue
                cycles.append((bottleneck, total, cycle, start))
                print(f"Scanning graph for cycles: {len(cycles)} found...", end="\r", flush=True)
                if max_cycles and len(cycles) >= max_cycles:
                    break
            if max_cycles and len(cycles) >= max_cycles:
                print(f"(stopped at {max_cycles} cycles — use --max-cycles to increase)")
            cycles.sort(key=lambda c: (c[0], c[1]), reverse=True)
            found = [_format_cycle(c, s, G) for _, _, c, s in cycles]
        print()
        if not found:
            print("No cycles found in the graph.")
            return
        _emit(found, f"{len(found)} cycle(s) found", output)


def main():
    parser = argparse.ArgumentParser(description="Analyze Mexican foundation transparency data")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_search = subparsers.add_parser("search", help="Search by keyword and export Destino de donativos")
    p_search.add_argument("--input-file", required=True)
    p_search.add_argument("--keyword", required=True)
    p_search.add_argument("--output", default="destino_donativos.csv")
    p_search.add_argument("--limit", type=int, default=None, help="Process only the first N matched files")

    p_graph = subparsers.add_parser("graph", help="Find suspicious donation patterns (cycles, round-trips, conduits, clusters)")
    p_graph.add_argument("--input-file", required=True)
    p_graph.add_argument("--rfc", default=None, help="RFC to focus on; omit to scan the whole graph")
    p_graph.add_argument("--force", action="store_true", help="Rebuild graph ignoring cache")
    p_graph.add_argument("--limit", type=int, default=None, help="Process only the first N files (skips cache write)")
    p_graph.add_argument("--output", default=None, help="Save results to file instead of printing")
    p_graph.add_argument("--max-cycles", type=int, default=100, help="Max cycles to return (default 100; 0 = unlimited)")
    p_graph.add_argument("--max-depth", type=int, default=8, help="Max cycle length in hops (default 8; 0 = unlimited)")
    p_graph.add_argument("--shortest", action="store_true", help="Return only the shortest cycles")
    p_graph.add_argument("--greater-than", type=int, default=0, dest="min_size", metavar="N", help="Only return cycles with more than N nodes")
    p_graph.add_argument("--distinct-prev", action="store_true", help="Shortest cycle per distinct direct predecessor (requires --rfc)")
    p_graph.add_argument("--min-amount", type=float, default=0.0, dest="min_amount", metavar="PESOS", help="Ignore cycles/pairs/nodes/clusters below this peso amount")
    p_graph.add_argument("--ratio", type=float, default=0.0, dest="ratio_min", metavar="R", help="Conduit filter: keep nodes with min(in,out)/max(in,out) >= R (default 0)")
    mode = p_graph.add_mutually_exclusive_group()
    mode.add_argument("--predecessors", action="store_true", help="List all RFCs that donate directly to --rfc")
    mode.add_argument("--reciprocal", action="store_true", help="Find mutual-donation pairs (A<->B) ranked by round-tripped amount")
    mode.add_argument("--conduits", action="store_true", help="Find pass-through nodes (inflow ~ outflow, ~0 retained)")
    mode.add_argument("--clusters", action="store_true", help="Rank strongly-connected groups by size and internal money retained")
    mode.add_argument("--self-loops", action="store_true", help="List RFCs that donate to themselves, ranked by amount")
    mode.add_argument("--successors", action="store_true", help="List all RFCs that --rfc donates directly to")

    args = parser.parse_args()
    if args.command == "search":
        cmd_search(args.input_file, args.keyword, args.output, args.limit)
    elif args.command == "graph":
        max_cycles = args.max_cycles if args.max_cycles != 0 else None
        max_depth = args.max_depth if args.max_depth != 0 else None
        cmd_graph(args.input_file, args.rfc, args.force, args.limit, args.output, max_cycles, max_depth, args.predecessors, args.shortest, args.min_size, args.distinct_prev, args.min_amount, args.ratio_min, args.reciprocal, args.conduits, args.clusters, args.self_loops, args.successors)


if __name__ == "__main__":
    main()
