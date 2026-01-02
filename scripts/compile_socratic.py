import sys
import argparse
import markdown
import yaml
from pathlib import Path

def compile_markdown_to_html(md_path, light_mode=False, output_dir=None):
    # Read the markdown file
    md_file = Path(md_path)
    if not md_file.exists():
        print(f"Error: {md_path} not found")
        return

    # Determine output path
    if output_dir:
        output_path = Path(output_dir) / md_file.with_suffix('.html').name
    else:
        output_path = md_file.with_suffix('.html')

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = md_file.read_text()

    # Split frontmatter if it exists
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter_str = parts[1]
            md_content = parts[2]
            frontmatter = yaml.safe_load(frontmatter_str) or {}
        else:
            frontmatter = {}
            md_content = content
    else:
        frontmatter = {}
        md_content = content

    # Convert Markdown to HTML
    html_body = markdown.markdown(md_content, extensions=['extra', 'nl2br', 'sane_lists'])

    # CSS Variables for Themes
    if light_mode:
        bg_color = "#f9f9f9"
        container_bg = "white"
        text_color = "#333"
        metadata_border = "#333"
        hr_color = "#eee"
        blockquote_border = "#ddd"
        blockquote_color = "#666"
        code_bg = "#eee"
    else:
        # Dark Mode (Default)
        bg_color = "#1a1a1a"
        container_bg = "#2d2d2d"
        text_color = "#e0e0e0"
        metadata_border = "#555"
        hr_color = "#444"
        blockquote_border = "#555"
        blockquote_color = "#aaa"
        code_bg = "#3d3d3d"

    title = frontmatter.get('title', md_file.stem)
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg-color: {bg_color};
            --container-bg: {container_bg};
            --text-color: {text_color};
            --metadata-border: {metadata_border};
            --hr-color: {hr_color};
            --blockquote-border: {blockquote_border};
            --blockquote-color: {blockquote_color};
            --code-bg: {code_bg};
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            background-color: var(--bg-color);
        }}
        .container {{
            background: var(--container-bg);
            padding: 3rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}
        h1, h2, h3 {{
            border-bottom: 1px solid var(--hr-color);
            padding-bottom: 0.5rem;
        }}
        code {{
            background: var(--code-bg);
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-family: monospace;
        }}
        blockquote {{
            border-left: 4px solid var(--blockquote-border);
            margin: 0;
            padding-left: 1rem;
            color: var(--blockquote-color);
            font-style: italic;
        }}
        hr {{
            border: 0;
            border-top: 1px solid var(--hr-color);
            margin: 2rem 0;
        }}
        .metadata {{
            font-size: 0.9rem;
            color: var(--blockquote-color);
            margin-bottom: 2rem;
            border-bottom: 2px solid var(--metadata-border);
            padding-bottom: 1rem;
        }}
        a {{
            color: #4a9eff;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="metadata">
            {"".join([f"<div><strong>{k.capitalize()}:</strong> {v}</div>" for k, v in frontmatter.items()])}
        </div>
        {html_body}
    </div>
</body>
</html>"""

    # Write output file
    output_path.write_text(html_template)
    print(f"Successfully compiled {md_path} to {output_path} ({'light' if light_mode else 'dark'} mode)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile Socratic Seminar Markdown to HTML")
    parser.add_argument("file", nargs="?", help="Path to a specific markdown file (optional)")
    parser.add_argument("--light", action="store_true", help="Use light mode instead of default dark mode")
    parser.add_argument("--input-dir", default="docs/arguments", help="Directory to search for MD files (default: docs/arguments)")
    parser.add_argument("--output-dir", default="compiled-html", help="Directory to output HTML files (default: compiled-html)")
    
    args = parser.parse_args()

    # Get the base directory relative to the script location
    script_dir = Path(__file__).parent.parent
    input_dir = script_dir / args.input_dir
    output_dir = script_dir / args.output_dir

    if args.file:
        # Compile a specific file
        compile_markdown_to_html(args.file, args.light, output_dir)
    else:
        # Compile all files in input_dir
        if not input_dir.exists():
            print(f"Error: Input directory {input_dir} not found")
            sys.exit(1)
        
        md_files = list(input_dir.glob("*.md"))
        if not md_files:
            print(f"No .md files found in {input_dir}")
        else:
            for md_file in md_files:
                compile_markdown_to_html(md_file, args.light, output_dir)
