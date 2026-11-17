# Usage

## Read the collection

The combined text view is available as a Parquet file.

```python
import pyarrow.parquet as pq

records = pq.read_table("unified/corpus.parquet")
```

Available views are listed in `catalog/dataset.yaml`. The combined view is named `all_text`.

## Local tools

```sh
python -m pip install -e .
holovec verify
holovec search "Mandalorian Wars" --top 5
```

Verification checks the release files against their manifest. Local search works directly with the text collection.

## Formats

The collection uses JSON, JSONL, Parquet and original document formats where applicable. Source references and attribution are retained with the records. No vector layer is currently released; vector publication remains on hold while source collection is incomplete.
