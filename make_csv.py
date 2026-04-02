import polars as pl
from pathlib import Path
import argparse


def read_excel_and_save_csv(sheet_columns_dict, empty_cols, data_folder="data", output_folder="output"):
    """
    Read specific sheets and columns from Excel files and save to CSV using Polars.
    
    Parameters:
    -----------
    sheet_columns_dict : dict
        Dictionary where keys are sheet names and values are lists of column names
        Example: {"Sheet1": ["col1", "col2"], "Sheet2": ["col3", "col4"]}
    
    data_folder : str, default="data"
        Path to folder containing Excel files
    
    output_folder : str, default="output"
        Path to folder where CSV files will be saved
    
    Returns:
    --------
    None
        Saves CSV files to the output folder
    
    Example:
    --------
    sheet_config = {
        "Sales": ["Date", "Product", "Amount"],
        "Customers": ["ID", "Name", "Email"]
    }
    read_excel_and_save_csv(sheet_config)
    """
    
    # Create output folder if it doesn't exist
    output_path = Path(output_folder)
    output_path.mkdir(exist_ok=True)
    
    # Get all Excel files from data folder
    data_path = Path(data_folder)
    excel_files = list(data_path.glob("*.xlsx")) + list(data_path.glob("*.xls"))
    
    if not excel_files:
        print(f"No Excel files found in '{data_folder}' folder")
        return
    
    # Process each Excel file
    df_dict = {}
    for excel_file in excel_files:
        print(f"Processing {excel_file.name}...")
        
        # Process each sheet and column configuration
        for sheet_name, columns in sheet_columns_dict.items():
            try:
                # Read the Excel sheet with specified columns
                df = pl.read_excel(
                    excel_file,
                    sheet_name=sheet_name,
                    columns=columns
                )
                
                if excel_file.name in df_dict:
                    if sheet_name in ["Carátula", "Generales", "Nómina"] and df.shape[0] == 1:
                        df_dict[excel_file.name] = df_dict[excel_file.name].join(df, how="cross")
                    else:
                        df = df.with_columns(pl.lit(1).alias("key"))
                        if sheet_name == "Órgano de gobierno":
                            df = df.group_by("key").agg([pl.col("Nombre integrante"), pl.col("Monto salario").sum()])
                            df = df.with_columns(pl.col("Nombre integrante").list.join(","))
                            df = df.rename({"Nombre integrante": "Integrantes del órgano de gobierno"})
                        elif sheet_name == "Ingreso por donativos":
                            df = df.group_by("key").agg([
                                pl.col("Monto efectivo").sum(), 
                                pl.col("Monto especie").sum()
                            ])
                            df = df.rename({
                                "Monto efectivo": f"{sheet_name}_Monto efectivo",
                                "Monto especie": f"{sheet_name}_Monto especie"
                            })
                        elif sheet_name == "Destino de donativos":
                            df = df.group_by("key").agg([
                                pl.col("Monto").sum(), 
                                pl.col("Número de beneficiados").sum()
                            ])
                            df = df.rename({"Monto": f"{sheet_name}_Monto"})
                        elif sheet_name == "Gastos":
                            df = df.group_by("key").agg([
                                    pl.col("Monto nacional operación").sum(), 
                                    pl.col("Monto nacional admin").sum(),
                                    pl.col("Monto extranjero operación").sum(),
                                    pl.col("Monto extranjero admin").sum()
                                ])
                        elif sheet_name == "Donativos otorgados":
                            df = df.group_by("key").agg([
                                    pl.col("Monto efectivo").sum(), 
                                    pl.col("Monto especie").sum()
                                ])
                        elif sheet_name == "Ingresos relacionados":
                            df = df.group_by("key").agg([
                                    pl.col("Monto").sum()
                                ])
                            df = df.rename({"Monto": f"{sheet_name}_Monto"})
                        elif sheet_name == "Ingresos no relacionados":
                            df = df.group_by("key").agg([
                                    pl.col("Monto").sum()
                                ])
                            df = df.rename({"Monto": f"{sheet_name}_Monto"})
                        df = df.select(pl.exclude("key"))
                        df_dict[excel_file.name] = df_dict[excel_file.name].join(df, how="cross")
                else:
                    df_dict[excel_file.name] = df
            except Exception as e:
                df = pl.DataFrame(empty_cols[sheet_name])
                df_dict[excel_file.name] = df_dict[excel_file.name].join(df, how="cross")
                #print(f"✗ Error reading sheet '{sheet_name}' from {excel_file.name}: {e}")

        df_dict[excel_file.name] = df_dict[excel_file.name].with_columns(
            pl.lit(str(excel_file)).alias("ref")
        )
        print(f"✓ Finish {excel_file}")
        print(df_dict[excel_file.name].shape)

    df_all = pl.concat(list(df_dict.values()))
    output_file = "fundations.csv"
    df_all.write_csv(output_file)
    print("Done!")


def main():
    # Example usage
    sheet_config = {
        "Carátula": ["Rfc", "Razón social", "Rubro"],
        "Generales": ["Misión", "Valores", "Actividad", "Activo circulante", "Activo fijo", "Activo diferido", "Pasivo", "Patrimonio"],
        "Ingreso por donativos": ["Donante", "Monto efectivo", "Monto especie"],
        "Donativos otorgados": ["Rfc destinatario", "Monto efectivo", "Monto especie"],
        "Órgano de gobierno": ["Nombre integrante", "Puesto", "Monto salario", "Tipo integrante"],
        "Nómina": ["Plantilla laboral", "Voluntarios", "Monto salarios"],
        "Ingresos relacionados": ["Ingresos relacionados_Monto"],
        "Ingresos no relacionados": ["Ingresos no relacionados_Monto"],
        "Destino de donativos": ["Concepto", "Sector beneficiado", "Monto", "Número de beneficiados", "Entidad federativa", "Municipio"],
        "Gastos": ["Concepto", "Especifique", "Monto nacional operación", "Monto nacional admin", "Monto extranjero operación", "Monto extranjero admin"]
    }
    agg_names = {
        "Carátula": ["Rfc", "Razón social", "Rubro"],
        "Generales": ["Misión", "Valores", "Actividad", "Activo circulante", "Activo fijo", "Activo diferido", "Pasivo", "Patrimonio"],
        "Ingreso por donativos": ["Ingreso por donativos_Monto efectivo", "Ingreso por donativos_Monto especie"],
        "Donativos otorgados": ["Monto efectivo", "Monto especie"],
        "Órgano de gobierno": ["Integrantes del órgano de gobierno", "Monto salario"],
        "Nómina": ["Plantilla laboral", "Voluntarios", "Monto salarios"],
        "Ingresos relacionados": ["Concepto", "Monto"],
        "Ingresos no relacionados": ["Concepto libre", "Monto"],
        "Destino de donativos": ["Destino de donativos_Monto", "Número de beneficiados"],
        "Gastos": ["Monto nacional operación", "Monto nacional admin", "Monto extranjero operación", "Monto extranjero admin"]
    }
    
    empty_cols = {}
    for key, columns in agg_names.items():
        empty_cols[key] = {col: [1] for col in columns}

    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True, type=int)

    args = parser.parse_args()
    if args.year:
        read_excel_and_save_csv(sheet_config, empty_cols, data_folder=f"data/{args.year}")


if __name__ == "__main__":
    main()
