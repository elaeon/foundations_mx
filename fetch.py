#!/usr/bin/env python3
"""
Processes RFC entries to extract transparency reports.
step 1. playwright-cli open https://eu2-por-pro-don-net-cons.azurewebsites.net/Consulta/Acceso?ReturnUrl=%2FConsulta%2FEventualidades --headed
step 2. resolve the captcha and go to the transparency tab
step 3. uv run python fetch.py 
"""

import subprocess
import time
import shutil
import re
from pathlib import Path


def read_rfcs(filename: str = "rfcs.txt") -> list[str]:
    """Read RFC values from a text file, filtering out empty lines and comments."""
    rfcs = []
    try:
        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    rfcs.append(line)
    except FileNotFoundError:
        print(f"Error: {filename} not found")
        return []
    return rfcs


def run_playwright_command(command: str, args: list | None = None) -> dict:
    """Execute a playwright-cli command and capture output/errors."""
    result = {
        "success": False,
        "stdout": None,
        "stderr": None,
        "error": None
    }
    try:
        if args is not None:
            process = subprocess.run(
                ["playwright-cli", command] + args,
                capture_output=True,
                text=True,
                check=True
            )
        else:
            process = subprocess.run(
                ["playwright-cli", command],
                capture_output=True,
                text=True,
                check=True
            )

        result["success"] = True
        result["stdout"] = process.stdout
        result["stderr"] = process.stderr
    except subprocess.CalledProcessError as e:
        result["error"] = f"Command failed: {e}"
        result["stderr"] = e.stderr if hasattr(e, "stderr") else str(e)
    except FileNotFoundError:
        result["error"] = "playwright-cli not found. Make sure it's installed."
    
    return result


def search_word_in_latest_file(word: str, directory: str = ".playwright-cli", stdout=None) -> dict:
    """Search for a word in the latest file of a directory and return the matching line."""
    result = {
        "found": False,
        "line": None,
        "line_number": None,
        "file": None,
        "error": None
    }
    
    def _search(lines):
        for line_num, line in enumerate(lines, start=1):
            if word.lower() in line.lower():
                result["found"] = True
                result["line"] = line.strip()
                result["line_number"] = line_num
                return result

    try:
        # Read the latest file and search for the word
        if stdout is not None:
            _search(stdout.split("\n"))
            ref_name = "stdout"
        else:
            dir_path = Path(directory)
            if not dir_path.exists():
                result["error"] = f"Directory '{directory}' not found"
                return result
        
            # Get all files in the directory, sorted by modification time (latest first)
            files = sorted(dir_path.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        
            if not files:
                result["error"] = f"No files found in '{directory}'"
                return result

            latest_file = files[0]
            ref_name = latest_file.name
            result["file"] = str(latest_file)
            with open(latest_file, "r", encoding="utf-8") as file:
                _search(file)
        
        if not result["found"]:
            result["error"] = f"Word '{word}' not found in {ref_name}"
    
    except Exception as e:
        result["error"] = f"Error reading file: {e}"
    
    return result


def extract_ref_pattern(text: str) -> dict:
    """Extract the pattern ref=e\\d+ from a string using regex."""
    result = {
        "found": False,
        "matches": [],
        "error": None
    }
    
    try:
        # Find all matches of the pattern ref=e followed by one or more digits
        pattern = r"ref=(?P<ref>e\d+)"
        matches = re.search(pattern, text)
        
        if matches:
            result["found"] = True
            result["matches"] = matches.groupdict()
        else:
            result["error"] = f"Pattern '{pattern}' not found in text"
    
    except Exception as e:
        result["error"] = f"Error extracting pattern: {e}"
    
    return result


def process_rfcs() -> None:
    """Process each RFC entry to extract transparency reports."""
    rfcs = read_rfcs("rfcs.txt")
    
    if not rfcs:
        print("No RFC entries to process")
        return
    
    # Ensure foundations directory exists
    foundations_dir = Path.home() / "foundations"
    foundations_dir.mkdir(exist_ok=True)
    
    def cmd_build(rfc, btn1, btn2):
        commands_opt = [
            ("click", [btn1]), #e34
            ("type", [rfc]),
            ("select", [btn2, "2024"]), #e41
            ("click", ["e48"]),
            ("click", ["e100"]),
            ("click", ["e47"])
        ]
        return commands_opt
    
    def get_ref():
        # Snapshot once to resolve stable form field refs (they don't change across iterations)
        result_cmd = run_playwright_command("snapshot")
        if result_cmd.get("success", False):
            result_word_rfc = search_word_in_latest_file('textbox "RFC"', stdout=result_cmd["stdout"])
            print(result_word_rfc)
            result_word_ef = search_word_in_latest_file('combobox "Ejercicio fiscal"', stdout=result_cmd["stdout"])
            ref_rfc = extract_ref_pattern(result_word_rfc["line"])["matches"]["ref"]
            ref_ef = extract_ref_pattern(result_word_ef["line"])["matches"]["ref"]
        return ref_rfc, ref_ef

    ref_rfc, ref_ef = get_ref()
    for rfc in rfcs:
        print(f"Processing: {rfc}")
        print(f"Form refs: rfc={ref_rfc}, ef={ref_ef}")
        commands_opt = cmd_build(rfc, ref_rfc, ref_ef)
        # Execute playwright commands in sequence
        for cmd, opts in commands_opt:
            result = run_playwright_command(cmd, opts)
            if "e48"in opts:
                result_cmd = run_playwright_command("snapshot")
                if result_cmd.get("success", False):
                    result_word = search_word_in_latest_file("No existen declaraciones de los filtros seleccionados", stdout=result_cmd["stdout"])
                    if result_word["found"] is True:
                        print(f"{rfc}: No existen declaraciones de los filtros seleccionados")
                        result_word = search_word_in_latest_file('button "Aceptar"')
                        match = extract_ref_pattern(result_word["line"])
                        print(match["found"], match["matches"]["ref"])
                        if match["found"] is True:
                            result = run_playwright_command("click", [match["matches"]["ref"]])
                            result = run_playwright_command("click", ["e47"])
                            ref_rfc, ref_ef = get_ref()
                            break
        else:
            # Move the file to foundations directory
            source_file = Path(".playwright-cli/InformeTransparencia.xlsx")
            retry = 0
            while retry < 3:
                time.sleep(1)
                if source_file.exists():
                    destination_file = foundations_dir / f"{rfc}.xlsx"
                    try:
                        shutil.move(str(source_file), str(destination_file))
                        print(f"Saved: {destination_file}")
                    except Exception as e:
                        print(f"Error moving file: {e}")
                    break
                else:
                    retry += 1
                    print(f"Warning: Source file not found for {rfc}")


if __name__ == "__main__":
    process_rfcs()
