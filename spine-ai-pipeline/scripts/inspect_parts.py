import argparse
from pathlib import Path
from PIL import Image
import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()

def inspect_directory(dir_path):
    p = Path(dir_path)
    if not p.exists():
        console.print(f"[red]Directory not found: {dir_path}[/red]")
        return

    files = sorted(list(p.glob("*.png")))
    
    table = Table(title=f"Part Inspection: {p.name}")
    table.add_column("Filename", style="cyan")
    table.add_column("Size (WxH)", style="green")
    table.add_column("Visible Area %", style="magenta")
    table.add_column("Status", style="bold")
    
    issues = []
    
    for f in files:
        try:
            img = Image.open(f).convert("RGBA")
            w, h = img.size
            
            # Analyze Alpha
            alpha = np.array(img.split()[3])
            visible_pixels = np.count_nonzero(alpha > 10) # Threshold for visibility
            total_pixels = w * h
            vis_pct = (visible_pixels / total_pixels) * 100
            
            status = "[green]OK[/green]"
            
            if vis_pct < 1.0:
                status = "[red]EMPTY/HOST[/red]"
                issues.append(f"{f.name}: Almost empty ({vis_pct:.2f}%)")
            elif w < 50 or h < 50:
                status = "[yellow]TOO SMALL[/yellow]"
                issues.append(f"{f.name}: Too small ({w}x{h})")
                
            table.add_row(f.name, f"{w}x{h}", f"{vis_pct:.1f}%", status)
            
        except Exception as e:
            table.add_row(f.name, "Error", "-", f"[red]{e}[/red]")

    console.print(table)
    
    if issues:
        console.print("\n[bold red]Issues Found:[/bold red]")
        for i in issues:
            console.print(f"- {i}")
    else:
        console.print("\n[bold green]All parts look valid![/bold green]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", help="Directory to inspect")
    args = parser.parse_args()
    
    inspect_directory(args.dir)
