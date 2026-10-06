import json
import sys
from datetime import date

import click
import requests
from tabulate import tabulate

from core.config import Settings
from core.constituents import CONSTITUENT_SYMBOLS
from core.validator import FileValidator

settings = Settings()


def api_url(path: str) -> str:
    return f"{settings.api_host}{path}"


def handle_response(response: requests.Response) -> dict:
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        click.echo(f"Error ({response.status_code}): {detail}", err=True)
        sys.exit(1)
    return response.json()


@click.group()
@click.version_option(version="1.0.0", prog_name="index-cli")
def cli():
    """Index Data Pipeline CLI - Query index values, manage runs, and validate files."""
    pass


@cli.command()
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
def latest(output_format: str):
    """Get the latest index value."""
    data = handle_response(requests.get(api_url("/api/v1/index/latest")))
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(tabulate(
            [[data["business_date"], data["index_level"], data["daily_return"],
              data["constituent_count"], data["run_id"]]],
            headers=["Date", "Index Level", "Daily Return", "Constituents", "Run ID"],
            tablefmt="grid",
        ))


@cli.command()
@click.option("--start", "start_date", required=True, type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--end", "end_date", required=True, type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--page", default=1, type=int)
@click.option("--page-size", default=50, type=int)
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
def range(start_date, end_date, page: int, page_size: int, output_format: str):
    """Get index values for a date range."""
    params = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "page": page,
        "page_size": page_size,
    }
    data = handle_response(requests.get(api_url("/api/v1/index/range"), params=params))
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        rows = [
            [d["business_date"], d["index_level"], d["daily_return"], d["constituent_count"]]
            for d in data["data"]
        ]
        click.echo(tabulate(
            rows,
            headers=["Date", "Index Level", "Daily Return", "Constituents"],
            tablefmt="grid",
        ))
        click.echo(f"\nPage {data['page']} of {data['total_pages']} (Total: {data['total']})")


@cli.command()
@click.option("--page", default=1, type=int)
@click.option("--page-size", default=20, type=int)
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
def runs(page: int, page_size: int, output_format: str):
    """List pipeline runs."""
    data = handle_response(requests.get(
        api_url("/api/v1/runs"),
        params={"page": page, "page_size": page_size},
    ))
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        rows = [
            [r["run_id"], r["business_date"], r["status"], r["data_quality_status"] or "-",
             r["started_at"] or "-"]
            for r in data["data"]
        ]
        click.echo(tabulate(
            rows,
            headers=["Run ID", "Date", "Status", "Quality", "Started"],
            tablefmt="grid",
        ))


@cli.command()
@click.argument("run_id")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
def run_detail(run_id: str, output_format: str):
    """Show details for a specific run."""
    data = handle_response(requests.get(api_url(f"/api/v1/runs/{run_id}")))
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        rows = [[k, v] for k, v in data.items()]
        click.echo(tabulate(rows, headers=["Field", "Value"], tablefmt="grid"))


@cli.command()
@click.argument("business_date", type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--api-key", envvar="API_KEY", default=None, help="API key for authentication")
@click.option("--force", is_flag=True, help="Force rerun even if completed run exists")
def rerun(business_date, api_key: str, force: bool):
    """Trigger a rerun for a business date."""
    key = api_key or settings.api_key
    payload = {
        "business_date": business_date.strftime("%Y-%m-%d"),
        "force": force,
    }
    data = handle_response(requests.post(
        api_url("/api/v1/rerun"),
        json=payload,
        headers={"X-API-Key": key},
    ))
    click.echo(f"Rerun initiated: {data['run_id']}")
    click.echo(f"Status: {data['status']}")
    click.echo(f"Message: {data['message']}")


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
def validate(file_path: str, output_format: str):
    """Validate a local price file against the input contract."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    file_name = file_path.split("/")[-1].split("\\")[-1]
    validator = FileValidator(constituent_symbols=CONSTITUENT_SYMBOLS)
    result = validator.validate(file_name, content)

    if output_format == "json":
        click.echo(json.dumps(result.to_report(), indent=2, default=str))
    else:
        status = click.style("VALID", fg="green") if result.is_valid else click.style("INVALID", fg="red")
        click.echo(f"File: {file_name}")
        click.echo(f"Status: {status}")
        click.echo(f"Business Date: {result.business_date}")
        click.echo(f"Rows: {result.row_count}")
        click.echo(f"Checksum: {result.checksum[:16]}...")

        if result.errors:
            click.echo(f"\nErrors ({len(result.errors)}):")
            error_rows = [
                [e.row or "-", e.column or "-", e.rule, e.message[:80]]
                for e in result.errors[:20]
            ]
            click.echo(tabulate(
                error_rows,
                headers=["Row", "Column", "Rule", "Message"],
                tablefmt="grid",
            ))

        if result.warnings:
            click.echo(f"\nWarnings ({len(result.warnings)}):")
            for w in result.warnings[:10]:
                click.echo(f"  - [{w.rule}] {w.message}")

    sys.exit(0 if result.is_valid else 1)


@cli.command()
@click.argument("as_of_date", type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
def constituents(as_of_date, output_format: str):
    """List index constituents for a date."""
    data = handle_response(requests.get(
        api_url("/api/v1/constituents"),
        params={"as_of_date": as_of_date.strftime("%Y-%m-%d")},
    ))
    if output_format == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        rows = [[c["symbol"], c["name"], c["set_version"]] for c in data["constituents"]]
        click.echo(tabulate(rows, headers=["Symbol", "Name", "Set Version"], tablefmt="grid"))
        click.echo(f"\nTotal: {data['count']} constituents as of {data['as_of_date']}")


if __name__ == "__main__":
    cli()
