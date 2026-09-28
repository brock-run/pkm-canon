import typer
from pathlib import Path
from pkmcanon.parsers.roam import RoamParser
from pkmcanon.models import Document, Node, Relation, Attribute, PreservationRecord

app = typer.Typer()

@app.command()
def ingest_roam(filepath: Path, graph_name: str, output_dir: Path):
    """Ingest a Roam JSON export into Canonical JSONL files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    parser = RoamParser(source_graph_name=graph_name)

    files = {
        Document: open(output_dir / "documents.jsonl", "w"),
        Node: open(output_dir / "nodes.jsonl", "w"),
        Relation: open(output_dir / "relations.jsonl", "w"),
        Attribute: open(output_dir / "attributes.jsonl", "w"),
        PreservationRecord: open(output_dir / "preservation_records.jsonl", "w"),
    }

    count = 0
    for model in parser.parse_file(filepath):
        # model_dump_json() handles Pydantic V2 serialization safely
        files[type(model)].write(model.model_dump_json(by_alias=True) + "\n")
        count += 1

    for f in files.values():
        f.close()

    typer.echo(f"Successfully ingested {count} records into {output_dir}")

if __name__ == "__main__":
    app()