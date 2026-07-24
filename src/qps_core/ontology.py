from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from importlib.resources import files
from typing import Any
from urllib.parse import quote

from pyshacl import validate
from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef

QPS = Namespace("https://qps.example/ontology#")
INSTANCE = Namespace("https://qps.example/instance/")


@dataclass(frozen=True)
class OntologyValidation:
    conforms: bool
    report_text: str


def snapshot_to_graph(snapshot: dict[str, Any]) -> Graph:
    graph = Graph()
    graph.bind("qps", QPS)
    quote_id = str(snapshot.get("quote_id", "")).strip()
    quote_node = URIRef(INSTANCE + "quote/" + quote(quote_id, safe=""))
    graph.add((quote_node, RDF.type, QPS.Quotation))
    graph.add((quote_node, QPS.identifier, Literal(quote_id)))
    if "currency" in snapshot:
        graph.add((quote_node, QPS.currency, Literal(str(snapshot["currency"]))))
    for field_name, predicate in (
        ("base_cost", QPS.baseCost),
        ("grand_total", QPS.grandTotal),
    ):
        if field_name in snapshot:
            graph.add(
                (
                    quote_node,
                    predicate,
                    Literal(Decimal(str(snapshot[field_name])), datatype=XSD.decimal),
                )
            )

    for index, line in enumerate(snapshot.get("lines", []), start=1):
        line_node = URIRef(quote_node + f"/line/{index}")
        graph.add((line_node, RDF.type, QPS.CostLine))
        graph.add((quote_node, QPS.hasCostLine, line_node))
        if line.get("category") is not None:
            graph.add((line_node, QPS.category, Literal(str(line["category"]))))
        for field_name, predicate in (
            ("quantity", QPS.quantity),
            ("unit_cost", QPS.unitCost),
            ("amount", QPS.amount),
        ):
            if line.get(field_name) is not None:
                graph.add(
                    (
                        line_node,
                        predicate,
                        Literal(
                            Decimal(str(line[field_name])),
                            datatype=XSD.decimal,
                        ),
                    )
                )
        if line.get("provenance") is not None:
            graph.add((line_node, QPS.provenance, Literal(str(line["provenance"]))))
    return graph


def validate_snapshot(snapshot: dict[str, Any]) -> OntologyValidation:
    data_graph = snapshot_to_graph(snapshot)
    ontology_graph = Graph().parse(
        files("qps_core").joinpath("resources/quotation.ttl")
    )
    shapes_graph = Graph().parse(
        files("qps_core").joinpath("resources/quotation.shacl.ttl")
    )
    conforms, _, report_text = validate(
        data_graph=data_graph,
        shacl_graph=shapes_graph,
        ont_graph=ontology_graph,
        inference="rdfs",
        abort_on_first=False,
    )
    return OntologyValidation(bool(conforms), str(report_text))
