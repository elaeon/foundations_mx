import polars as pl
from pathlib import Path
import argparse
import csv


def to_md(filename: str, sheet_columns_dict: dict):
    data_path = Path(filename)
    print(f"Processing {data_path}...")
    
    # Process each sheet and column configuration
    _md_file = []
    for sheet_name, columns in sheet_columns_dict.items():
        try:
            df = pl.read_excel(
                data_path,
                sheet_name=sheet_name,
                columns=columns
            )
            if df.shape[0] == 1:
                md = text_md(df, sheet_name, columns)
                _md_file.extend(md)
            else:
                md = table_md(df, sheet_name, columns)
                _md_file.extend(md)
        except ValueError as e:
            pass
    return "\n".join(_md_file)


def text_md(df: pl.DataFrame, sheet_name, columns):
    md = []
    # --- Title ---
    md.append(f"## {sheet_name}")
    md.append("")
    
    for row in df.iter_rows(named=True):
        for column in columns:
            md.append("")
            md.append(f"- **{column}**: {row[column]}")
    return md


def table_md(df: pl.DataFrame, sheet_name, columns):
    md = []

    # --- Title ---
    md.append(f"## {sheet_name}")
    md.append("")
    md.append("| " + " | ".join(columns) + " |")
    md.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for row in df.iter_rows(named=True):
        row_list = []
        for column in columns:
            row_list.append(f"{row[column]}")
        md.append("|" + "|".join(row_list) + "|")
    md.append("")
    return md
    

def main():
    sheet_config = {
        "Carátula": ["Rfc", "Razón social", "Rubro"],
        "Generales": ["Misión", "Valores", "Actividad", "Activo circulante", "Activo fijo", "Activo diferido", "Pasivo", "Patrimonio"],
        "Ingreso por donativos": ["Donante", "Monto efectivo", "Monto especie"],
        "Donativos otorgados": ["Rfc destinatario", "Monto efectivo", "Monto especie"],
        "Órgano de gobierno": ["Nombre integrante", "Puesto", "Monto salario", "Tipo integrante"],
        "Nómina": ["Plantilla laboral", "Voluntarios", "Monto salarios"],
        "Ingresos relacionados": ["Concepto", "Monto"],
        "Ingresos no relacionados": ["Concepto libre", "Monto"],
        "Destino de donativos": ["Concepto", "Sector beneficiado", "Monto", "Número de beneficiados", "Entidad federativa", "Municipio"],
        "Gastos": ["Concepto", "Especifique", "Monto nacional operación", "Monto nacional admin", "Monto extranjero operación", "Monto extranjero admin"]
    }

    parser = argparse.ArgumentParser(description="Convert excel to markdown")
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--force", required=False, action="store_true", help="Re-process even if .md exists")

    args = parser.parse_args()
    if args.year:
        processed = 0
        skipped = 0
        with open("fundations.csv") as f:
            fundations = csv.DictReader(f)
        
            for fundation in fundations:
                rfc = fundation["Rfc"]
                md_path = f"markdown/{rfc}.md"
                output_path = Path("markdown")
                output_path.mkdir(exist_ok=True)

                if not args.force and Path(md_path).exists():
                    skipped += 1
                    continue

                text_md = to_md(fundation["ref"], sheet_config)
                with open(md_path, "w") as f:
                    f.write(text_md)
                processed += 1
        
        print(f"Processed: {processed}, Skipped (cached): {skipped}")


if __name__ == "__main__":
    main()